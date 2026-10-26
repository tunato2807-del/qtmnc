# Giám sát Linux qua GNS3 — bản dễ học

**Windows chạy Python trong VS Code → GNS3 → SSH tới Linux → Telegram/Slack.**
Chương trình xem CPU, RAM, nhiệt độ và trạng thái card mạng, gửi cảnh báo khi lỗi
và khi phục hồi.

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

Bản đơn giản chọn SSH cho hướng đề tài "SNMP/SSH". Nếu bắt buộc cả hai giao thức,
dùng bản mở rộng: py -3 setup_project.py --profile gns3 --configure, rồi
python -m device_monitor --env-file .env.gns3. .env và .env.gns3 cũ được giữ nguyên.

Kiểm thử: python -m unittest discover -s tests -v. Bộ test dùng mock/loopback,
không gửi tin tới tài khoản thật. GNS3/Npcap/VMware cần kiểm tra trên Windows.
