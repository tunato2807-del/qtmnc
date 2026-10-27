# CPU tăng cao khi bật giám sát SSH

## Dữ liệu đã quan sát

Ngày 27/10/2026, người dùng đo trên Ubuntu VM có 2 vCPU, theo thứ tự tắt rồi bật
monitor. Bỏ dòng đầu của mỗi lần `vmstat` vì đó là trung bình từ khi khởi động:

| Trạng thái | 7 mẫu CPU bận (%) | Trung bình |
|---|---|---|
| Monitor đã dừng | 99, 80, 57, 55, 60, 56, 59 | 66,6% |
| Monitor đang chạy | 99, 100, 99, 100, 100, 100, 100 | 99,7% |

CPU bận = 100 − id − wa, cùng cách tính idle + iowait trong collector.
Các mẫu không có swap-in/swap-out, iowait hoặc steal đáng kể. Đây là hai lần
đo ngắn, cho thấy bật monitor đi kèm tải tăng; chưa xác định riêng tiến trình
nào gây toàn bộ phần tăng. Khi monitor dừng, các mẫu cuối vẫn bận 55–60%.

## Thay đổi trong mã

- Dùng lại kết nối SSH đã xác thực, thay vì xác thực mới mỗi vòng.
- Gộp CPU/RAM/interface/nhiệt độ Linux vào một exec channel, giảm từ 3–4 lần
  mở phiên lệnh xuống 1 lần mỗi vòng; không yêu cầu cài agent hoặc Python dự án
  trên Ubuntu.
- Giữ đọc hai mẫu /proc/stat cách nhau khoảng một giây và giữ nguyên ngưỡng.
- Mỗi chỉ số có khối đầu ra và mã kết thúc riêng; không đọc được một file thì
  chỉ số đó UNKNOWN, các khối hợp lệ khác vẫn được dùng.
- Đóng kết nối sau lỗi I/O để lần lấy mẫu tiếp theo tạo kết nối mới; Ctrl+C
  đóng kết nối đang giữ. Mọi kết nối mới tiếp tục kiểm tra host key.
- Mẫu `.env.simple` mới có timeout 15 giây. Cấu hình cũ cục bộ không bị ghi đè.

Các thay đổi giảm thao tác quản trị do monitor tạo ra. Chưa có kết quả đo CPU
sau sửa trên máy Windows/GNS3/Ubuntu của người dùng.

## Cập nhật trên Windows

1. Nhấn Ctrl+C trong cửa sổ **bảng monitor**; giữ cửa sổ cầu nối TAP và GNS3 chạy.
2. Trong Terminal VS Code, tại thư mục dự án, chạy:

   ```powershell
   cd D:\QTM_NC\telegram\qtmnc
   git fetch origin
   git merge --ff-only origin/main
   ```

3. Mở `.env.simple` trong VS Code. Giữ các thông tin truy cập và sửa hai dòng:

   ```dotenv
   MONITOR_INTERVAL='15'
   MONITOR_TIMEOUT='15'
   ```

   Đây là cấu hình thử trên VM đang bận. Sau khi ổn định, có thể thử lại chu kỳ
   5 giây và đo CPU để quyết định; chu kỳ thưa hơn làm cảnh báo tới chậm hơn.

4. Lưu rồi chạy:

   ```powershell
   .\run_windows.cmd
   ```

Không cần chạy lại wizard chỉ để cập nhật mã. Nếu Git báo sửa đổi cục bộ, giữ
lại và xử lý trước khi merge.

## Xác nhận trên Ubuntu

Giữ các ứng dụng khác ở cùng trạng thái khi so sánh. Mỗi lần chờ khoảng 10 giây
cho tải ổn định, rồi chạy trong Terminal **Ubuntu**, không phải PowerShell:

```bash
vmstat 1 8
```

Ghi riêng kết quả khi monitor dừng và khi bản mới đang chạy. Bỏ dòng đầu, tính
CPU bận bằng 100 − id − wa cho từng dòng sau. Đối chiếu thêm thời điểm lấy mẫu
trên dashboard; hai công cụ không lấy mẫu đồng bộ tuyệt đối.

Nếu CPU nền vẫn cao khi dừng monitor, chạy `top`, nhấn Shift+P và xác định tiến
trình đang chiếm CPU. Ảnh trước có polkitd, apt-check và lsb_release hoạt động;
tên tiến trình chưa đủ để kết luận cần dừng dịch vụ nào.

CPU ≤70% trong một mẫu của monitor sẽ phục hồi cảnh báo CPU theo cấu hình
75% và RECOVERY_MARGIN=5. Mất dữ liệu SSH vẫn phải báo UNKNOWN hoặc mất kết nối,
không đổi thành CPU 0% để tạo phục hồi giả.
