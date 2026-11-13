"""Dựng hướng dẫn tự vẽ thành HTML/DOCX; không cần để chạy ứng dụng NetWatch."""
import re
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/06_TU_VE_GNS3_TUNG_BUOC.md"


def plain(value):
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    return value.replace("**", "").replace("`", "")


def write_html(text):
    body = MarkdownIt("commonmark", {"html": False}).enable("table").render(text)
    document = '''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Tự vẽ GNS3 và chạy NetWatch</title><style>
body{font:16px/1.65 'Segoe UI',Arial,sans-serif;max-width:1100px;margin:32px auto;padding:0 24px;color:#173352;background:#fafcff}h1{font-size:30px}h1,h2,h3{color:#2456a9;line-height:1.3}h2{border-top:1px solid #dbe5f1;margin-top:36px;padding-top:24px;font-size:23px}a{color:#2456a9}pre{background:#edf2f8;border:1px solid #dce5f1;padding:17px;overflow-x:auto;font:14px/1.5 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}code{font-family:Consolas,monospace}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #d3dfed;padding:9px;text-align:left;vertical-align:top}th{background:#e8eff9}li{margin:6px 0}@media print{body{font-size:11pt;margin:0;max-width:none;padding:0;background:white}h2{break-after:avoid}pre{font-size:9pt}tr{break-inside:avoid}@page{size:A4;margin:16mm}}
</style></head><body>''' + body + '</body></html>'
    SOURCE.with_suffix(".html").write_text(document, encoding="utf-8")


def write_word(text):
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(1.7)
    section.left_margin = section.right_margin = Cm(1.8)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    for name in ("Title", "Heading 1", "Heading 2"):
        doc.styles[name].font.name = "Arial"
        doc.styles[name].font.color.rgb = RGBColor.from_string("2456A9")
    doc.styles["Heading 1"].font.size = Pt(16)
    header = section.header.paragraphs[0]
    header.text = "NETWATCH • WINDOWS / VMWARE / GNS3 • HƯỚNG DẪN TỰ VẼ"
    header.runs[0].font.size = Pt(8)
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run("13/11/2026 • ").font.size = Pt(8)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    lines = text.splitlines()
    code, index = False, 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            code = not code
        elif code:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(line)
            run.font.name, run.font.size = "Courier New", Pt(9)
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), "EDF2F8")
            p._p.get_or_add_pPr().append(shading)
        elif line.startswith("# "):
            doc.add_paragraph(line[2:], "Title")
        elif line.startswith("## "):
            doc.add_heading(line[3:], 1)
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [plain(c.strip()) for c in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                index += 1
            table = doc.add_table(rows=1, cols=len(rows[0]))
            table.style = "Light Shading Accent 1"
            for row_index, row in enumerate(rows):
                cells = table.rows[0].cells if row_index == 0 else table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = value
                    for p in cell.paragraphs:
                        p.paragraph_format.space_after = Pt(3)
                        for run in p.runs:
                            run.font.size = Pt(9)
                props = table.rows[row_index]._tr.get_or_add_trPr()
                props.append(OxmlElement("w:cantSplit"))
                if row_index == 0:
                    props.append(OxmlElement("w:tblHeader"))
            continue
        elif line.strip():
            value = plain(line)
            if re.match(r"^\d+\. ", value):
                doc.add_paragraph(re.sub(r"^\d+\. ", "", value), "List Number")
            elif value.startswith("- "):
                doc.add_paragraph(value[2:], "List Bullet")
            else:
                doc.add_paragraph(value)
        index += 1
    doc.save(SOURCE.with_suffix(".docx"))


if __name__ == "__main__":
    text = SOURCE.read_text(encoding="utf-8")
    if text.count("```") % 2:
        raise ValueError("Code fence chưa đóng")
    write_html(text)
    write_word(text)
    print("Đã dựng", SOURCE.with_suffix(".html").name, "và", SOURCE.with_suffix(".docx").name)
