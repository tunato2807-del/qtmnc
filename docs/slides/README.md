# Bộ slide thuyết trình QTMNC

- [PowerPoint 22 slide](QTMNC_Executive_Thuyet_trinh.pptx): định dạng 16:9, chữ, sơ đồ và thẻ thông tin là các phần tử PowerPoint có thể chỉnh sửa.
- [Dàn ý chi tiết 22 slide](QTMNC_Dan_y_22_slide.md): thông điệp, luận điểm, minh chứng, gợi ý trực quan và nguồn cho từng slide.
- [Mã dựng bộ slide](build_presentation.py): dữ liệu nội dung và bố cục; dùng để tái tạo PPTX và dàn ý.

## Nội dung và phạm vi

Bộ slide mô tả Windows chạy Python trong VS Code, kết nối Ubuntu VMware qua đường mạng GNS3, thu thập CPU/RAM/nhiệt độ/interface và gửi cảnh báo Telegram/Slack. Bản đơn giản đang dùng SSH; SNMP/hybrid được trình bày là phương án mở rộng. Kết quả tự động trên mock/loopback được tách rõ khỏi nghiệm thu trên agent và dịch vụ thật.

TAP chỉ xuất hiện ở phần mô hình mạng hiện tại như công cụ nối Windows vào lab GNS3; đây không phải chức năng đo lường của hệ thống giám sát.

## Sửa và dựng lại

Mở `QTMNC_Executive_Thuyet_trinh.pptx` trong Microsoft PowerPoint hoặc LibreOffice Impress. Các tiêu đề, chữ, thẻ, đường nối, sơ đồ và biểu đồ được tạo bằng shape/text của PowerPoint.

Để dựng lại từ mã nguồn, cài `python-pptx`, sau đó chạy từ thư mục gốc dự án:

```bash
python -m pip install python-pptx
python docs/slides/build_presentation.py
```
