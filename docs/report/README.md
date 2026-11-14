# Báo cáo đồ án NetWatch 2026–2027

Bản báo cáo mới, tổng hợp ngày 15/11/2026:

- [Bản Word chỉnh sửa được](Bao_cao_NetWatch_2026_2027.docx)
- [Nguồn Markdown](Bao_cao_NetWatch_2026_2027.md)
- [Kết quả kiểm tra và phạm vi xác minh](validation_report.txt)

Báo cáo theo bố cục ba chương của hai tài liệu hướng dẫn người dùng cung cấp. Khổ A4, lề trên/dưới/phải 2 cm, lề trái 3 cm; thân bài Times New Roman 13, giãn dòng 1,5; tiêu đề 16, tiêu đề đề tài trên bìa 18. Trang được đánh số từ Mở đầu. Bìa/bìa lót, tên trong header/footer, chữ ký, nhận xét và lịch làm việc chưa có thông tin được để trống hoặc làm biểu mẫu. Sinh viên cần đọc lại và ký lời cam đoan trước khi nộp.

## Kết quả được cập nhật

Mô hình gồm R1 Linux, SRV1 Linux, hai switch và hai VPCS. Windows chạy dashboard; R1 quản trị tại `192.168.73.10`, SRV1 tại `10.10.10.10`. Báo cáo ghi nhận hai máy đã được giám sát với chu kỳ 15 giây, Telegram đã nhận cảnh báo CPU và phục hồi. HTTP SRV1 chưa bật. Kết quả lab được phân biệt với 50 kiểm thử phần mềm chạy trên Linux và với các khả năng chưa nghiệm thu như Slack/SNMP trên clone thật.

## Tình trạng ảnh nghiệm thu

Năm ảnh hiển thị trong tin nhắn đã được đọc để chép số liệu và đối chiếu sự kiện. **Không có tệp PNG/JPG gốc có thể truy cập trong workspace**, và người dùng xác nhận không có đường dẫn hoặc URL tải ảnh. Do đó chưa thể nhúng năm ảnh chụp gốc vào Word/GitHub.

Thư mục [assets](assets) chứa sơ đồ logic và hai hình tổng hợp số liệu đã đọc từ ảnh. Các hình này ghi rõ nguồn và ghi rõ **không phải ảnh chụp màn hình gốc**. Chúng không được xem là bản sao ảnh nghiệm thu. Bảng đối chiếu năm ảnh nằm trong Phụ lục 3 của báo cáo. Khi có tệp ảnh gốc, có thể bổ sung và thay/cập nhật chú thích tương ứng.

## Dựng lại Word

Yêu cầu Python 3.12, `python-docx` và `Pillow`. Không cần chạy lại bộ sinh tài liệu cũ vì nó còn sinh PowerPoint và dùng thể thức khác.

```bash
python docs/report/build_netwatch_report.py
```

Lệnh đọc Markdown, tạo lại bốn hình PNG và dựng Word. Các đường dẫn được tính theo vị trí script, không phụ thuộc thư mục đang đứng. Nội dung ứng dụng, tests và dependency declarations không bị thay đổi.

Word chứa trường mục lục, danh mục hình/bảng và trường số trang. `report_pages.json` lưu số trang đã đối chiếu với lần render hiện tại để tài liệu có mục lục đọc được ngay. Sau khi sửa nội dung, đổi font hoặc chèn ảnh gốc, mở Word và chọn **Ctrl+A → F9 → Update entire table** để cập nhật các trường. Nếu Word hỏi cập nhật các trường khi mở, cho phép cập nhật. Phân trang có thể khác đôi chút giữa Word và bộ render do font thực tế trên máy.

Để kiểm tra bố cục với LibreOffice:

```bash
soffice --headless --convert-to pdf --outdir /tmp/netwatch-report-render docs/report/Bao_cao_NetWatch_2026_2027.docx
```

PDF dùng trong kiểm tra là bản render nội bộ; sản phẩm chính ở đây là Word và Markdown. Bản render đã được kiểm tra trang bìa, mục lục, header/footer, các hình, bảng và số trang. Thông tin chi tiết nằm trong `validation_report.txt`.

Các tệp `Bao_cao_NetWatch.*`, `tuna.md` và HTML demo có trước được giữ nguyên để tham khảo. Đặc biệt, nhận định cũ trong `tuna.md` về Telegram chưa nhận thành công không phản ánh bộ ảnh nghiệm thu mới; dùng bản `Bao_cao_NetWatch_2026_2027` cho kết quả cập nhật.
