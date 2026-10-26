# Thiết kế dự án GNS3 Device Monitor

## Phạm vi theo đề tài

Windows chạy Python trong VS Code, định kỳ kiểm tra CPU, RAM, nhiệt độ và trạng
thái interface của Ubuntu VMware qua đường quản trị GNS3. Dữ liệu lấy bằng SSH,
SNMP hoặc kết hợp; sự kiện đổi trạng thái được gửi tới Telegram/Slack.
Mỗi tiến trình theo dõi một thiết bị. VPCS chỉ tạo máy kiểm tra kết nối, không có
SSH/SNMP agent và không cung cấp CPU/RAM/nhiệt độ cho chương trình.

Profile GNS3 đặt chu kỳ 5 giây. Đây là **gần thời gian thực bằng polling**:
độ trễ phụ thuộc chu kỳ, thời gian lấy mẫu CPU khoảng 1 giây, timeout mạng và
API nhắn tin. Không bảo đảm cảnh báo tức thời hoặc có thời hạn cứng.

## Phân chia mã

| Thành phần | Trách nhiệm |
|---|---|
| device_monitor/config.py | Kiểm tra cấu hình, profile, credential, timeout |
| collectors/ssh.py | SSH xác minh host key; đọc Linux hoặc PowerShell Windows |
| collectors/snmp.py | SNMPv2c/v3; linux-extend hoặc OID riêng theo thiết bị |
| collectors/hybrid.py | Chọn nguồn ưu tiên/dự phòng; theo dõi từng dịch vụ |
| probe.py | Đọc CPU/RAM/cảm biến Linux, xuất JSON cho agent Net-SNMP |
| engine.py | Máy trạng thái, ngưỡng, hysteresis, UNKNOWN |
| storage.py | Giao dịch SQLite lưu trạng thái và outbox |
| notifications.py | Gửi Telegram/Slack, xác nhận API, backoff/retry |
| ui.py | Bảng Rich có nguồn đo, trạng thái, ngưỡng, hàng đợi |
| app.py | CLI, vòng lấy mẫu theo lịch và luồng gửi |
| lab/linux | Netplan theo MAC, cài agent riêng, tạo tải kiểm thử có hạn |
| tools/create_gns3_project.py | Sinh topology GNS3 và kiểm tra mapping local API |

monitor_ssh.py và terminal_ui.py là điểm vào tương thích với phiên bản cũ.
Chạy mới: python -m device_monitor --env-file .env.gns3.

## Thu thập đúng ý nghĩa chỉ số

CPU Linux dùng chênh lệch hai lần đọc /proc/stat; loại guest time khỏi phép cộng
kép. RAM dùng MemTotal và MemAvailable, có fallback khi kernel thiếu trường.
Lỗi đọc từng chỉ số trả None + lý do; không suy diễn rằng thiết bị đã mất mạng.

SSH dùng RejectPolicy và known_hosts. Không tự thêm khóa chưa xác minh.
Linux chỉ cần tài khoản đọc được /proc và /sys; monitor không cần đăng nhập root.

SNMP linux-extend đọc JSON từ Net-SNMP extend qtmnc cho CPU/RAM/nhiệt độ.
Interface lấy độc lập từ **IF-MIB**: tìm ifIndex bằng ifName rồi đọc ifOperStatus.
Kiểm tra lại tên của index đã cache; tên không còn khớp thì tìm lại.
Agent lab là service riêng, read-only, bind một IP và cho phép một source IP.

Chế độ custom dùng SNMP_CPU_OID, SNMP_RAM_OID hoặc USED/TOTAL, SNMP_TEMP_OID
và SNMP_IFACE_OID do người quản trị đối chiếu MIB. Không có một bộ OID CPU/nhiệt
độ chung cho mọi router/switch. CPU phải là phần trăm, không phải load average.

Hybrid thu cả hai giao thức: ưu tiên SSH cho CPU/RAM/nhiệt độ, SNMP cho interface;
nếu giá trị ưu tiên không đọc được thì dùng giá trị hợp lệ của nguồn còn lại.
Dashboard và cảnh báo dịch vụ vẫn phản ánh mất SSH hoặc SNMP dù đã có dự phòng.
Hai nguồn lấy tuần tự nên không phải cùng một thời điểm tuyệt đối.

## Nhiệt độ và tính trung thực dữ liệu

TEMP_SOURCE=auto chỉ đọc cảm biến phù hợp từ hwmon/thermal của Linux.
MONITOR_TEMP_PATH có thể chỉ file cảm biến CPU đã xác minh dưới /sys.
Không có cảm biến → UNKNOWN, không trả 0°C. VM thường không có cảm biến vật lý.
MONITOR_TEMP_ENABLED=false chủ động bỏ chỉ số khỏi đánh giá.

TEMP_SOURCE=demo đọc file có thời hạn; số đo, tin cảnh báo và phục hồi đều ghi
MÔ PHỎNG. Trong SNMP/hybrid phải cấu hình nguồn demo cả agent Linux và monitor
Windows. Không dùng demo để kết luận đo được nhiệt độ CPU vật lý của host.

## Trạng thái và thông báo

| Chỉ số | Cảnh báo | Phục hồi với margin=5 |
|---|---|---|
| CPU | >75% | <=70% |
| RAM | >65% | <=60% |
| Nhiệt độ | >65°C | <=60°C |
| Interface | down/lowerlayerdown/notpresent | up |
| Dịch vụ hybrid | down | up |

unknown/testing/dormant hoặc thiếu dữ liệu là UNKNOWN. Với chỉ số số học,
last_known giữ trạng thái trước khi mất dữ liệu để áp dụng đúng hysteresis
khi đo được lại. Chỉ gửi khi có chuyển trạng thái cần báo; không lặp mỗi chu kỳ,
không nhắc định kỳ khi lỗi kéo dài. Chạy bình thường lần đầu không tự gửi tin TEST.

Trạng thái + tin mới được lưu cùng transaction SQLite. Luồng gửi riêng lấy tin
cũ nhất đến hạn của mỗi kênh, duyệt kênh tuần tự. Telegram lỗi không xóa tin Slack.
HTTP 429 dùng retry-after; lỗi khác tăng thời gian chờ 2, 4, ... tối đa 300 giây.
Telegram cần HTTP thành công và ok=true; Slack cần nội dung ok.
Giữ kiểm tra TLS, không theo redirect và không đưa URL secret vào log.

Tin chưa gửi tồn tại qua restart. Giao thức gửi **at least once**: dịch vụ có thể
đã nhận nhưng phản hồi mất, nên retry có khả năng tạo tin trùng.
401/403 hoặc webhook bị thu hồi cần sửa cấu hình; tin vẫn được giữ chờ.

SQLite chứa states và outbox, không lưu toàn bộ lịch sử CPU/RAM theo thời gian,
không phải cơ sở dữ liệu biểu đồ lịch sử. Chạy một tiến trình trên mỗi state file.
Đổi đích Slack có thể gửi tin Slack tồn tới webhook mới; kiểm tra trước khi đổi.

## Bảo vệ cấu hình và giới hạn lab

.env.gns3, .env, .venv và .monitor_state bị Git bỏ qua. Không đưa token,
community, mật khẩu, private key vào source, ảnh báo cáo hoặc project GNS3.
SNMPv2c chỉ dùng lab tách biệt; SNMPv3 authPriv cần cấu hình user đúng trên agent.
Không mở cổng SSH/SNMP tới Internet để làm demo.

Windows, GNS3 và VM cùng nằm trên một máy vật lý: host ngủ/tắt có thể dừng toàn
bộ hệ thống. Nếu mục tiêu phát hiện host vật lý tắt, cần máy giám sát độc lập.
Ngắt đường quản trị chỉ chứng minh không tới được thiết bị; muốn biết cổng thử
nghiệm DOWN cần đường quản trị còn hoạt động.
