"""Güven skoru kalibrasyonu: RAG_SIMILARITY_FLOOR / CEILING değerlerini ölçerek seçmek için.

İki grup örnek talep bilgi bankasında aranır:
- ANSWERABLE: bilgi bankasının cevaplayabildiği sorunlar (yüksek benzerlik beklenir)
- OUT_OF_SCOPE: bilgi bankasında karşılığı olmayan sorunlar (düşük benzerlik beklenir)

İki grubun benzerlik dağılımı ayrışıyorsa floor kapsam dışı grubun üstüne,
eşik (0.6) de iki grubun arasına düşecek şekilde seçilir.

Çalıştırma (Ollama açık, bilgi bankası indekslenmiş olmalı):
    python -m app.infrastructure.ai.calibrate            # yalnızca benzerlikler
    python -m app.infrastructure.ai.calibrate --with-llm # ayrıca uçtan uca RAG yanıtı ve süresi
"""

import sys
import time

from app.core.config import get_settings
from app.domain.enums import TicketCategory
from app.domain.ticket import Ticket
from app.infrastructure.ai.ollama import OllamaEmbeddingProvider, OllamaLlmProvider
from app.infrastructure.ai.providers import EmbeddingProvider
from app.infrastructure.ai.rag_ai_support import RagAiSupport, SimilarityConfidence
from app.infrastructure.ai.retriever import KnowledgeRetriever, PgVectorRetriever
from app.infrastructure.db.models import EMBEDDING_DIMENSION
from app.infrastructure.db.session import Database

ANSWERABLE = [
    ("Şifremi unuttum", "Öğrenci bilgi sistemine giriş yapamıyorum, şifremi hatırlamıyorum.", TicketCategory.ACCOUNT),
    ("Hesabım kilitlendi", "Birkaç kez yanlış şifre girdim, şimdi hesabım açılmıyor.", TicketCategory.ACCOUNT),
    ("eduroam bağlanmıyor", "Telefonumdan eduroam ağına bağlanamıyorum, kimlik doğrulama hatası veriyor.", TicketCategory.NETWORK),
    ("Yazıcı kağıt sıkıştırıyor", "B2 katındaki yazıcı sürekli kağıt sıkışması uyarısı veriyor.", TicketCategory.HARDWARE),
    ("Evden kütüphaneye erişemiyorum", "Kampüs dışından kütüphane veritabanlarına girmeye çalışınca erişim reddediliyor.", TicketCategory.NETWORK),
    ("E-posta gönderemiyorum", "Outlook'ta gönderdiğim e-postalar giden kutusunda kalıyor.", TicketCategory.SOFTWARE),
    ("Projeksiyonda görüntü yok", "Derslikte dizüstü bilgisayarımı bağladım ama projeksiyona görüntü gelmiyor.", TicketCategory.HARDWARE),
    ("MATLAB lisans hatası", "MATLAB açılırken lisans sunucusuna ulaşılamıyor hatası veriyor.", TicketCategory.SOFTWARE),
    ("Bilgisayar çok yavaş", "Ofisteki bilgisayarım son günlerde çok yavaş çalışıyor.", TicketCategory.HARDWARE),
    ("Bilgisayardan duman çıkıyor", "Masaüstü bilgisayarın kasasından yanık kokusu ve duman geliyor.", TicketCategory.HARDWARE),
]

OUT_OF_SCOPE = [
    ("Klima çalışmıyor", "Ofisimdeki klima soğutmuyor, tamir edilmesi gerekiyor.", TicketCategory.HARDWARE),
    ("Yemekhane menüsü", "Bu haftanın yemekhane menüsü nerede yayınlanıyor?", TicketCategory.SOFTWARE),
    ("Not ortalamam yanlış", "Transkriptimdeki genel not ortalaması yanlış hesaplanmış görünüyor.", TicketCategory.ACCOUNT),
    ("Kapı kartım okumuyor", "Laboratuvarın kapısındaki kart okuyucu kartımı tanımıyor.", TicketCategory.HARDWARE),
    ("Excel pivot tablo", "Excel'de pivot tablo nasıl oluşturulur, öğrenmek istiyorum.", TicketCategory.SOFTWARE),
    ("Otopark izni", "Araç için kampüs otopark izni nasıl alınır?", TicketCategory.ACCOUNT),
]


class SimilarityCalibrator:
    """Örnek taleplerle retrieval benzerliğini ölçer; güven aralığını seçmeye yardım eder."""

    def __init__(
        self, embedder: EmbeddingProvider, retriever: KnowledgeRetriever, confidence: SimilarityConfidence
    ) -> None:
        self._embedder = embedder
        self._retriever = retriever
        self._confidence = confidence

    def measure(self, groups: dict[str, list[tuple[str, str, TicketCategory]]]) -> dict[str, list[float]]:
        """Her grup için örneklerin en iyi parça benzerliklerini yazdırır ve döndürür."""
        best: dict[str, list[float]] = {}
        for group, samples in groups.items():
            print(f"== {group}")
            best[group] = []
            texts = [f"{title}\n\n{description}" for title, description, _ in samples]
            for (title, _, _), vector in zip(samples, self._embedder.embed(texts), strict=True):
                top = self._retriever.search(vector, 1)
                similarity = top[0].similarity if top else 0.0
                best[group].append(similarity)
                source = top[0].file_path if top else "-"
                print(f"  {similarity:.3f}  güven {self._confidence.score(similarity):.2f}  {title:<32} → {source}")
            print()
        return best

    @staticmethod
    def run_end_to_end(rag: RagAiSupport, samples: list[tuple[str, str, TicketCategory]]) -> None:
        print("\n== UÇTAN UCA RAG")
        for title, description, category in samples:
            started = time.perf_counter()
            answer = rag.try_auto_resolve(SimilarityCalibrator.sample_ticket(title, description, category))
            elapsed = time.perf_counter() - started
            print(f"\n--- {title}  ({elapsed:.1f} sn, güven {answer.confidence:.2f}, kaynak {answer.sources})")
            print(answer.answer)

    @staticmethod
    def sample_ticket(title: str, description: str, category: TicketCategory) -> Ticket:
        return Ticket(id=0, title=title, description=description, category=category, requester_id=0)


def main() -> int:
    # Komut satırı giriş noktası: bağımlılıklar burada kurulur
    settings = get_settings()
    embedder = OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        dimension=EMBEDDING_DIMENSION,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    retriever = PgVectorRetriever(Database(settings.database_url).session_factory)
    confidence = SimilarityConfidence(floor=settings.rag_similarity_floor, ceiling=settings.rag_similarity_ceiling)
    calibrator = SimilarityCalibrator(embedder, retriever, confidence)

    print(f"Ayar: floor={confidence.floor}  ceiling={confidence.ceiling}  eşik={settings.ai_confidence_threshold}\n")
    best = calibrator.measure({"CEVAPLANABİLİR": ANSWERABLE, "KAPSAM DIŞI": OUT_OF_SCOPE})
    answerable, out_of_scope = best["CEVAPLANABİLİR"], best["KAPSAM DIŞI"]
    print(f"Cevaplanabilir: en düşük {min(answerable):.3f}, ortalama {sum(answerable) / len(answerable):.3f}")
    print(f"Kapsam dışı:    en yüksek {max(out_of_scope):.3f}, ortalama {sum(out_of_scope) / len(out_of_scope):.3f}")

    if "--with-llm" in sys.argv:
        llm = OllamaLlmProvider(
            settings.ollama_base_url,
            settings.llm_model,
            timeout_seconds=settings.ollama_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
        )
        rag = RagAiSupport(embedder=embedder, retriever=retriever, llm=llm, confidence=confidence, top_k=settings.rag_top_k)
        calibrator.run_end_to_end(rag, [ANSWERABLE[3], ANSWERABLE[9], OUT_OF_SCOPE[0]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
