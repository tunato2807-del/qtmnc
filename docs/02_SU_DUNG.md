# Cấu hình và sử dụng hệ thống giám sát

Làm sau [hướng dẫn GNS3](01_GNS3.md): R1 và SRV1 đã có probe; Windows TCP22 tới cả hai đều thành công.

## 1. Mở đúng dự án trong VS Code

**Windows → VS Code → File → Open Folder** → chọn `D:\QTM_NC\telegram\qtmnc`. Mở **Terminal → New Terminal**. Không gõ lệnh `sudo` ở đây; sudo chỉ dành cho console Ubuntu.

```powershell
.\setup.cmd
```

Đây là môi trường mới `.venv-netwatch`, khác `.venv` cũ. Các file `.cmd` dùng đường dẫn Python rõ ràng nên không cần Activate.ps1 hay đổi ExecutionPolicy để khởi chạy Python.

## 2. Kiểm tra inventory

Trong Explorer VS Code mở **inventory.json**. Mặc định:

- Chu kỳ `15` giây/thiết bị, timeout `12` giây.
- CPU cảnh báo `>75%`, RAM `>65%`; nhiệt độ ngưỡng `>65°C` nếu bật.
- Hysteresis `5`: CPU đã vượt 75% chỉ phục hồi khi xuống `≤70%`.
- `monitor_temperature=false`: hợp lý với VMware thường không cung cấp cảm biến nhiệt.
- R1 host `.73.10`, interfaces `mgmt0`, `srv0`, `users0`; SRV1 host `10.10.10.10`, interface `lan0`.

Không dùng `192.168.10.129` của mô hình trước. Nếu đổi IP, phải sửa netplan, route Windows, hướng dẫn lab và inventory đồng nhất. Lưu file bằng **Ctrl+S**; khởi động lại ứng dụng sau khi sửa cấu hình.

## 3. Nhập tài khoản và kênh cảnh báo

**PowerShell Windows:**

```powershell
.\configure.cmd
```

- SSH user: **monitor** đã tạo trên từng clone.
- Mật khẩu: nhập mật khẩu của `monitor` trên đúng clone; có thể khác mật khẩu `tuanto`.
- Chọn kênh `1` Telegram, `2` Slack, `3` cả hai; `0` chỉ dashboard.
- Nội dung nhập kín; Enter giữ secret cũ. Script ghi `.env.netwatch`, không in secret.

**Telegram:** mở Telegram → tìm **BotFather** → `/newbot` → nhận token → vào bot mới bấm **Start**. Nhập token và chat ID riêng của bạn vào trình cấu hình. Nếu đã có bot hoạt động, tiếp tục dùng thông tin cục bộ đó; không gửi token lên chat/Git. Muốn tìm chat ID, có thể dùng API `getUpdates` từ máy bạn sau khi gửi một tin tới bot; không chụp URL có token đưa vào báo cáo.

**Slack:** trong workspace có quyền cài app, tạo app → bật **Incoming Webhooks** → **Add New Webhook to Workspace** → chọn channel → Copy Webhook URL. Nhập URL vào `configure.cmd`. Script này không tự tạo workspace/app hoặc xin quyền thay bạn.

Các secret chỉ đọc khi khởi động. Thêm/bớt kênh cần restart ứng dụng. Không bật debug logging HTTP vì URL Telegram/Slack chứa secret. Quyền truy cập file trên Windows vẫn phụ thuộc tài khoản và ACL thư mục của bạn.

## 4. Xác minh danh tính SSH một lần

**Console Ubuntu R1**, rồi SRV1:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Giữ console để đối chiếu. **PowerShell Windows:**

```powershell
.\start.cmd trust
```

Với từng thiết bị, dán phần **SHA256:...** lấy trực tiếp từ đúng console. Có thể dán kèm comment cuối dòng; công cụ lấy token fingerprint đầu. Nếu không khớp sẽ từ chối và không lưu key. Không lấy fingerprint từ lỗi mạng rồi tự xác nhận lại chính giá trị đó. Host key lưu `.local/known_hosts`, không đưa lên Git. Khi thay clone/host key, xác minh lại bằng console.

## 5. Chạy thật và mở dashboard

**PowerShell Windows:**

```powershell
.\start.cmd
```

Mở trình duyệt tại **http://127.0.0.1:8765**. Giữ cửa sổ NetWatch và GNS3 đang chạy. Nếu dùng VS Code debug, chọn interpreter `.venv-netwatch\Scripts\python.exe`, chọn profile “NetWatch — lab thật”.

Phần bổ sung Buổi5 có thẻ RTT/mất gói và HTTP, biểu đồ RTT cùng nút báo cáo HTML. Xem [hướng dẫn Buổi5](05_BUOI_5.md) để bật web mẫu, CSV tự ghi và profile5s/CPU85%/RAM90%. ICMP không phản hồi không tự coi SSH mất kết nối.

Dashboard gồm:

| Vùng | Ý nghĩa |
|---|---|
| Tổng quan | Thiết bị có dữ liệu mới, số trạng thái cảnh báo, hàng đợi gửi, chu kỳ |
| Thẻ R1/SRV1 | CPU, RAM, nhiệt độ nếu đọc được; trạng thái cổng và lưu lượng Rx/Tx |
| Sơ đồ mạng | Sơ đồ thiết kế cố định, không tự phát hiện VPCS/switch |
| Lịch sử | Chọn thiết bị, xem 300 mẫu gần nhất, tải CSV tối đa 5.000 mẫu |
| Sự kiện | 100 thay đổi gần nhất: cảnh báo, thiếu dữ liệu và phục hồi |

Mẫu quá cũ bị đánh dấu và không tính là thiết bị đang kết nối. `—` nghĩa là chưa có số đo, không phải 0. Khi ứng dụng không chạy thu thập, có thể mở riêng `start.cmd --web-only` để đọc lịch sử; dữ liệu sẽ cũ dần.

## 6. Hiểu cách tính và phát cảnh báo

- **CPU:** đọc hai lần tổng `/proc/stat` cách nhau 1 giây; `100 × (Δtotal − Δidle)/Δtotal`, idle gồm idle+iowait. Không cộng đôi guest; thang toàn VM 0–100%.
- **RAM:** `100 × (MemTotal − MemAvailable)/MemTotal`, không lấy riêng MemFree để suy ra đã dùng.
- **Nhiệt độ:** đọc thermal sysfs; VMware không có sensor thì không giả lập nhiệt độ máy thật.
- **Interface:** đọc `operstate`; mất interface/không hiểu trạng thái là UNKNOWN; DOWN tạo cảnh báo riêng.
- **Lưu lượng:** `8 × Δbytes / Δthời_gian / 10^6` Mbps. Counter reset hoặc chưa có hai mẫu thì để trống.
- **Mất SSH/SNMP:** tạo một lỗi kết nối chung; không gửi thêm hàng loạt CPU/RAM=0. Probe lỗi trong phiên SSH còn sống thì chỉ số là UNKNOWN.
- **Phục hồi:** khi số đo có lại nhưng còn cao, báo “đã có dữ liệu, vẫn cảnh báo”; không gọi bình thường.

Một thiết bị có nhiều thay đổi cùng chu kỳ được gộp một tin/kênh. Trạng thái giữ qua lần restart. Lỗi gửi vẫn nằm SQLite, thử lại theo 2, 4, 8… tối đa 300 giây; nếu dịch vụ trả 429 thì tôn trọng thời gian chờ. Một tin có thể bị gửi trùng nếu dịch vụ đã nhận nhưng máy chưa kịp ghi trạng thái đã gửi; đây là cơ chế **at-least-once**, không cam kết đúng một lần.

“Real-time” trong đề tài là cảnh báo sau chu kỳ kiểm tra: chu kỳ 15s + thời gian lấy mẫu/SSH/API, không phải thời gian tức thời cứng. Khi mất Internet của Windows, việc lấy mẫu nội bộ có thể vẫn chạy nhưng tin nhắn phải chờ.

## 7. SNMP tùy chọn sau khi SSH đã chạy

Mặc định dùng SSH để lab dễ bắt đầu. Hỗ trợ SNMPv2c ở đây là **Net-SNMP extend của probe Python**, không phải OID CPU/nhiệt độ chung cho mọi hãng. SNMPv2c không mã hóa community: chỉ dùng mạng lab riêng; SNMPv3/SSH key là hướng mở rộng, chưa triển khai trong bản này.

**Console Ubuntu thiết bị cần chuyển SNMP**; nếu chưa cài snmpd:

```bash
sudo apt update
sudo apt install -y snmpd
```

Kiểm tra `sudo ss -lunp '( sport = :161 )'`. Nếu dịch vụ snmpd mặc định chiếm cổng, dừng riêng dịch vụ đó sau khi xác định nó chỉ vừa cài cho lab: `sudo systemctl disable --now snmpd`. Không tắt dịch vụ SNMP của hệ thống khác.

```bash
cd ~/netwatch-lab
sudo python3 lab/install_snmp.py
sudo python3 lab/install_snmp.py --apply
systemctl is-active netwatch-snmp
sudo ss -lunp '( sport = :161 )'
```

Nhập community riêng tối thiểu 16 ký tự; chỉ cho nguồn `192.168.73.1` đọc. Probe vẫn chạy với quyền Debian-snmp của daemon. Không công khai config có community.

**VS Code Windows:** đổi `"protocol": "ssh"` thành `"protocol": "snmp"` cho đúng thiết bị trong inventory, Ctrl+S → chạy `configure.cmd` nhập cùng community → restart `start.cmd`. Có thể R1 dùng SSH và SRV1 dùng SNMP, vẫn chung dashboard.

Extend `netwatch` dùng OID `1.3.6.1.4.1.8072.1.3.2.3.1.2.8.110.101.116.119.97.116.99.104`. UDP161 không kiểm tra bằng `Test-NetConnection -Port`, vì lệnh đó kiểm tra TCP. Dùng trạng thái collector/SNMP manager và bắt gói `udp.port == 161` để xác nhận.

## 8. Khi CPU vẫn cao

Tại **Ubuntu**, so sánh `vmstat 1 8` khi NetWatch dừng và chạy; bỏ dòng đầu vì đó là trung bình từ lúc boot. CPU bận ≈ `100 − id` (khác cách coi iowait khi máy có I/O lớn). Dùng `top -o %CPU` xác định tiến trình thật đang chiếm CPU. Không kết luận sai số chỉ vì một cửa sổ lấy mẫu khác cửa sổ khác.

Ứng dụng mới lấy một probe nhỏ mỗi 15s và giữ phiên SSH; không chạy lệnh dò OS lặp lại hay nhiều shell process cho từng chỉ số. Tắt tải thử/desktop dư thừa trên clone và kiểm tra CPU host Windows. Bản này chưa đo được phần trăm overhead trên VM thật của bạn, nên cần ghi số đo nghiệm thu thay vì khẳng định CPU sẽ luôn thấp.

## 9. Dừng và hoàn tác

Ctrl+C tại cửa sổ NetWatch. SQLite giữ lịch sử và hàng đợi. Dừng node trong GNS3 sau khi không còn cần lab. Muốn bỏ tuyến Windows dùng `tools/windows_routes.ps1 -Remove` như hướng dẫn phần mạng. Không xóa `.env.netwatch` hoặc database nếu muốn giữ thông tin cục bộ.
