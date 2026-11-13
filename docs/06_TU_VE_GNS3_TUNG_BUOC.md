# Tự vẽ GNS3 và chạy NetWatch từ đầu

Hướng dẫn dành cho máy thật Windows, GNS3 2.2.x và VMware Workstation. Giao diện VMware trong GNS3 đã đối chiếu với mã nguồn chính thức phiên bản 2.2.61. Một số phiên bản có tên nút hơi khác nhưng phải giữ đúng loại card, số adapter và đường mạng.

Ảnh VS Code của bạn đang mở thư mục ZIP `NetWatch_Lab_Moi`. Có thể chạy trực tiếp các file `.cmd`; không cần `git pull` trong thư mục ZIP không có `.git`. Bạn sẽ tự tạo project trống và kéo/nối thiết bị, không dùng trình tạo topology tự động.

Lưu công việc đang mở và dừng các phiên monitor/demo/helper cũ bằng Ctrl+C trước khi chuyển sang lab này. Để sao chép lệnh nguyên khối, dùng bản HTML hoặc VS Code Markdown Preview; bản PDF phù hợp để đọc đối chiếu từng chặng.

## 1. Đích cần làm và các cửa sổ sử dụng

```text
Windows thật: VS Code + Python + Dashboard + gửi Telegram/Slack
  VMnet8: 192.168.73.1/24
          |
          | mạng NAT gốc của VMware, không vẽ thành Cloud
          |
  R1-LINUX (Ubuntu router)
  mgmt0: 192.168.73.10/24       gateway Internet: 192.168.73.2
  srv0:  10.10.10.1/24
  users0:10.20.20.1/24
       |                         |
  SW-SERVERS                 SW-USERS
       |                     |       |
  SRV1-LINUX                PC01    PC02
  10.10.10.10              10.20.20.10  10.20.20.20
  GW 10.10.10.1            GW của hai PC: 10.20.20.1
```

Trong GNS3 có đúng **6 node**: 2 Ubuntu VMware, 2 Ethernet switch, 2 VPCS. Windows không phải VM/node GNS3. R1 là Ubuntu có bật chuyển tiếp IPv4, không phải router Cisco. Không cần IOS, Cloud, TAP hoặc GNS3 VM trong mô hình này.

| Cửa sổ | Chạy gì |
|---|---|
| VS Code → Terminal → PowerShell Windows | `setup.cmd`, cấu hình secret, chạy dashboard, Test-NetConnection |
| VMware → console Ubuntu R1 | `sudo`, `ip`, cấu hình router/probe |
| VMware → console Ubuntu SRV1 | `sudo`, `ip`, cấu hình server/probe/web |
| GNS3 → Console VPCS | `ip`, `ping`, `save` của VPCS |

Các khối ghi “Kỳ vọng” hoặc “Kết quả mong đợi” chỉ để đọc đối chiếu, không gõ thành lệnh. Không gõ `sudo`, `netplan`, `apt` vào PowerShell Windows. Không chép các ký hiệu `PS>`, `tuanto@...$` hoặc số thứ tự vào lệnh. Mật khẩu sudo không hiện ký tự khi gõ là bình thường.

## 2. Chạy thử phần mềm Windows từ đúng thư mục

**Nơi làm: VS Code trong ảnh.**

1. Nếu panel Chat làm chật màn hình, bấm X ở góc panel Chat để đóng panel đó.
2. Chọn menu **Terminal → New Terminal**; nếu menu bị thu gọn, bấm dấu `...` ở thanh menu để tìm Terminal. Có thể dùng Ctrl+`.
3. Trong terminal PowerShell mới, chạy:

```powershell
Get-Location
Test-Path .\setup.cmd
py -0p
```

`Test-Path` phải trả `True`. Nếu False: File → Open Folder → chọn đúng thư mục có `setup.cmd`, rồi mở terminal mới. Không tự `cd` về đường dẫn qtmnc cũ khi bạn đang dùng bản ZIP ở vị trí khác.

Nếu không có `py` nhưng `python --version` chạy được thì setup.cmd vẫn có thể dùng Python đó. Chỉ cài bổ sung Python khi máy chưa có trình chạy Python phù hợp.

Python 3.12 là phiên bản đã dùng kiểm thử. Nếu đã có Python dự án, dùng bộ cài hiện có; không cần thay Python chỉ vì GNS3 dùng một phiên bản khác. Chạy:

```powershell
.\setup.cmd
.\start.cmd --demo
```

Nếu chưa có Python: tải bản Python3 ổn định Windows64-bit từ python.org, chạy bộ cài và bật PATH/Python Launcher nếu có; cài xong mở terminal mới rồi chạy các lệnh trên. Python đóng gói bên trong GNS3 không thay cho Python dự án. Nếu đã có Python3.12 và muốn chọn rõ phiên bản, trước lần setup đầu chạy `py -3.12 -m venv .venv-netwatch`. Nếu đã có môi trường hoạt động, không cần tạo lại.

Mở trình duyệt: **http://127.0.0.1:8765**. Phải thấy nhãn **MÔ PHỎNG** và hai thẻ R1/SRV1. Demo không cần VM và không gửi tin. Quay lại terminal → Ctrl+C để dừng trước khi chạy chế độ khác. Không cần Activate.ps1.

**Điểm kiểm tra 1:** demo mở được. Đây mới là kiểm tra phần mềm Windows, chưa chứng minh mạng GNS3 hoạt động.

## 3. Chuẩn bị Ubuntu gốc và hai clone

Bạn đã có Ubuntu VMware thì dùng máy đó làm bản gốc. Chọn bản Ubuntu chưa provision thành R1/SRV1 của NetWatch; nếu máy nguồn đã có `/etc/netwatch/role`, dùng bản Ubuntu gốc khác hoặc tạo Ubuntu-BASE theo phụ lục A để không sao chép vai trò/host key đã provision. Giữ nguyên máy gốc; mọi cấu hình mạng lab thực hiện trên hai full clone mới. Nếu chưa có Ubuntu, xem phụ lục A ở cuối rồi quay lại đây.

| VM | RAM khởi đầu | CPU | Card khi chuẩn bị cài gói | Card khi đưa vào GNS3 |
|---|---|---|---|---|
| Ubuntu gốc | Giữ cấu hình hiện có | Giữ cấu hình hiện có | NAT | Không đưa vào project |
| R1-LINUX | 2 GB nếu chạy desktop; có thể giảm khi dùng console | 1 vCPU | 1 NAT | 1 NAT + 2 Custom |
| SRV1-LINUX | 2 GB nếu chạy desktop; có thể giảm khi dùng console | 1 vCPU | 1 NAT | 1 Custom |

Không mở Ubuntu gốc cùng hai clone khi không cần. Cần đủ RAM host và dung lượng đĩa cho hai bản sao; full clone không chia sẻ đĩa hệ điều hành với bản gốc.

**VMware Workstation:**

1. Tắt Ubuntu gốc bằng menu Power Off trong Ubuntu; không Suspend.
2. Chọn VM gốc ở Library bên trái.
3. **VM → Manage → Clone → Next**.
4. **The current state in the virtual machine → Next**.
5. **Create a full clone → Next**.
6. Name: `R1-LINUX`; Location ví dụ `D:\VMs\NetWatch\R1-LINUX` → Finish.
7. Lặp lại từ VM gốc để tạo `SRV1-LINUX`, thư mục riêng `D:\VMs\NetWatch\SRV1-LINUX`.
8. Mỗi clone → **Edit virtual machine settings** → chỉnh RAM/Processors.
9. Trong giai đoạn chuẩn bị, mỗi clone giữ đúng **một Network Adapter = NAT**. Nếu clone mang theo card thứ hai từ lab cũ, chỉ Remove card dư trên clone.
10. Khi VMware hỏi moved/copied ở lần bật đầu, chọn **I copied it** cho clone mới để nhận định danh/MAC mới.

Nếu đã có hai full clone đúng vai trò, dùng lại sau khi đối chiếu cấu hình; không tạo thêm nhiều VM trùng tên. Không dùng cùng một VMX cho cả R1 và SRV1.

## 4. Kiểm tra mạng NAT VMware trước

Thiết kế hiện tại dùng VMnet8 `192.168.73.0/24`, Windows `192.168.73.1`, NAT gateway `192.168.73.2`. Đây là dải đã dùng trong các bước trước của dự án.

**VMware → Edit → Virtual Network Editor → Change Settings nếu có → VMnet8:**

- Type: NAT.
- Subnet IP: `192.168.73.0`.
- Subnet mask: `255.255.255.0`.
- Bật host virtual adapter.
- Bấm **NAT Settings**: kiểm tra gateway `192.168.73.2`.
- Bấm **DHCP Settings**: kiểm tra IP `192.168.73.10` nằm ngoài pool và chưa được dùng; ví dụ pool `192.168.73.128` đến `192.168.73.254` thì `.10` nằm ngoài.

Không nhập `192.168.73.10` hoặc `.129` vào ô Subnet IP: đó là IP máy, không phải địa chỉ mạng /24. Không bấm Restore Defaults. Nếu VMnet8 hiện có subnet khác, không trộn các địa chỉ trong hướng dẫn này với subnet đó; cần quy hoạch đồng bộ trước khi chạy provision cố định.

**PowerShell Windows trong VS Code:**

```powershell
Get-NetIPAddress -InterfaceAlias "VMware Network Adapter VMnet8" -AddressFamily IPv4
```

Phải có `192.168.73.1`, PrefixLength `24`, AddressState Preferred. Nếu có nhiều dòng, xem đúng địa chỉ IPv4 của adapter VMnet8.

## 5. Cài công cụ trên từng clone khi còn NAT

Làm lần lượt R1 rồi SRV1. Trong Ubuntu desktop mở terminal bằng **Ctrl+Alt+T**. Dán bằng Ctrl+Shift+V; lệnh Linux chỉ chạy ở đây, không chạy trong PowerShell.

**Trên R1 Ubuntu:**

```bash
ip -br addr
ip route
```

**Trên SRV1 Ubuntu:**

```bash
ip -br addr
ip route
```

Nhận đúng máy bằng tab VMware `R1-LINUX`/`SRV1-LINUX`. Prompt Linux của hai clone có thể giống nhau vì được sao chép từ cùng bản gốc; không bắt buộc đổi hostname để chạy lab. Tài khoản đăng nhập clone vẫn là tài khoản Ubuntu gốc, ví dụ `tuanto`.

Mỗi máy phải có IPv4 `192.168.73.x` và default route qua `192.168.73.2`. Nếu không có, xem phụ lục B để phục hồi bootstrap DHCP trên clone một card NAT; không làm tiếp khi apt/git chưa có mạng.

**Trên cả hai Ubuntu clone:**

```bash
sudo apt update
sudo apt install -y python3 openssh-server git nftables iputils-ping iperf3
sudo systemctl enable --now ssh
git clone https://github.com/tunato2807-del/qtmnc.git ~/netwatch-manual
cd ~/netwatch-manual
python3 --version
systemctl is-active ssh
```

Nếu iperf3 hỏi có tự chạy daemon không, chọn **No**; sẽ chạy rõ ràng trong terminal khi thử. SSH phải báo `active`. Linux clone chỉ cần các gói này để chạy probe, không cần pip install toàn bộ requirements của ứng dụng Windows.

Nếu `~/netwatch-manual` đã tồn tại và là checkout dự án mới, vào thư mục đó kiểm tra rồi cập nhật `git pull --ff-only origin main`; không ghi đè thay đổi cục bộ. Hai VM có hai thư mục home độc lập dù cùng tài khoản `tuanto`.

Sau khi chuẩn bị xong mỗi clone:

```bash
sudo poweroff
```

**Điểm kiểm tra 2:** hai clone đã có code, Python, SSH và nftables; đang tắt hoàn toàn.

## 6. Gắn ba card cho R1 và một card cho SRV1

**VMware R1-LINUX → Edit virtual machine settings:**

1. Network Adapter đầu tiên → **NAT**; bật **Connect at power on**.
2. **Add → Network Adapter → Finish**.
3. Card vừa thêm → **Custom: Specific virtual network → VMnet1**; Connect at power on.
4. Add thêm một Network Adapter nữa → **Custom → VMnet1**; Connect at power on.
5. Xác nhận danh sách có đúng ba card: Network Adapter, Network Adapter2, Network Adapter3.
6. OK, giữ VM tắt.

**VMware SRV1-LINUX → Edit virtual machine settings:**

1. Có đúng một Network Adapter.
2. Chuyển NAT thành **Custom: Specific virtual network → VMnet1**.
3. Bật Connect at power on → OK, giữ VM tắt.

VMnet1 chỉ là lựa chọn tạm để GNS3 cấp lại các card Custom sang những VMnet riêng khi Start. Không bật hai VM và thử ping ở giai đoạn này; mạng cuối chưa được nối. Không đổi card NAT đầu tiên của R1 thành Custom. Nếu VMnet1 chưa tồn tại, thêm host-only VMnet1 trong Virtual Network Editor; không đặt IP lab vào host adapter VMnet1.

| VMware | Số adapter GNS3 | Vai trò cuối |
|---|---|---|
| R1 Network Adapter | 0 | NAT gốc, sau này tên Linux `mgmt0` |
| R1 Network Adapter2 | 1 | Servers, sau này `srv0` |
| R1 Network Adapter3 | 2 | Users, sau này `users0` |
| SRV1 Network Adapter | 0 | Servers, sau này `lan0` |

## 7. Cấu hình GNS3 chạy trên Windows local

Mở GNS3. Đóng project cũ nếu đang giữ các VM này. Chọn **Edit → Preferences**:

1. **Server → Local server**: bật **Enable local server** nếu có; dùng máy Windows hiện tại. Host loopback/port mặc định có thể giữ nếu đã hoạt động.
2. **VMware → Local settings**: mục **Path to vmrun** phải trỏ tới `vmrun.exe` trong thư mục VMware Workstation. Dùng Browse nếu cần; vị trí thường là thư mục VMware Workstation trong Program Files hoặc Program Files (x86).
3. **VMware → Advanced local settings**: mục **Managed VMnet interfaces (VMnet8 excluded)**.
4. Chọn ba VMnet trống liên tiếp, ví dụ `4` to `6` nếu chưa có VM khác dùng4/5/6.
5. Bấm **Configure** → chấp nhận UAC của Windows. Không bấm Reset.
6. Apply → OK.

GNS3 2.2.61 đặt cấu hình pool trong tab **Advanced local settings**, không phải tab Network của từng VM. Các phiên bản khác có thể đặt mục này ở vị trí hơi khác.

Mở lại **VMware Virtual Network Editor** kiểm tra ba VMnet được cấp cho GNS3:

- Host-only, DHCP tắt, host virtual adapter bật để GNS3/uBridge nhận diện.
- Subnet bên dưới không trùng `192.168.73.0/24`, `10.10.10.0/24`, `10.20.20.0/24` hoặc mạng khác đang dùng.
- Ví dụ nếu các dải chưa dùng: VMnet4=`172.30.4.0/24`, VMnet5=`172.30.5.0/24`, VMnet6=`172.30.6.0/24`.

Các subnet host-only này là mạng nối bên dưới; không phải địa chỉ đặt trên cổng Linux. GNS3 sẽ cấp một VMnet cho mỗi card Custom, và các switch GNS3 nối frame giữa chúng. Windows không cần thêm địa chỉ `10.10.10.x` hoặc `10.20.20.x` lên các host adapter đó.

## 8. Đưa R1 và SRV1 vào danh sách thiết bị GNS3

**Tạo template R1:**

1. GNS3 → **Edit → Preferences → VMware VMs → New**.
2. Chọn **Run this VMware VM on my local computer** → Next.
3. Tại **VM list**, chọn `R1-LINUX`.
4. **Bỏ chọn Use as a linked base VM (experimental)** vì đã có full clone riêng.
5. Finish.
6. Trong danh sách VMware VMs chọn R1-LINUX → **Edit**.
7. **General settings**: Console type=`none`; Auto start console bỏ chọn; Start VM in headless mode bỏ chọn để dễ mở console VMware; Linked base VM vẫn bỏ chọn.
8. **Network**: Adapters=`3`, Type=`e1000`.
9. **Bỏ chọn Allow GNS3 to override non custom VMware adapter**. Đây là nhãn chính xác của2.2.61; bản khác có thể ghi Allow GNS3 to use any configured VMware adapter. Phải tắt để giữ NAT đầu tiên của R1.
10. Vẫn ở tab **Network**, mục **Name format** có thể giữ mặc định; nếu muốn các cổng đúng tên trong bảng hướng dẫn, dùng `Ethernet{0}` và First port name để trống. Không nhầm với Default name format của node ở tab General settings.
11. OK → Apply.

**Tạo template SRV1:** lặp lại New, chọn VM `SRV1-LINUX`, linked base VM bỏ chọn. Edit → Console none, headless bỏ chọn, **Adapters=1, Type=e1000**, override non-custom adapter bỏ chọn → OK → Apply.

Nếu VM không xuất hiện: kiểm tra nó đã được mở/đăng ký trong VMware Workstation, đã tắt và vmrun đúng. Nếu template đã có trong danh sách bên trái, chọn Edit template đó; wizard New có thể không liệt kê VM đã thêm, không cần tạo trùng. Sau khi sửa template, các node đã kéo trước đó có thể cần kiểm tra lại Configure của chính node.

**Điểm kiểm tra 3:** có hai template R1/SRV1 trong danh sách All devices; chưa có Cloud, chưa có router Cisco.

## 9. Tự tạo project và kéo sáu thiết bị

1. GNS3 → **File → New blank project** hoặc Ctrl+N.
2. Name=`NETWATCH_MANUAL`. Chọn thư mục project dễ tìm hoặc giữ mặc định trong thư mục người dùng → OK.
3. Bên trái chọn **Browse all devices**; gõ `R1-LINUX` ở Filter → kéo một node ra giữa canvas.
4. Lọc `SRV1-LINUX` → kéo một node sang phải, phía trên.
5. Lọc `Ethernet switch` → kéo hai switch: một giữa R1/SRV1, một dưới nhánh đó.
6. Lọc `VPCS` → kéo hai PC sang phải switch dưới.
7. Đặt tên theo vai trò: R1-LINUX, SRV1-LINUX, SW-SERVERS, SW-USERS, PC01, PC02. Có thể dùng mục Change hostname ở menu chuột phải; với VM có thể Configure → General settings → Name. Đổi nhãn GNS3 không tự đổi hostname bên trong Ubuntu.
8. Nếu node VM mang hậu tố tự sinh như R1-LINUX-1 thì không ảnh hưởng đường mạng; chỉnh tên để dễ đọc.

Bố trí:

```text
                     SW-SERVERS -------- SRV1-LINUX
                    /
          R1-LINUX
                    \
                     SW-USERS ---------- PC01
                           \------------ PC02
```

Không kéo Windows thành Cloud. Windows kết nối với R1 bằng NAT gốc VMware nằm ngoài canvas. Có thể dùng biểu tượng Add a note để ghi “Windows/VMnet8:192.168.73.1 → R1:192.168.73.10”; note là chú thích, không phải thiết bị.

## 10. Tự nối đúng năm dây

Tất cả node đang dừng. Bấm **Add a link**, thường là biểu tượng đầu cáp ở thanh bên trái. Với mỗi dây: bấm thiết bị thứ nhất → chọn cổng → bấm thiết bị thứ hai → chọn cổng.

| Dây | Đầu thứ nhất | Đầu thứ hai |
|---|---|---|
| 1 | R1-LINUX **Ethernet1** | SW-SERVERS Ethernet0 |
| 2 | SW-SERVERS Ethernet1 | SRV1-LINUX Ethernet0 |
| 3 | R1-LINUX **Ethernet2** | SW-USERS Ethernet0 |
| 4 | SW-USERS Ethernet1 | PC01 Ethernet0 |
| 5 | SW-USERS Ethernet2 | PC02 Ethernet0 |

Nếu Name format hiện e0/e1/e2 thì dùng cùng số0/1/2. Cổng **Ethernet0 của R1 giữ NAT, không nối dây GNS3**; nếu hiện reserved hoặc không cho chọn thì đó là hành vi đúng. Không nhầm “cổng đầu tiên trong danh sách” với “Ethernet0”.

Xong năm dây → nhấn Esc để thoát Add a link. Bật hiển thị interface labels ở View nếu cần. Ctrl+S lưu project. Các port switch giữ mặc định Access VLAN1; mỗi switch là một LAN riêng nên chưa cần cấu hình VLAN trunk.

**Điểm kiểm tra 4:** đúng6 node,5 dây; nhánh server nối R1 Ethernet1, nhánh users nối Ethernet2; R1 Ethernet0 không có dây trên canvas.

## 11. Khởi động và xác định tên cổng Linux

1. Bấm tam giác xanh **Start all nodes** trong GNS3.
2. Mở VMware Workstation để xem console R1/SRV1 đang được GNS3 khởi động. Không khởi động thêm bản Ubuntu gốc.
3. Đăng nhập từng clone bằng user Ubuntu gốc, ví dụ `tuanto`.
4. Trên từng clone chạy:

```bash
hostnamectl --static
ip -br link
ip -br addr
```

R1 phải có ba cổng Ethernet ngoài lo; SRV1 có một. Tên trước provision có thể là ens33/ens37/ens38 hoặc khác. Phải xác định đúng MAC, không đoán theo số tên.

**Cách đối chiếu:** VMware → chọn R1 → **VM Settings → Network Adapter → Advanced → MAC Address**. Ghi MAC từng card rồi tìm dòng tương ứng trong `ip -br link`. Nếu giao diện không cho xem khi VM chạy, dừng đúng VM, đọc MAC rồi Start lại từ GNS3 và đối chiếu lại. Có thể xem các dòng ethernet0/1/2.generatedAddress trong VMX bằng editor chỉ đọc; không sửa VMX khi VM đang chạy.

| Vai trò R1 | Card VMware | MAC đọc từ VMware | Tên tìm được ở Ubuntu |
|---|---|---|---|
| Quản trị NAT | Network Adapter | Điền MAC thật | Ví dụ ens33 |
| Servers | Network Adapter2 | Điền MAC thật | Ví dụ ens37 |
| Users | Network Adapter3 | Điền MAC thật | Ví dụ ens38 |

Trước provision, chỉ card NAT R1 thường có `192.168.73.x` do DHCP; hai card LAN chưa có IP tĩnh là bình thường. SRV1 đã chuyển Custom nên mất Internet tạm thời là bình thường; code/gói đã cài trước đó.

## 12. Cấu hình R1 tại console Ubuntu R1

Các lệnh dưới chỉ dùng **nếu đã xác minh NAT=ens33, Servers=ens37, Users=ens38**. Nếu tên khác thì thay bằng tên thực đã điền ở bảng.

```bash
cd ~/netwatch-manual
sudo python3 lab/provision.py router --management-iface ens33 --server-iface ens37 --user-iface ens38
```

Đây là bản xem kế hoạch. Kiểm tra MAC và các địa chỉ: mgmt0 `192.168.73.10`, srv0 `10.10.10.1`, users0 `10.20.20.1` trước khi áp dụng. Sau đó:

```bash
sudo python3 lab/provision.py router --management-iface ens33 --server-iface ens37 --user-iface ens38 --apply --cloned-vm
```

Script chỉ dành cho clone lab: backup cấu hình cũ, thay netplan theo MAC, tạo `monitor` nếu chưa có, tạo host key riêng ở lần đầu, cài probe và bật IPv4 forwarding/nftables. Nếu hỏi mật khẩu monitor: nhập mật khẩu riêng bạn nhớ, không phải token Telegram. Nếu báo UFW active, xem phụ lục C trước khi làm tiếp.

Khi netplan try hỏi **Press ENTER before the timeout to accept**: kiểm tra không có lỗi rồi nhấn Enter trong120 giây. Các thay đổi đổi tên cổng có thể cần reboot mới ổn định; tiếp tục tại console:

```bash
sudo passwd monitor
sudo reboot
```

`passwd monitor` giúp bạn biết chắc mật khẩu tài khoản giám sát, kể cả account đã có từ clone. Đăng nhập lại bằng `tuanto`, rồi:

```bash
ip -br addr
ip route
sysctl net.ipv4.ip_forward
systemctl is-active ssh
sudo nft list table inet netwatch_router
sudo -u monitor /usr/bin/python3 /opt/netwatch/probe.py --interfaces mgmt0 srv0 users0
```

Kỳ vọng:

```text
mgmt0   UP   192.168.73.10/24
srv0    UP   10.10.10.1/24
users0  UP   10.20.20.1/24
default via 192.168.73.2 dev mgmt0
net.ipv4.ip_forward = 1
ssh: active
```

Probe trả một dòng JSON có cpu_pct, ram_pct và interfaces. Không cần tự đặt IP ở Settings Ubuntu song song với script. Tên cổng sau reboot phải là mgmt0/srv0/users0; inventory đã dùng các tên này.

## 13. Cấu hình SRV1 tại console Ubuntu SRV1

Xác định tên card duy nhất, ví dụ ens33:

```bash
ip -br link
cd ~/netwatch-manual
sudo python3 lab/provision.py server --server-iface ens33
sudo python3 lab/provision.py server --server-iface ens33 --apply --cloned-vm
```

Nếu tên khác ens33 thì thay đúng tên. Nhập password monitor nếu được hỏi; Enter giữ cấu hình trong netplan try, rồi:

```bash
sudo passwd monitor
sudo reboot
```

Sau reboot:

```bash
ip -br addr
ip route
ping -c 4 10.10.10.1
systemctl is-active ssh
sudo -u monitor /usr/bin/python3 /opt/netwatch/probe.py --interfaces lan0
```

Kỳ vọng lan0=`10.10.10.10/24`, default via`10.10.10.1`, ping gateway được, ssh active, probe có số đo. Gateway ở đây là R1, không phải `192.168.73.2`.

**Điểm kiểm tra 5:** R1 và SRV1 có đúng IP/tên cổng; SRV1 ping được10.10.10.1; probe chạy không cần quyền sudo của tài khoản monitor.

## 14. Cấu hình PC01 và PC02 trong GNS3

**GNS3 → chuột phải PC01 → Console.** Cửa sổ phải có prompt VPCS, không phải Ubuntu/PowerShell:

```text
ip 10.20.20.10/24 10.20.20.1
save
show ip
ping 10.20.20.1
ping 10.10.10.10
```

**PC02 → Console:**

```text
ip 10.20.20.20/24 10.20.20.1
save
show ip
ping 10.20.20.1
ping 10.10.10.10
```

Nếu lần ping đầu mất một gói vì đang học ARP, thử lại. Nếu tất cả thất bại, kiểm tra card Users, cáp, ip_forward và gateway server. VPCS chỉ dùng thử đường mạng; không cung cấp CPU/RAM qua SSH như Ubuntu.

**Điểm kiểm tra 6:** PC01/02 ping được gateway và server ở subnet khác. Đây là bằng chứng định tuyến trong GNS3, chưa phải bằng chứng Windows đã SSH được.

## 15. Thêm route trên Windows đúng thư mục ZIP

**VS Code → PowerShell Windows** tại thư mục có setup.cmd:

```powershell
Test-NetConnection 192.168.73.10 -Port 22
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\windows_routes.ps1
```

TCP22 của R1 phải True. Script route không có -Apply chỉ in kế hoạch. Để áp dụng bằng cửa sổ admin mà không phải nhập lại đường dẫn ZIP:

```powershell
$qtmncRoute = (Resolve-Path .\tools\windows_routes.ps1).Path
$qtmncArgs = '-NoProfile -ExecutionPolicy Bypass -NoExit -File "{0}" -Apply' -f $qtmncRoute
Start-Process powershell.exe -Verb RunAs -ArgumentList $qtmncArgs
```

Windows hỏi UAC → Yes. Cửa sổ mới áp dụng hai route qua gateway192.168.73.10 trên VMnet8 và giữ mở để bạn đọc kết quả. Không chạy Python/dashboard với quyền admin chỉ vì route cần admin.

Quay lại **PowerShell trong VS Code**:

```powershell
Find-NetRoute -RemoteIPAddress 10.10.10.10
Test-NetConnection 10.10.10.10 -Port 22 -InformationLevel Detailed
```

Kỳ vọng route: InterfaceAlias=`VMware Network Adapter VMnet8`, NextHop=`192.168.73.10`, SourceAddress=`192.168.73.1`; TCP22=True. Nếu lại chọn Wi-Fi thì route chưa có/không đúng; chưa chuyển sang kiểm tra Telegram.

**Điểm kiểm tra 7:** Windows TCP22 tới cả R1 và SRV1 đều True. TCP True mới chứng minh cổng mở; tài khoản và host key xác minh ở chặng sau.

Hai route dùng ActiveStore, cần chạy lại -Apply sau mỗi lần Windows reboot. Không cần đặt IP10.10.10.x lên Windows, bật weak-host, ARP tĩnh hoặc khởi động TAP.

## 16. Tạo Telegram Bot và lấy chat ID nếu chưa có

Nếu bạn đã có bot đang dùng được, giữ bot/token/chat ID cũ và chuyển sang configure.cmd. Không cần tạo lại bot mỗi lần dựng lab.

**Telegram:**

1. Tìm BotFather chính thức → Start.
2. Gửi `/newbot`.
3. Nhập tên hiển thị cho bot.
4. Nhập username duy nhất có đuôi `bot`.
5. Giữ token BotFather trả về ở nơi cục bộ, không chụp hoặc gửi lên chat/GitHub.
6. Mở cuộc trò chuyện với bot vừa tạo → Start → gửi `/start`.

Nếu chưa biết chat ID của cuộc chat với bot, chạy khối sau trong **PowerShell Windows**; token được nhập kín, chỉ chat ID được in:

```powershell
$qtmncSecureToken = Read-Host 'Token Telegram' -AsSecureString
$qtmncToken = [System.Net.NetworkCredential]::new('', $qtmncSecureToken).Password
try {
    $qtmncUri = 'https://api.telegram.org/bot' + $qtmncToken + '/getUpdates'
    $qtmncUpdates = Invoke-RestMethod -Uri $qtmncUri -Method Get -ErrorAction Stop
    $qtmncUpdates.result | Where-Object { $_.message } | ForEach-Object { $_.message.chat.id } | Sort-Object -Unique
} catch {
    Write-Host 'Chưa lấy được ID; kiểm tra Internet, token và tin /start gửi tới bot.'
} finally {
    $qtmncToken = $null
    $qtmncUri = $null
    $qtmncUpdates = $null
    $qtmncSecureToken = $null
}
```

Không có dòng ID: gửi thêm tin tới bot rồi thử lại; nếu bot đã dùng webhook/getUpdates bởi ứng dụng khác thì phải xử lý cơ chế nhận update của bot đó trước. Không tự xóa webhook của bot đang được hệ thống khác sử dụng. Với private chat, lấy đúng chat ID của bạn; không chọn ID nhóm khác nếu danh sách có nhiều ID.

Slack là tùy chọn: tạo Slack app trong workspace bạn có quyền → Incoming Webhooks → Activate → Add New Webhook to Workspace → chọn channel → Allow → giữ Webhook URL cục bộ. Thử Telegram trước, sau đó mới bật cả hai kênh nếu cần.

## 17. Nhập secret và xác minh host key

**PowerShell Windows trong VS Code:**

```powershell
.\configure.cmd
```

| Câu hỏi | Nhập gì |
|---|---|
| R1 SSH user | `monitor` |
| R1 mật khẩu | Password monitor đã đặt tại R1 |
| SRV1 SSH user | `monitor` |
| SRV1 mật khẩu | Password monitor đã đặt tại SRV1 |
| Kênh | `1`=Telegram; `0` chỉ dashboard; `2` Slack; `3` cả hai |
| TELEGRAM_TOKEN | Token bot của bạn |
| TELEGRAM_CHAT_ID | Chat ID vừa xác định |

Không cần tự sửa mã Python để thêm mật khẩu. Script lưu `.env.netwatch`, không phải `.env.example`. Enter giữ giá trị cũ ở ô secret khi đã có cấu hình; secret không hiện ký tự khi nhập. Không gửi file này cho người khác.

**Trên console R1 Ubuntu:**

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

**Trên console SRV1 Ubuntu:** chạy cùng lệnh. Đây là hai key riêng. Ví dụ output có dạng `256 SHA256:... comment (ED25519)`.

**PowerShell Windows:**

```powershell
.\start.cmd trust
```

Khi hỏi R1, dán fingerprint lấy từ console R1; khi hỏi SRV1, dán từ console SRV1. Chỉ lấy token bắt đầu **SHA256:**; không chép số256 đứng trước. Nếu không khớp phải kiểm tra đúng VM/IP, không chấp nhận key ngẫu nhiên. Công cụ lưu key đã xác minh vào `.local/known_hosts`.

## 18. Chạy giám sát thật

Mở inventory.json trong Explorer VS Code và đối chiếu:

| Thiết bị | Host | Interfaces |
|---|---|---|
| R1 | 192.168.73.10 | mgmt0, srv0, users0 |
| SRV1 | 10.10.10.10 | lan0 |

Giữ protocol ssh lúc bắt đầu; chu kỳ15 s, CPU75%, RAM65%; monitor_temperature=false phù hợp VM thường không có cảm biến nhiệt.

**PowerShell Windows:**

```powershell
.\start.cmd
```

Trình duyệt: **http://127.0.0.1:8765**. Phải thấy **LAB THẬT**, hai thiết bị nhận mẫu mới, CPU/RAM không còn là số giả demo. Cần chờ ít nhất một chu kỳ; thẻ HTTP Chưa bật trong profile mặc định là đúng.

- `—`: chưa có số đo, không phải0%.
- CPU cảnh báo >75%, đã cảnh báo thì xuống≤70% mới phục hồi do hysteresis5.
- RAM cảnh báo >65%, phục hồi≤60%.
- Nhiệt độ không có sensor: để trống, không tự tạo giá trị.
- Màu xanh của link/node trong GNS3 không chứng minh SSH, IP hoặc cổng bên trong Linux đã đúng.

Chỉ chạy **một** phiên NetWatch. Muốn đổi demo/lab/profile: Ctrl+C phiên cũ trước, rồi khởi động phiên mới.

## 19. Chạy các phần Buổi5: web, CSV, RTT và iperf3

**SRV1 Ubuntu**, mở terminal riêng và giữ cửa sổ này chạy:

```bash
cd ~/netwatch-manual
python3 lab/web_demo.py
```

**Trình duyệt Windows:** http://10.10.10.10:8000/ phải mở được trang Web SRV1.

**PowerShell Windows:** Ctrl+C NetWatch cũ, rồi:

```powershell
.\start_buoi5.cmd
```

Profile Buổi5 dùng5 s/CPU85%/RAM90%, tự ghi `data/system_metrics.csv`; ICMP10 gói/đích và HTTP chạy mỗi 60s. HTTP phải200 và thời gian nhận header≤3s. Các phép đo này độc lập với vòng CPU5s.

Thử lỗi web tại SRV1: Ctrl+C web, chạy `python3 lab/web_demo.py --status 503`; chờ một chu kỳ health để nhận cảnh báo. Ctrl+C, chạy lại mặc định để phục hồi. Thử chậm bằng `python3 lab/web_demo.py --delay 4`, rồi trở lại mặc định. Không xem việc dừng trình duyệt Windows là dừng server web.

**Đo thông lượng:** SRV1 mở terminal khác, chạy:

```bash
iperf3 -s -B 10.10.10.10 -p 5201
```

**R1 Ubuntu**, mở terminal và chạy:

```bash
cd ~/netwatch-manual
python3 lab/iperf_test.py --target 10.10.10.10 --seconds 5 --mbps 20
```

Hai lượt R1→SRV1 và SRV1→R1, giới hạn tải20 Mbps; CSV ở `~/netwatch-manual/data/iperf_results.csv` trên R1. Đây là throughput nội bộ với tải giới hạn, không phải tốc độ Internet hay băng thông tối đa.

## 20. Các thử nghiệm cần chụp cho báo cáo

Dùng profile mặc định `start.cmd` để bắt đầu các thử nghiệm tài nguyên, rồi dùng Buổi5 cho web/CSV khi đã hiểu profile khác nhau.

| Thử nghiệm | Nơi/lệnh tác động | Kết quả cần thấy |
|---|---|---|
| CPU cao | SRV1 Ubuntu: `python3 ~/netwatch-manual/lab/load_test.py cpu --seconds 45 --workers 1` | CPU thực vượt ngưỡng → cảnh báo; hết tải và xuống vùng phục hồi → tin phục hồi |
| RAM tăng | SRV1 Ubuntu: `python3 ~/netwatch-manual/lab/load_test.py ram --target 75 --seconds 45` | Chỉ cảnh báo nếu số đo thật vượt ngưỡng; script giới hạn bộ nhớ, không ép VM thiếu RAM |
| Users interface DOWN | Console R1: `sudo ip link set users0 down` | R1 còn quản trị được, cổng users0 cảnh báo, VPCS mất đường |
| Khôi phục interface | Console R1: `sudo ip link set users0 up` | PC ping lại được, báo phục hồi |
| Mất SSH server | Console SRV1: `sudo systemctl stop ssh` | SRV1 mất số đo SSH; R1 còn dữ liệu |
| Khôi phục SSH | Console SRV1: `sudo systemctl start ssh` | Dữ liệu và thông báo phục hồi |
| HTTP503/chậm | Console SRV1: đổi chế độ web mẫu | ICMP có thể còn tốt nhưng web cảnh báo; trở lại200/nhanh thì phục hồi |

Những lệnh sudo thực hiện bằng user setup có quyền sudo ở console đúng VM, không phải tài khoản monitor và không phải PowerShell. RAM không lên ngưỡng do giới hạn cấp phát thì chưa có cảnh báo là đúng; ghi kết quả thật, không giả số liệu.

**Capture:** GNS3 chuột phải link SW-SERVERS↔SRV1 → Start capture → Wireshark. Từ Windows chạy Test-NetConnection hoặc NetWatch. Filter `tcp.port == 22` để thấy SYN/SYN-ACK/ACK và SSH; `tcp.port == 8000` để thấy HTTP; `icmp` để thấy Echo Request/Reply. Dừng capture khi có đủ số gói cần báo cáo, lưu pcapng cục bộ. ARP Request không có Reply là vấn đề kết nối L2; chưa đến bước kiểm tra mật khẩu.

**Điểm kiểm tra 8:** có cảnh báo và phục hồi thật, số đo Ubuntu/dashboard, route đúng và capture trên link GNS3. Ảnh demo không thay cho bằng chứng này.

## 21. Xuất báo cáo và thứ tự dùng hằng ngày

Dashboard → Báo cáo HTML ↓ → mở file tải về → Ctrl+P → Save as PDF. Có thể tải CSV riêng. Hoặc PowerShell trong VS Code:

```powershell
.\export_report.cmd --inventory inventory.buoi5.json
Start-Process .\data\NetWatch_bao_cao.html
```

Lệnh trên dùng sau khi có SQLite từ buổi chạy thật; nếu chạy profile mặc định, bỏ tham số --inventory để dùng inventory.json. Báo cáo là ảnh chụp dữ liệu tại lúc xuất, không tự cập nhật. Secret, database, VMX cục bộ và capture không đưa lên GitHub.

**Mỗi lần bật máy:**

1. Windows có Internet nếu cần gửi Telegram/Slack.
2. Mở đúng project `NETWATCH_MANUAL.gns3` trong GNS3.
3. Start all nodes, kiểm tra hai Ubuntu đã lên và có IP.
4. Nếu Windows vừa reboot, chạy lại route helper -Apply bằng admin.
5. Kiểm tra TCP22; bật web SRV1 nếu dùng Buổi5.
6. VS Code mở đúng thư mục code → chạy một profile NetWatch → mở trình duyệt.

**Khi kết thúc:** Ctrl+C NetWatch; Ctrl+C web/iperf server; tắt Ubuntu bằng sudo poweroff khi có thể; khi VM đã tắt, dừng/lưu project GNS3. Không cần tạo lại clone, đặt lại IP hoặc nhập token mỗi ngày.

## 22. Lỗi thường gặp và kiểm tra đúng chỗ

| Hiện tượng | Kiểm tra / xử lý |
|---|---|
| Test-Path setup.cmd=False | Terminal sai thư mục; File→Open Folder và mở terminal mới |
| py không nhận / mở Microsoft Store | Cài Python dự án và Launcher, mở terminal mới; GNS3 có Python riêng không đủ |
| Không thấy R1 trong VMware wizard | Kiểm tra VM đã đăng ký, vmrun và template đã có; không tạo trùng |
| Chỉ có một cổng R1 trên canvas | Node/template Network Adapters phải3, sửa node đã kéo nếu cần |
| Adapter reserved khi nối dây | Đang chọn R1 Ethernet0 NAT; dùng1 và2 |
| GNS3 yêu cầu máy chủ khác/GNS3 VM | Chọn chạy node trên local computer Windows |
| Ubuntu ensxx UP nhưng không có IPv4 | Cấu hình IP chưa áp dụng/nhầm MAC; kiểm tra netplan ở console đúng VM |
| nmcli báo strictly unmanaged | Cổng do networkd quản lý theo netplan; không bật thêm cấu hình NM cho cùng cổng |
| PC ping gateway fail | Kiểm tra dây Users, IP/gateway PC, users0 và VM đang chạy |
| PC ping gateway được nhưng server fail | R1 ip_forward=1, srv0, lan0 và gateway server |
| Windows đi tới server qua Wi-Fi | Route Windows chưa đúng; chạy helper và Find-NetRoute |
| Ping True nhưng TCP22 False | Ubuntu `sudo ss -lntp '( sport = :22 )'`, trạng thái ssh và firewall; ping không chứng minh SSH |
| TCP22 True nhưng app báo AuthenticationException | Sai user/password monitor; đặt lại bằng sudo passwd monitor ở console đúng VM rồi configure.cmd |
| Host key không khớp | Xác minh lại từ console đúng VM; không tự chấp nhận fingerprint từ thông báo mạng |
| Telegram ConnectionError | Internet/DNS/proxy Windows và token; outbox giữ tin để thử lại, chưa chắc SSH lỗi |
| Nhiệt độ hiển thị — | VM không có sensor, không phải lỗi số đo CPU/RAM |
| CPU cao liên tục | Dừng tải thử, xem top/vmstat, tránh nhiều Ubuntu desktop/phiên monitor; so sánh cùng cửa sổ đo |
| Cổng8765 đã dùng | Đóng phiên NetWatch cũ bằng Ctrl+C trước khi chạy phiên khác |

Nếu provision đã bắt đầu thay cấu hình nhưng bạn chọn nhầm: dùng console VMware, xem thư mục `/root/netwatch-backups/` và script restore.sh trong backup đúng thời điểm. Khôi phục file không khôi phục mọi trạng thái tiến trình trước đó; Ubuntu gốc vẫn là bản dự phòng.

## Phụ lục A. Nếu chưa có Ubuntu gốc

Nếu đã có Ubuntu chạy được thì bỏ qua phụ lục này.

1. Tải ISO Ubuntu Desktop 22.04 LTS amd64 từ nguồn chính thức Ubuntu; đây là phiên bản phù hợp môi trường OpenSSH8.9 trong các ảnh trước của bạn.
2. VMware → File → New Virtual Machine → Typical → Next.
3. Chọn I will install the operating system later → Linux → Ubuntu 64-bit.
4. Name=`Ubuntu-BASE`, Location thư mục riêng.
5. Disk khoảng30 GB, dùng đĩa ảo mới; không chọn đĩa vật lý Windows.
6. Customize Hardware: tạm cấp4 GB RAM và2 vCPU khi cài desktop nếu host đủ tài nguyên; Network Adapter=NAT.
7. CD/DVD → Use ISO image file → chọn ISO → Connect at power on → Finish.
8. Power on → Install Ubuntu → chọn ngôn ngữ/bàn phím.
9. Chọn Minimal installation nếu muốn giảm gói nền. Tại Installation type chọn **Erase disk and install Ubuntu → Install Now → Continue** cho **ổ đĩa ảo mới của VM này**. Không chạy trình cài Ubuntu trên Windows thật.
10. Chọn múi giờ Việt Nam; tạo username bạn nhớ, ví dụ tuanto, và mật khẩu riêng.
11. Install → Restart Now → tháo ISO/nhấn Enter khi được hỏi.
12. Đăng nhập, kiểm tra Internet NAT. Trong VM Settings → CD/DVD, bỏ Connect at power on sau khi cài để không boot lại ISO. Tắt VM rồi quay lại chặng3 để full clone hai máy lab. Các clone được cấp RAM/vCPU riêng sau khi cài.

## Phụ lục B. Clone một card NAT không nhận IP

Chỉ dùng trên **clone lab có đúng một card NAT**, trước khi gắn các card LAN; không chạy trên Ubuntu gốc, R1 đã có3 card hoặc máy Linux khác.

```bash
sudo mkdir -p /root/netwatch-before-bootstrap
sudo cp -a /etc/netplan/. /root/netwatch-before-bootstrap/
sudo rm -f /etc/netplan/*.yaml
sudo tee /etc/netplan/90-bootstrap.yaml >/dev/null <<'EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    bootstrap:
      match:
        name: "en*"
      dhcp4: true
      optional: true
EOF
sudo chmod 600 /etc/netplan/90-bootstrap.yaml
sudo systemctl enable --now systemd-networkd
sudo netplan generate
sudo netplan apply
ip -br addr
ip route
```

Phải có `192.168.73.x/24` và default gateway`192.168.73.2`. Nếu không, kiểm tra NAT/Connected/Connect at power on, dịch vụ VMware NAT/DHCP trên Windows và VMnet8 trước khi đổi cấu hình khác.

## Phụ lục C. UFW và tài nguyên VM

Provision không tự vô hiệu hóa UFW đang active. Trên Ubuntu clone, dùng `sudo ufw status verbose` để xác định. Với clone mới dành riêng cho lab, bạn có thể chủ động `sudo ufw disable` trên **clone đó**, rồi chạy lại provision để dùng bảng nftables minh họa của lab. Không làm trên Windows, Ubuntu gốc hoặc máy đang phục vụ công việc khác. Nếu giữ UFW, cần tự thiết kế chính sách forwarding phù hợp trước khi áp dụng; cho phép TCP22 riêng không đủ cho định tuyến giữa hai LAN.

Nếu host thiếu RAM/CPU khi mở hai desktop: sau khi cài gói và biết đăng nhập console, trên từng clone dùng `sudo systemctl set-default multi-user.target` rồi reboot. Lần sau dùng console chữ; khôi phục desktop bằng `sudo systemctl set-default graphical.target`. Khi ở console chữ, việc dán lệnh có thể khác terminal desktop, nên hoàn thành các bước cần clipboard trước. Có thể cấp1–2 GB/VM và đo lại; không khẳng định overhead thấp nếu chưa đo trên máy thật.

## Tài liệu đối chiếu giao diện

GNS3 GUI v2.2.61: `gns3/modules/vmware/ui/vmware_vm_wizard_ui.py`, `vmware_vm_configuration_page_ui.py`, `vmware_preferences_page_ui.py` tại https://github.com/GNS3/gns3-gui/tree/v2.2.61/gns3/modules/vmware. Giao diện và chức năng được đối chiếu từ mã nguồn; chưa thao tác GUI VMware/GNS3 trên máy Windows của bạn.
