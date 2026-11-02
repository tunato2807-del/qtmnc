#!/usr/bin/env python3
"""Build editable Word and report diagrams; no device/API access."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
os.environ.setdefault("XDG_CACHE_HOME",str(Path(tempfile.gettempdir())/"qtmnc-font-cache"))
BASE='''graph [fontname="DejaVu Sans",bgcolor="white",pad="0.3",nodesep="0.4",ranksep="0.55"];
node [fontname="DejaVu Sans",shape=box,style="rounded,filled",fillcolor="#eef4ff",color="#6a89c4",fontsize=14,margin="0.20,0.14"];
edge [fontname="DejaVu Sans",fontsize=11,color="#69829b",arrowsize=0.7];'''
GRAPHS={
"01-topology":'''digraph G {'''+BASE+'''
rankdir=TB;
win [label="WINDOWS THẬT\nVS Code · Python · Dashboard\nTAP 192.168.10.1/24",fillcolor="#dff5ee",color="#299b80"];
subgraph cluster_mgmt {label="GNS3 · QUẢN TRỊ · ACCESS VLAN 10";fontname="DejaVu Sans";fontsize=16;color="#98c3cf";style=rounded;
 cw [label="Cloud-WINDOWS\nUDP local 30010 → 30011"];
 sm [label="SW-MANAGEMENT\nEthernet0 ↔ Ethernet1",fillcolor="#fff1da",color="#cf9c47"];
 cm [label="Cloud-LINUX-MGMT\nVMnet2"];
 {rank=same;cw;sm;cm} cw -> sm -> cm [dir=both];}
subgraph cluster_vm {label="VMWARE UBUNTU · MỘT MÁY ẢO";fontname="DejaVu Sans";fontsize=16;color="#86b89f";style=rounded;
 mg [label="ens37 · QUẢN TRỊ\n192.168.10.129/24\nSSH TCP/22",fillcolor="#e6f5e9"];
 la [label="gns3test · THEO DÕI\n192.168.30.129/24\noperstate",fillcolor="#e6f5e9"];
 nat [label="ens33 · NAT/VMnet8\nDHCP / default route",fillcolor="#e6f5e9"];
 {rank=same;mg;la;nat} mg -> la [style=dashed,dir=none,label="CPU/RAM/temp chung VM"];}
subgraph cluster_lab {label="GNS3 · THỬ NGHIỆM · ACCESS VLAN 30";fontname="DejaVu Sans";fontsize=16;color="#b0a9db";style=rounded;
 cl [label="Cloud-LINUX-LAB\nVMnet3"];
 sl [label="SW-LAB",fillcolor="#fff1da",color="#cf9c47"];
 p1 [label="PC01 · VPCS\n192.168.30.10/24"];
 p2 [label="PC02 · VPCS\n192.168.30.20/24"];
 {rank=same;cl;sl;p1;p2} cl -> sl [dir=both];sl -> p1 [dir=both];sl -> p2 [dir=both];}
net [label="INTERNET\nTelegram / Slack HTTPS",fillcolor="#eef0f8"];
win -> cw [dir=both,label="TAP helper 30011 ↔ GNS3 30010"];
cm -> mg [dir=both,label="Ethernet / VMnet2"];
la -> cl [dir=both,label="Ethernet / VMnet3"];
nat -> net [label="NAT Ubuntu",style=dashed];win -> net [label="HTTPS gửi tin từ Windows",style=dashed,constraint=false];
}''',
"02-architecture":'''digraph G {'''+BASE+'''
rankdir=LR;
subgraph cluster_linux {label="UBUNTU / VMWARE";fontname="DejaVu Sans";color="#93bda7";linux[label="/proc + /sys\nCPU/RAM/temp/interface",fillcolor="#e6f5e9"];}
subgraph cluster_win {label="WINDOWS NMS";fontname="DejaVu Sans";color="#93b1cd";
collect[label="Collector\nSSH dùng lại kết nối\nMột exec mỗi lượt"];
engine[label="Engine\nNgưỡng + hysteresis\nOK / ALERT / UNKNOWN"];
db[label="SQLite\nStates + samples\nEvents + outbox",shape=cylinder,fillcolor="#f0eaff",color="#a38ac4"];
sender[label="Luồng gửi\nRetry / backoff"];
web[label="Web server\n127.0.0.1:8765\nChỉ đọc SQLite"];
browser[label="Chrome / Edge\nDashboard + CSV",fillcolor="#dff5ee",color="#299b80"];
collect -> engine -> db;db -> sender;db -> web -> browser;}
api[label="Telegram / Slack\nHTTPS API",fillcolor="#fff1da",color="#cf9c47"];
linux -> collect[label="Qua GNS3 / SSH 22",dir=both];sender -> api[label="Gửi + xác nhận",dir=both];
}''',
"03-processing":'''digraph G {'''+BASE+'''
rankdir=TB;
start[label="Lấy mẫu theo lịch",fillcolor="#dff5ee"];
read[label="Dùng lại SSH / đọc một batch\nHai mẫu CPU cách nhau ~1 giây"];
check[label="Có kết nối / dữ liệu hợp lệ?",shape=diamond,fillcolor="#fff1da"];
engine[label="Đánh giá từng metric\nGiữ last_known khi UNKNOWN"];
missing[label="Không có mẫu mới\nDOWN hoặc UNKNOWN\nKhông tạo số 0 giả",fillcolor="#ffe9e9",color="#c16b75"];
tx[label="Một transaction SQLite\nState + sample + event + outbox",shape=cylinder,fillcolor="#f0eaff"];
ui[label="Dashboard đọc dữ liệu đã commit\nBiểu đồ / tuổi mẫu / CSV",fillcolor="#dff5ee"];
send[label="Luồng gửi lấy tin đầu hàng đợi"];
ack[label="API xác nhận?",shape=diamond,fillcolor="#fff1da"];
retry[label="Giữ outbox · tăng attempts\nBackoff / Retry-After",fillcolor="#ffe9e9"];
done[label="Xóa tin đã giao\nTiếp tục vòng đo",fillcolor="#dff5ee"];
start -> read -> check;check -> engine[label="Có"];check -> missing[label="Lỗi"];engine -> tx;missing -> tx;tx -> ui;tx -> send -> ack;ack -> retry[label="Chưa"];retry -> send[label="Đến hạn"];ack -> done[label="Có"];
}'''
}


def build_graphs():
    folder=ROOT/"figures";folder.mkdir(exist_ok=True)
    for name,source in GRAPHS.items():
        dot=folder/(name+".dot");dot.write_text(source,encoding="utf-8")
        for fmt in ("png","svg"):
            subprocess.run(["dot",str(dot),"-T"+fmt,"-Gdpi=180","-o",str(folder/(name+"."+fmt))],check=True,capture_output=True)


def inline(paragraph,value):
    for part in re.split(r"(\*\*.*?\*\*|`[^`]+`)",value):
        run=paragraph.add_run(part[2:-2] if part.startswith("**") else part[1:-1] if part.startswith("`") else part)
        run.bold=part.startswith("**")
        if part.startswith("`"):
            run.font.name="Consolas"


def build_word():
    from docx import Document
    from docx.enum.section import WD_SECTION_START
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm,Inches,Pt,RGBColor
    from PIL import Image
    doc=Document()
    section=doc.sections[0]
    section.page_width=Cm(21);section.page_height=Cm(29.7)
    section.top_margin=Cm(2.2);section.bottom_margin=Cm(2.1)
    section.left_margin=Cm(2.4);section.right_margin=Cm(2.0)
    normal=doc.styles["Normal"]
    normal.font.name="Times New Roman";normal.font.size=Pt(13)
    normal.paragraph_format.line_spacing=1.15
    normal.paragraph_format.space_after=Pt(7)
    for name,size in (("Title",28),("Heading 1",19),("Heading 2",15),("Heading 3",13)):
        style=doc.styles[name];style.font.name="Times New Roman";style.font.size=Pt(size)
        style.font.bold=True;style.font.color.rgb=RGBColor.from_string("19354A")
    section.different_first_page_header_footer=True
    for text,size in (("BÁO CÁO ĐỒ ÁN MÔN HỌC",22),("QUẢN TRỊ MẠNG NÂNG CAO",17)):
        p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        run=p.add_run(text);run.bold=True;run.font.size=Pt(size)
    doc.add_paragraph("\n")
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    run=p.add_run("HỆ THỐNG GIÁM SÁT\nTRẠNG THÁI THIẾT BỊ\nVÀ CẢNH BÁO TELEGRAM/SLACK")
    run.bold=True;run.font.size=Pt(23);run.font.color.rgb=RGBColor.from_string("087C71")
    p=doc.add_paragraph("Python · SSH/SNMP · GNS3 · Dashboard web")
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("\n")
    for line in ("Sinh viên: ........................................................", "MSSV / Lớp: ....................................................",
                 "Giảng viên hướng dẫn: .........................................", "Nhóm: ..........................................................."):
        doc.add_paragraph(line)
    p=doc.add_paragraph("Bản kỹ thuật ngày 02/11/2026\nHoàn thiện thông tin và bằng chứng thực nghiệm trước khi nộp")
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    section=doc.add_section(WD_SECTION_START.NEW_PAGE)
    section.different_first_page_header_footer=False
    section.header.is_linked_to_previous=False;section.footer.is_linked_to_previous=False
    numbering=OxmlElement("w:pgNumType");numbering.set(qn("w:start"),"1");section._sectPr.append(numbering)
    header=section.header.paragraphs[0];header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    run=header.add_run("QTMNC  |  ĐỒ ÁN QUẢN TRỊ MẠNG NÂNG CAO");run.font.size=Pt(9);run.font.color.rgb=RGBColor.from_string("718096")
    footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement("w:fldSimple");field.set(qn("w:instr"),"PAGE");footer._p.append(field)
    doc.add_heading("TÓM TẮT VÀ TRẠNG THÁI TÀI LIỆU",level=1)
    doc.add_paragraph("Báo cáo trình bày mô hình GNS3 hai vùng quản trị/thử nghiệm và ứng dụng Python giám sát Ubuntu từ Windows, bổ sung dashboard web đọc cùng SQLite. Nội dung đối chiếu 7 tài liệu môn học (265 trang PDF).")
    doc.add_paragraph("Mã và giao diện đã được kiểm thử trong môi trường phát triển. Cấu hình VMware/GNS3 trên máy sinh viên, số liệu sau sửa CPU và bảng nghiệm thu còn cần kiểm chứng thực tế. Ảnh dashboard đi kèm có nhãn MÔ PHỎNG.")
    doc.add_paragraph("VPN/SDN không bắt buộc. Phạm vi triển khai chính là SSH, dashboard, lịch sử và cảnh báo; các phần ngoài phạm vi được công bố trong từng chương.")
    doc.add_heading("MỤC LỤC NỘI DUNG",level=1)
    lines=(ROOT/"Bao_cao_do_an_QTMNC.md").read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.startswith("# "):doc.add_paragraph(line[2:])
    doc.add_paragraph("Các tiêu đề sử dụng Heading 1/2 của Word, hỗ trợ tạo mục lục tự động và điều hướng sau khi chỉnh sửa.")
    buffer=[];kind="Normal";code=False;code_lines=[];i=0
    def flush():
        nonlocal buffer,kind
        if buffer:
            p=doc.add_paragraph(style=kind);inline(p," ".join(s.strip() for s in buffer));buffer=[];kind="Normal"
    while i<len(lines):
        line=lines[i]
        if line.startswith("```"):
            flush()
            if code:
                p=doc.add_paragraph();r=p.add_run("\n".join(code_lines));r.font.name="Consolas";r.font.size=Pt(10)
                shading=OxmlElement("w:shd");shading.set(qn("w:fill"),"F0F4F8");p._p.get_or_add_pPr().append(shading)
                p.paragraph_format.line_spacing=1;code_lines=[]
            code=not code;i+=1;continue
        if code:code_lines.append(line);i+=1;continue
        if not line.strip():flush();i+=1;continue
        if line.startswith("#"):
            flush();level=len(line)-len(line.lstrip("#"))
            if level==1:doc.add_page_break()
            doc.add_heading(line[level:].strip(),level=min(level,3));i+=1;continue
        image=re.match(r"!\[(.*?)\]\((.*?)\)",line)
        if image:
            flush();caption,path=image.groups();path=ROOT/path
            with Image.open(path) as im:w,h=im.size
            width=min(6.5,7.9*w/h)
            p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run().add_picture(str(path),width=Inches(width))
            p=doc.add_paragraph(caption);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:r.italic=True;r.font.size=Pt(10)
            i+=1;continue
        if line.startswith("|"):
            flush();rows=[]
            while i<len(lines) and lines[i].startswith("|"):
                cells=[x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[:\- ]+",x) for x in cells):rows.append(cells)
                i+=1
            table=doc.add_table(rows=1,cols=len(rows[0]));table.style="Light Shading Accent 1"
            for ri,row in enumerate(rows):
                cells=table.rows[0].cells if ri==0 else table.add_row().cells
                for cell,value in zip(cells,row):
                    p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(3);p.paragraph_format.line_spacing=1.05;inline(p,value)
                    for r in p.runs:r.font.size=Pt(10.5);r.bold=ri==0
            doc.add_paragraph();continue
        bullet=re.match(r"^(- |\d+\. )(.*)",line)
        if bullet:
            flush();kind="List Bullet" if bullet.group(1).startswith("-") else "Normal"
            buffer=[bullet.group(2) if kind=="List Bullet" else line]
        else:buffer.append(line)
        i+=1
    flush()
    doc.core_properties.title="Hệ thống giám sát thiết bị và cảnh báo Telegram/Slack"
    doc.core_properties.subject="Đồ án Quản trị mạng nâng cao: Windows, GNS3, Ubuntu và dashboard web"
    doc.core_properties.author="QTMNC"
    output=ROOT/"Bao_cao_do_an_QTMNC.docx";doc.save(output);print(output)


if __name__=="__main__":
    build_graphs();build_word()
