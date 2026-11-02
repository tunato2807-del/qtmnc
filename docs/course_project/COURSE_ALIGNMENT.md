# Đối chiếu nội dung môn học

Đã phân tích 7 tài liệu người dùng cung cấp, tổng cộng **265 trang PDF**. Số
trang dưới đây là trang trong file PDF, không phải số slide in ở chân trang.
Tài liệu là nguồn kiến thức; các bài tập trong tài liệu không tự động trở thành
yêu cầu bắt buộc của đồ án. Người dùng xác nhận VPN/SDN **không bắt buộc**.

| Mã | Nguồn / số trang | Phần áp dụng vào đồ án | Giới hạn cần ghi rõ |
|---|---|---|---|
| TL1 | Chương 1 – Quản trị mạng nâng cao, 39 trang; tr.13–15, 20–22, 27 | Tự động hóa Python, quản trị tập trung, chỉ số tài nguyên, trực quan hóa, Git/kiểm thử | Chưa đo throughput, jitter, packet loss tự động |
| TL2 | Chương 2 – Phân tích các mô hình mạng, 28 trang; tr.5–6, 9–10 | FCAPS; NMS tập trung; hai vùng Ethernet lớp 2; phân biệt switch/router | Hai switch GNS3 không phải OpenFlow switch; không triển khai controller SDN |
| TL3 | Chương 3 – An ninh mạng không dây, 33 trang; tr.23, 31 | Tham khảo nguyên tắc phân đoạn và quản trị mã hóa, bảo vệ thông tin truy cập | Lab hữu tuyến không mô phỏng sóng Wi-Fi, WPA3, EAP hoặc WIPS |
| TL4 | Chương 4 – Tự động hóa quản trị hệ thống SDN bằng Python, 33 trang; tr.3, 6–8, 14, 28, 32–33 | Paramiko, JSON, xử lý ngoại lệ, phân quyền API, kiểm thử và xác nhận trạng thái | API dashboard là API ứng dụng giám sát, không phải Northbound API của SDN controller |
| TL5 | VPN VS CLOUD, 67 trang; tr.4, 15–18, 21, 55 | Quy hoạch IP không trùng, hiểu quản trị từ xa và phương án VPN khi mở rộng | Chưa tạo VPN, AWS VPC/Azure VNet; Cloud GNS3 chỉ nối adapter |
| TL6 | Chương 5 – Quản lý hiệu suất hoạt động, 38 trang; tr.2, 4–8, 11, 17–20, 23–26, 28–31 | Thu thập–lưu trữ–phân tích–dashboard; metrics/events; cảnh báo theo chuyển trạng thái; lịch sử CSV | Polling gần thời gian thực; tỷ lệ thành công theo lượt không phải SLA theo thời gian; chưa có distributed tracing |
| TL7 | Chương 6 – Quản lý bảo mật, 27 trang; tr.6–9, 16, 18–19, 27 | SSH host key, secret cục bộ, API chỉ đọc localhost, nhật ký sự kiện, kiểm thử/khôi phục | Không tự động khóa tài khoản/chặn IP; không tuyên bố đã triển khai SIEM/IDS/IPS |

## Những luận điểm đưa vào báo cáo

- FCAPS: trọng tâm F/P, hỗ trợ C/S; chưa thực hiện kế toán tài nguyên/tính cước A.
- Metrics và Events được lưu bền trong SQLite; log vận hành có ở Terminal.
  Chưa có trace phân tán và chưa thu syslog tập trung từ router.
- Giảm alert lặp bằng chuyển trạng thái và hysteresis, không dùng AI/ML.
- Phân biệt interface thử nghiệm DOWN, mất SSH và mất Internet gửi tin.
- Thực nghiệm tắt/bật monitor trước đây là bằng chứng chi phí lấy mẫu; cập nhật
  dùng lại SSH và batch probes giảm số thao tác, chưa thay thế đo sau sửa.
- Báo cáo chỉ được điền “Đạt” khi có bằng chứng lab thực tế; ảnh dashboard
  dựng từ chế độ demo phải giữ nhãn MÔ PHỎNG.
