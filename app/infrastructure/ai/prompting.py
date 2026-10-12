"""RAG'in "A"sı (augmentation): bulunan parçalarla LLM istemini kurar.

LLM'e yalnızca verilen bilgi bankası parçalarına dayanması söylenir. Bilgi
yetmiyorsa uydurmak yerine sabit bir işaret (NO_ANSWER_MARKER) yazması istenir;
facade bu işareti görünce güven skorunu düşürür ve talep teknisyene gider.
"""

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

SYSTEM_PROMPT = f"""Sen bir üniversite fakültesinin Bilgi İşlem destek asistanısın.
Kullanıcının arıza kaydına, YALNIZCA aşağıda verilen bilgi bankası parçalarına dayanarak Türkçe yanıt ver.

Kurallar:
- Bilgi bankasında olmayan bilgi, adres, telefon veya adım uydurma.
- Yanıtı kısa tut: kullanıcının kendisinin uygulayabileceği en fazla 5 adım.
- Kullanıcıdan asla şifresini isteme.
- Cihazdan duman, yanık kokusu, aşırı ısınma veya şişmiş batarya gibi tehlikeli bir durum varsa yalnızca cihazı kapatıp fişini çekmesini ve teknisyeni beklemesini söyle.
- Verilen parçalar bu sorunu çözmeye yetmiyorsa başka hiçbir şey yazmadan yalnızca {NO_ANSWER_MARKER} yaz."""


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
            f"Yanıtın:"
        )
        return SYSTEM_PROMPT, user_prompt

    @staticmethod
    def embedding_query(ticket: Ticket) -> str:
        """Retriever için aranacak metin: başlık ve açıklama birlikte."""
        return f"{ticket.title}\n\n{ticket.description}"
