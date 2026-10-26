#!/usr/bin/env python3
"""Build offline Vietnamese learning diagrams, interactive HTML and an illustrated PDF."""
from __future__ import annotations
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('XDG_CACHE_HOME', str(Path(tempfile.gettempdir()) / 'qtmnc-font-cache'))


def graphs(models):
    for fmt in ('svg', 'png'):
        (ROOT / fmt).mkdir(exist_ok=True)
    for item in models:
        for fmt in ('svg', 'png'):
            command = ['dot', str(ROOT / 'source' / (item['stem'] + '.dot')), '-T' + fmt,
                       '-o', str(ROOT / fmt / (item['stem'] + '.' + fmt))]
            if fmt == 'png':
                command.append('-Gdpi=180')
            subprocess.run(command, check=True, capture_output=True)


def build_html(models):
    tabs, panels = [], []
    for index, item in enumerate(models):
        name = item['id']
        tabs.append(f'<button class="tab" role="tab" id="tab-{name}" aria-controls="panel-{name}" '
                    f'aria-selected="{str(index == 0).lower()}" tabindex="{0 if index == 0 else -1}" '
                    f'data-model="{name}">{html.escape(item["tab"])}</button>')
        svg = (ROOT / 'svg' / (item['stem'] + '.svg')).read_text(encoding='utf-8')
        svg = svg[svg.index('<svg'):]
        # Multiple Graphviz SVGs share node1/graph0 IDs; scope them in the HTML.
        svg = re.sub(r'\bid="([^"]+)"', lambda match: f'id="{name}-{match[1]}"', svg)
        svg = re.sub(r'url\(#([^)]*)\)', lambda match: f'url(#{name}-{match[1]})', svg)
        svg = re.sub(r'<svg\b', f'<svg role="img" aria-label="{html.escape(item["title"], quote=True)}"', svg, count=1)
        cards = ''.join(f'<article class="explain"><h3>{html.escape(section["title"])}</h3>'
                        f'<p>{html.escape(section["body"])}</p></article>' for section in item['sections'])
        points = ''.join('<li>' + html.escape(point) + '</li>' for point in item['takeaways'])
        panels.append(f'<section class="panel" id="panel-{name}" role="tabpanel" aria-labelledby="tab-{name}"'
                      + (' hidden' if index else '') + f'><h2>{html.escape(item["title"])}</h2>'
                      f'<p class="intro">{html.escape(item["intro"])}</p><figure class="diagram">{svg}'
                      '<figcaption>Sơ đồ thiết kế. Xem phần giải thích bên dưới; trên màn hình nhỏ có thể cuộn ngang hình.</figcaption></figure>'
                      f'<div class="explain-grid">{cards}</div><aside class="takeaways"><strong>Điểm cần nhớ</strong><ul>{points}</ul></aside></section>')
    template = (ROOT / 'template.html').read_text(encoding='utf-8')
    output = template.replace('@@TABS@@', '\n'.join(tabs)).replace('@@PANELS@@', '\n'.join(panels))
    (ROOT / 'index.html').write_text(output, encoding='utf-8')


def build_markdown(data):
    lines = ['# ' + data['title'], '', data['subtitle'], '',
             'Mở **index.html** bằng Chrome/Edge để xem 6 sơ đồ và thử mô phỏng tương tác. '
             'File HTML chứa sẵn hình, CSS và JavaScript, chạy không cần Internet hay cài thư viện.', '',
             'Trang HTML là tài liệu học, không phải dashboard lấy dữ liệu thiết bị thật. '
             'Các nút không điều khiển Linux và không gửi tin nhắn thật.', '',
             '[Tải PDF minh họa](Huong_dan_truc_quan.pdf). PNG/SVG nằm trong thư mục tương ứng; '
             'source chứa Graphviz để chỉnh sửa. Dựng lại bằng python build.py; cần Graphviz, Pillow và ReportLab.', '']
    for item in data['models']:
        lines += ['## ' + item['title'], '', item['intro'], '',
                  f'![{item["title"]}](png/{item["stem"]}.png)', '']
        for section in item['sections']:
            lines += ['**' + section['title'] + '.** ' + section['body'], '']
        lines += ['Điểm cần nhớ:', ''] + ['- ' + point for point in item['takeaways']] + ['']
    lines += ['## Liên hệ với code', '',
              '| Phần | File |', '|---|---|', '| Vòng giám sát SSH | monitor.py |',
              '| Thu thập | device_monitor/collectors/ssh.py, snmp.py, hybrid.py |',
              '| So ngưỡng | device_monitor/engine.py |', '| SQLite và hàng đợi | device_monitor/storage.py |',
              '| Gửi cảnh báo | device_monitor/notifications.py |', '| Hiển thị | device_monitor/ui.py |', '',
              'Mật khẩu/token ở .env.simple cục bộ. Không đưa file cấu hình thật vào báo cáo hoặc GitHub.', '',
              'Nguồn đối chiếu: code của kho qtmnc và cấu hình người dùng cung cấp. '
              'Địa chỉ DHCP có thể thay đổi. Các phép thử thực tế cần ghi nhận kết quả thay vì suy ra từ sơ đồ.', '']
    (ROOT / 'README.md').write_text('\n'.join(lines), encoding='utf-8')


def build_pdf(data):
    from PIL import Image
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph
    font_options = [('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                    ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf')]
    for regular, bold in font_options:
        if Path(regular).is_file() and Path(bold).is_file():
            break
    else:
        raise RuntimeError('Cần font DejaVu Sans hoặc Arial có dấu tiếng Việt')
    pdfmetrics.registerFont(TTFont('LearnSans', regular))
    pdfmetrics.registerFont(TTFont('LearnBold', bold))
    styles = {'title': ParagraphStyle('title', fontName='LearnBold', fontSize=23, leading=31, textColor=colors.HexColor('#17243b')),
              'heading': ParagraphStyle('heading', fontName='LearnBold', fontSize=15, leading=22, textColor=colors.HexColor('#17243b')),
              'body': ParagraphStyle('body', fontName='LearnSans', fontSize=10.5, leading=16, textColor=colors.HexColor('#334155'))}
    c = canvas.Canvas(str(ROOT / 'Huong_dan_truc_quan.pdf'), pagesize=A4)
    c.setTitle(data['title'])
    page = 1

    def paragraph(text, x, y, width, style='body'):
        p = Paragraph(html.escape(text).replace('\n', '<br/>'), styles[style])
        _, height = p.wrap(width, 3000)
        p.drawOn(c, x, y - height)
        return y - height

    def footer():
        width, _ = c._pagesize
        c.setFont('LearnSans', 8)
        c.setFillColor(colors.HexColor('#64748b'))
        c.drawString(35, 22, 'qtmnc · Tài liệu học bằng hình · 26/10/2026')
        c.drawRightString(width - 35, 22, str(page))

    width, height = A4
    y = paragraph('HỆ THỐNG GIÁM SÁT\nTRẠNG THÁI THIẾT BỊ', 40, height - 70, width - 80, 'title') - 20
    y = paragraph('Và gửi cảnh báo qua Telegram / Slack', 40, y, width - 80, 'heading') - 30
    y = paragraph(data['subtitle'], 40, y, width - 80) - 25
    for text in [
        'Tài liệu đi từ vai trò thiết bị đến đường mạng, vòng lấy mẫu, điều kiện cảnh báo, SSH/SNMP và cách phân biệt sự cố.',
        'Windows chạy Python là máy giám sát. Ubuntu trong VMware là thiết bị được đo. GNS3 tạo mạng thử nghiệm. Telegram/Slack là nơi nhận thông báo.',
        'Bản đơn giản hiện dùng SSH. SNMP/hybrid là bản mở rộng. TAP/UDP chỉ là hỗ trợ kết nối trong lab hiện tại, không phải chức năng giám sát bắt buộc.',
        'Mở index.html để thử tăng RAM, ngắt ens33, mất đường SSH hoặc mất Internet. Mô phỏng không điều khiển thiết bị và không gửi tin thật.',
        'Địa chỉ theo cấu hình người dùng cung cấp. Sơ đồ không thay thế kết quả nghiệm thu thực tế. Không chứa mật khẩu/token.'
    ]:
        y = paragraph(text, 40, y, width - 80) - 17
    footer(); c.showPage(); page += 1
    for item in data['models']:
        path = ROOT / 'png' / (item['stem'] + '.png')
        with Image.open(path) as im:
            iw, ih = im.size
        size = landscape(A4) if iw / ih > 1.3 else A4
        c.setPageSize(size); width, height = size
        y = paragraph(item['tab'] + ' — ' + item['title'], 35, height - 30, width - 70, 'heading') - 10
        y = paragraph(item['intro'], 35, y, width - 70) - 15
        notes = '\n'.join('• ' + point for point in item['takeaways'])
        probe = Paragraph(html.escape(notes).replace('\n', '<br/>'), styles['body'])
        notes_h = probe.wrap(width - 70, 1000)[1]
        available = y - notes_h - 70
        scale = min((width - 70) / iw, available / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(str(path), (width - dw) / 2, y - dh, width=dw, height=dh, mask='auto')
        paragraph(notes, 35, y - dh - 12, width - 70)
        footer(); c.showPage(); page += 1
        c.setPageSize(A4); width, height = A4
        y = paragraph('Giải thích — ' + item['title'], 35, height - 35, width - 70, 'heading') - 18
        for section in item['sections']:
            p = Paragraph(html.escape(section['body']), styles['body'])
            body_h = p.wrap(width - 70, 3000)[1]
            heading_p = Paragraph(html.escape(section['title']), styles['heading'])
            heading_h = heading_p.wrap(width - 70, 3000)[1]
            if y - heading_h - body_h - 20 < 45:
                footer(); c.showPage(); page += 1
                y = height - 35
            y = paragraph(section['title'], 35, y, width - 70, 'heading') - 6
            y = paragraph(section['body'], 35, y, width - 70) - 18
        footer(); c.showPage(); page += 1
    c.save()
    return page - 1


def main():
    data = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    graphs(data['models'])
    build_html(data['models'])
    build_markdown(data)
    pages = build_pdf(data)
    archive = ROOT / 'QTMNC_TrucQuan.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(ROOT.rglob('*')):
            if path.is_file() and path.suffix in {'.html', '.md', '.pdf', '.json', '.py', '.dot', '.png', '.svg'}:
                bundle.write(path, Path('QTMNC_TrucQuan') / path.relative_to(ROOT))
    print(f'Built {len(data["models"])} PNG/SVG diagrams, offline interactive HTML, Markdown, PDF ({pages} pages) and ZIP.')


if __name__ == '__main__':
    main()
