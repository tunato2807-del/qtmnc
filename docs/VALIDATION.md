# Kiểm chứng bản GNS3

Kết quả trong môi trường phát triển Linux ngày 26/10/2026:

| Kiểm tra | Kết quả |
|---|---|
| Python unittest discover | 119 tests, OK |
| Bản đơn giản | Wizard giữ secret cục bộ, lab 3 node, runner SSH, retry khi gửi lỗi; chạy được khi chặn import SNMP |
| pip check | Không có dependency hỏng |
| SSH loopback | Thu thập thật, từ chối khóa lạ/khóa thay đổi, chấp nhận fingerprint đúng |
| SNMPv2c/v3 loopback | GET/GETNEXT thật, JSON extend, tìm ifIndex và DOWN → UP |
| Probe Linux đã sao chép như khi cài agent | Chạy Python cô lập không site-packages, JSON hợp lệ, CPU/RAM trong 0–100 |
| File topology | Hợp lệ theo schema chính thức GNS3, revision 9 |
| Cầu nối TAP/UDP | Truyền frame hai chiều qua UDP localhost thật, giữ nguyên byte Ethernet, từ chối peer sai và frame thiếu header |
| API TAP Windows | Giả lập registry, mở handle, overlapped I/O, hủy I/O và bật trạng thái cáp; chưa chạy driver Windows thật |
| Project QTMNC_TAP | Hợp lệ theo schema project và schema cổng UDP Cloud; cả hai link qua Switch1 |
| Mermaid | Cả 8 sơ đồ phân tích cú pháp hợp lệ |
| Báo cáo | Dựng lại 8 PNG/SVG, PDF 10 trang và Word |

Schema tham chiếu từ kho GNS3/gns3-server, commit
9c6a0c7be42629fd0c72fab1e3376c34f7dd1681, file docs/gns3_file.json.
Các kết nối loopback cần môi trường kiểm thử cho phép tạo socket cục bộ.

Chưa chạy GUI Windows/GNS3/Npcap/VMware hoặc cài snmpd bằng root trên máy người
dùng. Agent SNMP trong kiểm thử giao thức dùng PySNMP trên loopback; đây không
phải bằng chứng service Net-SNMP đã chạy trên Ubuntu của bạn.
Không gửi Telegram/Slack thật từ bộ test. Hoàn thành [TEST_PLAN.md](TEST_PLAN.md)
để xác nhận toàn bộ lab và nhận tin trên tài khoản thực tế.

Riêng trường hợp Windows không nhận SYN-ACK qua loopback, làm theo
[WINDOWS_TAP_GNS3.md](../WINDOWS_TAP_GNS3.md). Cần kiểm tra SSH thành công trên
Windows và mất kết nối khi tháo dây switch GNS3 trước khi xác nhận cách này đã
khắc phục lỗi trên máy thật.
