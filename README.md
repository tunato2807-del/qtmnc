# Hệ thống giám sát thiết bị và cảnh báo Telegram/Slack

**Windows chạy Python trong VS Code → GNS3 → SSH tới Linux → Telegram/Slack.**
Chương trình xem CPU, RAM, nhiệt độ và trạng thái card mạng, gửi cảnh báo khi lỗi
và khi phục hồi.

**Xem [6 mô hình trực quan và giải thích từ đầu đến cuối](docs/truc_quan/README.md).**
Tải [index.html](docs/truc_quan/index.html) rồi mở bằng Chrome/Edge để thử tăng
RAM, ngắt interface, mất SSH và mất Internet trong mô phỏng. Trang chạy offline,
không điều khiển thiết bị và không gửi tin thật. Có PNG/SVG và PDF đi kèm.
[Tải trọn bộ trực quan dạng ZIP](docs/truc_quan/QTMNC_TrucQuan.zip).

**[Tải slide PowerPoint 22 trang](docs/slides/QTMNC_Executive_Thuyet_trinh.pptx)**
(cỡ chữ tối thiểu 20 pt, có thể sửa trực tiếp) · [Dàn ý chi tiết](docs/slides/QTMNC_Dan_y_22_slide.md) ·
[Hướng dẫn dùng slide](docs/slides/README.md).

**Làm theo [HUONG_DAN_DON_GIAN.md](HUONG_DAN_DON_GIAN.md), từ bước 1 đến bước 6.**

![Mô hình GNS3 đơn giản](docs/simple/topology.png)

Chỉ **2 Cloud + 1 Ethernet switch** trong GNS3. Linux dùng 2 card VMware:

| Card Linux | Địa chỉ | Vai trò |
|---|---|---|
| ens33, NAT/VMnet8 | 192.168.73.129 nếu DHCP chưa đổi | Internet Linux và card được theo dõi |
| gns3mgmt, VMnet2 | 192.168.10.129 | SSH qua GNS3 |

Windows VMnet1 .10.1 → Cloud → switch → Cloud VMnet2 → Linux .10.129.
Windows VMnet2 để .20.1 như hướng dẫn, để đường SSH đi qua GNS3.
Chưa cần router, VPCS, GNS3 VM, SNMP agent hoặc card VMware thứ ba.

## Tải hoặc cập nhật

Tải lần đầu trong Terminal VS Code:

~~~powershell
git clone https://github.com/tunato2807-del/qtmnc.git
cd qtmnc
code .
~~~

Bạn đã có dự án:

~~~powershell
cd D:\QTM_NC\telegram\qtmnc
git fetch origin
git merge --ff-only origin/main
~~~

Không chép số thứ tự hoặc dấu PS ...> trước lệnh. Nếu Git báo có sửa đổi cục bộ,
giữ lại và xử lý trước khi merge; không reset --hard.

## Cài và chạy

Sau khi nối mạng và SSH được 192.168.10.129 theo hướng dẫn:

~~~powershell
.\setup_windows.cmd --configure
.\run_windows.cmd --test
.\run_windows.cmd
~~~

Windows cần Python 3.10+. Bộ cài tự tạo .venv và cài thư viện SSH, HTTP, dotenv,
Rich; không cần cài SNMP cho bản này. Chỉ hỏi IP, tài khoản, card mạng, mật khẩu
và nơi nhận tin. Cấu hình lưu ở .env.simple, tự lấy lại secret từ file cũ cục bộ.
Mật khẩu gõ không hiện ký tự là bình thường.

--test gửi tin thử thật. --once đọc một lần rồi dừng. F5 chạy cùng bản này.
Mỗi vòng đọc xong chờ 5 giây. Ctrl+C dừng; tin chưa gửi được giữ để thử lại.
Token/mật khẩu không nằm trong code và không được đẩy GitHub.

Collector giữ lại kết nối SSH và gom các chỉ số Linux vào **một lệnh mỗi lượt**,
giảm số lần xác thực và tạo phiên trên Ubuntu. Nếu CPU tăng cao khi bật monitor
hoặc SSH hay timeout, xem [hướng dẫn đối chiếu và cập nhật](docs/SSH_CPU_TROUBLESHOOTING.md).

## Đọc code theo thứ tự

1. Mở **monitor.py**: luồng chính được đánh dấu bốn bước.
2. Xem **examples/simple.env** để biết các giá trị cấu hình.
3. Sửa ngưỡng trong **.env.simple** do bộ cài tạo.
4. Khi cần hiểu chi tiết, đọc dần thư mục device_monitor.

Chi tiết SSH, tính chỉ số và gửi lại tin dùng phần mã đã kiểm thử.
File monitor.py tập trung vào luồng chạy để bạn dễ học và trình bày.

| Mặc định | Cảnh báo | Phục hồi |
|---|---|---|
| CPU | >75% | <=70% |
| RAM | >65% | <=60% |
| Nhiệt độ | >65°C | <=60°C |
| Interface | DOWN | UP |

VM thường không có cảm biến nhiệt độ, nên UNKNOWN là đúng. Có thể chủ động tắt,
hoặc dùng demo có nhãn MÔ PHỎNG theo hướng dẫn; không giả thành số đo phần cứng.
Chỉ gửi khi đổi trạng thái, tránh lặp tin mỗi vòng. Đây là polling gần thời gian
thực; mạng chậm và retry có thể làm tin tới muộn.

## Khi cần mở rộng

- [Hướng dẫn SNMP/hybrid, mạng thử riêng](docs/GNS3_LAB.md).
- [Thiết kế chi tiết](docs/ARCHITECTURE.md).
- [Kịch bản nghiệm thu mở rộng](docs/TEST_PLAN.md).
- [Bộ 8 sơ đồ Word/PDF của mô hình mở rộng](docs/diagrams/README.md).

Với lab Windows đã bắt được SYN-ACK nhưng không kết nối qua Cloud/loopback,
xem [cách hỗ trợ kết nối TAP/UDP](WINDOWS_TAP_GNS3.md). Đây là công cụ hỗ trợ
mạng của lab hiện tại, không phải chức năng bắt buộc của đề tài.

Bản đơn giản chọn SSH cho hướng đề tài "SNMP/SSH". Nếu bắt buộc cả hai giao thức,
dùng bản mở rộng: py -3 setup_project.py --profile gns3 --configure, rồi
python -m device_monitor --env-file .env.gns3. .env và .env.gns3 cũ được giữ nguyên.

Kiểm thử: python -m unittest discover -s tests -v. Bộ test dùng mock/loopback,
không gửi tin tới tài khoản thật. GNS3/Npcap/VMware cần kiểm tra trên Windows.
