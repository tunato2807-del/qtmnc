# Kịch bản nghiệm thu và thu bằng chứng

Chỉ đánh dấu **Đạt** sau khi chạy trên máy Windows/GNS3 thực tế. Kết quả test phần mềm không thay thế phần này. Tạo bản sao [bảng kết quả](acceptance.csv) để ghi thời gian, số đo và đường dẫn ảnh.

Các mã bổ sung từ Buổi 5: **B501** đo10 ICMP/đích và so sánh RTT/loss; **B502** HTTP 200→503→200 và phản hồi chậm4s; **B503** iperf3 hai chiều, giới hạn20 Mbps; **B504** CSV tự ghi và báo cáo HTML/PDF. Làm theo [05_BUOI_5.md](05_BUOI_5.md), ghi kết quả thật vào acceptance.csv.

## Chuẩn bị

R1/SRV1/PC01/PC02 chạy; hai tuyến Windows đúng; NetWatch chạy chế độ thật; tài khoản/kênh đã nhập. Chụp mô hình GNS3, `ip -br addr` trên hai clone, `Find-NetRoute` và TCP22 thành công. Che token, mật khẩu và webhook trong mọi hình.

| Mã | Thao tác và nơi chạy | Kết quả cần quan sát |
|---|---|---|
| N01 | VPCS PC01: `ping 10.10.10.10` | Qua gateway R1, server phản hồi |
| N02 | Windows: `Find-NetRoute -RemoteIPAddress 10.10.10.10` | VMnet8, next hop `.73.10` |
| N03 | Windows: `Test-NetConnection 10.10.10.10 -Port 22` | TCP True; capture link GNS3 có handshake đầy đủ |
| M01 | Dashboard thật; Ubuntu kiểm tra `vmstat 1 8`, `free -m` | Có CPU/RAM cùng đơn vị/công thức; cửa sổ đo gần nhau |
| A01 | **SRV1 Ubuntu:** `python3 ~/netwatch-lab/lab/load_test.py cpu --seconds 45 --workers 1` | CPU vượt75% trên VM1vCPU → dashboard và tin cảnh báo |
| A02 | Chờ tải CPU tự dừng | CPU xuống≤70% → tin phục hồi; không lặp cảnh báo mỗi15s khi không đổi trạng thái |
| A03 | **SRV1 Ubuntu:** `python3 ~/netwatch-lab/lab/load_test.py ram --target 75 --seconds 45` | RAM vượt65% nếu đủ RAM dự phòng → cảnh báo; script tự giải phóng |
| A04 | **R1 console:** `sudo ip link set users0 down` | R1 còn quản trị được; báo interface users0 DOWN, PC mất đường mạng |
| A05 | **R1 console:** `sudo ip link set users0 up` | Cổng hoạt động trở lại; báo phục hồi |
| A06 | **SRV1 console:** `sudo systemctl stop ssh`; chờ một chu kỳ | R1 còn dữ liệu, SRV1 báo mất SSH; không gán CPU=0 |
| A07 | **SRV1 console:** `sudo systemctl start ssh` | Collector kết nối lại, số liệu và thông báo phục hồi xuất hiện |
| A08 | Ngắt Internet Windows tạm thời trong khi mạng VMware nội bộ vẫn chạy, tạo một cảnh báo có kiểm soát | Dashboard có thể tiếp tục lấy mẫu; số chờ gửi tăng khi API không truy cập được |
| A09 | Khôi phục Internet Windows | Tin được gửi lại, hàng đợi giảm; không cần tạo sự kiện mới |
| R01 | Dừng NetWatch → chạy lại | Lịch sử/trạng thái/hàng đợi còn; không phát lại toàn bộ cảnh báo cũ |
| R02 | GNS3 dừng R1; thử TCP22 server; bật lại R1 | Server mất đường qua router rồi phục hồi; chứng minh không dùng đường tắt |
| S01 | Làm theo cấu hình SNMP, đổi một thiết bị sang snmp | Có số liệu qua UDP161/extend; capture và dashboard ghi nguồn SNMP |
| E01 | Dashboard chọn SRV1 → Tải CSV | CSV có timestamp, host ID, nguồn, sample_kind=lab và số đo thật |

Nếu RAM không thể lên ngưỡng vì script giữ dự phòng 200MiB và giới hạn cấp phát, ghi **chưa tạo đủ tải**; không bỏ giới hạn an toàn. Có thể tạm giảm ngưỡng RAM trong inventory để kiểm thử logic, ghi rõ ngưỡng thử rồi khôi phục65%. Không giả số liệu nhiệt độ; máy không có sensor thì ghi **không hỗ trợ**.

## Đo độ trễ cảnh báo

Ghi `t0` lúc bắt đầu tác động, `t1` lúc dashboard đổi trạng thái, `t2` lúc nhận tin. Đo ít nhất ba lần CPU/interface/mất SSH. Tính `t1−t0`, `t2−t0`; ghi min/trung bình/max cùng chu kỳ15s và điều kiện Internet. Không dùng timestamp khác múi giờ hoặc đồng hồ chưa đồng bộ để suy ra độ trễ.

## Đo tác động giám sát

Mỗi thiết bị: chờ tải ổn định → dừng NetWatch → `vmstat 1 31`, bỏ dòng đầu, ghi trung bình `100−id` → chạy NetWatch → đo lại 30 mẫu. Lặp điều kiện giống nhau; ghi tài nguyên host/VM và ứng dụng nền. Không so sánh một mẫu CPU cao ngắn hạn với trung bình30s.

## Đọc capture khi kết nối lỗi

- **Không ARP/SYN:** kiểm tra địa chỉ, route, node/link và VMnet đã gán.
- **Có SYN, không SYN/ACK:** kiểm tra SSH listener/firewall/đường trả về server.
- **Có SYN và SYN/ACK, thiếu ACK:** kiểm tra đường trả về Windows và bắt gói cả hai phía; không kết luận mật khẩu sai vì chưa xong TCP.
- **Có SSH handshake rồi lỗi xác thực:** kiểm tra account monitor, mật khẩu và host key; không tắt host key validation.

## Bảo mật và giới hạn nghiệm thu

Không push `.env.netwatch`, file DB, VMX có đường dẫn cá nhân, VM disk, capture nhạy cảm hoặc ảnh token. Xác nhận `git check-ignore .env.netwatch data/netwatch.sqlite3 .local/known_hosts`. Tỷ lệ mẫu kết nối thành công chỉ là chỉ báo theo mẫu, không tự gọi SLA thời gian. Luật Users→Servers là minh họa ACL; không phải thiết kế firewall hoàn chỉnh.
