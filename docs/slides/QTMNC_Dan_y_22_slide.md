# Dàn ý thuyết trình: Hệ thống giám sát thiết bị

**Bộ trình chiếu:** 22 slide · 16:9 · phần tử PowerPoint có thể chỉnh sửa.
**Phạm vi trình bày:** Windows chạy Python → GNS3 → Ubuntu VMware → Telegram/Slack.
**Lưu ý trạng thái:** Bản đơn giản đã cấu hình SSH; SNMP/hybrid là phương án mở rộng. Kết quả loopback tự động không thay thế nghiệm thu agent/API trên thiết bị thật.

## SLIDE 1: Giám sát thiết bị và cảnh báo

- **Thông điệp cốt lõi:** Windows chạy Python kiểm tra Ubuntu định kỳ; khi trạng thái đổi, hệ thống gửi cảnh báo Telegram/Slack.
- **Điểm chính 1: Đối tượng** — Ubuntu VMware; theo dõi CPU, RAM, nhiệt độ và interface.
- **Điểm chính 2: Đường chính** — SSH qua GNS3; bản đơn giản chờ 5 giây sau mỗi lượt đọc.
- **Điểm chính 3: Mở rộng** — SNMP/hybrid; gửi cảnh báo qua HTTPS tới Telegram/Slack.
- **Số liệu/Minh chứng:** PHẠM VI  4 chỉ số  ·  SSH TCP/22  ·  polling gần thời gian thực
- **Gợi ý trực quan:** Sơ đồ luồng điều hành 4 tác nhân.
- **Nguồn:** README.md · docs/ARCHITECTURE.md · examples/simple.env

## SLIDE 2: Bối cảnh và mục tiêu hệ thống

- **Thông điệp cốt lõi:** Giải pháp biến số liệu thiết bị thành cảnh báo và bằng chứng xử lý sự cố có thể trình diễn.
- **Điểm chính 1: Vấn đề** — Lỗi CPU, bộ nhớ, nhiệt độ hoặc interface có thể bị phát hiện muộn.
- **Điểm chính 2: Mục tiêu** — Kiểm tra có lịch; phát hiện chuyển trạng thái; báo người quản trị.
- **Điểm chính 3: Phạm vi** — Một Windows giám sát Ubuntu VM qua mạng GNS3 hiện có.
- **Số liệu/Minh chứng:** ĐẦU RA  Dashboard · cảnh báo lỗi/phục hồi · hàng đợi tin chưa gửi
- **Gợi ý trực quan:** Sơ đồ người kiểm tra – hệ thống – người nhận.
- **Nguồn:** README.md · docs/ARCHITECTURE.md

## SLIDE 3: Kiến trúc tổng thể giải pháp

- **Thông điệp cốt lõi:** Thu thập, đánh giá, lưu trữ và gửi tin là các bước tách biệt trong cùng một ứng dụng.
- **Điểm chính 1: Máy giám sát** — Windows chạy monitor.py và bảng Rich trong Terminal.
- **Điểm chính 2: Thiết bị đích** — Ubuntu trả số liệu qua SSH; SNMP là collector mở rộng.
- **Điểm chính 3: Kênh gửi** — Luồng gửi riêng chuyển tin qua Telegram Bot API/Slack Webhook.
- **Số liệu/Minh chứng:** MÔ HÌNH  Python Windows → GNS3 → Ubuntu; HTTPS → dịch vụ nhắn tin
- **Gợi ý trực quan:** Kiến trúc end-to-end dạng 2 tầng.
- **Nguồn:** docs/ARCHITECTURE.md · docs/truc_quan/README.md

## SLIDE 4: Thiết bị và công cụ thực hành

- **Thông điệp cốt lõi:** Mỗi thiết bị đảm nhiệm một vai trò; chỉ Ubuntu là đối tượng lấy CPU/RAM trong lab hiện tại.
- **Điểm chính 1: Windows** — Máy thật; chạy VS Code, Python, cấu hình và gửi cảnh báo.
- **Điểm chính 2: VMware** — Cấp CPU/RAM ảo, Ubuntu và các card mạng cho thiết bị đích.
- **Điểm chính 3: GNS3** — Hai Cloud và Switch1 chuyển tiếp mạng; không tự đo tài nguyên.
- **Số liệu/Minh chứng:** ĐỐI TƯỢNG ĐO  Số CPU/RAM lấy từ Ubuntu VM, không phải toàn Windows
- **Gợi ý trực quan:** Thẻ vai trò 4 khối thiết bị.
- **Nguồn:** docs/GNS3_LAB.md · docs/truc_quan/README.md

## SLIDE 5: Mô hình mạng hiện tại trên GNS3

- **Thông điệp cốt lõi:** Đường giám sát dùng subnet 192.168.10.0/24; ens37 quản trị và ens33 là interface theo dõi.
- **Điểm chính 1: Windows** — Card TAP Local Area Connection: 192.168.10.1/24.
- **Điểm chính 2: Đường SSH** — Cloud-WINDOWS → Switch1 → Cloud-LINUX/VMnet2 → ens37.
- **Điểm chính 3: Interface đo** — ens33 NAT; đã ghi nhận 192.168.73.129/24, gateway .73.2.
- **Số liệu/Minh chứng:** SSH ĐÍCH  192.168.10.129:22  ·  ens37 192.168.10.129/24
- **Gợi ý trực quan:** Sơ đồ mạng phân cột Windows – GNS3 – Ubuntu – Internet.
- **Nguồn:** WINDOWS_TAP_GNS3.md · docs/truc_quan/README.md · kết quả người dùng

## SLIDE 6: Đường SSH và vai trò TAP

- **Thông điệp cốt lõi:** TAP/UDP chỉ nối Windows vào lab GNS3 hiện tại; SSH mới vận chuyển yêu cầu lấy số liệu.
- **Điểm chính 1: SSH** — Phiên TCP/22 được thiết lập từ Windows tới Ubuntu .10.129.
- **Điểm chính 2: Cầu nối** — TAP-Windows + UDP localhost đưa Ethernet vào Cloud GNS3.
- **Điểm chính 3: Phạm vi** — TAP không đo CPU/RAM, không đánh giá và không gửi cảnh báo.
- **Số liệu/Minh chứng:** UDP CẦU NỐI  Cloud local 30010 ↔ helper 127.0.0.1:30011
- **Gợi ý trực quan:** Luồng yêu cầu và chiều trả lời SSH.
- **Nguồn:** WINDOWS_TAP_GNS3.md · tools/windows_tap_bridge.py

## SLIDE 7: Lựa chọn giao thức thu thập

- **Thông điệp cốt lõi:** SSH, SNMP và hybrid dùng các cách lấy số liệu khác nhau nhưng chung phần đánh giá và cảnh báo.
- **Điểm chính 1: SSH** — TCP/22; chạy lệnh Linux qua Paramiko; là bản đơn giản hiện dùng.
- **Điểm chính 2: SNMP** — UDP/161; hỏi agent bằng OID; cần agent và cấu hình tương ứng.
- **Điểm chính 3: Hybrid** — Ưu tiên SSH cho metric; ưu tiên SNMP cho interface; có dự phòng.
- **Số liệu/Minh chứng:** HYBRID  Mất từng dịch vụ vẫn hiển thị trạng thái; nguồn còn lại có thể tiếp tục
- **Gợi ý trực quan:** So sánh 3 giao thức bằng thẻ.
- **Nguồn:** device_monitor/collectors/{ssh,snmp,hybrid}.py · docs/ARCHITECTURE.md

## SLIDE 8: Các module phần mềm chính

- **Thông điệp cốt lõi:** Các module tách thu thập, trạng thái và gửi cảnh báo để dễ giải thích và mở rộng.
- **Điểm chính 1: Điểm vào** — monitor.py điều phối cấu hình, SSH, bảng và vòng lặp.
- **Điểm chính 2: Xử lý** — Collectors lấy số liệu; engine quyết định OK/ALERT/UNKNOWN.
- **Điểm chính 3: Đầu ra** — storage.py lưu SQLite; notifications.py gửi và retry.
- **Số liệu/Minh chứng:** MÃ CHÍNH  config → collectors → engine → storage → notifications → ui
- **Gợi ý trực quan:** Sơ đồ module dạng lưới.
- **Nguồn:** monitor.py · device_monitor/app.py · docs/ARCHITECTURE.md

## SLIDE 9: Bốn chỉ số thiết bị cần theo dõi

- **Thông điệp cốt lõi:** Bản đơn giản thu thập bốn nhóm chỉ số trên Ubuntu; một chỉ số thiếu không phủ định các chỉ số khác.
- **Điểm chính 1: CPU** — Hai lần đọc /proc/stat; chênh lệch biểu thị thời gian bận.
- **Điểm chính 2: RAM** — /proc/meminfo; dùng MemTotal và MemAvailable.
- **Điểm chính 3: Nhiệt độ/interface** — Cảm biến /sys nếu có; operstate của ens33.
- **Số liệu/Minh chứng:** NGUỒN  CPU/RAM/temp/interface đều thuộc Ubuntu VM
- **Gợi ý trực quan:** Bốn thẻ metric và nguồn dữ liệu.
- **Nguồn:** device_monitor/collectors/ssh.py · examples/simple.env

## SLIDE 10: Cách hệ thống tính CPU và RAM

- **Thông điệp cốt lõi:** Giá trị được chuẩn hóa thành phần trăm từ bộ đếm Linux và lượng RAM còn dùng được.
- **Điểm chính 1: CPU** — 100 × (1 − idle delta / total delta); đọc cách nhau khoảng 1 giây.
- **Điểm chính 2: RAM** — 100 × (MemTotal − MemAvailable) / MemTotal.
- **Điểm chính 3: Diễn giải** — 4 GB cấp cho VM, còn 1 GB khả dụng → RAM dùng xấp xỉ 75%.
- **Số liệu/Minh chứng:** VÍ DỤ  3/4 GB sử dụng = 75% RAM Ubuntu
- **Gợi ý trực quan:** Hai công thức và ví dụ định lượng.
- **Nguồn:** device_monitor/collectors/ssh.py · docs/ARCHITECTURE.md

## SLIDE 11: Nhiệt độ và tính toàn vẹn số liệu

- **Thông điệp cốt lõi:** Không có cảm biến phải được báo UNKNOWN hoặc bỏ theo cấu hình, không đổi thành nhiệt độ 0°C.
- **Điểm chính 1: Auto** — Đọc cảm biến CPU đã nhận diện trong /sys/hwmon hoặc thermal.
- **Điểm chính 2: UNKNOWN** — Máy ảo thường không lộ cảm biến vật lý; ghi nhận thiếu dữ liệu.
- **Điểm chính 3: Demo** — Đọc mẫu có hạn dùng; mọi số đo/cảnh báo phải gắn nhãn MÔ PHỎNG.
- **Số liệu/Minh chứng:** PROFILE  MONITOR_TEMP_ENABLED · TEMP_SOURCE=auto/demo
- **Gợi ý trực quan:** Ba nhánh auto – thiếu sensor – demo.
- **Nguồn:** device_monitor/probe.py · lab/linux/labctl.py · docs/ARCHITECTURE.md

## SLIDE 12: Chu kỳ thu thập và độ trễ

- **Thông điệp cốt lõi:** Polling 5 giây là gần thời gian thực; phát hiện và giao tin vẫn chịu độ trễ đo, mạng và API.
- **Điểm chính 1: Lấy mẫu** — Kết nối, đọc chỉ số, đánh giá và cập nhật bảng mỗi vòng.
- **Điểm chính 2: Chu kỳ** — Profile đơn giản chờ 5 giây sau lượt đọc; CPU cần mẫu ~1 giây.
- **Điểm chính 3: Độ trễ** — Sự cố chờ lượt kế tiếp; timeout/retry/API làm tin tới muộn.
- **Số liệu/Minh chứng:** 5 GIÂY  Không phải cam kết mọi cảnh báo đến trong đúng 5 giây
- **Gợi ý trực quan:** Timeline 6 bước trong vòng đo.
- **Nguồn:** examples/simple.env · docs/ARCHITECTURE.md · docs/TEST_PLAN.md

## SLIDE 13: Ngưỡng cảnh báo và phục hồi

- **Thông điệp cốt lõi:** Ngưỡng phục hồi có khoảng đệm 5 điểm để giảm đổi trạng thái liên tục.
- **Điểm chính 1: CPU** — Cảnh báo >75%; sau đó phục hồi khi ≤70%.
- **Điểm chính 2: RAM** — Cảnh báo >65%; sau đó phục hồi khi ≤60%.
- **Điểm chính 3: Nhiệt độ** — Cảnh báo >65°C; sau đó phục hồi khi ≤60°C.
- **Số liệu/Minh chứng:** HYSTERESIS  RECOVERY_MARGIN=5; interface DOWN→ALERT, UP→OK
- **Gợi ý trực quan:** Thanh ngưỡng 4 metric.
- **Nguồn:** examples/simple.env · device_monitor/engine.py

## SLIDE 14: Máy trạng thái và hysteresis

- **Thông điệp cốt lõi:** Chỉ tạo tin khi trạng thái chuyển; UNKNOWN giữ trạng thái hợp lệ gần nhất để xử lý phục hồi đúng.
- **Điểm chính 1: OK** — Giá trị trong miền bình thường; không gửi lại mỗi vòng.
- **Điểm chính 2: ALERT** — Vượt ngưỡng; giữ cảnh báo tới khi đạt ngưỡng phục hồi.
- **Điểm chính 3: UNKNOWN** — Thiếu dữ liệu; không suy diễn là bình thường hoặc bằng 0.
- **Số liệu/Minh chứng:** RAM  50 → 72 → 74 → 63 → 58: một cảnh báo, một tin phục hồi
- **Gợi ý trực quan:** Dòng trạng thái RAM với hysteresis.
- **Nguồn:** device_monitor/engine.py · device_monitor/storage.py

## SLIDE 15: Phân biệt ba nhóm sự cố

- **Thông điệp cốt lõi:** Ngắt interface đo, mất đường SSH và mất Internet gây ba kết quả vận hành khác nhau.
- **Điểm chính 1: ens33 DOWN** — SSH qua ens37 còn; đọc trạng thái interface và báo lỗi.
- **Điểm chính 2: Mất SSH** — Không có số đo mới; đánh dấu mất kết nối và báo phục hồi.
- **Điểm chính 3: Mất Internet** — Lấy mẫu vẫn chạy; cảnh báo xếp hàng chờ gửi.
- **Số liệu/Minh chứng:** NGUYÊN TẮC  Ngắt ens33 để thử trạng thái; ngắt GNS3 để thử mất SSH
- **Gợi ý trực quan:** Ma trận 3 loại sự cố và phản ứng.
- **Nguồn:** docs/TEST_PLAN.md · docs/truc_quan/README.md

## SLIDE 16: Hàng đợi và độ tin cậy cảnh báo

- **Thông điệp cốt lõi:** SQLite lưu trạng thái và tin trong cùng giao dịch; luồng gửi riêng thử lại các tin chưa xác nhận.
- **Điểm chính 1: Outbox** — Giữ tin chưa giao qua lần dừng/chạy lại ứng dụng.
- **Điểm chính 2: Retry** — Backoff 2, 4, 8… tối đa 300 giây; HTTP 429 đọc retry-after.
- **Điểm chính 3: Cam kết** — At-least-once; phản hồi thất lạc có thể làm tin bị gửi trùng.
- **Số liệu/Minh chứng:** SQLite  states + outbox; mỗi kênh giữ thứ tự tin riêng
- **Gợi ý trực quan:** Luồng state → SQLite → sender → API/retry.
- **Nguồn:** device_monitor/storage.py · device_monitor/notifications.py · docs/ARCHITECTURE.md

## SLIDE 17: Bảo vệ thông tin và kết nối

- **Thông điệp cốt lõi:** Xác minh host key, lưu secret cục bộ và giới hạn giao thức quản trị trong mạng lab.
- **Điểm chính 1: SSH** — RejectPolicy + known_hosts; không tự tin host key lạ.
- **Điểm chính 2: Secret** — Mật khẩu/token/webhook ở .env bị Git ignore; không ghi log.
- **Điểm chính 3: SNMP** — v2c chỉ lab cô lập; v3 authPriv hỗ trợ xác thực/mã hóa.
- **Số liệu/Minh chứng:** PORT  SSH TCP/22 · SNMP UDP/161 · API HTTPS/TCP 443
- **Gợi ý trực quan:** Bốn lớp xác minh và bảo vệ.
- **Nguồn:** device_monitor/collectors/ssh.py · device_monitor/config.py · docs/ARCHITECTURE.md

## SLIDE 18: Hai profile triển khai dự án

- **Thông điệp cốt lõi:** Bản đơn giản giảm bước cài đặt; profile GNS3 mở rộng SNMP/hybrid và mạng thử nghiệm riêng.
- **Điểm chính 1: Đơn giản** — run_windows.cmd; SSH tới .10.129; theo dõi ens33.
- **Điểm chính 2: Mở rộng** — .env.gns3; SSH/SNMP/hybrid; gns3test .30.129.
- **Điểm chính 3: Dùng chung** — Ngưỡng, SQLite, dashboard và Telegram/Slack.
- **Số liệu/Minh chứng:** LAB MỞ RỘNG  VMnet3 .30.0/24 · VPCS .30.10 (kiểm tra mạng)
- **Gợi ý trực quan:** So sánh hai profile đơn giản/mở rộng.
- **Nguồn:** README.md · docs/GNS3_LAB.md · examples/{simple,gns3}.env

## SLIDE 19: Kế hoạch kiểm thử và nghiệm thu

- **Thông điệp cốt lõi:** Mỗi tình huống phải gắn kích thích, phản ứng mong đợi và bằng chứng trên máy thật.
- **Điểm chính 1: Tài nguyên** — Tạo tải CPU/RAM; xác nhận cảnh báo và phục hồi.
- **Điểm chính 2: Kết nối** — Ngắt ens33, SSH/GNS3 hoặc Internet riêng theo từng ca.
- **Điểm chính 3: Dữ liệu** — Kiểm tra nhiệt độ UNKNOWN/demo và host key sai.
- **Số liệu/Minh chứng:** BẰNG CHỨNG  Thời điểm đo · tin nhận · ảnh đã che secret · phiên bản/commit
- **Gợi ý trực quan:** Ma trận kích thích – kết quả – bằng chứng.
- **Nguồn:** docs/TEST_PLAN.md · docs/GNS3_LAB.md

## SLIDE 20: Kết quả kiểm chứng hiện có

- **Thông điệp cốt lõi:** Kiểm thử mã bao phủ collector, ngưỡng và retry; xác nhận trên Windows/GNS3 thật vẫn là bước riêng.
- **Điểm chính 1: Tự động** — 119 unit tests; SSH/SNMP loopback và parser/test outbox.
- **Điểm chính 2: Mạng thật** — TCP/22 tới .10.129 từng thành công qua Local Area Connection.
- **Điểm chính 3: Giới hạn chứng cứ** — Loopback tests không chứng minh Telegram/SNMP agent thật.
- **Số liệu/Minh chứng:** ẢNH NGƯỜI DÙNG  TAP counters: 106→GNS3, 57→TAP, dropped 0 (một thời điểm)
- **Gợi ý trực quan:** Thẻ số liệu kiểm chứng thực tế.
- **Nguồn:** docs/VALIDATION.md · ảnh/test người dùng · docs/TEST_PLAN.md

## SLIDE 21: Giới hạn kỹ thuật cần công bố

- **Thông điệp cốt lõi:** Kết quả phải nêu giới hạn môi trường, phạm vi đo và mức xác nhận thực tế.
- **Điểm chính 1: Nhiệt độ** — VM có thể thiếu cảm biến; demo không phải đo phần cứng.
- **Điểm chính 2: Lịch sử** — SQLite lưu state/outbox, không phải kho thời gian-series.
- **Điểm chính 3: Cùng máy** — Windows tắt/ngủ có thể làm monitor và VM cùng dừng.
- **Số liệu/Minh chứng:** PHẠM VI  Một thiết bị / tiến trình / state file theo cấu hình
- **Gợi ý trực quan:** Bốn khối giới hạn kỹ thuật.
- **Nguồn:** docs/ARCHITECTURE.md · docs/VALIDATION.md · docs/TEST_PLAN.md

## SLIDE 22: Kết luận và hành động tiếp theo

- **Thông điệp cốt lõi:** Mô hình chứng minh được vòng giám sát end-to-end khi hoàn tất nghiệm thu collector, đường truyền và kênh nhận tin.
- **Điểm chính 1: Chạy lab** — Xác nhận TAP/GNS3 và khôi phục Test-NetConnection TCP/22.
- **Điểm chính 2: Nghiệm thu** — Chạy các ca ens33, CPU/RAM, mất SSH và phục hồi.
- **Điểm chính 3: Báo cáo** — Ghi rõ SSH đã dùng; chỉ tuyên bố SNMP/Telegram khi đã đo thật.
- **Số liệu/Minh chứng:** THÀNH CÔNG  Cảnh báo đúng · phục hồi đúng · không spam · secret an toàn
- **Gợi ý trực quan:** Lộ trình 5 bước nghiệm thu.
- **Nguồn:** docs/TEST_PLAN.md · docs/VALIDATION.md · docs/ARCHITECTURE.md
