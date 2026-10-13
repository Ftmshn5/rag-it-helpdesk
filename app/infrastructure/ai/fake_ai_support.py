"""Gerçek RAG hazır olana kadar kullanılan sahte AI.

Anahtar kelimeye dayalı, tamamen deterministik çalışır: aynı talep her zaman
aynı yanıtı ve güven skorunu üretir. Bu sayede hem iş kuralı 4'ün (düşük
güvende eskalasyon) iki yolu da elle denenebilir, hem de testler kararlıdır.

Örnek: "şifremi unuttum" → güven 0.85 (AI yanıt verir)
       "monitörden duman çıkıyor" → güven 0.20 (doğrudan eskalasyon)
"""

from dataclasses import dataclass

from app.application.interfaces.ai_support import AiSupportFacade, AutoAnswer
from app.domain.ticket import Ticket


@dataclass(frozen=True)
class CannedAnswer:
    keywords: tuple[str, ...]
    answer: str
    confidence: float
    source: str


CANNED_ANSWERS: tuple[CannedAnswer, ...] = (
    CannedAnswer(
        keywords=("şifre", "parola", "hesabım kilit", "giriş yapamıyorum"),
        answer=(
            "Şifrenizi https://hesap.ornekfakulte.edu.tr adresindeki 'Şifremi unuttum' "
            "bağlantısından sıfırlayabilirsiniz. Hesabınız 5 hatalı denemeden sonra "
            "15 dakika kilitlenir; bu süre sonunda tekrar deneyin."
        ),
        confidence=0.85,
        source="knowledge/hesap-sifre-sifirlama.md",
    ),
    CannedAnswer(
        keywords=("wifi", "wi-fi", "kablosuz", "eduroam", "internet"),
        answer=(
            "eduroam ağına kullanıcı adınız 'kullanici@ornekfakulte.edu.tr' biçiminde "
            "olmalıdır. Ağı cihazınızda 'unutup' yeniden bağlanmayı deneyin; sorun "
            "sürerse cihazınızın tarih/saat ayarını kontrol edin."
        ),
        confidence=0.75,
        source="knowledge/kablosuz-ag-baglantisi.md",
    ),
    CannedAnswer(
        keywords=("yazıcı", "çıktı", "kağıt sıkış"),
        answer=(
            "Yazıcıyı kapatıp kağıt yolundaki sıkışan kağıdı çıkarın, ardından yazdırma "
            "kuyruğunu temizleyip tekrar deneyin. Ağ yazıcılarında doğru yazıcıyı "
            "seçtiğinizden emin olun."
        ),
        confidence=0.70,
        source="knowledge/yazici-sorunlari.md",
    ),
)

FALLBACK = AutoAnswer(
    answer="Bilgi bankasında bu sorunla ilgili yeterli bilgi bulunamadı.",
    confidence=0.20,
    sources=[],
)


class FakeAiSupport(AiSupportFacade):
    """Facade deseni — sahte implementasyon: anahtar kelimeyle deterministik yanıt (geliştirme ve testler için)."""

    def try_auto_resolve(self, ticket: Ticket) -> AutoAnswer:
        text = self._normalize(f"{ticket.title} {ticket.description}")
        for canned in CANNED_ANSWERS:
            if any(keyword in text for keyword in canned.keywords):
                return AutoAnswer(
                    answer=canned.answer, confidence=canned.confidence, sources=[canned.source]
                )
        return FALLBACK

    @staticmethod
    def _normalize(text: str) -> str:
        # Türkçe büyük "İ" küçük harfe çevrilince "i̇" (noktalı) olur; önce düzeltilir
        return text.replace("İ", "i").replace("I", "ı").lower()
