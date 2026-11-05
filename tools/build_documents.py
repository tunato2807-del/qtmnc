"""Dựng Word và PowerPoint chỉnh sửa được; cần python-docx, python-pptx."""
import json
import re
from pathlib import Path

from docx import Document
from docx.shared import Inches as DInches, Pt as DPt, Cm, RGBColor as DColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

ROOT = Path(__file__).resolve().parents[1]


def plain(text):
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "").replace("`", "")


def build_report():
    source = ROOT / "docs/report/Bao_cao_NetWatch.md"
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(1.9), Cm(1.8)
    section.left_margin, section.right_margin = Cm(2), Cm(2)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", DPt(10.5)
    normal.paragraph_format.space_after = DPt(7)
    for name in ("Title", "Heading 1", "Heading 2", "Heading 3"):
        doc.styles[name].font.name = "Arial"
        doc.styles[name].font.color.rgb = DColor.from_string("183B70")
    doc.styles["Heading 1"].font.size = DPt(17)
    doc.styles["Heading 2"].font.size = DPt(14)
    header = section.header.paragraphs[0]
    header.text = "NETWATCH  /  QUẢN TRỊ MẠNG NÂNG CAO"
    header.runs[0].font.size = DPt(8)
    header.runs[0].font.color.rgb = DColor.from_string("637691")
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run("NetWatch 2.0  •  ").font.size = DPt(8)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    lines = source.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            p = doc.add_paragraph(line[2:], "Title")
            p.runs[0].font.size = DPt(26)
        elif line.startswith("## "):
            if line == "## Tóm tắt":
                doc.add_paragraph()
                doc.add_picture(str(ROOT / "docs/figures/topology.png"), width=DInches(6.65))
                p = doc.add_paragraph("PYTHON  •  SSH / SNMP  •  TELEGRAM / SLACK")
                p.alignment = 1
                p.runs[0].font.size = DPt(12)
                p.runs[0].font.color.rgb = DColor.from_string("2761CE")
                doc.add_page_break()
            doc.add_heading(line[3:], 1)
        elif line.startswith("!["):
            match = re.match(r"!\[([^]]*)\]\(([^)]+)\)", line)
            path = (source.parent / match[2]).resolve()
            # Dashboard dọc: thu gọn bản xem báo cáo; PNG/SVG gốc có kèm riêng.
            width = DInches(5.0 if "dashboard" in path.name else 6.65)
            if "dashboard" in path.name:
                from PIL import Image
                with Image.open(path) as image:
                    width = DInches(min(5.0, 6.8 * image.width / image.height))
            doc.add_picture(str(path), width=width)
            p = doc.add_paragraph(match[1])
            p.alignment = 1
            p.runs[0].font.size = DPt(9)
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                raw = lines[index].strip()
                cells = [plain(v.strip()) for v in raw.strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", v) for v in cells):
                    rows.append(cells)
                index += 1
            table = doc.add_table(rows=1, cols=len(rows[0]))
            table.style = "Light Shading Accent 1"
            for row_no, row in enumerate(rows):
                cells = table.rows[0].cells if row_no == 0 else table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = value
                    for p in cell.paragraphs:
                        p.paragraph_format.space_after = DPt(4)
                        for run in p.runs:
                            run.font.size = DPt(9)
                trpr = table.rows[row_no]._tr.get_or_add_trPr()
                trpr.append(OxmlElement("w:cantSplit"))
            continue
        else:
            style = "List Number" if re.match(r"^\d+\. ", line) else "Normal"
            doc.add_paragraph(plain(re.sub(r"^\d+\. ", "", line)) if style == "List Number" else plain(line), style)
        index += 1
    target = source.with_suffix(".docx")
    doc.save(target)
    print(target.relative_to(ROOT))


BLUE, NAVY, MUTED = "2761CE", "132E51", "596E88"


def build_slides():
    content = json.loads((ROOT / "docs/presentation/slides.json").read_text())
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    def rect(slide, x, y, w, h, color, line=None):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor.from_string(color)
        shape.line.fill.background() if not line else None
        if line:
            shape.line.color.rgb = RGBColor.from_string(line)
        return shape

    def text(slide, value, x, y, w, h, size=22, color=NAVY, bold=False):
        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = shape.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(.03)
        tf.margin_top = tf.margin_bottom = 0
        paragraph = tf.paragraphs[0]
        run = paragraph.add_run(); run.text = value
        run.font.name = "Arial"; run.font.size = Pt(size);run.font.bold = bold
        run.font.color.rgb = RGBColor.from_string(color)
        return shape

    outline = []
    for number, data in enumerate(content, 1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = RGBColor.from_string("F5F8FD")
        text(slide, "NETWATCH / ĐỒ ÁN QUẢN TRỊ MẠNG", .55,.22,11,.36,20,BLUE,True)
        text(slide, data["title"], .55,.85,12.2,.7,34,NAVY,True)
        text(slide, data["message"], .55,1.70,12.2,1.0,24,MUTED)
        if data.get("layout") == "topology":
            for label,x,y,w,h,color in [("WINDOWS\n192.168.73.1",.6,3.45,3,.95,"E2ECFF"),("R1-LINUX\n192.168.73.10",4.3,3.45,3,.95,BLUE),("SW-SERVERS → SRV1\n10.10.10.0/24",8.1,2.9,4.55,1.05,"E2ECFF"),("SW-USERS → PC01/02\n10.20.20.0/24",8.1,4.3,4.55,1.05,"E2F3EB")]:
                rect(slide,x,y,w,h,color)
                text(slide,label,x+.1,y+.14,w-.2,h-.1,20,"FFFFFF" if color==BLUE else NAVY,True)
            for x1,y1,x2,y2 in ((3.65,3.92,4.25,3.92),(7.35,3.90,8.04,3.43),(7.35,3.95,8.04,4.83)):
                connection = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
                connection.line.color.rgb = RGBColor.from_string(BLUE)
                connection.line.width = Pt(2)
                arrow = OxmlElement("a:headEnd")
                arrow.set("type", "triangle")
                connection._element.spPr.get_or_add_ln().append(arrow)
            text(slide,"NAT gốc VMware → R1 → hai nhánh LAN GNS3",.65,5.6,12,.5,22,BLUE,True)
        else:
            for index, point in enumerate(data["points"]):
                x = .55 + index * 4.12
                rect(slide,x,3,3.97,2.75,"FFFFFF","D7E2F1")
                keyword, explanation = point.split(":",1)
                text(slide,f"0{index+1}",x+.22,3.18,3.4,.45,22,BLUE,True)
                text(slide,keyword+":",x+.22,3.78,3.42,.65,24,NAVY,True)
                text(slide,explanation.strip(),x+.22,4.48,3.42,1.08,22,MUTED)
        text(slide,data["evidence"],.6,6.15,12.1,.65,20,MUTED)
        text(slide,"THIẾT KẾ MỚI · 05/11/2026",.6,7.02,10,.3,20,MUTED)
        text(slide,f"{number:02d} / {len(content)}",11.4,7.02,1.4,.3,20,BLUE,True)
        notes = "Thông điệp cốt lõi: " + data["message"] + "\n" + "\n".join(data["points"]) + "\nSố liệu/Minh chứng: " + data["evidence"] + "\nGợi ý trực quan: " + data["visual"]
        slide.notes_slide.notes_text_frame.text = notes
        outline.append(f"---\n[SLIDE {number}: {data['title']}]\n\n- Thông điệp cốt lõi: {data['message']}\n" + "\n".join("- " + p for p in data["points"]) + f"\n- Số liệu/Minh chứng: {data['evidence']}\n- Gợi ý trực quan: {data['visual']}\n")
    target = ROOT / "docs/presentation/NetWatch_22_slide.pptx"
    prs.save(target)
    (target.parent / "Dan_y_22_slide.md").write_text("\n".join(outline), encoding="utf-8")
    # Kiểm tra font trên tất cả shape dạng text, kể cả footer.
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    for run in p.runs:
                        assert run.font.size and run.font.size.pt >= 20
    print(target.relative_to(ROOT), "— 22 slide; mọi text run >=20pt")


if __name__ == "__main__":
    build_report()
    build_slides()
