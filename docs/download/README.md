# Gói tải về

`NetWatch_Lab_Moi.zip` chứa mã nguồn, cấu hình mẫu trống, hướng dẫn GNS3, sơ đồ, báo cáo Word/PDF và PowerPoint 22 slide cỡ chữ tối thiểu 20 pt.

Giải nén vào một thư mục mới trên Windows → mở PowerShell tại thư mục đó → chạy `setup.cmd` rồi `start.cmd --demo` → mở http://127.0.0.1:8765. Làm theo `docs/01_GNS3.md` để triển khai thật.

Gói không có VM disk, secret, SQLite cá nhân hoặc VMX của người dùng. Dùng `create_lab.cmd` và chọn hai VMX của hai full clone Ubuntu để sinh project đúng máy.

Bản cập nhật Buổi5 có `lab/gns3/NETWATCH_XEM_NGAY.gns3` để mở xem sơ đồ ngay; `open_gns3_lab.cmd` tạo/mở lab VM thật. Hướng dẫn tải bằng VS Code ở `docs/00_TAI_BANG_VSCODE.md`; phần bổ sung từ tài liệu ở `docs/05_BUOI_5.md`.
