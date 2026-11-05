# Liên hệ bảy tài liệu môn học với thiết kế mới

Nguồn do người dùng tải lên: **7 PDF, tổng 265 trang**; danh mục và SHA-256 tại [sources.json](sources.json). Số trang dưới đây là **thứ tự trang PDF**, không phải số in trên slide bài giảng. Không phát hành lại các PDF gốc trong repository.

| Tài liệu | Trang PDF liên quan | Đưa vào đồ án | Giới hạn phải nói rõ |
|---|---|---|---|
| Chương 1 — Quản trị mạng nâng cao | 20–22, 27 | Chỉ số tài nguyên/lưu lượng, SNMP, dashboard, phân đoạn và quy trình quản lý cấu hình | Không triển khai NetFlow, HA hoặc tuyên bố đạt Zero Trust |
| Chương 2 — Phân tích các mô hình mạng | 5–6, 9–10 | FCAPS: Fault/Performance là trọng tâm; quản trị tập trung; phân biệt switch L2 với router L3 | Không có OpenFlow controller; R1 là router Linux truyền thống |
| Chương 3 — An ninh mạng không dây | 23, 31 | Vận dụng nguyên tắc phân đoạn Users/Servers và quản trị qua SSH | Không có AP/WLAN/SSID thật; SNMPv2c chỉ là tùy chọn lab, tài liệu khuyến nghị SNMPv3 cho vận hành bảo mật |
| Chương 4 — Tự động hóa SDN bằng Python | 3, 6, 8, 28, 32–33 | JSON, xử lý lỗi, Paramiko, chu trình giám sát–phát hiện–cảnh báo–xác minh phục hồi, test tự động | Không đẩy flow rule; không tự chữa lỗi hay ngắt thiết bị tự động |
| VPN VS CLOUD | 55 | Quy hoạch CIDR không trùng và hiểu vai trò NAT trong lab VMware | Không triển khai VPN hoặc kết nối cloud; đây không phải yêu cầu bắt buộc của đề tài |
| Chương 5 — Quản lý hiệu suất hoạt động | 2–8, 17–20, 23–26, 28–29 | Thu thập/lưu trữ/phân tích/trực quan; chọn chu kỳ; tránh bão cảnh báo; đo độ trễ và tác động giám sát | Lưu lượng Mbps không phải khả năng băng thông tối đa; chưa có phép đo SLA theo thời gian |
| Chương 6 — Quản lý bảo mật | 16, 18–19, 27 | Kiểm tra cấu hình, nhật ký sự kiện, tài khoản không sudo, host key, secret cục bộ, backup/rollback | Không triển khai SIEM/SOAR/EDR hoặc đáp ứng sự cố bảo mật toàn diện |

Đồ án lấy **giám sát CPU/RAM/nhiệt độ/interface và gửi cảnh báo** làm bài toán chính. Router, mạng hai nhánh, ACL, dashboard và lịch sử cung cấp bối cảnh triển khai/kiểm chứng; không đổi đề tài thành triển khai VPN/SDN.

Nguồn bổ sung: **Bài tập thực hành buổi 5.docx** — áp dụng Lab1/2/3/4/6/10 vào CSV, RTT/mất gói, iperf3, HTTP, bắt gói và báo cáo HTML/PDF. Xem [đối chiếu chi tiết cả 10 lab](05_BUOI_5.md). Không tuyên bố đã triển khai các Lab7/8/9 về phát hiện tấn công và tự chặn IP.
