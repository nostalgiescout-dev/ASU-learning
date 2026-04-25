from __future__ import annotations

import re
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "academic_kechafa_deployment_guide.md"
OUTPUT = ROOT / "docs" / "Academic_Kechafa_Deployment_Guide.pdf"

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 48
RIGHT = 48
TOP = 54
BOTTOM = 48
CONTENT_WIDTH = PAGE_WIDTH - LEFT - RIGHT


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def strip_markdown_inline(value: str) -> str:
    value = value.replace("**", "")
    value = value.replace("*", "")
    value = value.replace("`", "")
    return value


def wrap_text(text: str, width_chars: int) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(
        text,
        width=width_chars,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [text]


def parse_blocks(markdown: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    lines = markdown.splitlines()
    i = 0

    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()

        if not line:
            i += 1
            continue

        if line.startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i].rstrip())
                i += 1
            blocks.append(("code", code_lines))
            i += 1
            continue

        if line.startswith("# "):
            blocks.append(("title", [strip_markdown_inline(line[2:].strip())]))
            i += 1
            continue

        if line.startswith("## "):
            blocks.append(("h1", [strip_markdown_inline(line[3:].strip())]))
            i += 1
            continue

        if line.startswith("### "):
            blocks.append(("h2", [strip_markdown_inline(line[4:].strip())]))
            i += 1
            continue

        if line.startswith("- "):
            blocks.append(("bullet", [strip_markdown_inline(line[2:].strip())]))
            i += 1
            continue

        if re.match(r"^\d+\.\s+", line):
            blocks.append(("number", [strip_markdown_inline(line)]))
            i += 1
            continue

        paragraph = [strip_markdown_inline(line)]
        i += 1
        while i < len(lines):
            next_line = lines[i].rstrip()
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if next_stripped.startswith(("```", "# ", "## ", "### ", "- ")):
                break
            if re.match(r"^\d+\.\s+", next_stripped):
                break
            paragraph.append(strip_markdown_inline(next_stripped))
            i += 1
        blocks.append(("body", [" ".join(paragraph)]))

    return blocks


def layout_blocks(blocks: list[tuple[str, list[str]]]) -> list[list[tuple[str, int, int, str]]]:
    pages: list[list[tuple[str, int, int, str]]] = [[]]
    y = PAGE_HEIGHT - TOP

    def ensure_space(height_needed: int) -> None:
        nonlocal y
        if y - height_needed < BOTTOM:
            pages.append([])
            y = PAGE_HEIGHT - TOP

    def add_line(font: str, size: int, leading: int, text: str) -> None:
        nonlocal y
        ensure_space(leading)
        pages[-1].append((font, size, y, text))
        y -= leading

    for kind, values in blocks:
        if kind == "title":
            y -= 10
            for line in wrap_text(values[0], 38):
                add_line("F2", 22, 30, line)
            y -= 8
        elif kind == "h1":
            y -= 8
            for line in wrap_text(values[0], 55):
                add_line("F2", 16, 22, line)
            y -= 2
        elif kind == "h2":
            y -= 4
            for line in wrap_text(values[0], 68):
                add_line("F2", 13, 18, line)
            y -= 2
        elif kind == "body":
            for line in wrap_text(values[0], 92):
                add_line("F1", 10, 14, line)
            y -= 4
        elif kind == "bullet":
            bullet_text = f"- {values[0]}"
            for index, line in enumerate(wrap_text(bullet_text, 88)):
                prefix = "" if index else ""
                add_line("F1", 10, 14, f"{prefix}{line}")
            y -= 2
        elif kind == "number":
            for line in wrap_text(values[0], 88):
                add_line("F1", 10, 14, line)
            y -= 2
        elif kind == "code":
            y -= 2
            for code_line in values:
                text = code_line if code_line else " "
                for wrapped in wrap_text(text, 78):
                    add_line("F3", 9, 12, wrapped)
            y -= 4

    return pages


def page_stream(lines: list[tuple[str, int, int, str]], page_no: int, total_pages: int) -> bytes:
    chunks = []
    chunks.append("BT\n")
    chunks.append("/F1 9 Tf\n")
    chunks.append(f"1 0 0 1 {LEFT} 24 Tm\n")
    chunks.append(f"({escape_pdf_text(f'Academic Kechafa Deployment Guide - Page {page_no} of {total_pages}')}) Tj\n")
    chunks.append("ET\n")

    for font, size, y, text in lines:
        x = LEFT
        if font == "F2" and size == 22:
            approx_text_width = len(text) * 11
            x = max(LEFT, int((PAGE_WIDTH - approx_text_width) / 2))
        chunks.append("BT\n")
        chunks.append(f"/{font} {size} Tf\n")
        chunks.append(f"1 0 0 1 {x} {y} Tm\n")
        chunks.append(f"({escape_pdf_text(text)}) Tj\n")
        chunks.append("ET\n")

    return "".join(chunks).encode("latin-1", errors="replace")


def build_pdf(pages: list[list[tuple[str, int, int, str]]]) -> bytes:
    objects: list[bytes] = []

    def add_object(data: bytes | str) -> int:
        if isinstance(data, str):
            data = data.encode("latin-1", errors="replace")
        objects.append(data)
        return len(objects)

    font1 = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font2 = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font3 = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_refs: list[int] = []
    content_refs: list[int] = []
    pages_root_index_placeholder = len(objects) + 1

    total_pages = len(pages)
    for idx, lines in enumerate(pages, start=1):
        stream = page_stream(lines, idx, total_pages)
        content_ref = add_object(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        content_refs.append(content_ref)
        page_refs.append(0)

    pages_root = add_object("<< /Type /Pages /Kids [] /Count 0 >>")

    for idx, content_ref in enumerate(content_refs):
        page_ref = add_object(
            f"<< /Type /Page /Parent {pages_root} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R /F3 {font3} 0 R >> >> "
            f"/Contents {content_ref} 0 R >>"
        )
        page_refs[idx] = page_ref

    kids = " ".join(f"{ref} 0 R" for ref in page_refs)
    objects[pages_root - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode("latin-1")
    )

    catalog = add_object(f"<< /Type /Catalog /Pages {pages_root} 0 R >>")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    blocks = parse_blocks(markdown)
    pages = layout_blocks(blocks)
    pdf = build_pdf(pages)
    OUTPUT.write_bytes(pdf)
    print(f"PDF generated: {OUTPUT}")


if __name__ == "__main__":
    main()
