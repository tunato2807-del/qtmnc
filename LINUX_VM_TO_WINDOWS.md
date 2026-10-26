# Máy ảo Linux giám sát máy thật Windows qua VMware NAT

> Đây là mô hình tham khảo chiều ngược lại. Dự án chính hiện là Windows/VS Code
> → GNS3 → Linux VMware: xem [GNS3_LAB.md](docs/GNS3_LAB.md).

Mô hình: **Linux VM chạy Python → SSH tới Windows → đọc chỉ số bằng PowerShell**.
Chính Linux VM gửi thông báo tới Telegram/Slack qua Internet.

Theo ipconfig của bạn:

| IP Windows | Vai trò |
|---|---|
| 192.168.73.1 | VMnet8: dùng làm đích SSH khi máy ảo chọn NAT |
| 192.168.10.1 | VMnet1: dùng cho mạng Host-only, không phải hướng dẫn NAT này |
| 192.168.1.227 | Wi-Fi Windows |
| 26.94.94.11 | Radmin VPN, không dùng cho mô hình này |

MONITOR_HOST là **192.168.73.1**, không phải IP Linux. IP Linux có thể là
192.168.73.129 như trước, nhưng phải kiểm tra lại.

## 1. Kiểm tra mạng VMware

Trong VMware: VM → Settings → Network Adapter → chọn **NAT**, bật Connected
và Connect at power on. Nếu VMware yêu cầu, tắt VM bình thường trước khi chỉnh.

Trên Terminal **Linux**:

~~~bash
ip -br addr
ip route
~~~

Cần IPv4 192.168.73.x/24 nếu VMnet8 vẫn dùng subnet đã cung cấp. Nếu subnet khác,
kiểm tra Virtual Network Editor và IP VMnet8 hiện tại, không tự gán IP trùng.
NAT giúp VM truy cập GitHub và Telegram qua Internet.

## 2. Bật SSH trên Windows

Chạy trong **Windows PowerShell → Run as administrator**, không dán trực tiếp
vào cửa sổ CMD C:\Users\DELL>.

~~~powershell
Get-WindowsCapability -Online -Name OpenSSH.Server*
~~~

Nếu State chưa là Installed:

~~~powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
~~~

Sau đó:

~~~powershell
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
Get-Service sshd
Get-NetTCPConnection -State Listen -LocalPort 22
~~~

Dịch vụ phải Running và có cổng 22 lắng nghe. Lỗi tải capability cần kiểm tra
Windows Update/Internet của Windows; không cài thành phần này trong Linux.

Cho phép SSH từ mạng NAT tới adapter VMnet8:

~~~powershell
if (-not (Get-NetFirewallRule -Name "DeviceMonitor-SSH-VMnet8" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "DeviceMonitor-SSH-VMnet8" -DisplayName "Device monitor SSH from VMware NAT" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 -LocalAddress 192.168.73.1 -RemoteAddress 192.168.73.0/24 -Profile Any
}
~~~

Không cần tắt Windows Firewall.

## 3. Xác định tài khoản, adapter và fingerprint Windows

Vẫn trên **Windows PowerShell**:

~~~powershell
whoami
$env:USERNAME
Get-NetAdapter | Select-Object Name,Status,InterfaceDescription
& "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -lf "$env:ProgramData\ssh\ssh_host_ed25519_key.pub"
~~~

Nếu USERNAME là DELL thì dùng DELL trong các ví dụ sau. C:\Users\DELL không tự
chứng minh tên đăng nhập SSH là DELL; thay bằng tài khoản thực tế nếu khác.
Dùng **mật khẩu Windows**, không dùng PIN Windows Hello. Với domain/Microsoft
account, cần kiểm tra chính xác tên đăng nhập SSH trước.

Chọn MONITOR_IFACE='Wi-Fi' để giám sát Wi-Fi vật lý hoặc
'VMware Network Adapter VMnet8' để giám sát adapter NAT ảo. Tên phải khớp
Get-NetAdapter, không phải ens33 của Linux.

Giữ fingerprint ED25519 để so sánh khi SSH. Host key Windows nằm trong
C:\ProgramData\ssh, không phải /etc/ssh.

## 4. Cài công cụ và thử SSH từ Linux

Dùng Ubuntu 22.04/24.04 hoặc Debian có Python >=3.10:

~~~bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip openssh-client netcat-openbsd
python3 --version
nc -vz -w 5 192.168.73.1 22
ssh -o HostKeyAlgorithms=ssh-ed25519 DELL@192.168.73.1
~~~

Lần đầu, chỉ nhập yes khi fingerprint khớp với giá trị vừa lấy trực tiếp trên
Windows. Nhập mật khẩu Windows; ký tự mật khẩu không hiện là bình thường.
Khóa được lưu trong ~/.ssh/known_hosts để script xác minh các lần sau.

Trong phiên SSH Windows, thử:

~~~text
powershell.exe -NoProfile -Command "Get-NetAdapter | Select-Object Name,Status"
powershell.exe -NoProfile -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,TotalVisibleMemorySize,FreePhysicalMemory"
exit
~~~

exit đưa bạn trở lại Linux; làm các bước tiếp theo trên Linux.
Ping có thể bị chặn ICMP dù SSH hoạt động; ưu tiên kết quả nc và đăng nhập SSH.

## 5. Tải mã GitHub trên Linux

Trong Terminal Linux, không phải phiên SSH Windows:

~~~bash
cd ~
git clone https://github.com/tunato2807-del/qtmnc.git
cd qtmnc
git log -1 --oneline
~~~

Nếu đã clone:

~~~bash
cd ~/qtmnc
git status --short
git pull --ff-only origin main
~~~

Nếu Git báo sửa đổi chưa lưu, không reset/xóa file. Với kho riêng tư, dùng quy
trình đăng nhập GitHub của bạn; không đưa token vào URL clone hoặc chat.
Git proxy của môi trường cloud không tự có trên máy ảo riêng của bạn.

## 6. Cài dependency và cấu hình

Trên Linux, trong ~/qtmnc:

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp examples/windows-vm.env .env
chmod 600 .env
nano .env
~~~

Nếu .env đã có thông tin riêng thì chỉ chỉnh file cũ, không dùng cp ghi đè.
Trong nano: Ctrl+O, Enter để lưu; Ctrl+X để thoát.

Các giá trị chính:

~~~bash
MONITOR_PROTOCOL=ssh
MONITOR_OS=windows
MONITOR_HOST=192.168.73.1
SSH_PORT=22
SSH_USER='DELL'
SSH_PASSWORD='DIEN_MAT_KHAU_WINDOWS'
SSH_KNOWN_HOSTS=~/.ssh/known_hosts
MONITOR_IFACE='Wi-Fi'
MONITOR_TEMP_ENABLED=false
TELEGRAM_TOKEN='DIEN_TOKEN_BOT_MOI'
TELEGRAM_CHAT_ID='DIEN_CHAT_ID'
~~~

Điền các giá trị DIEN_... thực tế vào .env. Nếu dùng key, để SSH_PASSWORD=''
và điền SSH_KEY_FILE. Các credential trong file gốc đã được chia sẻ cần đổi mới.
File .env tự được đọc bằng dotenv, không chạy shell hoặc nội suy biến. Có thể
dùng bộ cấu hình để ghi đúng secret chứa ký tự đặc biệt. Không cần source file.

Nhiệt độ tạm tắt rõ ràng vì Windows không có API CPU temperature thống nhất.
Muốn bật, cần LibreHardwareMonitor WMI và phần cứng hỗ trợ, xem README.
Không coi việc bỏ qua nhiệt độ là đo được 0°C.

Slack: điền SLACK_WEBHOOK_URL. Chỉ dùng Slack thì để trống cả hai biến Telegram;
có thể điền cả hai kênh để nhận song song.

## 7. Nạp cấu hình và chạy

Trong cùng Terminal Linux:

~~~bash
cd ~/qtmnc
.venv/bin/python monitor_ssh.py --check-config
.venv/bin/python monitor_ssh.py --once
~~~

--check-config không kết nối/gửi tin; --once mới đọc dữ liệu thật. Mong đợi:
cpu/ram là phần trăm, iface=up nếu Wi-Fi đang hoạt động, không có temp vì đã tắt.

Bắt đầu bình thường không tự gửi tin thử. Chỉ tạo tin khi vượt ngưỡng, thiếu
dữ liệu, mất kết nối hoặc phục hồi. Không có tin khi mọi chỉ số OK là bình thường,
chưa chứng minh bot gửi tin được.

Giám sát liên tục:

~~~bash
.venv/bin/python monitor_ssh.py
~~~

Ctrl+C dừng; chu kỳ mặc định 30 giây. Sau khi sửa .env, khởi động lại chương trình
để đọc cấu hình mới. Terminal mới không cần khai báo lại các biến trong file.

## 8. Thử cảnh báo có kiểm soát

Sau khi --once đọc đúng chỉ số, nhắn /start cho bot hoặc thêm bot vào nhóm
đúng quyền. Hạ ngưỡng RAM chỉ cho một lần chạy với state riêng để thử tin thật
mà không gây quá tải Windows:

~~~bash
DEMO_STATE="$PWD/.monitor_state/demo-$(date +%s).sqlite3"
MONITOR_STATE_FILE="$DEMO_STATE" RAM_THRESHOLD=0 RECOVERY_MARGIN=0 \
    .venv/bin/python monitor_ssh.py --once
~~~

RAM Windows đang hoạt động >0% nên state mới sẽ tạo cảnh báo. Đây là demo
ngưỡng hạ thấp, không phải kết luận máy quá tải. File .env không bị sửa.
Nếu gửi lỗi, tin thử còn trong DEMO_STATE; sau khi sửa mạng/token, chạy lại
lệnh có MONITOR_STATE_FILE="$DEMO_STATE" để gửi tiếp từ đúng hàng đợi đó.
Lệnh giám sát thông thường vẫn dùng ngưỡng thật và state mặc định.

## 9. Chẩn đoán

| Biểu hiện | Kiểm tra |
|---|---|
| nc timeout | Đúng NAT/subnet/IP VMnet8, firewall Windows |
| Connection refused | Dịch vụ sshd, cổng 22 lắng nghe |
| Permission denied | Username, mật khẩu thật thay vì PIN, quyền SSH; thử đăng nhập thủ công trước |
| Host key lỗi | Xác minh fingerprint trên Windows trước khi cập nhật known_hosts |
| Không thấy MONITOR_OS | git pull nhánh main mới nhất và chỉnh đúng cấu hình |
| CPU/RAM/JSON UNKNOWN | Chạy lệnh PowerShell thủ công trong SSH; kiểm tra quyền CIM/performance counters |
| Interface UNKNOWN | Get-NetAdapter, đúng tên Windows và MONITOR_OS=windows |
| Telegram 401/403 | Token, bot bị chặn hoặc quyền chat |
| Không có tin khi OK | Bình thường; dùng bước thử ngưỡng riêng |
| Linux không có Internet | Windows Wi-Fi, VMware NAT và mạng của VM |

## 10. Giới hạn

- Test tự động có fixture cho Windows và SSH/SNMP cục bộ, chưa chạy trên chính
  Windows của bạn. Chỉ các bước thực tế trên mới xác nhận hệ thống của bạn.
- VM nằm trên Windows: Windows tắt/sleep hoặc VMware dừng có thể làm VM dừng,
  nên không gửi được cảnh báo. Muốn phát hiện host tắt cần máy giám sát độc lập.
- Wi-Fi Windows tắt có thể làm VM mất Internet; tin sẽ chờ trong SQLite.
  Giữ adapter quản trị VMnet8 hoạt động khi thử Wi-Fi.
- Đây là polling gần thời gian thực, không phải sự kiện tức thì; nhiệt độ chưa
  được kiểm chứng nếu bạn tắt thu thập.
