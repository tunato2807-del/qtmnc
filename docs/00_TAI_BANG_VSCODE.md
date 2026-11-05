# Tải dự án bằng VS Code và mở GNS3

## Cách 1 — bạn đã có thư mục qtmnc

Trên **Windows**:

1. Mở **VS Code → File → Open Folder**.
2. Chọn `D:\QTM_NC\telegram\qtmnc` → **Select Folder**.
3. Chọn **Terminal → New Terminal**. Cửa sổ phía dưới phải là PowerShell tại thư mục qtmnc.
4. Dán từng dòng, không chép số thứ tự hoặc ký hiệu `PS>`:

```powershell
git pull --ff-only origin main
.\open_gns3_preview.cmd
```

Lệnh đầu tải thay đổi từ GitHub. Lệnh sau mở **bản xem sơ đồ** trong GNS3, không cần biết đường dẫn Ubuntu VMX. Nếu file .gns3 chưa có ứng dụng mở mặc định: **GNS3 → File → Open** → chọn `lab\gns3\NETWATCH_XEM_NGAY.gns3`.

Để xem dashboard minh họa:

```powershell
.\setup.cmd
.\start.cmd --demo
```

Mở trình duyệt tại **http://127.0.0.1:8765**. Giữ cửa sổ lệnh đang chạy; Ctrl+C để dừng.

## Cách 2 — tải toàn bộ dự án bằng giao diện

1. Mở VS Code → nhấn **Ctrl+Shift+P**.
2. Gõ **Git: Clone** → bấm mục đó.
3. Dán URL `https://github.com/tunato2807-del/qtmnc.git` → **Enter**.
4. Chọn thư mục cha muốn lưu, ví dụ `D:\QTM_NC\lab_moi`.
5. Đợi tải xong → bấm **Open** khi VS Code hỏi mở repository vừa clone.
6. Chọn **Terminal → New Terminal** → chạy `setup.cmd`, `start.cmd --demo` như trên.

Nếu không thấy Git: Clone, kiểm tra `git --version` trong terminal; cài Git for Windows nếu chưa có rồi mở lại VS Code. Không cài thêm Git khi lệnh đã hoạt động.

## Cách 3 — chỉ tải riêng file sơ đồ

**VS Code → Terminal → New Terminal**, chuyển đến thư mục muốn lưu rồi chạy:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/tunato2807-del/qtmnc/main/lab/gns3/NETWATCH_XEM_NGAY.gns3" -OutFile ".\NETWATCH_XEM_NGAY.gns3"
Start-Process ".\NETWATCH_XEM_NGAY.gns3"
```

File độc lập chứa toàn bộ hình vẽ SVG, không gọi ảnh ngoài hoặc đường dẫn VMX giả. Đây là **bản xem**, các khối là hình vẽ, không phải VM/VPCS đang chạy; bấm Start không tạo hệ thống giám sát.

## Chạy bằng nút trong VS Code

Sau khi tải cả repository: **Terminal → Run Task** rồi chọn:

| Task | Thực hiện |
|---|---|
| NetWatch: 1. Cài môi trường Windows | Tạo môi trường Python và cài thư viện |
| NetWatch: 2. Xem dashboard demo | Chạy giao diện minh họa, không SSH/gửi tin |
| NetWatch: 3. Mở sơ đồ GNS3 ngay | Mở bản xem, không cần VMX |
| NetWatch: 4. Tạo và mở lab Ubuntu thật | Tìm hoặc hỏi hai file VMX, sinh topology chạy thật |
| NetWatch: 5. Chạy cấu hình Buổi 5 | Dùng CPU85%, RAM90%, chu kỳ 5s và HTTP |
| NetWatch: 6. Xuất báo cáo HTML | Lấy dữ liệu SQLite thật để xuất báo cáo |

Các task dành cho VS Code chạy trên Windows. Trong môi trường Linux phát triển, dùng trực tiếp các lệnh Python tương ứng.

## Lab Ubuntu thật: chọn VMX một lần

Hai full clone đã chuẩn bị theo [01_GNS3.md](01_GNS3.md): R1 có một NAT và hai Custom adapter; SRV1 có một Custom adapter. Chạy:

```powershell
.\open_gns3_lab.cmd
```

- Nếu VMware inventory có duy nhất hai clone tên **R1-LINUX**, **SRV1-LINUX**, công cụ tự tìm chúng.
- Nếu chưa tìm thấy duy nhất, hộp chọn file hỏi **R1-LINUX.vmx**, sau đó **SRV1-LINUX.vmx**. Chọn đúng hai clone đang tắt.
- Công cụ kiểm tra card, tạo và mở `lab\generated\NETWATCH_ROUTED\NETWATCH_ROUTED.gns3` có **6 node thật và 5 link**.
- Lần sau dùng cùng lệnh sẽ chỉ mở project đã có, không ghi đè cấu hình bạn đã chỉnh.

Máy ảo Ubuntu và đường dẫn VMX thuộc máy của bạn; file tải về không thể chứa sẵn ổ đĩa Ubuntu đã cài và cấu hình SSH. Sau khi mở topology thật, vẫn cần cấu hình IP/probe và route Windows theo hướng dẫn. Đây là bước triển khai thực tế, khác việc mở hình sơ đồ.
