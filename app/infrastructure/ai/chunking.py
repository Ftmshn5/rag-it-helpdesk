"""Bilgi bankası dokümanlarını parçalara (chunk) bölme.

Neden parçalama: embedding, tüm dokümanı tek vektöre sıkıştırırsa farklı
konular birbirine karışır ve arama isabeti düşer. Her parça tek bir konuyu
anlatırsa talebe en yakın parça (ve yanıtta kaynak gösterilecek bölüm) net olur.

Strateji: Markdown yapısına göre bölme. Dokümanlar "## " başlıklarıyla konulara
ayrılmış olduğu için her başlık bir parçadır. Çok uzun bir bölüm paragraf
sınırlarından ek parçalara ayrılır (cümle ortasından asla kesilmez).

Her parçanın başına "Doküman başlığı > Bölüm başlığı" eklenir: "Hesabım kilitlendi"
bölümü tek başına okunduğunda hangi sistemin hesabı olduğu belli olmaz; başlık
bağlamı hem embedding'e hem LLM'e verilir.
"""

import re
from dataclasses import dataclass

# Yaklaşık 300-400 token; bge-m3 için rahat, LLM istemine birkaç parça sığar
DEFAULT_MAX_CHARS = 1500


@dataclass(frozen=True)
class Chunk:
    heading: str | None  # bölüm başlığı (giriş metni için None)
    content: str  # embedding'e ve LLM'e verilen metin (başlık bağlamıyla)


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    chunks: list[Chunk]


def parse_markdown(text: str, *, fallback_title: str, max_chars: int = DEFAULT_MAX_CHARS) -> ParsedDocument:
    title = fallback_title
    sections: list[tuple[str | None, list[str]]] = [(None, [])]

    for line in text.splitlines():
        if line.startswith("# ") and title == fallback_title and not _has_content(sections):
            title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        prefix = f"{title} > {heading}" if heading else title
        for part in _split_paragraphs(body, max_chars):
            chunks.append(Chunk(heading=heading, content=f"{prefix}\n\n{part}"))

    return ParsedDocument(title=title, chunks=chunks)


def _has_content(sections: list[tuple[str | None, list[str]]]) -> bool:
    return any(line.strip() for _, lines in sections for line in lines)


def _split_paragraphs(body: str, max_chars: int) -> list[str]:
    """Paragrafları sırayla toplar; sınır aşılacaksa yeni parçaya geçer."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    parts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = paragraph  # tek paragraf sınırdan uzunsa bölünmeden kalır
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts
