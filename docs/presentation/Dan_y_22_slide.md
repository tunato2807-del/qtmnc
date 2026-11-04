---
[SLIDE 1: Giám sát thiết bị và cảnh báo]

- Thông điệp cốt lõi: NetWatch kết hợp mạng định tuyến GNS3 với giám sát Python và thông báo tập trung.
- Bài toán: Theo dõi CPU, RAM, nhiệt độ và interface.
- Giải pháp: Windows thu thập dữ liệu từ R1 và SRV1.
- Đầu ra: Dashboard, lịch sử, cảnh báo và phục hồi.
- Số liệu/Minh chứng: Phạm vi thiết kế: 2 thiết bị Linux, 2 mạng LAN, 6 node GNS3.
- Gợi ý trực quan: Ba khối bài toán–giải pháp–đầu ra.

---
[SLIDE 2: Bài toán quản trị cần giải quyết]

- Thông điệp cốt lõi: Số đo tập trung và cảnh báo có kiểm soát giúp phát hiện sự cố dễ hơn.
- Quan sát: Log rời rạc khó theo dõi xu hướng.
- Thông báo: Tin lặp mỗi chu kỳ dễ gây nhiễu.
- Tin cậy: Lỗi API cần hàng đợi gửi lại.
- Số liệu/Minh chứng: Cơ sở: Chương 5, trang PDF 23–26 về cảnh báo và dashboard.
- Gợi ý trực quan: Ba thẻ vấn đề và tác động.

---
[SLIDE 3: Mục tiêu và phạm vi đồ án]

- Thông điệp cốt lõi: Giữ trọng tâm giám sát, bổ sung mô hình mạng để kiểm chứng đường đi.
- Thiết bị: R1 router Linux và SRV1 server Linux.
- Chức năng: Thu thập, lưu trữ, phân tích và cảnh báo.
- Phạm vi: VPN và SDN thuộc hướng mở rộng.
- Số liệu/Minh chứng: Thiết kế hiện tại không triển khai controller OpenFlow hoặc VPN.
- Gợi ý trực quan: Ba vùng thiết bị–chức năng–phạm vi.

---
[SLIDE 4: Liên hệ kiến thức môn học]

- Thông điệp cốt lõi: Thiết kế vận dụng quản trị hiệu suất, tự động hóa và bảo mật.
- FCAPS: Trọng tâm quản lý lỗi và hiệu suất.
- Python: JSON, Paramiko, xử lý lỗi và kiểm thử.
- Bảo mật: Phân đoạn, ít quyền và bảo vệ secret.
- Số liệu/Minh chứng: Nguồn: 7 PDF, tổng 265 trang; bảng đối chiếu trong báo cáo.
- Gợi ý trực quan: Sơ đồ ba trụ cột kiến thức.

---
[SLIDE 5: Thiết bị sử dụng và vai trò]

- Thông điệp cốt lõi: Ubuntu đảm nhiệm router/server; VPCS dùng kiểm tra đường mạng.
- Ubuntu: Hai full clone độc lập chạy R1 và SRV1.
- Switch: Hai switch L2 nối hai nhánh LAN.
- VPCS: PC01, PC02 tạo lưu lượng thử nghiệm.
- Số liệu/Minh chứng: 6 node GNS3 = 2 Ubuntu VMware + 2 switch + 2 VPCS.
- Gợi ý trực quan: Ba nhóm thiết bị kèm số lượng.

---
[SLIDE 6: Mô hình mạng định tuyến mới]

- Thông điệp cốt lõi: R1 là điểm định tuyến giữa Windows, mạng Servers và mạng Users.
- Quản trị: Windows đi tới card NAT gốc của R1.
- Servers: SRV1 nằm sau switch và router.
- Users: Hai VPCS dùng gateway của R1.
- Số liệu/Minh chứng: Không có node Cloud; adapter 0 của R1 không nối link GNS3.
- Gợi ý trực quan: Topology router trung tâm, hai nhánh LAN.

---
[SLIDE 7: Quy hoạch địa chỉ IP]

- Thông điệp cốt lõi: Ba subnet riêng giúp phân biệt quản trị, server và người dùng.
- Quản trị: 192.168.73.0/24; R1 dùng .10.
- Servers: 10.10.10.0/24; SRV1 dùng .10.
- Users: 10.20.20.0/24; PC01/02 dùng .10/.20.
- Số liệu/Minh chứng: Gateway LAN: 10.10.10.1 và 10.20.20.1; NAT VMware: 192.168.73.2.
- Gợi ý trực quan: Ba thẻ subnet và gateway.

---
[SLIDE 8: Đường đi và phân đoạn mạng]

- Thông điệp cốt lõi: Windows cần route qua R1 để quản trị máy chủ SRV1.
- Tuyến: Hai mạng LAN dùng next hop 192.168.73.10.
- NAT: R1 masquerade hai LAN khi ra mgmt0.
- ACL: Users bị chặn TCP22 và UDP161 tới Servers.
- Số liệu/Minh chứng: Luật minh họa trong bảng nftables riêng; ICMP vẫn được phép.
- Gợi ý trực quan: Sơ đồ đường gói tin và điểm áp dụng ACL.

---
[SLIDE 9: Ánh xạ VMware và GNS3]

- Thông điệp cốt lõi: GNS3 quản lý cổng LAN, còn NAT gốc giữ đường quản trị Windows.
- R1: Adapter 0 NAT; adapter 1/2 là LAN.
- SRV1: Một Custom adapter nối SW-SERVERS.
- VMnet: Ba mạng riêng, DHCP tắt, CIDR không trùng.
- Số liệu/Minh chứng: use_any_adapter=false; generator yêu cầu hai file VMX thật.
- Gợi ý trực quan: Bảng ánh xạ card vật lý ảo và cổng Linux.

---
[SLIDE 10: Kiến trúc phần mềm giám sát]

- Thông điệp cốt lõi: Thu thập, lưu trữ và gửi tin chạy thành các luồng độc lập.
- Collector: Một worker riêng cho mỗi thiết bị.
- SQLite: Lưu mẫu, trạng thái, sự kiện và outbox.
- Web: Đọc dữ liệu để hiển thị và xuất CSV.
- Số liệu/Minh chứng: Chu kỳ mặc định 15 giây; timeout 12 giây.
- Gợi ý trực quan: Pipeline probe → collector → store → web/kênh tin.

---
[SLIDE 11: Thu thập qua SSH]

- Thông điệp cốt lõi: Một probe nhỏ trên phiên SSH giữ sẵn giúp giảm công việc lặp.
- Danh tính: Xác minh SHA256 từ console Ubuntu.
- Lấy mẫu: Một lệnh Python đọc proc/sys mỗi chu kỳ.
- Ít quyền: Tài khoản monitor không cần sudo.
- Số liệu/Minh chứng: Kiểm thử loopback: hai lần exec dùng cùng một transport SSH.
- Gợi ý trực quan: Sơ đồ manager–SSH–probe.

---
[SLIDE 12: Tùy chọn thu thập SNMP]

- Thông điệp cốt lõi: Net-SNMP extend trả cùng JSON probe để dùng chung logic giám sát.
- Agent: Extend netwatch trên UDP161.
- Manager: PySNMP đọc dữ liệu theo OID extend.
- Giới hạn: SNMPv2c chỉ dùng trong lab riêng.
- Số liệu/Minh chứng: SNMPv3 chưa được triển khai; không dùng OID nhiệt độ giả định.
- Gợi ý trực quan: Luồng SNMP manager–agent–probe.

---
[SLIDE 13: Các chỉ số và công thức]

- Thông điệp cốt lõi: Số đo thiếu phải được phân biệt với mức sử dụng bằng 0.
- CPU: Hai snapshot cách 1s; không cộng đôi guest.
- RAM: Dùng MemAvailable để tính tỷ lệ đã dùng.
- Interface: Đọc trạng thái và chênh lệch byte counters.
- Số liệu/Minh chứng: CPU/RAM: 0–100%; lưu lượng: Mbps; nhiệt độ không có sensor để trống.
- Gợi ý trực quan: Ba thẻ chỉ số và đơn vị.

---
[SLIDE 14: Trạng thái cảnh báo và phục hồi]

- Thông điệp cốt lõi: Ngưỡng và vùng phục hồi giúp tránh cảnh báo dao động liên tục.
- Ngưỡng: CPU >75%, RAM >65% trong thiết kế lab.
- Phục hồi: CPU ≤70%, RAM ≤60% sau cảnh báo.
- Thiếu dữ liệu: UNKNOWN giữ trạng thái hợp lệ trước đó.
- Số liệu/Minh chứng: Hysteresis 5 đơn vị; nhiệt độ >65°C chỉ áp dụng khi bật và có sensor.
- Gợi ý trực quan: Sơ đồ OK ↔ ALERT ↔ UNKNOWN.

---
[SLIDE 15: Gửi tin và xử lý lỗi]

- Thông điệp cốt lõi: Cảnh báo được lưu trước khi gửi để có thể thử lại khi mạng lỗi.
- Gộp tin: Một thiết bị/chu kỳ gửi một tin mỗi kênh.
- Thử lại: Lỗi API giữ nguyên tin trong outbox.
- Phục hồi: Restart tiếp tục xử lý hàng đợi cũ.
- Số liệu/Minh chứng: Backoff 2, 4, 8… tối đa 300s; 429 theo Retry-After; at-least-once.
- Gợi ý trực quan: Sơ đồ hàng đợi và nhánh gửi lại.

---
[SLIDE 16: Dashboard và dữ liệu lịch sử]

- Thông điệp cốt lõi: Một màn hình kết hợp hiện trạng, xu hướng và sự kiện.
- Thiết bị: CPU/RAM, nhiệt độ, cổng và Rx/Tx Mbps.
- Xu hướng: Chọn R1/SRV1, xem biểu đồ và tải CSV.
- Tính mới: Đánh dấu mẫu cũ, không giả số đo thiếu.
- Số liệu/Minh chứng: Web localhost:8765; tối đa 24h, 5.000 mẫu/thiết bị, 1.000 sự kiện.
- Gợi ý trực quan: Wireframe bốn vùng dashboard.

---
[SLIDE 17: Bảo mật và quản lý cấu hình]

- Thông điệp cốt lõi: Quyền tối thiểu và secret cục bộ là điều kiện vận hành cơ bản.
- Secret: .env.netwatch bị Git bỏ qua.
- SSH: Pin host key, từ chối key chưa kiểm chứng.
- Thay đổi: Provision có bản xem trước và backup.
- Số liệu/Minh chứng: Web chỉ localhost; chưa có xác thực để công khai ra LAN/Internet.
- Gợi ý trực quan: Ba lớp secret–truy cập–phục hồi cấu hình.

---
[SLIDE 18: Quy trình triển khai từng bước]

- Thông điệp cốt lõi: Hoàn thiện đường mạng trước khi chạy giám sát thật.
- Chuẩn bị: Full clone, cài gói, gắn đúng card.
- Dựng lab: Chọn VMX, Start node, provision và route.
- Vận hành: Nhập secret, trust host key, mở dashboard.
- Số liệu/Minh chứng: Hướng dẫn chia rõ lệnh Windows, console Ubuntu và console VPCS.
- Gợi ý trực quan: Ba giai đoạn chuẩn bị–mạng–ứng dụng.

---
[SLIDE 19: Kịch bản thử nghiệm đồ án]

- Thông điệp cốt lõi: Mỗi chức năng phải có tác động, quan sát và bằng chứng phục hồi.
- Tài nguyên: Tải CPU/RAM có thời hạn 45s.
- Kết nối: Tắt/bật users0 hoặc SSH của SRV1.
- Tin nhắn: Ngắt/khôi phục Internet để thử hàng đợi.
- Số liệu/Minh chứng: Đo t0 tác động, t1 dashboard, t2 nhận tin; tối thiểu 3 lần/kịch bản.
- Gợi ý trực quan: Ma trận tác động–cảnh báo–phục hồi.

---
[SLIDE 20: Kết quả xác minh hiện có]

- Thông điệp cốt lõi: Phần mềm đã kiểm thử; nghiệm thu VMware/GNS3 thật còn phải bổ sung.
- Tự động: 26 test logic, DB, web và lab đạt.
- Giao thức: SSH/SNMP trao đổi qua loopback thật.
- Nghiệm thu: Checklist Windows/GNS3 để CHUA_CHAY.
- Số liệu/Minh chứng: Ảnh dashboard dùng dữ liệu MÔ PHỎNG; không là số đo VM thật.
- Gợi ý trực quan: Hai cột đã kiểm thử và cần nghiệm thu.

---
[SLIDE 21: Giới hạn và hướng phát triển]

- Thông điệp cốt lõi: Các cải tiến tiếp theo cần dựa trên đo lường của lab thực tế.
- Giới hạn: R1 là điểm lỗi đơn; VM thiếu sensor nhiệt.
- Đo lường: So sánh tải nền, overhead và độ trễ.
- Mở rộng: SSH key, SNMPv3, xác thực web và HA.
- Số liệu/Minh chứng: Chưa có số liệu overhead, SLA hoặc độ trễ cảnh báo trên máy người dùng.
- Gợi ý trực quan: Lộ trình ba mức ưu tiên.

---
[SLIDE 22: Kết luận và hành động tiếp theo]

- Thông điệp cốt lõi: Hoàn tất nghiệm thu để chuyển thiết kế thành bài báo cáo có bằng chứng.
- Dựng đúng: Hai Ubuntu, hai LAN, đường đi qua R1.
- Đo thật: CPU/RAM/interface, cảnh báo và phục hồi.
- Báo cáo: Bổ sung ảnh, capture, thời gian và nhận xét.
- Số liệu/Minh chứng: Sản phẩm: mã nguồn, generator GNS3, dashboard, hướng dẫn và báo cáo.
- Gợi ý trực quan: Checklist bàn giao và nghiệm thu.
