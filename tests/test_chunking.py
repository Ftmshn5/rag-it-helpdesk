from pathlib import Path

from app.infrastructure.ai.chunking import MarkdownChunker

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"

DOCUMENT = """# Kablosuz Ağ

Fakültede iki ağ vardır.

## Bağlanamıyorum

Ağı unutup yeniden bağlanın.

Saat ayarını kontrol edin.

## Boş bölüm

## Misafir ağı

SMS doğrulaması yapılır.
"""


def test_title_comes_from_first_level_one_heading():
    assert MarkdownChunker().parse(DOCUMENT, fallback_title="dosya").title == "Kablosuz Ağ"


def test_fallback_title_is_used_without_heading():
    assert MarkdownChunker().parse("Yalnızca metin.", fallback_title="dosya").title == "dosya"


def test_each_section_becomes_a_chunk_with_title_context():
    chunks = MarkdownChunker().parse(DOCUMENT, fallback_title="dosya").chunks

    assert [chunk.heading for chunk in chunks] == [None, "Bağlanamıyorum", "Misafir ağı"]
    assert chunks[0].content == "Kablosuz Ağ\n\nFakültede iki ağ vardır."
    assert chunks[1].content == (
        "Kablosuz Ağ > Bağlanamıyorum\n\nAğı unutup yeniden bağlanın.\n\nSaat ayarını kontrol edin."
    )


def test_empty_sections_are_skipped():
    headings = [chunk.heading for chunk in MarkdownChunker().parse(DOCUMENT, fallback_title="d").chunks]
    assert "Boş bölüm" not in headings


def test_long_section_is_split_at_paragraph_boundaries():
    paragraphs = [f"Paragraf {i}: " + "x" * 40 for i in range(5)]
    text = "# Başlık\n\n## Uzun\n\n" + "\n\n".join(paragraphs)

    chunks = MarkdownChunker(max_chars=120).parse(text, fallback_title="d").chunks

    assert len(chunks) > 1
    assert all(chunk.heading == "Uzun" for chunk in chunks)
    assert all(chunk.content.startswith("Başlık > Uzun\n\n") for chunk in chunks)
    # Hiçbir paragraf bölünmez ve kaybolmaz
    joined = "\n\n".join(chunk.content.split("\n\n", 1)[1] for chunk in chunks)
    assert joined == "\n\n".join(paragraphs)


def test_paragraph_longer_than_limit_stays_whole():
    long_paragraph = "y" * 300
    chunks = MarkdownChunker(max_chars=100).parse(f"## Bölüm\n\n{long_paragraph}", fallback_title="d").chunks
    assert len(chunks) == 1
    assert long_paragraph in chunks[0].content


def test_knowledge_base_documents_have_titles_and_reasonable_chunks():
    files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    assert len(files) >= 8

    for path in files:
        document = MarkdownChunker().parse(path.read_text(encoding="utf-8"), fallback_title=path.stem)
        assert document.title != path.stem, f"{path.name} başlıksız"
        assert len(document.chunks) >= 3, f"{path.name} çok az bölüm içeriyor"
        for chunk in document.chunks:
            body = chunk.content.split("\n\n", 1)[1]
            assert len(body) <= MarkdownChunker.DEFAULT_MAX_CHARS, f"{path.name}: {chunk.heading} çok uzun"
