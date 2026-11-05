# Phạm vi xác minh bản viết lại

Ngày: 05/11/2026. Môi trường phát triển: Linux, Python3.12; không có VMware Workstation Windows hoặc hai clone của người dùng tại đây.

| Hạng mục | Cách kiểm tra | Kết quả |
|---|---|---|
| Logic, DB, web, lab generator | `python -m unittest discover -v` | 50 test đạt |
| SSH | Server Paramiko loopback; pin key,2lệnh,1transport | Đạt; không phải xác thực máy Ubuntu của người dùng |
| SNMP | SNMPv2c GET qua UDP loopback, OID extend và JSON | Đạt; chưa chạy Net-SNMP trên clone thật |
| HTTP | Server loopback200/503/chậm, timeout và chuyển trạng thái | Đạt; chưa thử web trên SRV1 thật |
| ICMP/iperf3 | Parse bộ đếm, lệnh .NET Ping, iperf3 JSON, xử lý lỗi | Đạt phần mềm; chưa đo trên Windows/hai clone |
| GNS3 file | JSON Schema revision9 + VMware properties2.2.61 | Đạt cấu trúc; chưa boot VM bằng GNS3 |
| Trình duyệt | Chromium desktop1440px/mobile390px, thẻ ICMP/HTTP, tải CSV/HTML, render HTML độc lập | Kiểm tra bằng dữ liệu mô phỏng; xem ảnh demo |
| Provision Ubuntu | Xem/kiểm tra kế hoạch netplan, vai trò và bảng nftables | Không áp dụng lên mạng máy phát triển; cần nghiệm thu trên clone |
| PowerShell/VMware | Script và hướng dẫn trong repo | Cần chạy trên Windows; không tuyên bố đã chạy ở đây |
| Telegram/Slack thật | Test HTTP được giả lập | Chưa gửi tin thật; cần token và nghiệm thu cục bộ |
| Hiệu năng/độ trễ | Có quy trình đo A/B và t0/t1/t2 | Chưa có kết quả thực nghiệm trên máy người dùng |

Ảnh dashboard ghi MÔ PHỎNG, không phải số đo thật. `docs/acceptance.csv` để CHUA_CHAY cho các bước trên máy Windows/GNS3. Không thay số liệu còn thiếu bằng kết quả tự tạo.

Bổ sung từ Buổi 5: HTTP 200/503/chậm đã kiểm tra qua loopback; phân tích ICMP mất gói một phần và JSON .NET Ping kiểm tra bằng dữ liệu có kiểm soát, chưa chạy PowerShell thực trên Windows. iperf3 mới kiểm tra lệnh/parser và xử lý lỗi, chưa có số đo throughput giữa hai VM. Sơ đồ NETWATCH_XEM_NGAY.gns3 đạt schema/XML/SVG, chưa mở GUI GNS3 tại môi trường phát triển. Báo cáo HTML tải từ dashboard và render nội dung tĩnh trên Chromium; policy môi trường chặn file:// nên không tuyên bố đã điều hướng mở file cục bộ bằng browser ở đây.
