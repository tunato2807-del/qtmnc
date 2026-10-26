# Kịch bản nghiệm thu và bằng chứng

Làm [GNS3_LAB.md](GNS3_LAB.md) trước. Ghi kết quả thực tế, thời gian và ảnh chụp
của từng ca vào báo cáo; không điền "đạt" từ các số minh họa trong tài liệu.
Chạy monitor ở Windows, tạo tải trên Ubuntu, thử từng ca một.

## Điều kiện đầu

- GNS3 Start, Linux có gns3mgmt .10.129 và gns3test .30.129.
- Windows SSH được .10.129; VPCS ping được .30.129.
- --test-notifications nhận được trên các kênh cấu hình.
- Nếu VM thiếu cảm biến: ghi rõ UNKNOWN/tắt hoặc dùng demo có nhãn.
- Đợi CPU/RAM về nền trước từng ca; chờ hết thời gian và tin phục hồi.

| Ca | Thao tác | Kết quả cần quan sát |
|---|---|---|
| Đường GNS3 | Stop SW-MANAGEMENT, kiểm tra SSH .10.129 rồi Start | Mất đường khi Stop, kết nối lại khi Start |
| Bình thường | Chạy ít nhất 3 chu kỳ | Bảng cập nhật mỗi ~5s, CPU/RAM hợp lệ, interface UP, không spam tin |
| CPU | python3 lab/linux/labctl.py cpu --seconds 60 | CPU >75 phát cảnh báo, hết tải <=70 phát phục hồi |
| RAM | python3 lab/linux/labctl.py ram --target 75 --seconds 90 | RAM >65 phát cảnh báo; chỉ phục hồi khi <=60 |
| Interface | sudo python3 lab/linux/labctl.py interface --iface gns3test --seconds 45 | Interface DOWN rồi UP, SSH quản trị vẫn được |
| Nhiệt độ thiếu | TEMP_SOURCE=auto, bật temp trên VM không có cảm biến | UNKNOWN, báo thiếu dữ liệu; không hiện 0°C/OK |
| Nhiệt độ demo | Nguồn demo cả hai đầu, nền 40 rồi 75 trong 60s | >65 cảnh báo; hết hạn về40 phục hồi; luôn ghi MÔ PHỎNG |
| Mất thiết bị | Stop SW-MANAGEMENT hoặc tắt VM; sau đó bật lại | Cảnh báo mất kết nối, số đo cũ không hiển thị là mới; có phục hồi |
| Mất SSH riêng | Hybrid; từ console sudo systemctl stop ssh, rồi start | Dịch vụ SSH DOWN; SNMP tiếp tục, chỉ số có nguồn SNMP |
| Mất SNMP riêng | Hybrid; sudo systemctl stop qtmnc-lab-snmp, rồi start | SNMP DOWN; SSH tiếp tục, interface có nguồn SSH |
| Không lặp | Giữ một lỗi qua nhiều chu kỳ | Một tin chuyển trạng thái, không gửi mỗi 5s |
| Mất Internet | Ngắt Internet Windows khi tạo một cảnh báo, giữ lab local | Tin nằm hàng đợi; lấy mẫu tiếp tục; nối Internet thì gửi lại |
| Restart | Khi có tin chờ, Ctrl+C rồi chạy lại cùng profile | Tin chưa gửi còn nguyên, tiếp tục retry |
| Hai kênh | Cấu hình both và làm một kênh không hợp lệ | Kênh còn đúng vẫn nhận, tin kênh lỗi còn trong queue |
| Host key sai | Thử profile riêng với fingerprint sai, không sửa known_hosts thật | Bị từ chối; không tự tin khóa chưa xác minh |

Các lệnh stop/start dịch vụ phải chạy từ **console VMware** để không tự mất phiên
SSH đang dùng. Dịch vụ Ubuntu tên ssh; SNMP lab tên qtmnc-lab-snmp.
Không Stop GNS3 local server trong lúc thử interface nếu muốn chứng minh đọc được
trạng thái DOWN. Nếu RAM nền vẫn >60% thì chưa có phục hồi là đúng hysteresis,
không phải mất thông báo.

Không khẳng định tháo dây Cloud làm operstate VMware đổi DOWN: dùng labctl
interface để thử trạng thái cổng; tháo dây để thử mất đường truyền.

## Mẫu ghi nhận

| Mục | Giá trị bạn ghi |
|---|---|
| Phiên bản Windows/GNS3/VMware/Ubuntu/Python | ... |
| Commit của dự án: git rev-parse --short HEAD | ... |
| Giao thức / nguồn nhiệt độ | ssh/snmp/hybrid; auto/demo/tắt |
| Trước thử | CPU ..., RAM ..., interface ..., temp ... |
| Bắt đầu lỗi và thời điểm đo phát hiện | ... |
| Telegram/Slack nhận | ... |
| Khôi phục và nhận tin phục hồi | ... |
| Kết quả / ảnh chụp đã che secret | ... |

Polling 5 giây không có nghĩa mọi tin luôn tới trong đúng 5 giây; đo độ trễ thực
tế và giải thích thời gian lấy mẫu, timeout và retry.

## Kiểm thử tự động của mã

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
~~~

Bộ test gồm parser Linux/Windows, hysteresis, host key, lỗi cấu hình, SQLite,
retry/restart, phân tách kênh, UI, hybrid và probe. Kiểm thử giao thức chạy SNMPv2c
và SNMPv3 thật trên **loopback cục bộ**, có GET/GETNEXT, tìm ifIndex, JSON extension
và thay đổi trạng thái IF-MIB. Không gửi tin tới tài khoản người dùng.

Kiểm tra schema project GNS3 chỉ xác nhận định dạng file; không xác nhận Npcap,
VMware, firewall hay GUI Windows. Những phần này cần các ca nghiệm thu ở trên.
