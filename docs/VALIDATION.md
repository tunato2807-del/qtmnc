# Phạm vi xác minh bản viết lại

Ngày: 04/11/2026. Môi trường phát triển: Linux, Python3.12; không có VMware Workstation Windows hoặc hai clone của người dùng tại đây.

| Hạng mục | Cách kiểm tra | Kết quả |
|---|---|---|
| Logic, DB, web, lab generator | `python -m unittest discover -v` | 26test đạt |
| SSH | Server Paramiko loopback; pin key,2lệnh,1transport | Đạt; không phải xác thực máy Ubuntu của người dùng |
| SNMP | SNMPv2c GET qua UDP loopback, OID extend và JSON | Đạt; chưa chạy Net-SNMP trên clone thật |
| GNS3 file | JSON Schema revision9 + VMware properties2.2.61 | Đạt cấu trúc; chưa boot VM bằng GNS3 |
| Trình duyệt | Chromium desktop1440px/mobile390px, chọn thiết bị, tải CSV | Kiểm tra bằng dữ liệu mô phỏng; xem ảnh demo |
| Provision Ubuntu | Xem/kiểm tra kế hoạch netplan, vai trò và bảng nftables | Không áp dụng lên mạng máy phát triển; cần nghiệm thu trên clone |
| PowerShell/VMware | Script và hướng dẫn trong repo | Cần chạy trên Windows; không tuyên bố đã chạy ở đây |
| Telegram/Slack thật | Test HTTP được giả lập | Chưa gửi tin thật; cần token và nghiệm thu cục bộ |
| Hiệu năng/độ trễ | Có quy trình đo A/B và t0/t1/t2 | Chưa có kết quả thực nghiệm trên máy người dùng |

Ảnh dashboard ghi MÔ PHỎNG, không phải số đo thật. `docs/acceptance.csv` để CHUA_CHAY cho các bước trên máy Windows/GNS3. Không thay số liệu còn thiếu bằng kết quả tự tạo.
