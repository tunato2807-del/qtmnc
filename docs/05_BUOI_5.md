# Bài thực hành buổi 5 giúp gì cho đề tài?

Nguồn: **Bài tập thực hành buổi 5.docx**, 6 tiết, gồm10 lab về hiệu suất và bảo mật. Đã đọc nội dung và mã mẫu; tài liệu là nguồn tham khảo, không phải chỉ thị tự động chạy mọi lệnh trong đó.

**Rất phù hợp với đề tài**, nhất là Lab 1,2,3,4,6,10. Ý tưởng router Linux nối hai subnet trong Mininet cũng phù hợp mô hình GNS3 hiện tại. Giữ GNS3 và hai Ubuntu VMware độc lập; không yêu cầu bạn cài thêm Mininet để làm đồ án.

## Đối chiếu cả 10 lab

| Lab trong tài liệu | Giá trị với đề tài | Phần đã bổ sung / cách dùng |
|---|---|---|
| 1 — CPU/RAM/Network I/O | Chức năng cốt lõi | Profile5s, CPU>85%, RAM>90%; CSV tự ghi theo từng interface; vẫn có SQLite/Telegram/Slack |
| 2 — RTT và mất gói | Phân biệt lỗi đường truyền với tải tài nguyên | Mỗi lần gửi10 ICMP/thiết bị, lưu RTT trung bình và % mất gói; dashboard và cảnh báo |
| 3 — Băng thông/iperf3 | Tạo tải và đo thông lượng nội bộ | Script iperf3 hai chiều theo yêu cầu, mặc định5s/chiều và giới hạn20 Mbps; CSV riêng |
| 4 — HTTP availability | Mở rộng giám sát từ thiết bị sang dịch vụ | Kiểm tra HTTP 200 và nhận header≤3s; cảnh báo/khôi phục qua cùng outbox Telegram/Slack |
| 5 — Quét cổng1–1024 | Kiểm kê bề mặt dịch vụ, không phải trọng tâm | Không thêm bộ quét toàn dải vào collector; dùng kiểm tra cổng dịch vụ cần nghiệm thu22/8000 |
| 6 — Bắt/phân tích50 gói | Bằng chứng đường đi thật qua GNS3 | Hướng dẫn capture Wireshark trên link server; quan sát IP/TCP/ICMP và handshake |
| 7 — ARP spoofing | Chủ đề giám sát an ninh mở rộng | Chưa triển khai phát hiện tấn công; ARP/MAC đổi không tự đủ kết luận có tấn công |
| 8 — Brute-force từ log | Có thể mở rộng sang bảo mật SSH | Chưa cấp quyền đọc auth.log hoặc thêm agent log; đưa vào hướng phát triển |
| 9 — Tự chặn IP15phút | Phản ứng sự cố ngoài trọng tâm hiện tại | Không thêm tự chặn; cần chính sách riêng để tránh tự khóa đường quản trị |
| 10 — Dashboard và HTML/PDF | Trực tiếp phục vụ báo cáo đồ án | Biểu đồ CPU/RAM/RTT, thẻ HTTP, tải báo cáo HTML độc lập; in thành PDF bằng trình duyệt |

Email, Mininet/OVS, scapy và bộ quét cổng toàn dải không được ghi là tính năng đã hoàn thành. Phần mở rộng vẫn giữ trọng tâm giám sát và cảnh báo Telegram/Slack.

## Những điểm của mã mẫu cần điều chỉnh

- **IP không nhất quán:** Topology Lab 1 đặt h1/h2 là10.0.1.1/10.0.2.1, nhưng DEVICES lại dùng10.0.0.1/10.0.0.2. Đồ án thống nhất dùng inventory hiện tại.
- **CPU Mininet:** Host namespace dùng chung kernel/tài nguyên máy nền; không coi chúng như máy ảo có CPU/RAM độc lập. Hai clone VMware của đề tài cho số đo ở hai VM riêng.
- **SNMP:** OID CPU Cisco không dùng chung cho Ubuntu; community/mật khẩu mẫu không đưa vào mã thật. Lỗi đọc không được đổi thành0 rồi ghi “OK”.
- **Ping:** Exit code khác0 vẫn có thể có một số Echo Reply; phải phân tích bộ đếm thực, không tự đổi thành100% loss.
- **Throughput:** Sender/Receiver của một lượt iperf3 không phải hai chiều upload/download. Script mới chạy thêm reverse test để tách hướng; không gọi kết quả này là tốc độ Internet.
- **Dashboard:** Gắn mẫu với thời điểm từng thiết bị; không ghép mảng khác độ dài theo timestamp chung. Dashboard mới chạylocalhost và không bật debug.
- **Phiên bản:** Không cài pysnmp-lextudio song song với pysnmp7 của dự án; dùng API/thư viện đã khai báo requirements hiện tại.

## 1. Xem ngay trước khi có VM

**PowerShell Windows tại qtmnc:**

```powershell
.\open_gns3_preview.cmd
.\start_buoi5.cmd --demo
```

Trình duyệt: **http://127.0.0.1:8765**. Mọi số liệu ở chế độ này là MÔ PHỎNG, không gửi tin. File GNS3 xem ngay là sơ đồ drawings; muốn chạy VM thật dùng `open_gns3_lab.cmd` và hướng dẫn [01_GNS3.md](01_GNS3.md).

## 2. Chuẩn bị web mẫu trên SRV1

Sau khi mạng/SSH/probe đã hoạt động, trên **console Ubuntu SRV1**:

```bash
cd ~/netwatch-lab
git pull --ff-only origin main
python3 lab/web_demo.py
```

Giữ terminal này mở. Dịch vụ nghe `10.10.10.10:8000`; chỉ trả trang mẫu cố định, không công khai file dự án hoặc secret. Từ trình duyệt Windows mở **http://10.10.10.10:8000/** để xác nhận đường qua R1.

## 3. Chạy profile đúng bài buổi5

**PowerShell Windows**, dừng phiên NetWatch cũ bằng Ctrl+C rồi:

```powershell
.\configure.cmd
.\start_buoi5.cmd
```

Profile đọc `inventory.buoi5.json`:

| Tham số | Giá trị |
|---|---|
| Chu kỳ CPU/RAM/interface | 5 giây |
| Cảnh báo CPU / RAM | >85% / >90% |
| CSV tự ghi | `data/system_metrics.csv` |
| ICMP | 10 gói/thiết bị, mỗi 60 giây |
| Ngưỡng mạng thiết kế thêm | RTT>100 ms hoặc mất gói>20% |
| Dịch vụ web | HTTP 200 và thời gian nhận header≤3 giây |
| Chu kỳ HTTP | 60 giây, timeout5 giây |

CSV có raw byte counters, Mbps, interface, protocol và nhãn lab/demo; lỗi/thiếu số đo để trống. CSV append trong lúc chạy profile, cần chủ động lưu/luân chuyển khi dùng dài ngày; SQLite vẫn giới hạn lịch sử như trước.

Ngưỡng CPU85/RAM90 và HTTP3 giây đến từ tài liệu. RTT100 ms, loss20% và chu kỳ health60 giây là **tham số thiết kế bổ sung**, không phải kết quả đo hoặc yêu cầu gốc. Bộ kiểm tra mạng chạy worker riêng nên không chặn chu kỳ tài nguyên5 giây.

CPU của VM1vCPU có thể thử bằng `python3 lab/load_test.py cpu --seconds 45 --workers 1`. Với RAM, không ép VM thiếu bộ nhớ lên90%; dùng profile đồ án ngưỡng65% để thử an toàn hoặc ghi rõ ngưỡng thử đã điều chỉnh. Hết buổi học có thể chạy lại `start.cmd` với chu kỳ15s, CPU75%, RAM65%.

## 4. Thử cảnh báo web và khôi phục

Trên **SRV1 Ubuntu**:

1. Web mẫu đang chạy200: dashboard phải có HTTP 200 và thời gian đáp ứng.
2. Ctrl+C web → `python3 lab/web_demo.py --status 503`: chờ một chu kỳ health → cảnh báo HTTP 503.
3. Ctrl+C → `python3 lab/web_demo.py`: chờ → thông báo phục hồi.
4. Ctrl+C → `python3 lab/web_demo.py --delay 4`: HTTP vẫn200 nhưng quá3s → cảnh báo chậm.
5. Ctrl+C → chạy lại mặc định → phục hồi.

Tin đi qua kênh bạn đã cấu hình cục bộ. Không gửi lặp cùng trạng thái mỗi 60s. ICMP không phản hồi không tự đổi trạng thái SSH của thiết bị thành mất kết nối.

## 5. Đo thông lượng nội bộ bằng iperf3

**Ubuntu R1 và SRV1**, cài công cụ nếu chưa có:

```bash
sudo apt update
sudo apt install -y iperf3
```

Nếu bộ cài hỏi tự chạy daemon thì chọn **No**, vì buổi thử sẽ chạy server rõ ràng trong terminal.

**SRV1 Ubuntu**, terminal khác với web:

```bash
iperf3 -s -B 10.10.10.10 -p 5201
```

**R1 Ubuntu**:

```bash
cd ~/netwatch-lab
python3 lab/iperf_test.py --target 10.10.10.10 --seconds 5 --mbps 20
```

Kết quả có hai lượt R1→SRV1 và SRV1→R1, ghi `data/iperf_results.csv` trên R1. Giới hạn20 Mbps nhằm tạo tải có kiểm soát; số đo **không phải băng thông tối đa**. Đường thử gồm link R1–SW-SERVERS–SRV1, không phải đường Internet Windows. Công cụ chạy theo yêu cầu, không tự bơm tải mỗi 5 giây.

Tham số direction của script dành cho R1 làm client, SRV1 làm server; nếu đổi vị trí chạy phải diễn giải lại hướng theo client/server. Dừng iperf3 server bằng Ctrl+C khi xong.

## 6. Thu bằng chứng50 gói theo Lab 6

**GNS3:** chuột phải link **SW-SERVERS ↔ SRV1 → Start capture** → chọn Wireshark.

1. Tạo lưu lượng bằng ping, chạy NetWatch, mở web và/hoặc iperf3.
2. Wireshark → **Capture → Options → Options** → chọn điều kiện dừng sau50 packets nếu phiên bản hỗ trợ; hoặc dừng thủ công sau khi có ít nhất50 gói và ghi rõ số lượng thật.
3. Display filter: `icmp or tcp.port == 22 or tcp.port == 8000 or tcp.port == 5201`.
4. Chụp cột Source, Destination, Protocol, Info; mở TCP/UDP trong packet details để thấy cổng nguồn/đích.
5. Lưu `.pcapng` cục bộ cùng ngày đo; không push capture có thông tin nhạy cảm lên GitHub.

Đây là thực hiện mục tiêu bắt/phân tích gói bằng công cụ Wireshark tích hợp GNS3, không tuyên bố đã xây chương trình scapy hoặc bộ phát hiện ARP spoofing.

## 7. Xuất báo cáo tự động

Dashboard → **Báo cáo HTML ↓**. File có CPU/RAM/RTT, kết quả HTTP và sự kiện, không cần Internet/CDN khi mở lại. Chế độ demo có nhãn MÔ PHỎNG.

Hoặc **PowerShell Windows**, sau khi đã có SQLite từ buổi chạy thật:

```powershell
.\export_report.cmd --inventory inventory.buoi5.json
Start-Process .\data\NetWatch_bao_cao.html
```

Trong trình duyệt: **Ctrl+P → Destination: Save as PDF → Save**. Báo cáo lấy ảnh chụp dữ liệu tại thời điểm xuất; số liệu không tự cập nhật. Kèm file CSV, ảnh cảnh báo/phục hồi và capture để hoàn thiện báo cáo học phần. Trạng thái nghiệm thu trong repository vẫn để CHUA_CHAY cho đến khi bạn chạy trên máy thật.
