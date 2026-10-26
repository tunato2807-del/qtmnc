# SSH phải đi xuyên GNS3: Windows TAP ↔ UDP ↔ switch ↔ Linux

Áp dụng cho trường hợp đã bắt được SYN/SYN-ACK nhưng Windows không hoàn tất TCP
qua Cloud gắn loopback. Trong file được phân tích, 15 gói TCP đều có checksum
IP và TCP hợp lệ.
Capture không ghi hướng RX/TX hay lý do kernel loại gói, nên chưa thể kết luận
chính xác driver/bộ lọc nào gây lỗi.

Cầu nối này đưa Ethernet vào **chiều nhận** của driver TAP-Windows V9 bằng
WriteFile. Nó không dùng pcap_sendpacket để đưa gói vào chính máy Windows.
**Cả chiều đi và chiều về SSH đều qua switch GNS3.**

~~~text
Python giám sát trên Windows
        │ 192.168.10.1 — GNS3-TAP (TAP-Windows V9)
        │ run_tap_windows.cmd — cửa sổ cần giữ mở
        │ UDP localhost: helper 30011 ↔ GNS3 30010
  Cloud-WINDOWS (UDP tunnels)
        │
     Switch1
        │
  Cloud-LINUX (VMnet2)
        │
  Ubuntu ens37 — 192.168.10.129/24, SSH TCP22

  Ubuntu ens33 vẫn NAT/VMnet8 để có Internet.
~~~

Đây là cách xử lý mới cần xác minh trên Windows thực tế. Mã đã có kiểm thử vận
chuyển Ethernet qua UDP và API TAP giả lập; môi trường phát triển Linux không
thể chạy driver TAP Windows của bạn.

## 1. Lấy code và cài thư viện trước, chưa hỏi mật khẩu/token

Trong Terminal Windows:

~~~powershell
cd D:\QTM_NC\telegram\qtmnc
git fetch origin
git merge --ff-only origin/main
.\setup_windows.cmd --with-tap --install-only
.\run_tap_windows.cmd --list
~~~

Lệnh --list chỉ liệt kê TAP-Windows V9, chưa mở card hoặc thay IP. Trong ảnh
Network Connections trước đó, máy bạn có **Local Area Connection** với mô tả
**TAP-Windows Adapter V9**. Đây là card cần dùng. Microsoft KM-TEST và
Npcap Loopback Adapter là các adapter khác.

Nếu không tìm thấy TAP V9, dùng driver TAP-Windows có chữ ký từ nguồn OpenVPN
chính thức: https://github.com/OpenVPN/tap-windows6 hoặc bộ cài OpenVPN phù hợp.
Không tải DLL/driver từ các trang chia sẻ không rõ nguồn. Không cần làm bước
cài driver nếu --list đã thấy adapter.

## 2. Chuyển IP .10.1 sang TAP

Nhấn Windows+R → nhập ncpa.cpl → Enter.

### 2.1 Bỏ IP thử nghiệm trên Microsoft KM-TEST

1. Chuột phải card **Ethernet — Microsoft KM-TEST Loopback Adapter**.
2. Properties → Internet Protocol Version 4 (TCP/IPv4) → Properties.
3. Chọn Obtain an IP address automatically → OK → Close.
4. Chuột phải chính card KM-TEST đó → Disable.

Mục đích là dành 192.168.10.1 cho TAP, tránh trùng IP. Card VMnet1 của bạn đã
chuyển .40.1 trước đó thì giữ nguyên. VMnet2 giữ .20.1; VMnet8 giữ .73.1.
Không đặt .10.x trên host adapter VMnet2 vì sẽ tạo đường trực tiếp bỏ qua GNS3.

### 2.2 Đặt TAP

1. Tìm **Local Area Connection — TAP-Windows Adapter V9**.
2. Nếu đang Disabled, chuột phải → Enable.
3. Chuột phải → Rename → đặt **GNS3-TAP**.
4. Chuột phải → Properties → chọn/tích IPv4 → Properties.
5. Chọn Use the following IP address:

| Ô | Giá trị |
|---|---|
| IP address | 192.168.10.1 |
| Subnet mask | 255.255.255.0 |
| Default gateway | Để trống |
| DNS | Để trống |

6. OK → Close.

**Network cable unplugged ở TAP trước khi chạy cầu nối là bình thường.**
Công cụ sẽ bật trạng thái cáp khi mở driver.

## 3. Gỡ đúng các ARP tĩnh đã dùng để chẩn đoán

PowerShell **Run as administrator**:

~~~powershell
Get-NetNeighbor -IPAddress 192.168.10.129 -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetNeighbor -Confirm:$false
~~~

Trong Ubuntu:

~~~bash
sudo ip neigh flush to 192.168.10.1 dev ens37 nud all
ip -br addr show dev ens37
~~~

nud all bao gồm entry Permanent đã tạo. ens37 vẫn cần có 192.168.10.129/24.
Không chạy lại script đổi tên interface nếu ens37 đã cấu hình đúng.

WeakHostReceive đã được bạn khôi phục sau phép thử thất bại. Cầu nối TAP không
yêu cầu bật weak-host.

## 4. Đổi Cloud-WINDOWS sang UDP tunnel

Trong GNS3, dùng project hiện tại:

1. Dừng capture Wireshark cũ nếu đang mở.
2. Xóa dây **Cloud-WINDOWS — Switch1** để có thể chỉnh cổng Cloud.
3. Chuột phải Cloud-WINDOWS → Configure.
4. Trong Ethernet interfaces, chọn mục Ethernet cũ → Delete.
5. Chuyển sang tab **UDP tunnels**.
6. Nhập:

| Trường của GNS3 | Giá trị |
|---|---|
| Local port | 30010 |
| Remote host | 127.0.0.1 |
| Remote port | 30011 |

7. Bấm Add → Apply → OK. Nếu có tên cổng, đặt TAP-UDP.
8. Add a link → Cloud-WINDOWS → cổng UDP vừa thêm → Switch1 Ethernet0.
9. Cloud-LINUX vẫn gắn **VMware Network Adapter VMnet2** → Switch1 Ethernet1.
10. Hai port switch access cùng VLAN1.

Cloud-WINDOWS **không gắn trực tiếp Ethernet/TAP trong tab Ethernet interfaces
hay TAP interfaces** ở phương án này. Cổng của nó là UDP; công cụ Python sở hữu
handle TAP và đưa frame vào chiều nhận của Windows.

Có mẫu sẵn **lab/gns3/QTMNC_TAP.gns3**. Nếu dùng mẫu, sao chép sang thư mục
Documents trước khi mở để GNS3 không sửa bản mẫu trong Git. Đóng project cũ
trước khi mở mẫu để tránh chiếm cổng UDP 30010.

## 5. Chạy cầu nối

Mở một **PowerShell bằng Run as administrator**, chạy:

~~~powershell
cd D:\QTM_NC\telegram\qtmnc
.\run_tap_windows.cmd
~~~

Chương trình cần tìm card GNS3-TAP và in MAC, phiên bản TAP, cặp cổng:

~~~text
UDP: 127.0.0.1:30011 <-> GNS3 127.0.0.1:30010
TAP -> GNS3: ... | GNS3 -> TAP: ... | Bỏ qua: ...
~~~

**Giữ cửa sổ này mở**, rồi mở/khởi chạy project GNS3. Nếu project đã mở nhưng
cầu nối không nhận frame, đóng/mở lại project sau khi cầu nối đã chạy để nạp
lại socket UDP. Kiểm tra hai đầu dây màu xanh.

Lưu ý cặp cổng đảo chiều có chủ ý:

- Công cụ Python bind 30011, gửi tới 30010.
- GNS3 bind 30010, gửi tới 30011.
- Cả hai chỉ dùng localhost, không mở UDP ra Internet.

## 6. Kiểm tra SSH

Trong một Terminal Windows khác:

~~~powershell
Get-NetAdapter -Name GNS3-TAP
Get-NetIPAddress -InterfaceAlias GNS3-TAP -AddressFamily IPv4
Test-NetConnection 192.168.10.129 -Port 22 -InformationLevel Detailed
~~~

Mong đợi:

~~~text
InterfaceAlias   : GNS3-TAP
SourceAddress    : 192.168.10.1
TcpTestSucceeded : True
~~~

Nếu False, ghi lại hai bộ đếm cầu nối và kết quả:

~~~powershell
$qtmncTapIndex = (Get-NetAdapter -Name GNS3-TAP).ifIndex
Get-NetNeighbor -InterfaceIndex $qtmncTapIndex -IPAddress 192.168.10.129 -ErrorAction SilentlyContinue
~~~

Không thêm ARP tĩnh để che lỗi. Mục tiêu là ARP tự học MAC Linux.

## 7. Chạy dự án giám sát

Khi phép thử SSH True:

~~~powershell
.\setup_windows.cmd --configure
.\run_windows.cmd --test
.\run_windows.cmd
~~~

Host vẫn **192.168.10.129**, user tuanto, MONITOR_IFACE=ens33.
Xác minh fingerprint bằng console Linux trước khi chấp nhận host key lạ.
.env.simple, token, mật khẩu và outbox cũ được giữ cục bộ.

## 8. Chứng minh SSH đi xuyên GNS3

1. Giữ cầu nối TAP và monitor đang chạy.
2. Trong GNS3, xóa một dây nối switch rồi thử lại SSH .10.129: phải mất kết nối.
3. Nối lại đúng port: SSH phục hồi.
4. Bắt gói trên hai dây; sau SYN và SYN-ACK cần có ACK cuối và dữ liệu SSH.
5. Giữ MONITOR_HOST=.10.129 khi trình diễn; .20.129 và .73.129 là đường trực
   tiếp khác, không chứng minh yêu cầu đi xuyên GNS3.

Muốn thử interface DOWN mà SSH còn hoạt động, ngắt Connected của card **NAT
ens33** trong VMware rồi bật lại, giữ ens37/VMnet2 Connected.

## Lỗi công cụ có thể báo

| Thông báo / bộ đếm | Kiểm tra |
|---|---|
| Không tìm thấy TAP | --list, mô tả TAP-Windows V9, tên GNS3-TAP |
| Access denied | Mở PowerShell bằng Run as administrator |
| Sharing violation / card đang bận | Đóng ứng dụng VPN đang dùng chính adapter TAP này |
| Cổng đang dùng | Đóng cầu nối/project trùng; không chạy hai bản trên cùng cặp UDP |
| TAP -> GNS3 tăng, chiều về 0 | GNS3 local server, hai dây, UDP 30010/30011, Cloud-LINUX VMnet2 |
| Hai chiều có frame nhưng không SSH | Kiểm tra TAP IP .10.1/24, Linux ens37 .10.129, ARP động và SSH |
| Dừng cầu nối | Ctrl+C; TAP trở lại cable unplugged; cấu hình IP vẫn còn |

Cửa sổ cầu nối cần quyền quản trị và phải giữ mở. Chương trình giám sát có thể
chạy trong Terminal thông thường.

Nguồn đối chiếu API:
[OpenVPN TAP-Windows IOCTL](https://github.com/OpenVPN/tap-windows6/blob/master/src/tap-windows.h),
[TAP nhận frame từ WriteFile](https://github.com/OpenVPN/tap-windows6/blob/master/src/rxpath.c),
[uBridge UDP NIO](https://github.com/GNS3/ubridge/blob/master/src/nio_udp.c).
