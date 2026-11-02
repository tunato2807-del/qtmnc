# Hồ sơ đồ án môn học

[Tải trọn bộ hồ sơ và sơ đồ dạng ZIP](QTMNC_Course_Report.zip).

- [Báo cáo Word chỉnh sửa được](Bao_cao_do_an_QTMNC.docx).
- [Bản PDF để xem/in](Bao_cao_do_an_QTMNC.pdf).
- [Nội dung báo cáo Markdown](Bao_cao_do_an_QTMNC.md).
- [Hướng dẫn từng bước Windows–VMware–GNS3](../COURSE_LAB.md).
- [Project GNS3 7 node](../../lab/gns3/QTMNC_COURSE.gns3).
- [Đối chiếu cả 7 tài liệu môn học](COURSE_ALIGNMENT.md).
- [Ảnh dashboard desktop](figures/dashboard-demo-desktop.png) và [mobile](figures/dashboard-demo-mobile.png): đều là dữ liệu **MÔ PHỎNG**, không dùng làm kết quả nghiệm thu thật.

Mô hình giữ SSH qua GNS3 đã dùng, thêm vùng thử nghiệm riêng và hai VPCS. Một
Ubuntu VM dùng 3 card: ens33 NAT, ens37 quản trị, gns3test thử nghiệm. Dashboard
web chạy trên Windows tại http://127.0.0.1:8765, đọc SQLite của monitor.

VPN/SDN là hướng mở rộng theo tài liệu, không phải phần bắt buộc hay phần đã
triển khai. Báo cáo có bảng nghiệm thu cần điền kết quả và chèn ảnh thiết bị thật
trước khi nộp; các kết quả kiểm thử mã được tách khỏi kết quả lab Windows.

## Dựng lại báo cáo

Chỉ cần cho người sửa bộ tài liệu, không phải dependency chạy monitor:

```bash
python -m pip install python-docx Pillow
python docs/course_project/build_report.py
```

Máy dựng cần Graphviz (`dot`) để xuất sơ đồ. Tệp SVG/DOT là nguồn chỉnh sửa sơ
đồ; Word chứa hình PNG để mở ổn định. LibreOffice hoặc Word có thể xuất DOCX
thành PDF. Không đưa .env, SQLite thật hoặc tài liệu bài giảng gốc vào Git.
