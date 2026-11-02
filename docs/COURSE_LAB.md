# Lab đồ án: GNS3 và dashboard web

## 1. Mục tiêu và phạm vi

Windows chạy Python trong VS Code, SSH tới Ubuntu VMware qua GNS3, theo dõi
CPU/RAM/nhiệt độ/interface và gửi Telegram/Slack. Dashboard web đọc cùng SQLite
để hiển thị số đo, lịch sử và sự kiện. Nó không mở thêm SSH.

VPN/SDN không bắt buộc theo xác nhận của người dùng. Mô hình chính không cần
router image, GNS3 VM, controller Ryu hoặc máy ảo Ubuntu thứ hai.
SNMP/hybrid là nhánh mở rộng có sẵn, chưa được mặc định tuyên bố đã nghiệm thu.

## 2. Mô hình mới: 7 node

```text
Windows thật · VS Code / Python / Telegram/Slack / Dashboard localhost:8765
TAP Local Area Connection 192.168.10.1/24
        │ công cụ TAP/UDP: helper 30011 ↔ Cloud 30010
Cloud-WINDOWS ── SW-MANAGEMENT (access VLAN 10) ── Cloud-LINUX-MGMT
                                                          │ VMnet2
                                      Ubuntu ens37 · 192.168.10.129/24
                                      CPU / RAM / nhiệt độ của một VM
                                      Ubuntu gns3test · 192.168.30.129/24
                                                          │ VMnet3
                PC01 ── SW-LAB (access VLAN 30) ── Cloud-LINUX-LAB
                           │
                          PC02

Ubuntu ens33 · NAT/VMnet8 · DHCP: Internet/cài gói, không dùng làm IP SSH lab.
```

Hai Cloud phía Ubuntu biểu diễn hai card của **cùng một máy ảo**. Cloud GNS3 là
cầu nối tới adapter, không phải dịch vụ cloud AWS/Azure. Hai switch không nối
với nhau và không có router giữa hai subnet. VLAN 10/30 là port access riêng;
đây không phải bài trunk, định tuyến liên VLAN hoặc kiến trúc SDN.

| Thành phần | Địa chỉ / cổng | Vai trò |
|---|---|---|
| Windows TAP | 192.168.10.1/24 | IP nguồn SSH qua GNS3 |
| Host VMnet2 | Giữ 192.168.20.1/24 như lab trước | Không tạo đường host trực tiếp .10.129 |
| Ubuntu ens37 / VMnet2 | 192.168.10.129/24 | Quản trị SSH TCP/22 |
| Host VMnet3 | 192.168.30.1/24 | Adapter host-only cho vùng lab |
| Ubuntu gns3test / VMnet3 | 192.168.30.129/24 | Interface cần theo dõi |
| PC01 | 192.168.30.10/24 | Ping mạng thử |
| PC02 | 192.168.30.20/24 | Ping mạng thử |
| Ubuntu ens33 / VMnet8 | DHCP, đã từng .73.129 và .73.130 | NAT/Internet; không cố định theo ảnh cũ |
| Dashboard | http://127.0.0.1:8765 | Chỉ xem trên Windows hiện tại |

VPCS không cung cấp CPU/RAM hoặc SSH/SNMP agent. Số liệu dashboard thuộc Ubuntu.

## 3. Lấy bản mới trên Windows

Ctrl+C ở cửa sổ bảng giám sát, giữ cầu nối đang chạy. Trong Terminal VS Code:

```powershell
cd D:\QTM_NC\telegram\qtmnc
git fetch origin
git merge --ff-only origin/main
```

Nếu Git báo có thay đổi cục bộ, giữ lại và xử lý trước khi merge.
File .env.simple và secret cũ không bị ghi đè.

## 4. Thêm card thử nghiệm trong VMware

1. Tắt Ubuntu bằng Shut Down trong hệ điều hành, chờ máy tắt hẳn.
2. VMware → Edit → Virtual Network Editor → Change Settings.
3. Add Network → VMnet3 → Host-only; Subnet IP `192.168.30.0`, mask `255.255.255.0`.
4. Bật Connect a host virtual adapter; tắt DHCP cho VMnet3 vì lab dùng IP tĩnh.
5. Giữ cấu hình VMnet2 và VMnet8 đang dùng. VMnet2 host .20.1 và ens37 guest
   .10.129 là hai địa chỉ thuộc hai vai trò khác nhau; đường Ethernet .10.x được
   nối qua switch GNS3 và TAP, không dùng DHCP VMnet2.
6. Chọn Ubuntu → Edit virtual machine settings → Add → Network Adapter → Finish.
7. Chọn card mới → Custom: VMnet3 → bật Connected / Connect at power on.
8. Card thứ nhất vẫn NAT; card ens37 hiện tại vẫn Custom VMnet2.
9. Mở Ubuntu, chạy trong Terminal **Ubuntu**:

   ```bash
   ip -br link
   ip -br addr
   ```

   Ghi MAC card mới (thường tên ens38 nhưng phải đọc kết quả thực tế).

## 5. Gán IP cho card mới, giữ nguyên ens33/ens37

Mở cấu hình mới trên console VMware:

```bash
sudo nano /etc/netplan/99-qtmnc-lab.yaml
```

Nhập nội dung sau, thay MAC ví dụ bằng **MAC card mới nối VMnet3**:

```yaml
network:
  version: 2
  ethernets:
    qtmnc_lab:
      renderer: networkd
      match:
        macaddress: "00:0c:29:aa:bb:cc"
      set-name: gns3test
      dhcp4: false
      dhcp6: false
      addresses: [192.168.30.129/24]
      optional: true
```

Ctrl+O → Enter → Ctrl+X. Đây là file bổ sung riêng, không chép đè file .99 cũ
đang cấu hình ens33/ens37. Không thêm gateway vào card lab.

```bash
sudo chmod 600 /etc/netplan/99-qtmnc-lab.yaml
sudo netplan generate
sudo systemctl enable --now systemd-networkd
sudo netplan try --timeout 60
```

Kiểm tra trên console rồi Enter chấp nhận. Nếu tên chưa đổi sau hotplug, khởi
động lại Ubuntu một lần và kiểm tra:

```bash
ip -br addr
ip route
```

Cần có gns3test .30.129 và ens37 .10.129; default route vẫn qua ens33 NAT.

## 6. Mở project GNS3 mới

Đóng project cũ để giải phóng cổng UDP 30010 trước khi mở project mới.
Trong Windows PowerShell:

```powershell
$qtmncCourseDir = Join-Path $env:USERPROFILE 'Documents\GNS3\projects\QTMNC_COURSE'
New-Item -ItemType Directory -Force -Path $qtmncCourseDir
Copy-Item .\lab\gns3\QTMNC_COURSE.gns3 $qtmncCourseDir
```

1. GNS3 → File → Open → chọn file vừa sao chép trong Documents.
2. Chọn Local server nếu được hỏi. Ubuntu vẫn chạy riêng trong VMware.
3. Chuột phải Cloud-WINDOWS → Configure → UDP tunnels: local `30010`, remote
   host `127.0.0.1`, remote port `30011`.
4. Cloud-LINUX-MGMT → Configure → Ethernet interfaces → chọn đúng VMware
   Network Adapter VMnet2. Nếu adapter không được nhận, Refresh, xóa mục cũ và
   Add lại adapter đúng tên trên máy hiện tại.
5. Cloud-LINUX-LAB làm tương tự nhưng chọn VMnet3.
6. SW-MANAGEMENT: các port access VLAN 10; SW-LAB: các port access VLAN 30.
7. Bấm Start/Resume all devices (tam giác xanh). Hai vùng không nối tắt với nhau.
8. Mở PowerShell **Run as administrator** cho cầu nối nếu nó chưa chạy:

   ```powershell
   cd D:\QTM_NC\telegram\qtmnc
   .\run_tap_windows.cmd --adapter "Local Area Connection"
   ```

   Giữ cửa sổ này mở. Tên adapter đã đổi thì dùng `--list` rồi chọn đúng tên.

## 7. Cấu hình VPCS bằng console

GNS3 → chuột phải PC01 → Console:

```text
ip 192.168.30.10/24
save
ping 192.168.30.129
```

PC02 → Console:

```text
ip 192.168.30.20/24
save
ping 192.168.30.129
ping 192.168.30.10
```

Không đặt gateway vì chưa triển khai router liên subnet. Trên Windows thử:

```powershell
Test-NetConnection 192.168.10.129 -Port 22 -InformationLevel Detailed
```

Cần nguồn .10.1 qua TAP và TcpTestSucceeded True. Đường SSH .73.x hoặc .30.x
không được dùng làm bằng chứng SSH đi xuyên vùng quản trị GNS3.

Sau khi SSH thành công, sao chép công cụ tạo tải có giới hạn từ Terminal Windows:

```powershell
scp .\lab\linux\labctl.py tuanto@192.168.10.129:~/labctl.py
```

Nhập mật khẩu Ubuntu khi được hỏi. Các bài thử dưới đây chạy bằng python3 có
sẵn trên Ubuntu, không cần cài dependency của dự án lên máy đích.

## 8. Chạy monitor và dashboard

Trong VS Code, mở `.env.simple`, giữ credential cũ và chỉnh:

```dotenv
MONITOR_HOST='192.168.10.129'
MONITOR_IFACE='gns3test'
MONITOR_INTERVAL='15'
MONITOR_TIMEOUT='15'
MONITOR_TEMP_ENABLED='true'
TEMP_SOURCE='auto'
```

Nhiệt độ không có cảm biến sẽ UNKNOWN. Nếu chưa thêm card lab, có thể thử giao
diện ngay với MONITOR_IFACE='ens33', sau đó chuyển sang gns3test.

Terminal Windows thứ nhất:

```powershell
.\run_windows.cmd
```

Terminal Windows thứ hai:

```powershell
.\run_dashboard.cmd
```

Mở Chrome/Edge → `http://127.0.0.1:8765`. Dashboard đọc .monitor_state/simple.sqlite3
giống runner bản đơn giản. Không tạo thêm SSH hoặc gửi thêm tin.

Muốn xem trước giao diện khi chưa chạy lab:

```powershell
.\run_dashboard.cmd --demo
```

Chế độ này luôn có nhãn MÔ PHỎNG, không đọc thiết bị, không ghi dữ liệu demo vào
DB thật và không gửi tin. Dừng demo bằng Ctrl+C trước khi chạy dashboard thật.

Nếu dùng profile .env.gns3 với đường dẫn SQLite mặc định, chạy:

```powershell
.\run_dashboard.cmd --state-file .\.monitor_state\gns3.sqlite3
```

## 9. Những ca trình diễn quan trọng

| Ca | Thao tác | Kết quả cần ghi |
|---|---|---|
| Bình thường | Chạy 3–5 lượt | CPU/RAM hợp lệ, iface UP; lịch sử và thời gian cập nhật |
| CPU | Ubuntu: python3 ~/labctl.py cpu --seconds 30 | Vượt 75 → cảnh báo, ≤70 → phục hồi |
| RAM | Ubuntu: python3 ~/labctl.py ram --target 75 --seconds 45 | Vượt 65 → cảnh báo, ≤60 → phục hồi; có giới hạn theo RAM khả dụng |
| Interface DOWN | VMware → card VMnet3 → bỏ Connected rồi bật lại | gns3test DOWN/UP; SSH ens37 vẫn còn |
| Mất đường quản trị | GNS3 xóa dây SW-MANAGEMENT rồi nối lại | Mất SSH, gap trên chart, tin phục hồi |
| Mất đường thử lớp 2 | Xóa dây SW-LAB rồi ping từ PC01 | Ping lỗi; operstate VMware có thể vẫn UP |
| Monitor dừng | Ctrl+C cửa sổ monitor, để web chạy | Sau hạn mới dữ liệu: dashboard hiện dữ liệu cũ |
| Mất Internet Windows | Tắt Wi-Fi khi quản trị lab vẫn còn | Outbox tăng, thu thập vẫn tiếp tục; có Internet gửi lại |
| Không có cảm biến | TEMP_SOURCE=auto trên VM | Temp UNKNOWN; không thay thành 0°C |

Không dùng tắt ens37 để minh họa lỗi gns3test: đây là hai loại sự cố khác nhau.
Dashboard không tự chạy các lệnh gây tải hoặc đổi mạng.

## 10. Thu bằng chứng cho báo cáo

- Chụp topology và VMware mapping 3 card; ghi IP/MAC thực tế.
- Chụp Test-NetConnection nguồn TAP .10.1 và kết nối SSH thành công.
- Mỗi ca lưu thời điểm kích thích, ảnh dashboard và tin Telegram/Slack tương ứng.
- Chọn khoảng thời gian trên dashboard → Xuất CSV; timestamp CSV dùng UTC.
- Dùng [mẫu báo cáo Word/PDF](course_project/README.md); điền họ tên/MSSV và kết
  quả đo thật vào bảng nghiệm thu trước khi nộp.

Lịch sử giữ tối đa 5000 mẫu và 1000 sự kiện/thiết bị, tối đa 24 giờ. Tin outbox
chưa giao không bị xóa theo giới hạn lịch sử. Web hiện tối đa 100 sự kiện trong
khoảng đã chọn. Tỷ lệ kết nối tính theo số lượt, không thay thế SLA theo thời gian.
