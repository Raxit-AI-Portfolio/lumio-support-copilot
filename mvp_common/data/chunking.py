"""Split a KB markdown file into chunks, one per "##" section."""


def read_header(text: str) -> tuple[dict, str]:
    """Split the front matter (doc_id, title, access_group) from the body."""
    parts = text.split("---", 2)
    header = {}
    for line in parts[1].strip().splitlines():
        key, value = line.split(":", 1)
        header[key.strip()] = value.strip()
    return header, parts[2].strip()


def split_sections(body: str) -> list[tuple[str, str]]:
    """Return (section title, section text) pairs. Text before the first heading is the intro."""
    sections = []
    title = "Intro"
    lines = []
    for line in body.splitlines():
        if line.startswith("## "):
            sections.append((title, "\n".join(lines).strip()))
            title = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    sections.append((title, "\n".join(lines).strip()))
    return [(name, text) for name, text in sections if text]


def make_chunks(markdown: str) -> list[dict]:
    """Turn one KB file into chunk dicts, without vectors."""
    header, body = read_header(markdown)
    chunks = []
    for number, (section, text) in enumerate(split_sections(body), start=1):
        chunks.append(
            {
                "chunk_id": f"{header['doc_id']}#{number}",
                "doc_id": header["doc_id"],
                "title": header["title"],
                "section": section,
                "access_group": header["access_group"],
                "text": text,
            }
        )
    return chunks
