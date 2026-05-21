#!/usr/bin/env python3
"""Minimal OOXML (docx) -> Markdown converter for FRS-style Word docs."""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def qn(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def text_from(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts: list[str] = []
    for t in el.iter(qn("t")):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts)


def get_pstyle(p: ET.Element) -> str | None:
    ppr = p.find(qn("pPr"))
    if ppr is None:
        return None
    ps = ppr.find(qn("pStyle"))
    if ps is None:
        return None
    return ps.get(qn("val"))


def get_num_level(p: ET.Element) -> int | None:
    ppr = p.find(qn("pPr"))
    if ppr is None:
        return None
    np = ppr.find(qn("numPr"))
    if np is None:
        return None
    ilvl = np.find(qn("ilvl"))
    if ilvl is None:
        return 0
    v = ilvl.get(qn("val"))
    return int(v) if v is not None else 0


def is_centered(p: ET.Element) -> bool:
    ppr = p.find(qn("pPr"))
    if ppr is None:
        return False
    jc = ppr.find(qn("jc"))
    if jc is None:
        return False
    return jc.get(qn("val")) == "center"


def is_bold_first_run(p: ET.Element) -> bool:
    for r in p.findall(qn("r")):
        rpr = r.find(qn("rPr"))
        if rpr is None:
            continue
        b = rpr.find(qn("b"))
        if b is not None and b.get(qn("val"), "1") not in ("0", "false"):
            return True
    return False


STYLE_TO_MD = {
    "Title": "#",
    "Heading1": "#",
    "Heading2": "##",
    "Heading3": "###",
    "Heading4": "####",
    "Heading5": "#####",
    "Heading6": "######",
}


def paragraph_to_md(p: ET.Element, list_depth: list[int]) -> str | None:
    """Return markdown line(s) or None to skip."""
    # Skip paragraphs that only contain sectPr
    if p.find(qn("sectPr")) is not None and not text_from(p).strip():
        return None

    txt = text_from(p).strip()
    if not txt and not p.findall(qn("r")):
        return ""

    style = get_pstyle(p)
    num_lvl = get_num_level(p)

    if num_lvl is not None:
        indent = "  " * num_lvl
        return f"{indent}- {txt}"

    if style in STYLE_TO_MD:
        prefix = STYLE_TO_MD[style]
        return f"{prefix} {txt}"

    if style == "Title" or (is_centered(p) and is_bold_first_run(p) and len(txt) < 120):
        # Title-like without explicit style
        if txt and not style:
            pass

    if is_centered(p) and len(txt) < 200:
        return f"<p align=\"center\">{txt}</p>"

    return txt


def table_to_md(tbl: ET.Element) -> str:
    rows: list[list[str]] = []
    for tr in tbl.findall(f".//{qn('tr')}"):
        cells: list[str] = []
        for tc in tr.findall(qn("tc")):
            cell_parts: list[str] = []
            for p in tc.findall(qn("p")):
                t = text_from(p).strip()
                if t:
                    cell_parts.append(t.replace("|", "\\|").replace("\n", " "))
            cells.append(" ".join(cell_parts) if cell_parts else "")
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    n = max(len(r) for r in rows)
    norm = [r + [""] * (n - len(r)) for r in rows]
    lines = []
    lines.append("| " + " | ".join(norm[0]) + " |")
    lines.append("| " + " | ".join(["---"] * n) + " |")
    for r in norm[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines) + "\n"


def convert(docx_path: Path, md_path: Path) -> None:
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(qn("body"))
    if body is None:
        raise SystemExit("No w:body in document.xml")

    out: list[str] = []
    out.append("---")
    out.append(f"title: {docx_path.stem}")
    out.append("source: FRS - Module-quan-ly-nghi-phep.docx (converted)")
    out.append("language: vi")
    out.append("---")
    out.append("")
    out.append(f"> **Nguồn:** `{docx_path.name}` — chuyển tự động từ Word (OOXML). Hình ảnh trong file gốc không được nhúng; cần mở `.docx` để xem diagram.")
    out.append("")

    for child in body:
        tag = child.tag
        if tag == qn("p"):
            line = paragraph_to_md(child, [])
            if line is None:
                continue
            if line == "":
                out.append("")
                continue
            out.append(line)
            out.append("")
        elif tag == qn("tbl"):
            md_tbl = table_to_md(child)
            if md_tbl.strip():
                out.append(md_tbl)
                out.append("")

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove empty markdown headings (Word sometimes emits empty Heading2/3)
    text = re.sub(r"(?m)^#+\s*$\n", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    md_path.write_text(text.strip() + "\n", encoding="utf-8")
    print(f"Wrote {md_path} ({len(text)} chars)")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    docx = base / "FRS - Module-quan-ly-nghi-phep.docx"
    md = base / "requestment.md"
    if len(sys.argv) >= 2:
        docx = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        md = Path(sys.argv[2])
    convert(docx, md)
