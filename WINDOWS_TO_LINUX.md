# Windows / VS Code giám sát máy ảo Linux

> Tài liệu đường NAT trực tiếp của bản trước. Với dự án GNS3 mới, làm theo
> [GNS3_LAB.md](docs/GNS3_LAB.md). setup_windows.cmd và run_windows.cmd hiện dùng
> .env.simple. Để dùng profile cũ, chạy python setup_project.py --profile classic
> rồi python monitor_ssh.py --env-file .env.

Máy Windows chạy Python, thu thập CPU/RAM/interface từ Linux qua SSH rồi gửi
Telegram/Slack. Preset theo mạng hiện tại: Linux 192.168.73.129, user tuanto,
interface ens33. Nhiệt độ VM được bỏ qua rõ ràng vì thường không có cảm biến.

## 1. Chuẩn bị một lần trên Linux VM

Trong Terminal Linux:

~~~bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
ip -br addr
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
~~~

Xác nhận Linux vẫn là 192.168.73.129. Giữ fingerprint SHA256 từ console Linux
để đối chiếu khi bộ cài hỏi. Không lấy fingerprint từ một nguồn chưa tin cậy.

## 2. Tải và cài từ Terminal VS Code trên Windows

Máy Windows cần Git và Python 3.10+:
- Python: https://www.python.org/downloads/windows/
- Git: https://git-scm.com/downloads/win

Cài xong thì mở lại VS Code để Terminal nhận PATH mới. Kiểm tra:

~~~powershell
git --version
py --version
~~~

Trong VS Code: Terminal → New Terminal → chọn **PowerShell**. Chạy lệnh sau
tại thư mục bạn muốn chứa dự án, nơi chưa có thư mục qtmnc:

~~~powershell
git clone https://github.com/tunato2807-del/qtmnc.git; if ($LASTEXITCODE -eq 0) { Set-Location qtmnc; .\setup_windows.cmd; if ($LASTEXITCODE -eq 0) { code . } }
~~~

Lệnh tải toàn bộ dự án, tạo .venv, cài thư viện, chạy bộ nhập cấu hình và mở
thư mục dự án trong VS Code khi thiết lập thành công. Nếu lệnh code chưa có
trong PATH, dùng File → Open Folder → chọn thư mục qtmnc vừa tải.

Nếu GitHub yêu cầu xác thực do kho riêng tư, dùng quy trình đăng nhập GitHub
của bạn; không đưa token vào URL clone hoặc chat.

Nếu đã có thư mục qtmnc, không clone đè. Chạy trong thư mục đó:

~~~powershell
git pull --ff-only origin main
if ($LASTEXITCODE -eq 0) { .\setup_windows.cmd }
~~~

Nếu có sửa đổi cục bộ khiến pull thất bại, giữ lại file và xử lý thay đổi;
không reset hoặc xóa cấu hình để ép cập nhật.

## 3. Trả lời bộ cấu hình

Nhấn Enter để giữ các giá trị mặc định phù hợp:

| Trường | Giá trị |
|---|---|
| Hệ điều hành máy đích | linux |
| IP/hostname | 192.168.73.129 |
| Cổng SSH | 22 |
| Tài khoản SSH | tuanto |
| Interface | ens33 |
| Giám sát nhiệt độ | false |
| Xác thực | password, hoặc chọn key/agent nếu đã cấu hình |
| Kênh cảnh báo | telegram, slack hoặc both |

Nhập mật khẩu **tài khoản Linux tuanto**, token Telegram mới và chat ID.
Mật khẩu/token không hiện ký tự trong Terminal là bình thường. Chỉ nhập trên
máy của bạn; bộ cài không lấy lại credential đã lộ trong file ban đầu.

Nếu chọn key, nhập đường dẫn private key và passphrase nếu có. Nếu chọn agent,
cần SSH agent/key mặc định đã được cấu hình từ trước.

Khi chưa có host key, bộ cài hiển thị loại key và fingerprint. Lấy fingerprint
đúng loại trực tiếp trên Linux rồi dán nguyên chuỗi SHA256:... để xác nhận:
- ED25519: /etc/ssh/ssh_host_ed25519_key.pub
- RSA: /etc/ssh/ssh_host_rsa_key.pub
- ECDSA: /etc/ssh/ssh_host_ecdsa_key.pub

Lệnh kiểm tra mẫu là ssh-keygen -lf FILE_PUBLIC_KEY. Nếu khác nhau hoặc bạn chưa
xác minh, dừng để kiểm tra. Khóa đã lưu mà thay đổi sẽ bị từ chối, không tự chấp nhận.

Bộ cài lưu .env tại máy bạn và kiểm tra SSH. File này chứa secret dạng văn bản,
được .gitignore bỏ qua, không được commit và không nên chia sẻ/copy lên GitHub.
Cài lại giữ file có sẵn; secret cũ được giữ khi bạn chọn chỉnh cấu hình và nhấn
Enter ở ô secret.

## 4. Chạy những lần sau

Trong Terminal VS Code, mở đúng thư mục dự án:

~~~powershell
.\run_windows.cmd
~~~

Bản mới dùng bảng màu cập nhật tại chỗ: CPU/RAM làm tròn, thanh sử dụng, ngưỡng
và trạng thái cảnh báo, thời gian kiểm tra tiếp theo; Telegram/Slack có số tin
đang chờ và thời điểm gửi thành công. Mở rộng khung Terminal nếu bảng bị chật.
Khi mất SSH, số đo cũ được ghi rõ, không hiển thị như dữ liệu mới.

Chọn bảng in từng chu kỳ hoặc log gọn:

~~~powershell
.\run_windows.cmd --display table
.\run_windows.cmd --display log
~~~

Sau khi cập nhật mã, cài dependency mới một lần:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Để dùng Ctrl+C mà không gặp câu hỏi Terminate batch job của CMD, chạy Python
trực tiếp trong PowerShell hoặc dùng F5:

~~~powershell
.\.venv\Scripts\python.exe monitor_ssh.py --env-file .env
~~~

Thu thập một lần:

~~~powershell
.\run_windows.cmd --once
~~~

Chỉ kiểm tra cấu hình/dependency, không kết nối/gửi tin:

~~~powershell
.\run_windows.cmd --check-config
~~~

Hoặc cài extension Python/Debugger được VS Code đề xuất, nhấn F5 và chọn
Windows -> Linux: monitor. Không cần kích hoạt venv thủ công hoặc đổi
Execution Policy của PowerShell.

Cấu hình được tự đọc từ .env. Các launcher chọn rõ file này, nên cấu hình đã
lưu được ưu tiên hơn các biến cũ bạn từng gõ trong Terminal. Tắt/mở Terminal
không yêu cầu nhập lại mật khẩu/token. Sau khi sửa .env cần khởi động lại script.

Bộ cài chỉ kiểm tra SSH và cấu hình, không tự gửi tin Telegram/Slack. Cần
nhắn /start cho bot và kiểm chứng nhận tin khi tạo cảnh báo. Nếu mọi chỉ số
bình thường, chương trình không tự phát tin thử.

## 5. Chỉnh cấu hình hoặc cập nhật

~~~powershell
.\setup_windows.cmd --configure
~~~

Dùng khi IP Linux đổi hoặc cần thay username, mật khẩu, token, interface.
Hoặc chỉnh .env trực tiếp trong VS Code. Đừng chỉnh .env.example để ghi secret.

Cập nhật mã và dependency:

~~~powershell
git pull --ff-only origin main
if ($LASTEXITCODE -eq 0) { .\setup_windows.cmd }
~~~

Nếu chỉ muốn chuẩn bị file và chưa kiểm tra SSH, có tùy chọn
--skip-ssh-check. Kết quả đó không chứng minh đã kết nối được; phải chạy
setup bình thường sau khi máy Linux sẵn sàng.

## 6. Chẩn đoán

| Vấn đề | Cách kiểm tra |
|---|---|
| git/py không được nhận diện | Cài Git/Python, mở lại toàn bộ VS Code |
| nc/SSH timeout | Windows: Test-NetConnection 192.168.73.129 -Port 22; Linux: dịch vụ ssh, NAT và firewall |
| Đăng nhập thất bại | Mật khẩu Linux tuanto; không phải mật khẩu/PIN Windows |
| Fingerprint không khớp | Xác minh đúng loại khóa từ console Linux; không tự bỏ kiểm tra |
| .venv không hợp lệ | Kiểm tra thư mục, không tự xóa file riêng trong đó |
| Không thấy log | Chạy launcher trong Terminal VS Code và đọc lỗi |
| Không có Telegram khi chỉ số OK | Bình thường; kiểm chứng bằng ngưỡng demo có kiểm soát |
| Nhiệt độ không hiển thị | Đang đặt false vì VM không cung cấp cảm biến |
| CMD wrapper không chạy trên Linux | Các file .cmd dành cho Windows; Linux dùng .venv/bin/python |

Các kiểm thử tự động chạy phần Python và SSH/SNMP loopback; CMD/VS Code cần
được kiểm chứng trên Windows thật của bạn. Không có kết nối tới VM của bạn
hoặc gửi tin Telegram/Slack thật trong kiểm thử.
