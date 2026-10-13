"""RAG'in "A"sı (augmentation): bulunan parçalarla LLM istemini kurar.

LLM'e yalnızca verilen bilgi bankası parçalarına dayanması söylenir. Bilgi
yetmiyorsa uydurmak yerine sabit bir işaret (NO_ANSWER_MARKER) yazması istenir;
facade bu işareti görünce güven skorunu düşürür ve talep teknisyene gider.
"""

import re

from app.domain.enums import TicketCategory
from app.domain.ticket import Ticket
from app.infrastructure.ai.retriever import RetrievedChunk

NO_ANSWER_MARKER = "BILGI_YOK"

CATEGORY_NAMES = {
    TicketCategory.HARDWARE: "Donanım",
    TicketCategory.SOFTWARE: "Yazılım",
    TicketCategory.NETWORK: "Ağ / İnternet",
    TicketCategory.ACCOUNT: "Hesap / Şifre",
}

# Not (qwen2.5:3b ile ölçüldü): "bilgi yetmiyorsa işaret yaz" gibi geniş bir kural
# küçük modelde cevaplanabilir taleplerde bile işarete yol açıyordu. Bu yüzden
# işaret yalnızca parçalar "hiç ilgisiz" olduğunda istenir ve ilgili adım varsa
# yanıt vermesi açıkça söylenir. İlgisiz taleplere karşı asıl koruma zaten
# retrieval tabanlı güven skorudur (düşük güvenli yanıt kullanıcıya gösterilmez).
SYSTEM_PROMPT = f"""Sen bir üniversite fakültesinin Bilgi İşlem destek asistanısın. Kullanıcıların arıza kayıtlarına, bilgi bankasına dayanarak Türkçe çözüm önerirsin.

Kurallar:
- Yalnızca verilen bilgi bankası parçalarındaki bilgileri kullan; adres, telefon veya adım uydurma.
- Doğrudan kullanıcıya hitap et ve kısa yaz: kullanıcının kendisinin uygulayabileceği en fazla 5 numaralı adım.
- Kullanıcıdan asla şifresini isteme.
- Duman, yanık kokusu, aşırı ısınma veya şişmiş batarya varsa yalnızca cihazı kapatıp fişini çekmesini ve teknisyeni beklemesini söyle.
- Parçalar bu sorunla HİÇ ilgili değilse (bambaşka bir konudan bahsediyorsa) yalnızca {NO_ANSWER_MARKER} yaz. Parçalarda sorunla ilgili herhangi bir adım varsa mutlaka o adımlarla yanıt ver."""


class PromptBuilder:
    def build(self, ticket: Ticket, chunks: list[RetrievedChunk]) -> tuple[str, str]:
        """(sistem talimatı, kullanıcı istemi) döndürür."""
        context = "\n\n---\n\n".join(
            f"[{index}] Kaynak: {chunk.file_path}\n{chunk.content}"
            for index, chunk in enumerate(chunks, start=1)
        )
        user_prompt = (
            f"Bilgi bankası parçaları:\n\n{context}\n\n"
            f"=== Arıza kaydı ===\n"
            f"Kategori: {CATEGORY_NAMES[ticket.category]}\n"
            f"Başlık: {ticket.title}\n"
            f"Açıklama: {ticket.description}\n\n"
            f"Yukarıdaki parçalara dayanarak kullanıcıya çözüm adımlarını yaz."
        )
        return SYSTEM_PROMPT, user_prompt

    @staticmethod
    def embedding_query(ticket: Ticket) -> str:
        """Retriever için aranacak metin: başlık ve açıklama birlikte."""
        return f"{ticket.title}\n\n{ticket.description}"

    @staticmethod
    def is_no_answer(text: str) -> bool:
        """Model işareti farklı yazabiliyor ("Bilgi_YOK", "BİLGİ YOK"); harf ve ayraç duyarsız tanınır."""
        return re.search(r"b[iıİI]lg[iıİI][\s_]*yok", text, flags=re.IGNORECASE) is not None
