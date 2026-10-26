# Thực hành GNS3: Windows/VS Code giám sát Linux bằng SSH và SNMP

Hướng dẫn cho **Windows đã cài GNS3 và VMware Workstation**, Ubuntu 22.04/24.04
Python 3.10 trở lên. Giao diện tham chiếu GNS3 2.2; bản khác có thể đổi tên menu.
Windows chạy chương trình Python và gửi HTTPS tới Telegram/Slack. Ubuntu là thiết
bị đích. GNS3 tạo đường mạng quản trị và mạng thử nghiệm giữa hai máy.

Làm lần lượt các mục. Dòng PS ...> hay tuanto@...$ là dấu nhắc, không gõ lại.
Chỉ chép nội dung trong khối lệnh; không thêm số thứ tự như "1." trước lệnh.

## 1. Mô hình và địa chỉ

![Mạng GNS3](diagrams/png/02-trien-khai-vmware.png)

~~~mermaid
flowchart LR
  W["Windows: VS Code + Python<br/>VMnet1: 192.168.10.1"] --> C1["Cloud WINDOWS-VMNET1"]
  C1 --- S1["SW-MANAGEMENT"]
  S1 --- C2["Cloud LINUX-MGMT-VMNET2"]
  C2 --- L["Ubuntu NIC2: gns3mgmt<br/>192.168.10.129/24<br/>SSH 22 / SNMP 161"]
  L --- T["Ubuntu NIC3: gns3test<br/>192.168.30.129/24"]
  T --- C3["Cloud LINUX-DATA-VMNET3"]
  C3 --- S2["SW-TEST"]
  S2 --- V["VPCS-TEST<br/>192.168.30.10/24"]
  W --> M["Telegram / Slack qua Internet"]
  L -. "NIC1 ens33: NAT, tải gói/cứu hộ" .-> N["VMnet8: 192.168.73.129<br/>gateway 192.168.73.2"]
~~~

| Thành phần | Cấu hình |
|---|---|
| Windows VMnet1 | 192.168.10.1/24, đầu vào đường quản trị GNS3 |
| Windows VMnet2 | 192.168.20.1/24, nối Cloud tới NIC2 Ubuntu |
| Windows VMnet3 | 192.168.30.1/24, nối Cloud tới NIC3 Ubuntu |
| Ubuntu NIC1 | NAT/VMnet8, giữ địa chỉ cũ 192.168.73.129 nếu chưa đổi |
| Ubuntu NIC2 | Custom VMnet2, đổi tên gns3mgmt, IP tĩnh 192.168.10.129/24 |
| Ubuntu NIC3 | Custom VMnet3, đổi tên gns3test, IP tĩnh 192.168.30.129/24 |
| VPCS | 192.168.30.10/24 |

**VMnet2 để subnet .20 nhưng Ubuntu NIC2 dùng .10 là có chủ ý.** VMnet là mạng
Ethernet lớp 2; hai Cloud và switch trong GNS3 nối VMnet1 với VMnet2. Địa chỉ .20.1
của Windows không dùng để SSH. Đừng đặt thêm .10.x trên adapter Windows VMnet2:
Windows cần gửi gói .10.129 qua VMnet1 để đường giám sát thực sự đi qua GNS3.
Không tạo Windows Network Bridge hoặc bật ICS cho các adapter lab.

NIC1 NAT giữ Internet và đường cứu hộ; NIC2 giữ quản trị; NIC3 dùng thử lỗi.
Hai NIC lab **không có gateway/default route**. Không cần router Cisco hoặc image
IOS cho mô hình này. Linux là máy VMware bên ngoài, được đại diện bằng hai Cloud
trong GNS3, không phải một VPCS hoặc máy Linux tự sinh khi mở project.

## 2. Lấy mã về Windows bằng Terminal trong VS Code

Cài Git và Python 3.10+ nếu chưa có. Mở VS Code → Terminal → New Terminal,
chọn PowerShell. Tải lần đầu:

~~~powershell
cd D:\
git clone https://github.com/tunato2807-del/qtmnc.git
cd .\qtmnc
code .
~~~

Nếu đang có dự án ở đường dẫn cũ của bạn, **không clone chồng thư mục**:

~~~powershell
cd D:\QTM_NC\telegram\qtmnc
git status --short
git fetch origin
git merge --ff-only origin/main
~~~

Nếu Git báo thay đổi cục bộ hoặc nhánh phân kỳ, giữ lại file và xem thông báo
trước; không dùng reset --hard. File .env cũ được giữ riêng; bản GNS3 dùng
.env.gns3. Chưa chạy wizard đến khi mạng ở mục 7 hoạt động.

## 3. Chuẩn bị mạng trong VMware Workstation

1. **Shut Down Ubuntu**; không chọn Suspend.
2. VMware → Edit → Virtual Network Editor → Change Settings (quyền Administrator).
3. Giữ VMnet8 hiện tại: NAT 192.168.73.0/24. Không bấm Restore Defaults.
4. Chọn VMnet1, đặt Host-only, subnet 192.168.10.0, mask 255.255.255.0.
   Bật "Connect a host virtual adapter to this network"; tắt "Use local DHCP service".
5. Add Network → VMnet2, Host-only, subnet 192.168.20.0, mask 255.255.255.0,
   bật host virtual adapter, tắt DHCP.
6. Add Network → VMnet3, Host-only, subnet 192.168.30.0, mask 255.255.255.0,
   bật host virtual adapter, tắt DHCP. Bấm Apply/OK.
7. Windows PowerShell chạy ipconfig. Xác nhận VMnet1 .10.1, VMnet2 .20.1,
   VMnet3 .30.1. Nếu host adapter có IP khác, vào ncpa.cpl → adapter tương ứng
   → Properties → IPv4, đặt IP trong bảng; không thêm gateway/DNS cho ba adapter.
8. VMware → Ubuntu → Edit virtual machine settings:
   - Network Adapter thứ nhất: giữ NAT (VMnet8).
   - Add → Network Adapter thứ hai → Custom: VMnet2.
   - Add → Network Adapter thứ ba → Custom: VMnet3.
   - Tất cả bật Connected/Connect at power on.
9. Ở Advanced của từng NIC, ghi lại MAC của NIC2/NIC3. Sau này nhận dạng bằng MAC,
   không đoán tên ens37/ens38 vì số có thể khác theo VM.
10. Khởi động Ubuntu.

Nếu VMware đang dùng VMnet2/3 cho lab khác, không sửa lab đó. Chọn hai VMnet trống,
đổi mapping Cloud tương ứng trong GNS3; phần địa chỉ IP ở đây có thể giữ nếu không
trùng mạng có sẵn. Thay thế tên VMnet nhất quán ở mọi bước.

## 4. Chọn đúng server GNS3 trên Windows

1. Mở GNS3 → Edit → Preferences → Server → Local server.
2. Bật local server trên Windows; kiểm tra đường dẫn gns3server.exe hợp lệ.
   Dùng địa chỉ loopback và cổng 3080 theo cấu hình cài đặt của bạn.
3. Cloud, Ethernet switch và VPCS trong lab này phải **Run on local computer /
   Local server**. Cloud chạy trong GNS3 VM/remote server sẽ nhìn NIC của máy đó,
   không thấy VMware Network Adapter VMnet1/2/3 của Windows.
4. Với các node tích hợp này, không bắt buộc bật GNS3 VM. Nếu đã có GNS3 VM cho
   lab khác, có thể giữ nhưng vẫn chọn local server cho các node của lab này.
5. Nếu Cloud không thấy adapter, kiểm tra Npcap đã cài từ bộ cài GNS3, local server
   đang chạy và khởi động lại GNS3 sau khi thêm VMnet. Chấp nhận quyền firewall
   cho GNS3 trên mạng lab phù hợp; không tắt toàn bộ Windows Firewall.

## 5. Mở project mẫu hoặc tự kéo thả

### Cách A: mở mẫu có sẵn

Trong Terminal Windows ở thư mục dự án, sao chép mẫu sang Documents để GNS3 có thể
lưu trạng thái mà không sửa file mẫu trong Git:

~~~powershell
$labDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "GNS3\projects\QTMNC_GNS3_MONITOR"
New-Item -ItemType Directory -Force $labDir
Copy-Item .\lab\gns3\QTMNC_GNS3_MONITOR.gns3 $labDir
~~~

Chỉ sao chép lần đầu; nếu đã sửa project, không ghi đè file đang dùng.
GNS3 → File → Open Project → chọn file vừa sao chép. Mẫu dùng định dạng GNS3 2.2.
Nếu khác phiên bản hoặc báo mapping không tồn tại, dùng cách B.

**Kiểm tra từng Cloud trước khi Start:**

1. Chuột phải WINDOWS-VMNET1 → Configure → Ethernet interfaces.
2. Bật "Show special Ethernet interfaces" nếu có.
3. Port Ethernet 0 phải là **VMware Network Adapter VMnet1**.
4. Lặp lại LINUX-MGMT-VMNET2 → VMnet2, LINUX-DATA-VMNET3 → VMnet3.
5. Nếu mapping cũ sai: xóa link đang nối Cloud đó, xóa interface cũ trong cấu hình
   Cloud, Add đúng adapter, rồi nối lại. Nếu hỏi server, chọn local Windows.

Không chọn Wi-Fi, Radmin VPN, VMnet8 hoặc adapter của GNS3 VM thay VMnet1/2/3.
Tên adapter có thể được Windows dịch; chọn đúng số VMnet.

### Cách B: tạo từ đầu bằng GUI

1. File → New blank project → đặt QTMNC_GNS3_MONITOR.
2. Browse all devices → kéo **3 Cloud**, chọn local server cho cả ba.
   Đổi tên lần lượt WINDOWS-VMNET1, LINUX-MGMT-VMNET2, LINUX-DATA-VMNET3.
3. Kéo **2 Ethernet switch**, đổi tên SW-MANAGEMENT, SW-TEST.
4. Kéo **1 VPCS**, đổi tên VPCS-TEST.
5. Configure từng Cloud → Ethernet interfaces → chọn đúng adapter → Add → OK:

| Cloud | Adapter Windows |
|---|---|
| WINDOWS-VMNET1 | VMware Network Adapter VMnet1 |
| LINUX-MGMT-VMNET2 | VMware Network Adapter VMnet2 |
| LINUX-DATA-VMNET3 | VMware Network Adapter VMnet3 |

6. Add a link (biểu tượng dây mạng), nối đúng **4 dây**:

| Từ | Đến |
|---|---|
| WINDOWS-VMNET1 Ethernet 0 | SW-MANAGEMENT Ethernet 0 |
| SW-MANAGEMENT Ethernet 1 | LINUX-MGMT-VMNET2 Ethernet 0 |
| LINUX-DATA-VMNET3 Ethernet 0 | SW-TEST Ethernet 0 |
| SW-TEST Ethernet 1 | VPCS-TEST Ethernet 0 |

7. Giữ các port switch cùng VLAN access 1. Bấm nút xanh Start/Resume all nodes.
   Ubuntu phải đang chạy trong VMware; nút Start của GNS3 không tự mở VM bên ngoài.
8. Chuột phải VPCS → Console. Chưa ping được Linux nếu chưa cấu hình IP ở mục 6.

~~~text
ip 192.168.30.10/24
save
~~~

Tùy chọn: sau khi có Python, tạo project với mapping adapter phát hiện từ local API:

~~~powershell
py -3 tools/create_gns3_project.py --check-local-api
~~~

API chỉ đọc http://127.0.0.1:3080/v2/compute/network/interfaces. Nếu GNS3 dùng
xác thực/cổng khác, chọn mapping bằng GUI; không cần tắt xác thực để dùng tool.
Project mẫu đã được kiểm tra cấu trúc theo schema GNS3 chính thức; việc bắt gói
Npcap và mapping adapter vẫn phải kiểm tra trên máy Windows thực tế.

## 6. Cài SSH và đặt IP cho hai NIC Ubuntu

### 6.1 Trên console Ubuntu trong VMware

~~~bash
sudo apt update
sudo apt install -y openssh-server python3 snmpd snmp
sudo systemctl enable --now ssh
ip -br addr
ip -br link
ip route
~~~

Giữ NIC NAT ens33 và default via 192.168.73.2. Nếu DHCP đã đổi IP .73.129,
dùng IP NAT thực tế trong hai lệnh chuyển file dưới đây.

### 6.2 Chuyển các file hỗ trợ từ Windows qua đường NAT sẵn có

Chạy ở Terminal **Windows**, trong thư mục dự án:

~~~powershell
ssh tuanto@192.168.73.129 "mkdir -p ~/qtmnc-gns3"
scp -r .\device_monitor .\lab tuanto@192.168.73.129:~/qtmnc-gns3/
~~~

Lần đầu SSH hỏi host key: trên **console Ubuntu** lấy fingerprint:

~~~bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
~~~

Chỉ chấp nhận khi fingerprint đúng cùng loại key. Mật khẩu Linux khi gõ không
hiện dấu * là bình thường. Nếu tên tài khoản không phải tuanto, thay đúng user.
Không chuyển .env, .venv hay token sang Linux.

### 6.3 Tạo cấu hình mạng từ console VMware

Đối chiếu MAC mục 3 với ip -br link. Ví dụ NIC2 VMnet2 là ens37 và NIC3 VMnet3 là
ens38: **chỉ dùng ví dụ này nếu MAC của bạn khớp**.

~~~bash
cd ~/qtmnc-gns3
sudo python3 lab/linux/configure_network.py --management-iface ens37 --test-iface ens38
sudo netplan try --timeout 60
~~~

Xem thông báo, kiểm tra rồi Enter xác nhận. Sau đó khởi động lại Ubuntu để tên
interface theo MAC được áp dụng nhất quán:

~~~bash
sudo reboot
~~~

Tool chỉ thêm /etc/netplan/90-qtmnc-gns3.yaml cho hai NIC lab, không ghi đè cấu
hình NAT đang có. Nếu netplan báo NIC được quản lý bởi cấu hình khác, xem
sudo netplan get và các file /etc/netplan; loại bỏ khai báo trùng cho **hai NIC
lab** sau khi sao lưu. Giữ cấu hình NIC NAT. Nếu Ubuntu Desktop có profile
NetworkManager cũ cho NIC2/3, tắt autoconnect của đúng profile trùng trước khi
áp dụng. Không xóa toàn bộ cấu hình mạng.

Sau reboot:

~~~bash
ip -br addr
ip route
ip route get 192.168.10.1
~~~

Kết quả cần có:

~~~text
ens33       UP  192.168.73.129/24       (hoặc IP NAT thực tế)
gns3mgmt    UP  192.168.10.129/24
gns3test    UP  192.168.30.129/24
default via 192.168.73.2 dev ens33
192.168.10.1 dev gns3mgmt src 192.168.10.129
~~~

## 7. Kiểm tra đường đi qua GNS3

GNS3 phải Start; Ubuntu phải đang bật. Từ Windows:

~~~powershell
ping 192.168.10.129
Test-NetConnection 192.168.10.129 -Port 22
ssh tuanto@192.168.10.129
~~~

TcpTestSucceeded cần True. Ping có thể bị chặn ICMP dù SSH vẫn hoạt động.
Từ console VPCS:

~~~text
ping 192.168.30.129
~~~

Để chứng minh GNS3 nằm trên đường quản trị: tạm Stop SW-MANAGEMENT hoặc tháo
một dây của nó, kiểm tra SSH .10.129 mất; nối lại/Start rồi SSH trở lại.
Không thay MONITOR_HOST thành .73.129 khi trình diễn đường GNS3 vì đó là đường
NAT trực tiếp. Có thể dùng .73.129 để sửa cấu hình khi đường GNS3 bị lỗi.

Nếu Ubuntu đã bật UFW, thêm đúng luật cho lab, giữ các luật khác:

~~~bash
sudo ufw status
sudo ufw allow from 192.168.10.1 to 192.168.10.129 port 22 proto tcp
sudo ufw allow from 192.168.10.1 to 192.168.10.129 port 161 proto udp
~~~

Không cần bật UFW chỉ để thực hành; nếu chưa bật thì không tự bật giữa phiên SSH.

## 8. Chạy bản SSH trước

Trong Windows, thư mục dự án:

~~~powershell
.\setup_windows.cmd --configure
~~~

Wizard tạo .venv, cài thư viện và lưu .env.gns3. Chọn:

| Câu hỏi | Giá trị cho lab |
|---|---|
| Giao thức | ssh |
| Hệ điều hành | linux |
| IP | 192.168.10.129 |
| SSH port/user | 22 / tuanto |
| Interface | gns3test |
| Giám sát nhiệt độ | true để kiểm tra đủ chỉ số; auto thiếu cảm biến sẽ UNKNOWN |
| Nguồn nhiệt độ | auto, hoặc demo theo mục 10 |
| Xác thực SSH | password, rồi nhập mật khẩu ở **ô kế tiếp** |
| Kênh | telegram, slack hoặc both |

Nhập secret không hiển thị ký tự. Dán fingerprint lấy từ console Ubuntu khi
wizard yêu cầu; chấp nhận cả chuỗi SHA256:... hoặc toàn dòng ssh-keygen.
Wizard không tự tin khóa lạ chỉ vì máy đang trả về một fingerprint.

Cấu hình Telegram: mở @BotFather → /newbot → lấy token; nhắn /start cho bot mới.
Để biết chat ID, có thể dùng Telegram Bot API getUpdates từ máy của bạn sau khi
nhắn bot; lấy message.chat.id, không nhầm với ID của bot. Không chia sẻ URL chứa
token hoặc log phản hồi có nội dung hội thoại.

Cấu hình Slack: api.slack.com/apps → Create New App → From scratch → workspace
của bạn → Incoming Webhooks → Activate → Add New Webhook to Workspace → chọn
channel → Allow. Dán webhook vào ô secret; workspace có thể cần admin cho phép.
Chọn both nếu muốn kiểm thử nhận trên cả hai ứng dụng.

~~~powershell
.\.venv\Scripts\python.exe -m device_monitor --env-file .env.gns3 --check-config
.\.venv\Scripts\python.exe -m device_monitor --env-file .env.gns3 --test-notifications
.\.venv\Scripts\python.exe -m device_monitor --env-file .env.gns3 --once
.\run_windows.cmd
~~~

--check-config chỉ kiểm tra cấu hình, không chứng minh mạng/credential hợp lệ.
--test-notifications **thực sự gửi tin TEST** tới các kênh đã cấu hình.
--once thu thập một chu kỳ và có thể gửi cảnh báo thực. Sau đó F5 trong VS Code
hoặc run_windows.cmd để xem bảng cập nhật. Chu kỳ profile GNS3 là 5 giây.
Ctrl+C dừng; tin chưa gửi còn trong SQLite để thử lại lần chạy sau.

## 9. Thêm SNMP, rồi chuyển sang hybrid

### 9.1 Trên Ubuntu, cài agent lab riêng

~~~bash
cd ~/qtmnc-gns3
sudo python3 lab/linux/install_agent.py --iface gns3test
sudo systemctl status qtmnc-lab-snmp --no-pager
sudo ss -lunp
~~~

Nhập community riêng 8–128 ký tự chữ/số/_/-. Đây là secret, sẽ nhập cùng giá trị
trong wizard Windows. Agent riêng bind 192.168.10.129:161 và chỉ cho đọc từ
192.168.10.1. Không thay file /etc/snmp/snmpd.conf của dịch vụ khác.

Nếu cổng 161 đã bị dịch vụ khác chiếm, dùng --port 1161, mở đúng UDP 1161 nếu có
firewall và đặt SNMP_PORT=1161 trên Windows. Không dừng dịch vụ khác chỉ để chạy lab.
Chạy lại installer giữ config; muốn đổi community/bind/nhiệt độ, thêm --reconfigure.
Sau khi đổi file chương trình, chạy lại installer để sao chép bản mới.

### 9.2 Trên Windows

~~~powershell
.\setup_windows.cmd --configure
~~~

Chọn snmp để kiểm tra riêng: profile linux-extend, version 2c, port 161,
community giống trên Ubuntu. Sau đó chạy --once như mục 8.
Khi cả SSH và SNMP đều hoạt động, chạy wizard lần nữa chọn **hybrid**.

| Chế độ | CPU/RAM/nhiệt độ | Interface | Phát hiện |
|---|---|---|---|
| ssh | Linux qua SSH | /sys/class/net/.../operstate | Mất SSH / thiếu dữ liệu |
| snmp | NET-SNMP-EXTEND-MIB, JSON probe Linux | IF-MIB, tự tìm ifIndex theo ifName | Mất SNMP / thiếu dữ liệu |
| hybrid | Ưu tiên SSH, dự phòng SNMP | Ưu tiên SNMP, dự phòng SSH | Mất từng dịch vụ và mất cả thiết bị |

SNMP CPU không dùng nhầm load average: probe đọc chênh lệch /proc/stat.
RAM dùng MemAvailable. JSON extension lấy qua OID
1.3.6.1.4.1.8072.1.3.2.3.1.2.5.113.116.109.110.99 (nsExtendOutputFull."qtmnc").
Interface dùng IF-MIB riêng; không lấy trạng thái trong JSON làm bằng chứng IF-MIB.
ifName được kiểm tra lại khi cache ifIndex để tránh đọc nhầm cổng sau thay đổi.

Installer lab thiết lập **SNMPv2c read-only**, không mã hóa, giới hạn IP nguồn.
Chương trình cũng hỗ trợ SNMPv3 authPriv SHA/AES; để dùng v3 phải cấu hình user
v3 tương ứng trên agent do bạn quản lý, rồi chọn version 3 trong wizard.
Installer ở trên chưa tự cấp user v3. Không mở UDP 161 ra Internet.

## 10. Kiểm thử cảnh báo có thời hạn

Giữ Windows đang run_windows.cmd. Chạy các lệnh sau **trên Ubuntu** từ console
VMware hoặc một phiên SSH khác; thực hiện từng ca, chờ phục hồi rồi mới ca tiếp.

~~~bash
cd ~/qtmnc-gns3
python3 lab/linux/labctl.py cpu --seconds 60
python3 lab/linux/labctl.py ram --target 75 --seconds 90
sudo python3 lab/linux/labctl.py interface --iface gns3test --seconds 45
~~~

CPU thường tăng theo số worker/vCPU; mặc định tối đa 4 worker. VM có hơn 4 vCPU
có thể cần --cores bằng số vCPU để vượt 75%; ví dụ --cores 8 cho VM 8 vCPU.
RAM target là gần đúng, bị giới hạn theo RAM khả dụng; nếu dùng nhiều RAM sẵn
có, chờ ứng dụng khác giảm tải. Không dùng thử cấp phát vô hạn.
Lệnh interface từ chối NIC default route và đường về Windows quản trị; kết thúc
tự bật lại gns3test. Nếu tiến trình bị kill -9 hoặc VM dừng giữa chừng, từ console:

~~~bash
sudo ip link set gns3test up
~~~

**Không dùng việc xóa dây GNS3 làm bằng chứng chắc chắn operstate DOWN.**
VMware có thể giữ virtual NIC carrier UP dù Cloud mất đường. Muốn test IF-MIB
DOWN dùng labctl interface; muốn test mất toàn bộ đường quản trị, Stop switch
SW-MANAGEMENT rồi Start lại.

### Nhiệt độ thật và mô phỏng

VMware thường không cung cấp nhiệt độ CPU vật lý. TEMP_SOURCE=auto mà không có
cảm biến sẽ UNKNOWN và cảnh báo thiếu dữ liệu; đó là hành vi đúng.
Nếu chưa cần ca nhiệt độ, đặt MONITOR_TEMP_ENABLED=false và ghi rõ phạm vi demo.

Để thử logic ngưỡng nhiệt trên VM, chọn nguồn demo trong wizard Windows,
giữ MONITOR_TEMP_ENABLED=true. Tạo giá trị nền và cài lại nguồn demo cho SNMP:

~~~bash
cd ~/qtmnc-gns3
sudo python3 lab/linux/labctl.py temperature --celsius 40 --seconds 10
sudo python3 lab/linux/install_agent.py --iface gns3test --temperature-source demo --reconfigure
~~~

Chạy lại monitor, chờ nhiệt độ nền 40°C có nhãn MÔ PHỎNG, rồi:

~~~bash
sudo python3 lab/linux/labctl.py temperature --celsius 75 --seconds 60
~~~

Sau 60 giây nguồn demo trở về nền 40°C và phát phục hồi. Cả dashboard, cảnh báo
và tin phục hồi phải ghi **MÔ PHỎNG**. File demo có hạn tại
/var/lib/qtmnc-lab/temperature.json; không phải nhiệt độ CPU thực của host.
Muốn trở lại cảm biến thật, đổi Windows TEMP_SOURCE=auto và reconfigure agent
--temperature-source auto. Không cần cài lại agent nếu chỉ dùng SSH.

Xem [bảng kiểm thử đầy đủ](TEST_PLAN.md) cho mất dịch vụ SSH/SNMP, retry
Telegram/Slack, khởi động lại và kiểm tra phục hồi.

## 11. Lỗi thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| Cloud không có VMnet | Local Windows server, Show special Ethernet interfaces, Npcap, restart GNS3 |
| Template không mở | Dùng cách B tạo GUI; kiểm tra phiên bản GNS3 |
| SSH .73.129 được nhưng .10.129 không được | NIC2 đúng VMnet2/MAC/IP, đủ 2 Cloud + switch quản trị, Start và mapping VMnet1/2 |
| SSH .10.129 vẫn được khi tháo quản trị GNS3 | Kiểm tra adapter Windows VMnet2 không có .10.x; bỏ Network Bridge/ICS hoặc đường nối ngoài lab |
| Interface không tên ens37 | Nhận dạng bằng MAC, không đoán số; sau netplan và reboot phải có gns3mgmt/gns3test |
| SNMP timeout nhưng SSH được | Agent active, bind IP/UDP port, source Windows .10.1, community, firewall; Test-NetConnection chỉ kiểm tra TCP |
| SNMP IF-MIB không tìm thấy cổng | MONITOR_IFACE=gns3test, NIC tồn tại, tên sau reboot; không dùng tên làm ifIndex |
| Nhiệt độ UNKNOWN | VM thiếu cảm biến; bật demo có nhãn hoặc tắt rõ ràng |
| telegram ConnectionError rồi gửi được | Lỗi HTTPS tạm thời; hàng đợi giữ tin, thử lại; kiểm tra Internet/proxy/DNS nếu kéo dài |
| Telegram không nhận TEST | Đã /start, chat ID đúng, token đúng, bot không bị chặn; không đăng token lên GitHub |
| Fingerprint thay đổi | Đối chiếu từ console Ubuntu trước khi cập nhật known_hosts; không tắt kiểm tra host key |
| Lỗi PowerShell Unexpected token | Bỏ số "1." và dấu nhắc PS ở đầu; gõ đúng một dòng lệnh |
| Không có cảnh báo ngay lần chạy đầu | Chỉ số bình thường không gửi tin; dùng --test-notifications để thử kênh |

GNS3 trên Windows, Npcap, VMware và firewall phải được kiểm tra trên máy của bạn.
Bộ test trong repo kiểm tra mã và SNMP loopback; không thay cho bước xác nhận
đường đi trên GUI GNS3 thực tế.

Tham chiếu định dạng project và Cloud:
[schema GNS3](https://github.com/GNS3/gns3-server/blob/master/docs/gns3_file.json),
[Cloud implementation](https://github.com/GNS3/gns3-server/blob/master/gns3server/compute/builtin/nodes/cloud.py).
