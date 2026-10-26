# Giám sát thiết bị qua SSH/SNMP, cảnh báo Telegram/Slack

Bản sửa của `monitor_ssh.py`, dùng Python 3.10 trở lên. Mỗi tiến trình giám sát
một thiết bị, bằng **SSH hoặc SNMP**, và gửi cảnh báo qua **Telegram, Slack hoặc
cả hai**. Máy chạy script cần truy cập mạng được tới thiết bị và HTTPS tới các
dịch vụ nhắn tin. Thiết bị đích SSH có thể là Linux (`MONITOR_OS=linux`, mặc định)
hoặc Windows 10/11 có OpenSSH Server và Windows PowerShell 5.1 (`MONITOR_OS=windows`).

**[Bắt đầu trên Windows/VS Code: giám sát Linux VM, tải và cài bằng một lệnh](WINDOWS_TO_LINUX.md)**

Chiều ngược lại: [Linux VM giám sát Windows qua VMware NAT](LINUX_VM_TO_WINDOWS.md).

**[Bộ 8 mô hình và sơ đồ dùng cho báo cáo: Word, PDF, PNG, SVG, Mermaid](docs/diagrams/README.md)**

## Các lỗi đã sửa

- CPU Linux lấy chênh lệch hai mẫu `/proc/stat` cách nhau một giây; không phụ thuộc
  định dạng/ngôn ngữ `top`, không tính trùng guest time.
- RAM ưu tiên `MemAvailable`, có cách tính dự phòng cho Linux cũ.
- Cảm biến thiếu/lỗi trả về `UNKNOWN`, không giả thành 0°C hoặc báo phục hồi sai.
  Tự tìm cảm biến CPU phổ biến, hoặc đọc đường dẫn do bạn cấu hình.
- Interface phân biệt `up`, các trạng thái mất kết nối và `unknown/testing/dormant`.
- Lỗi đọc/phân tích dữ liệu từng chỉ số không bị báo thành mất kết nối SSH.
- SSH luôn được đóng trong `finally`, có timeout, xác minh host key bằng
  `RejectPolicy`; hỗ trợ SSH key, ssh-agent và mật khẩu qua biến môi trường.
- Cảnh báo và trạng thái được lưu cùng giao dịch SQLite. Gửi lỗi vẫn còn trong
  hàng đợi, thử lại POST với thời gian chờ tăng dần, tối đa 300 giây giữa các lần
  thử; HTTP 429 tuân theo thời gian chờ máy chủ yêu cầu nếu dài hơn.
- Xác nhận thành công ở mức API (`ok=true` của Telegram, `ok` của Slack), giữ TLS
  verification, không tự đi theo redirect và không in URL chứa token vào log.
- Luồng gửi tin tách khỏi vòng thu thập; hàng đợi mỗi kênh độc lập. Telegram lỗi
  không làm mất tin Slack. Dữ liệu và hàng đợi tồn tại sau khi khởi động lại.
- Gửi văn bản thuần để tránh lỗi Markdown; không lưu token/mật khẩu trong mã.
- Có vùng phục hồi (hysteresis) để tránh bật/tắt cảnh báo liên tục quanh ngưỡng.
- Bổ sung SNMPv3 authPriv (SHA-1/AES-128) và tùy chọn SNMPv2c; Slack Incoming Webhook.

## 1. Cài đặt

Trong thư mục dự án, trên Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

Để dùng SNMP, thay lệnh cài bằng:

```bash
.venv/bin/python -m pip install -r requirements-snmp.txt
```

Windows/VS Code: chạy `setup_windows.cmd` để tạo venv, cài dependency, nhập và
lưu cấu hình, xác minh host key và kiểm tra SSH. Sau đó chạy `run_windows.cmd`
hoặc nhấn F5 với cấu hình Windows đã cung cấp. Cài lại giữ cấu hình cũ;
`setup_windows.cmd --configure` cho phép chỉnh lại.

Chương trình tự đọc `.env` cạnh script, không thực thi shell hay nội suy biến
trong file. Với `.env` mặc định, biến môi trường đang có được ưu tiên.
Chọn rõ `--env-file <path>` thì giá trị trong file được ưu tiên, phù hợp khi
chạy profile đã lưu. File `.env` chứa secret cục bộ và được Git bỏ qua.

Các phiên bản dependency đã kiểm thử được ghi trong `requirements-tested.txt`.
File này gồm cả SNMP; dùng nó thay requirements khác nếu cần tái lập đúng phiên bản.

## 2. Cấu hình SSH + Telegram

Sửa `.env` bằng trình soạn thảo, không ghi secret vào mã nguồn:

| Biến | Ý nghĩa |
|---|---|
| `MONITOR_HOST` | IP/hostname thiết bị được giám sát |
| `MONITOR_OS` | Hệ điều hành thiết bị đích: `linux` hoặc `windows` |
| `SSH_USER` | Tài khoản có quyền đọc các chỉ số; không cần root |
| `SSH_KEY_FILE` | Đường dẫn private key, nếu dùng key; bỏ trống để dùng ssh-agent/key mặc định |
| `SSH_PASSWORD` | Chỉ điền nếu dùng mật khẩu |
| `SSH_KNOWN_HOSTS` | File known_hosts chứa host key thiết bị đã được xác minh |
| `MONITOR_IFACE` | Tên interface trên thiết bị: `ip link` (Linux), `Get-NetAdapter` (Windows) |
| `TELEGRAM_TOKEN` | Token bot mới do BotFather cấp |
| `TELEGRAM_CHAT_ID` | Chat nhận tin; cần nhắn `/start` cho bot hoặc thêm bot vào nhóm phù hợp |

**Token Telegram và mật khẩu trong file gốc đã được chia sẻ. Hãy thu hồi/cấp lại
token và đổi mật khẩu trước khi sử dụng. Bản sửa không sử dụng các giá trị cũ.**

### Xác minh host key

Lấy fingerprint từ console máy Linux hoặc quản trị viên qua kênh tin cậy,
ví dụ chạy trên console thiết bị:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Từ máy chạy script, kết nối SSH thủ công tới đúng host/cổng, đối chiếu fingerprint
hiển thị với giá trị tin cậy rồi mới chấp nhận. Khóa sẽ được ghi vào known_hosts.
Cổng khác 22 dùng mục `[host]:port`. Nếu key thay đổi, xác minh nguyên nhân và
khóa mới trước khi cập nhật; script không tự chấp nhận khóa lạ.

### Nhiệt độ trong máy ảo

Máy ảo thường không cung cấp cảm biến nhiệt độ. Mặc định sẽ cảnh báo thiếu dữ
liệu một lần, không giả thành nhiệt độ bình thường. Nếu đã xác nhận không hỗ trợ,
đặt `MONITOR_TEMP_ENABLED=false`; chỉ số này sẽ được bỏ qua và cần ghi rõ trong
báo cáo demo. Có cảm biến riêng thì đặt `MONITOR_TEMP_PATH` tới file millidegree
bên dưới `/sys/`, ví dụ một file `temp*_input` đã xác minh đúng là cảm biến CPU.

### Nhiệt độ Windows

Đặt `MONITOR_OS=windows`. CPU/RAM/interface được lấy bằng PowerShell qua SSH.
Nếu bật nhiệt độ, bộ thu thập truy vấn WMI `root/LibreHardwareMonitor`, chỉ chọn
cảm biến thuộc phần cứng loại CPU. Cần tự cài và chạy LibreHardwareMonitor với
WMI provider hoạt động, đủ quyền truy vấn và phần cứng được hỗ trợ. Thiếu provider
hoặc cảm biến sẽ là `UNKNOWN`; không thay bằng nhiệt độ ACPI không xác định.
`MONITOR_TEMP_PATH` chỉ dành cho Linux. Có thể bắt đầu với
`MONITOR_TEMP_ENABLED=false` và ghi rõ chưa giám sát nhiệt độ trong demo.

## 3. Slack và SNMP

### Slack

Tạo Incoming Webhook trong workspace của bạn, đặt `SLACK_WEBHOOK_URL` trong
`.env`. Bỏ trống cặp biến Telegram nếu chỉ dùng Slack, hoặc điền cả hai kênh để
nhận song song. Webhook phải dùng HTTPS trên `hooks.slack.com` hoặc
`hooks.slack-gov.com`. Không chia sẻ webhook.

### SNMP

Đặt `MONITOR_PROTOCOL=snmp`. Mặc định dùng SNMPv3 **authPriv** với
`SNMP_USER`, `SNMP_AUTH_KEY`, `SNMP_PRIV_KEY`; thiết bị phải cấu hình khớp
SHA-1 authentication và AES-128 privacy. Không tự hạ cấp giao thức.

Nếu thiết bị lab chỉ hỗ trợ v2c, chọn rõ `SNMP_VERSION=2c` và điền
`SNMP_COMMUNITY` read-only. SNMPv2c không mã hóa, chỉ nên dùng trên mạng tin cậy.
SNMP cần UDP tới `SNMP_PORT` (mặc định 161); môi trường chỉ cho HTTPS proxy có
thể không hỗ trợ đường mạng này.

**OID phụ thuộc hãng, model và SNMP agent; không có một bộ OID đúng cho mọi thiết bị.**
Tra MIB/tài liệu thiết bị và kiểm tra đầu ra trước khi điền:

| Biến | Dữ liệu yêu cầu |
|---|---|
| `SNMP_CPU_OID` | Mức sử dụng CPU tổng thể, phần trăm 0–100; không phải load average |
| `SNMP_RAM_OID` | RAM sử dụng, phần trăm 0–100 |
| `SNMP_RAM_USED_OID` + `SNMP_RAM_TOTAL_OID` | Thay thế RAM %, hai giá trị cùng đơn vị; tính `used/total*100` |
| `SNMP_TEMP_OID` | Giá trị cảm biến CPU; nhân với `SNMP_TEMP_SCALE` để ra °C |
| `SNMP_IFACE_OID` | `IF-MIB::ifOperStatus.<ifIndex>` dạng số: `1.3.6.1.2.1.2.2.1.8.<ifIndex>` |

Nếu thiết bị chỉ có tải theo từng core hoặc OID idle/load-average, cần bổ sung
cách tổng hợp/chuyển đổi đúng theo MIB; không gán trực tiếp vào OID CPU phần trăm.
Không dùng `ens33` làm ifIndex: phải tra index SNMP của đúng cổng. Trong chế độ
SNMP, `MONITOR_IFACE` chỉ là nhãn hiển thị; OID xác định cổng thực sự được đọc.
Nhiệt độ chưa có OID là `UNKNOWN`, hoặc tắt rõ ràng bằng cấu hình trên.

## 4. Chạy

Mặc định Terminal tương tác hiển thị bảng cập nhật tại chỗ: CPU/RAM làm tròn
một chữ số, thanh sử dụng, ngưỡng, trạng thái, lịch kiểm tra và hàng đợi từng kênh.
Ẩn log kết nối/xác thực Paramiko lặp lại. Nếu mất kết nối, số đo trước đó được
đánh dấu dữ liệu cũ; trạng thái bảng dùng cùng hysteresis với cảnh báo thực tế.
Nhiệt độ chủ động bỏ qua hiển thị `ĐÃ TẮT`, không hiển thị 0°C.

`--display table` in bảng mới mỗi chu kỳ; `--display log` dùng các dòng log gọn.
Khi chuyển hướng đầu ra vào file, chế độ tự động dùng bảng tĩnh, không có mã
điều khiển con trỏ. Mục gửi thành công chỉ ghi nhận các lần đã được API xác nhận
trong phiên hiện tại; số tin chờ đọc từ SQLite, bao gồm tin còn từ phiên trước.

Từ thư mục dự án trên Linux, sau khi điền `.env`:

```bash
.venv/bin/python monitor_ssh.py --check-config
.venv/bin/python monitor_ssh.py --once
.venv/bin/python monitor_ssh.py
```

- `--check-config`: kiểm tra cấu hình, dependency và sự tồn tại file key/known_hosts;
  không kết nối thiết bị hay gửi tin, không xác nhận credential thực sự dùng được.
- `--env-file <path>`: chọn profile dotenv cụ thể và ưu tiên giá trị trong file.
- `--display auto|table|log`: chọn bảng cập nhật tại chỗ (mặc định khi có TTY),
  bảng tĩnh hoặc log gọn; `--once` luôn dùng bảng tĩnh trừ khi chọn log.
- `--once`: đo một lần, thử gửi thông báo cũ nhất đang đến hạn của mỗi kênh. Mã
  thoát 0 khi dữ liệu hợp lệ và không còn tin tồn ở các kênh đang cấu hình; 1 khi
  mất kết nối, thiếu dữ liệu hoặc còn tin chưa gửi; 2 khi lỗi cấu hình/nội bộ.
- Chạy liên tục: đo ngay khi khởi động, sau đó theo chu kỳ bắt đầu mỗi 30 giây
  mặc định. Nếu tác vụ quá lâu sẽ ghi log và bỏ qua lịch trễ, không tạo vòng lặp
  dồn dập. Ctrl+C dừng chương trình; tin chưa gửi vẫn nằm trên đĩa.
- Bắt đầu bình thường không tự gửi tin thử. Cảnh báo phát khi vượt ngưỡng, mất
  dữ liệu/kết nối, interface lỗi hoặc khi phục hồi. Khi demo, tạo tải có kiểm soát
  hoặc hạ ngưỡng trong lab để kiểm chứng nhận tin thực tế.

## 5. Quy tắc cảnh báo và giới hạn

- Ngưỡng mặc định: CPU >75%, RAM >65%, nhiệt độ >65°C. Với
  `RECOVERY_MARGIN=5`, CPU chỉ phục hồi khi <=70%, RAM <=60%, nhiệt độ <=60°C.
- `UNKNOWN` không phải bình thường. Nếu mất cảm biến trong lúc đang nóng, chỉ
  thông báo thiếu dữ liệu; khi dữ liệu trở lại mới đánh giá ngưỡng phục hồi.
- Interface `down/lowerlayerdown/notpresent` là cảnh báo; `unknown/testing/dormant`
  là chưa xác định khả năng hoạt động. Các trường hợp đặc thù như interface ảo
  `unknown` cần được giải thích theo thiết bị, không kết luận cổng vật lý bị đứt.
- Nếu chính interface dùng để SSH/SNMP bị ngắt, chỉ có thể xác định mất đường
  giám sát. Muốn xác định chính xác trạng thái cổng đó cần đường quản trị độc lập.
- Đây là **cảnh báo gần thời gian thực bằng polling**, không phải sự kiện tức thời.
  Độ trễ phụ thuộc chu kỳ, thời gian thu thập, mạng và retry. Retry Telegram/Slack
  không chặn thu thập, nhưng các lần gửi của hai kênh vẫn được xử lý tuần tự.
- Chỉ thông báo khi đổi trạng thái; không có nhắc lại định kỳ khi lỗi kéo dài.
- Hàng đợi giữ thứ tự từng kênh. Lỗi vĩnh viễn (401/403, bot bị chặn, webhook bị
  thu hồi) cần sửa cấu hình; hệ thống vẫn giữ tin, nên theo dõi log và dung lượng đĩa.
- Mô hình gửi là **at least once**: nếu dịch vụ đã nhận tin nhưng phản hồi bị mất,
  hoặc chương trình dừng trước khi ghi nhận gửi thành công, lần thử lại có thể tạo
  tin trùng. Không tuyên bố đảm bảo exactly-once với Telegram/Slack.
- Chạy một tiến trình trên mỗi state file. Muốn nhiều thiết bị, dùng mỗi tiến
  trình một `.env` và `MONITOR_STATE_FILE` riêng. Không chạy hai bản cùng state.
- State mặc định là `.monitor_state/state.sqlite3`, không chứa credential nhưng
  có IP/chỉ số/lịch sử tin chưa gửi: giữ riêng tư và không commit. Đổi token bot
  vẫn giữ hàng đợi cùng chat; đổi chat tạo hàng đợi mới. Có một đích Slack mỗi state
  file: đổi webhook thì tin Slack tồn sẽ gửi tới webhook mới. Kênh bị tắt giữ tin
  trên đĩa và gửi tiếp khi bật lại. Xóa state sẽ xóa cả lịch sử chống lặp và tin tồn.

## 6. Kiểm thử

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

Các kiểm thử dùng fixture, mock và dịch vụ loopback cục bộ, không liên hệ máy
của bạn hoặc Telegram/Slack thật. Kiểm tra gửi lại sau lỗi/restart, thứ tự tin,
tách kênh, HTTP 429, dữ liệu thiếu, CPU/RAM, hysteresis, lỗi SSH và SNMP.
Kiểm thử tích hợp tùy chọn cần các dependency trong requirements-snmp.txt.
Việc nhận tin thực tế và OID trên thiết bị của bạn cần được xác minh sau khi
bạn điền cấu hình; bộ kiểm thử không thay thế bước đó.
