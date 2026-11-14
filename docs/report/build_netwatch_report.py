#!/usr/bin/env python3
"""Build the editable report from Markdown without changing application code.

Requires Python 3.12, python-docx, Pillow. Optional: LibreOffice for PDF rendering.
Run from any directory: python docs/report/build_netwatch_report.py
Generated evidence summaries are explicitly labelled; they are not screenshots.
"""
import argparse
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'Bao_cao_NetWatch_2026_2027.md'
TARGET = SOURCE.with_suffix('.docx')
FONT_ROOT = Path('/usr/share/fonts/truetype/dejavu')


def image_font(size, bold=False):
    return ImageFont.truetype(str(FONT_ROOT / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size)


def figures():
    assets = HERE / 'assets'
    assets.mkdir(exist_ok=True)
    ink, blue, muted = '#172d48', '#234f85', '#536579'

    def canvas(w, h, title, subtitle):
        im = Image.new('RGB', (w, h), 'white')
        dr = ImageDraw.Draw(im)
        dr.text((55, 32), title, fill=ink, font=image_font(38, True))
        dr.text((55, 91), subtitle, fill=muted, font=image_font(23))
        return im, dr

    def box(dr, xy, title, lines, fill='#f3f6fb'):
        dr.rounded_rectangle(xy, 16, fill=fill, outline='#9cafc7', width=3)
        x0, y0, x1, y1 = xy
        center = (x0+x1)/2
        dr.text((center, y0+22), title, anchor='mt', fill=blue, font=image_font(28, True))
        for i, line in enumerate(lines):
            dr.text((center, y0+70+i*36), line, anchor='mt', fill=ink, font=image_font(23))

    def arrow(dr, start, end, label=None):
        import math
        dr.line([start, end], fill=blue, width=5)
        a = math.atan2(end[1]-start[1], end[0]-start[0])
        dr.polygon([end, (end[0]-19*math.cos(a-.45), end[1]-19*math.sin(a-.45)),
                    (end[0]-19*math.cos(a+.45), end[1]-19*math.sin(a+.45))], fill=blue)
        if label:
            dr.text(((start[0]+end[0])/2, (start[1]+end[1])/2-34), label,
                    anchor='mm', fill=muted, font=image_font(21))

    im, dr = canvas(1800, 900, 'MÔ HÌNH LOGIC NETWATCH', '6 node GNS3; Windows chạy giám sát bên ngoài topology')
    box(dr, (45, 365, 405, 585), 'WINDOWS', ['Python · Dashboard', 'VMnet8: 192.168.73.1', 'Telegram qua Internet'])
    box(dr, (555, 340, 940, 610), 'R1 LINUX', ['mgmt0: 192.168.73.10', 'srv0: 10.10.10.1', 'users0: 10.20.20.1', 'Định tuyến IPv4'])
    box(dr, (1080, 180, 1390, 350), 'SW-SERVERS', ['10.10.10.0/24'])
    box(dr, (1470, 180, 1760, 350), 'SRV1 LINUX', ['lan0: 10.10.10.10'])
    box(dr, (1080, 610, 1390, 780), 'SW-USERS', ['10.20.20.0/24'])
    box(dr, (1470, 610, 1760, 780), 'PC01 · PC02', ['Hai VPCS'])
    arrow(dr, (405, 470), (550, 470), 'VMnet8')
    arrow(dr, (940, 400), (1080, 270))
    arrow(dr, (1390, 270), (1470, 270))
    arrow(dr, (940, 550), (1080, 695))
    arrow(dr, (1390, 695), (1470, 695))
    dr.text((55, 845), 'Nguồn: lab/design.json và xác nhận người triển khai. Sơ đồ thiết kế, không phải ảnh chụp GNS3.', fill=muted, font=image_font(22))
    im.save(assets / 'mo_hinh_netwatch.png')

    im, dr = canvas(1800, 790, 'LUỒNG DỮ LIỆU GIÁM SÁT', 'Thu thập, đánh giá trạng thái và gửi tin được tách thành các worker')
    box(dr, (45, 190, 445, 405), 'LINUX R1 / SRV1', ['Probe đọc /proc, /sys', 'JSON qua SSH'])
    box(dr, (615, 190, 1055, 405), 'WINDOWS · NETWATCH', ['Kiểm tra mẫu', 'Tính metric, chuyển trạng thái'])
    box(dr, (1225, 190, 1755, 405), 'SQLITE', ['Current · Samples · Events', 'Outbox lưu bền'])
    box(dr, (590, 540, 1080, 710), 'FLASK DASHBOARD', ['Trạng thái · lịch sử · xuất dữ liệu'])
    box(dr, (1225, 540, 1755, 710), 'WORKER GỬI TIN', ['Telegram; thử lại khi có lỗi'])
    arrow(dr, (445, 300), (615, 300), 'JSON')
    arrow(dr, (1055, 300), (1225, 300), 'Ghi')
    arrow(dr, (1390, 410), (1000, 535), 'Đọc')
    arrow(dr, (1510, 410), (1510, 535))
    im.save(assets / 'luong_du_lieu.png')

    im, dr = canvas(1800, 850, 'TỔNG HỢP MINH CHỨNG DASHBOARD', 'Số liệu chép từ ảnh người dùng cung cấp; không phải ảnh chụp màn hình')
    box(dr, (55, 170, 865, 325), '2/2 THIẾT BỊ · CHU KỲ 15 GIÂY', ['0 chỉ số cảnh báo · 0 tin đang chờ'])
    box(dr, (935, 170, 1745, 325), 'LAB THẬT · PHƯƠNG THỨC SSH', ['HTTP SRV1: chưa bật'])
    box(dr, (55, 380, 865, 750), 'R1-LINUX · 192.168.73.10', ['CPU: 1,0%    RAM: 41,1%', 'mgmt0 · srv0 · users0: UP', 'Ngưỡng CPU >75% · RAM >65%', 'Không có số đo nhiệt độ'])
    box(dr, (935, 380, 1745, 750), 'SRV1-LINUX · 10.10.10.10', ['CPU: 1,0%    RAM: 58,0%', 'lan0: UP', 'Ngưỡng CPU >75% · RAM >65%', 'Không có số đo nhiệt độ'])
    dr.text((55, 797), 'Nguồn: ảnh A01, A03 trong tin nhắn. Giá trị tại thời điểm chụp, không phải trung bình toàn phiên.', fill=muted, font=image_font(22))
    im.save(assets / 'tong_hop_dashboard.png')

    im, dr = canvas(1800, 940, 'CẢNH BÁO CPU VÀ PHỤC HỒI', '13/11/2026 (+0700) · Chép từ sự kiện dashboard và nội dung tin Telegram')
    data = [('SRV1-LINUX', '19:52:19 · CPU 100,0%', '19:52:34 · CPU 2,0%'),
            ('SRV1-LINUX', '20:36:39 · CPU 76,9%', '20:36:54 · CPU 0,5%'),
            ('R1-LINUX', '20:36:54 · CPU 87,4%', '20:37:09 · CPU 1,0%')]
    for i, (name, alert, recovery) in enumerate(data):
        y = 180 + i*225
        dr.text((65, y+70), name, fill=ink, font=image_font(28, True))
        box(dr, (390, y, 980, y+170), 'ALERT · CPU >75%', [alert], '#fff2f2')
        box(dr, (1140, y, 1735, y+170), 'OK · ĐÃ PHỤC HỒI', [recovery], '#eef8f2')
        arrow(dr, (985, y+85), (1130, y+85), '15 giây')
    dr.text((55, 875), 'Bản tổng hợp, không phải ảnh chụp Telegram. Khoảng cách sự kiện không phải độ trễ nhận tin.', fill=muted, font=image_font(22))
    im.save(assets / 'chuoi_su_kien_cpu.png')


def font_style(style, size=13, bold=False):
    style.font.name = 'Times New Roman'
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr=style.element.get_or_add_rPr()
    fonts=rpr.rFonts
    for attr in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme','csTheme']:
        fonts.attrib.pop(qn('w:'+attr),None)
    for attr in ['ascii','hAnsi','eastAsia','cs']:
        fonts.set(qn('w:'+attr),'Times New Roman')
    size_cs=rpr.find(qn('w:szCs'))
    if size_cs is not None: size_cs.set(qn('w:val'),str(size*2))


def field(paragraph, code, result=''):
    for tag, content in [('begin', None), ('instr', code), ('separate', None), ('text', result), ('end', None)]:
        r = paragraph.add_run()
        if tag == 'instr':
            node = OxmlElement('w:instrText'); node.set(qn('xml:space'), 'preserve'); node.text = ' '+content+' '
        elif tag == 'text':
            r.text = content
            continue
        else:
            node = OxmlElement('w:fldChar'); node.set(qn('w:fldCharType'), tag)
        r._r.append(node)


def rich(p, text):
    for token in re.split(r'(\*\*.*?\*\*|\*[^*]+\*|`[^`]+`)', text):
        if not token:
            continue
        if token.startswith('**'):
            r = p.add_run(token[2:-2]); r.bold = True
        elif token.startswith('*'):
            r = p.add_run(token[1:-1]); r.italic = True
        elif token.startswith('`'):
            p.add_run(token[1:-1])
        else:
            p.add_run(token)


def bookmark(p, name, number):
    start = OxmlElement('w:bookmarkStart'); start.set(qn('w:id'), str(number)); start.set(qn('w:name'), name)
    end = OxmlElement('w:bookmarkEnd'); end.set(qn('w:id'), str(number))
    p._p.insert(0, start); p._p.append(end)


def configure_section(section):
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = section.right_margin = Cm(2)
    section.left_margin = Cm(3)
    section.header_distance = section.footer_distance = Cm(1)


def build(page_map=None):
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    page_map = page_map or {}
    headings, caps = [], {'figures': [], 'tables': []}
    body = False
    for line in lines:
        if line == '# MỞ ĐẦU': body = True
        if body and line.startswith('#'):
            level = len(line)-len(line.lstrip('#'))
            if level <= 3: headings.append((level, line[level+1:]))
        if re.match(r'^Bảng \d+\.\d+\.', line): caps['tables'].append(line)
        m = re.match(r'!\[(.*?)\]\(', line)
        if m: caps['figures'].append(m[1])

    doc = Document()
    configure_section(doc.sections[0])
    doc.core_properties.title = 'NetWatch – Báo cáo đồ án chuyên ngành'
    doc.core_properties.subject = 'Giám sát hai thiết bị Linux và cảnh báo Telegram'
    doc.core_properties.author = ''
    doc.core_properties.keywords = 'NetWatch, Linux, GNS3, Telegram, nghiệm thu'
    normal = doc.styles['Normal']
    font_style(normal)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.first_line_indent = Cm(1)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.widow_control = True
    for name in ['Front Title', 'Cover Title', 'Cover Text', 'Figure Caption', 'Table Caption', 'Source Note', 'Code Text', 'TOC Entry']:
        doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        font_style(doc.styles[name])
        doc.styles[name].paragraph_format.line_spacing = 1.5
        doc.styles[name].paragraph_format.space_after = Pt(6)
    for name in ['Front Title', 'Cover Title']:
        font_style(doc.styles[name], 16, True)
        doc.styles[name].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.styles[name].paragraph_format.space_after = Pt(18)
    doc.styles['Cover Text'].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.styles['Cover Text'].paragraph_format.space_after = Pt(12)
    for n in range(1, 4):
        st = doc.styles[f'Heading {n}']; font_style(st,16,True)
        st.paragraph_format.first_line_indent = Cm(0)
        st.paragraph_format.line_spacing = 1.5
        st.paragraph_format.space_before = Pt(12)
        st.paragraph_format.space_after = Pt(8)
        st.paragraph_format.keep_with_next = True
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if n == 1 else WD_ALIGN_PARAGRAPH.LEFT
    for name in ['Figure Caption', 'Table Caption']:
        st = doc.styles[name]
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        st.paragraph_format.keep_with_next = name == 'Table Caption'
        st.font.bold = True
    doc.styles['Source Note'].font.italic = True
    doc.styles['Code Text'].paragraph_format.line_spacing = 1.0
    doc.styles['Code Text'].paragraph_format.space_after = Pt(3)
    doc.styles['Code Text'].paragraph_format.keep_with_next = True
    settings = doc.settings.element
    upd = OxmlElement('w:updateFields'); upd.set(qn('w:val'), 'true'); settings.append(upd)

    count = 1
    bookmarks = {}
    for _, text in headings:
        bookmarks[text] = f'h{count}'; count += 1
    for group in caps.values():
        for text in group:
            bookmarks[text] = f'h{count}'; count += 1

    def index(kind):
        entries = headings if kind == 'toc' else [(1, t) for t in caps[kind]]
        code = 'TOC \\o "1-3" \\h \\z \\u' if kind == 'toc' else 'TOC \\t "'+('Figure Caption' if kind=='figures' else 'Table Caption')+',1" \\h \\z'
        # A complex field with cached, clickable entries and PAGEREF fields.
        p = doc.add_paragraph(style='TOC Entry')
        for tag in ['begin', 'instr', 'separate']:
            r = p.add_run()
            el = OxmlElement('w:instrText' if tag=='instr' else 'w:fldChar')
            if tag=='instr': el.set(qn('xml:space'), 'preserve'); el.text = ' '+code+' '
            else: el.set(qn('w:fldCharType'), tag)
            r._r.append(el)
        for level, text in entries:
            p = doc.add_paragraph(style='TOC Entry')
            p.paragraph_format.left_indent = Cm((level-1)*.5)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(16), 2, 1)
            r=p.add_run(text); r.bold = level == 1
            p.add_run('\t')
            field(p, f'PAGEREF {bookmarks[text]} \\h', str(page_map.get(text, '')))
        r = p.add_run(); el=OxmlElement('w:fldChar'); el.set(qn('w:fldCharType'),'end'); r._r.append(el)

    def main_section():
        section=doc.add_section(WD_SECTION_START.NEW_PAGE)
        configure_section(section)
        section.header.is_linked_to_previous = False
        section.footer.is_linked_to_previous = False
        pg = OxmlElement('w:pgNumType'); pg.set(qn('w:start'), '1'); section._sectPr.append(pg)
        for part, left, right in [
            (section.header, 'NetWatch – Giám sát thiết bị Linux', 'GVHD: ........................'),
            (section.footer, 'Sinh viên: ........................................', None),
        ]:
            # Borderless cells avoid inherited Word template tab stops.
            empty = part.paragraphs[0]
            empty.paragraph_format.space_after=Pt(0)
            empty.paragraph_format.line_spacing=1
            empty.add_run().font.size=Pt(1)
            table=part.add_table(rows=1,cols=2,width=Cm(16))
            table.autofit=False
            table.columns[0].width=Cm(10); table.columns[1].width=Cm(6)
            for cell, width in zip(table.rows[0].cells,[10,6]): cell.width=Cm(width)
            for idx,text in enumerate([left,right]):
                p=table.cell(0,idx).paragraphs[0]
                p.paragraph_format.first_line_indent=Cm(0)
                p.paragraph_format.space_after=Pt(0)
                p.paragraph_format.line_spacing=1
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT if idx==0 else WD_ALIGN_PARAGRAPH.RIGHT
                if text is None: field(p, 'PAGE', '1')
                else: p.add_run(text)
                for r in p.runs: r.font.name='Times New Roman'; r.font.size=Pt(13)

    i=0; cover=False; first=True; body=False
    while i < len(lines):
        line=lines[i].strip()
        if not line:
            i+=1; continue
        if line.startswith('<!--'):
            if line in ['<!-- cover -->', '<!-- inner-cover -->']: cover=True
            elif line in ['<!-- toc -->','<!-- figures -->','<!-- tables -->']:
                kind=line[5:-4].strip()
                index(kind)
                closing=f'<!-- /{kind} -->'
                if closing in lines[i+1:]:
                    while lines[i] != closing: i+=1
            i+=1; continue
        if line.startswith('# '):
            title=line[2:]
            if title=='MỞ ĐẦU':
                main_section(); body=True
            elif not first:
                doc.add_page_break()
            if title!='BÁO CÁO ĐỒ ÁN CHUYÊN NGÀNH': cover=False
            p=doc.add_paragraph(title, 'Cover Title' if cover else 'Heading 1' if body else 'Front Title')
            if title in bookmarks: bookmark(p,bookmarks[title],int(bookmarks[title][1:]))
            first=False; i+=1; continue
        if line.startswith('##'):
            level=len(line)-len(line.lstrip('#'))
            title=line[level+1:]
            p=doc.add_paragraph(title, f'Heading {min(level,3)}')
            bookmark(p,bookmarks[title],int(bookmarks[title][1:]))
            i+=1; continue
        if line.startswith('```'):
            i+=1; block=[]
            while i<len(lines) and not lines[i].startswith('```'):
                block.append(lines[i]); i+=1
            for n, code in enumerate(block):
                p=doc.add_paragraph(code,'Code Text')
                p.paragraph_format.keep_with_next = n<len(block)-1
            i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[s.strip() for s in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',s) for s in cells): rows.append(cells)
                i+=1
            table=doc.add_table(rows=0, cols=len(rows[0])); table.style='Table Grid'
            table.autofit=False
            # Keep narrow columns usable with 13pt body type.
            weights={2:[.29,.71],3:[.24,.38,.38],4:[.18,.28,.27,.27],5:[.18,.25,.16,.25,.16]}.get(len(rows[0]))
            for c,w in zip(table.columns,weights): c.width=Cm(16*w)
            for n,row in enumerate(rows):
                cells=table.add_row().cells
                for cell,value,w in zip(cells,row,weights):
                    cell.width=Cm(16*w)
                    p=cell.paragraphs[0]; p.paragraph_format.first_line_indent=Cm(0)
                    p.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.line_spacing=1.5
                    p.paragraph_format.space_after=Pt(3)
                    rich(p,value)
                    for r in p.runs: r.font.size=Pt(13); r.bold=True if n==0 else r.bold
                    if n==0:
                        shade=OxmlElement('w:shd'); shade.set(qn('w:fill'),'EDEDED'); cell._tc.get_or_add_tcPr().append(shade)
                trpr=table.rows[-1]._tr.get_or_add_trPr(); trpr.append(OxmlElement('w:cantSplit'))
                if n==0:
                    repeat=OxmlElement('w:tblHeader'); trpr.append(repeat)
            continue
        m=re.match(r'!\[(.*?)\]\((.*?)\)',line)
        if m:
            path=HERE/m[2]
            if not path.exists(): raise FileNotFoundError(path)
            p=doc.add_paragraph(); p.paragraph_format.first_line_indent=Cm(0)
            p.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next=True
            p.add_run().add_picture(str(path),width=Cm(16))
            p=doc.add_paragraph(m[1],'Figure Caption')
            bookmark(p,bookmarks[m[1]],int(bookmarks[m[1]][1:]))
            i+=1; continue
        if re.match(r'^Bảng \d+\.\d+\.',line):
            p=doc.add_paragraph(line,'Table Caption')
            bookmark(p,bookmarks[line],int(bookmarks[line][1:]))
            i+=1; continue
        paragraph=[line]; i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|!\[|<!--|\d+\. )',lines[i]):
            paragraph.append(lines[i].strip()); i+=1
        text=' '.join(paragraph)
        style='Cover Text' if cover else 'Source Note' if text.startswith('Nguồn:') else 'Normal'
        p=doc.add_paragraph(style=style); rich(p,text)
        if re.match(r'^\d+\. ',text) or text.startswith('['): p.paragraph_format.first_line_indent=Cm(0)
        if cover and ('XÂY DỰNG' in text or text=='**NETWATCH**'):
            for r in p.runs: r.font.bold=True; r.font.size=Pt(18)
            p.paragraph_format.space_before=Pt(12); p.paragraph_format.space_after=Pt(18)
    doc.save(TARGET)
    print(TARGET)
    return doc


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page-map',type=Path,default=HERE/'report_pages.json',
                        help='Rendered heading/caption page numbers in JSON (refresh after content changes)')
    args=parser.parse_args()
    figures()
    build(json.loads(args.page_map.read_text()) if args.page_map.exists() else None)
