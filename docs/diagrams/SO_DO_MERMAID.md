# Bộ sơ đồ Mermaid — GNS3 Device Monitor

## Hình 1. Kiến trúc tổng thể hệ thống

Windows chạy Python, thu chỉ số Linux qua đường GNS3 bằng SSH/SNMP hoặc hybrid, đánh giá trạng thái, lưu SQLite và gửi Telegram/Slack bằng luồng riêng.

```mermaid
flowchart TB
    admin["Người quản trị"]
    subgraph win["WINDOWS — VS CODE / PYTHON"]
      env[".env.gns3 + known_hosts"]
      app["device_monitor<br/>Lập lịch 5s + trạng thái"]
      collectors["SSH / SNMP / HYBRID"]
      ui["Dashboard: chỉ số, nguồn và trạng thái"]
      db[("SQLite: states + outbox")]
      sender["Luồng gửi: retry và xác nhận API"]
      env --> app --> collectors
      app --> ui
      app --> db --> sender
    end
    gns["GNS3 local Windows<br/>Cloud VMnet1 ↔ Switch ↔ Cloud VMnet2"]
    linux["Ubuntu VM: 192.168.10.129<br/>OpenSSH + Net-SNMP extend / IF-MIB"]
    temp["Nhiệt: auto → cảm biến / UNKNOWN<br/>demo luôn có nhãn MÔ PHỎNG"]
    tg["Telegram Bot API"]
    slack["Slack Incoming Webhook"]
    receiver["Ứng dụng nhận cảnh báo / phục hồi"]
    admin --> env
    collectors <-->|"SSH 22 / SNMP 161"| gns
    gns <--> linux
    linux -.- temp
    sender -->|"HTTPS"| tg --> receiver
    sender -->|"HTTPS"| slack --> receiver
```

Profile GNS3 lấy mẫu mỗi 5 giây. Nhiệt độ VM có thể UNKNOWN; nguồn demo phải ghi MÔ PHỎNG. Các kênh và giao thức được chọn bằng cấu hình.

## Hình 2. Mô hình triển khai GNS3 và VMware ba interface

Quản trị: Windows VMnet1 .10.1 qua hai Cloud và switch tới Linux VMnet2 .10.129. Mạng thử: NIC gns3test .30.129 qua Cloud VMnet3 tới switch và VPCS .30.10.

```mermaid
flowchart LR
  W["Windows: VS Code + Python<br/>VMnet1: 192.168.10.1"] --> C1["Cloud WINDOWS-VMNET1"]
  C1 --- S1["SW-MANAGEMENT"]
  S1 --- C2["Cloud LINUX-MGMT-VMNET2"]
  C2 --- L["Ubuntu NIC2: gns3mgmt<br/>192.168.10.129/24<br/>SSH 22 / SNMP 161"]
  L --- T["Ubuntu NIC3: gns3test<br/>192.168.30.129/24"]
  T --- C3["Cloud LINUX-DATA-VMNET3"]
  C3 --- S2["SW-TEST"]
  S2 --- V["VPCS-TEST<br/>192.168.30.10/24"]
  W --> M["Telegram / Slack qua Internet"]
  L -. "NIC1 ens33: NAT, tải gói/cứu hộ" .-> N["VMnet8: 192.168.73.129<br/>gateway 192.168.73.2"]
```

Windows VMnet2 dùng .20.1 để không có đường .10 trực tiếp. NIC NAT ens33 giữ .73.129/gateway .73.2; hai NIC lab không có gateway. VMware có thể giữ carrier UP khi Cloud mất đường.

## Hình 3. Biểu đồ ca sử dụng

Người quản trị cấu hình, chạy/dừng, xem dashboard và nhận cảnh báo. Linux cung cấp chỉ số qua SSH/SNMP; Telegram/Slack chuyển thông báo tới ứng dụng nhắn tin.

```mermaid
flowchart LR
    admin["«actor»<br/>Người quản trị"]
    linux["«hệ thống ngoài»<br/>Linux / SSH + SNMP"]
    telegram["«hệ thống ngoài»<br/>Telegram / Slack API"]
    subgraph system["HỆ THỐNG GIÁM SÁT VÀ CẢNH BÁO"]
        config(["Cấu hình thiết bị<br/>ngưỡng và kênh nhận tin"])
        monitor(["Khởi chạy / dừng<br/>giám sát định kỳ"])
        view(["Xem trạng thái<br/>và hàng đợi cảnh báo"])
        collect(["Thu thập chỉ số<br/>qua SSH/SNMP"])
        evaluate(["Đánh giá ngưỡng<br/>và chuyển trạng thái"])
        persist(["Lưu trạng thái<br/>và tin chưa gửi"])
        notify(["Phát cảnh báo<br/>và thông báo phục hồi"])
        retry(["Thử lại<br/>khi gửi thất bại"])
        monitor -. "«include»" .-> collect
        monitor -. "«include»" .-> evaluate
        monitor -. "«include»" .-> persist
        notify -. "«extend»<br/>có chuyển trạng thái cần báo" .-> monitor
        retry -. "«extend»<br/>gửi lỗi / chưa xác nhận" .-> notify
    end
    admin --- config
    admin --- monitor
    admin --- view
    admin --- notify
    linux --- collect
    telegram --- notify
    classDef actor fill:#f1f5f9,stroke:#64748b,color:#0f172a;
    classDef uc fill:#eaf2ff,stroke:#2563eb,color:#0f172a;
    class admin,linux,telegram actor;
    class config,monitor,view,collect,evaluate,persist,notify,retry uc;
```

«include» biểu diễn chức năng trong giám sát; «extend» biểu diễn phát cảnh báo khi đổi trạng thái và retry khi gửi lỗi. GNS3 là hạ tầng đường truyền, không phải nguồn số đo.

## Hình 4. Lưu đồ thu thập và đánh giá trạng thái

Mỗi chu kỳ theo profile GNS3 5 giây, hệ thống thu thập chỉ số, phân biệt lỗi kết nối với lỗi dữ liệu, đánh giá ngưỡng và so sánh trạng thái đã lưu.

```mermaid
flowchart TB
    start(["Bắt đầu chu kỳ kiểm tra"])
    read["Thu thập chỉ số qua SSH/SNMP<br/>CPU / RAM / interface<br/>Nhiệt độ nếu đã bật"]
    connected{"Có nguồn thu<br/>hoạt động?"}
    parse["Chuẩn hóa dữ liệu<br/>Lỗi từng chỉ số → UNKNOWN"]
    down["Kết nối → DOWN<br/>Không suy diễn chỉ số thành 0"]
    evaluate["So sánh với trạng thái đã lưu<br/>Ngưỡng + hysteresis + mất dữ liệu"]
    change{"Có chuyển trạng thái<br/>cần thông báo?"}
    tx["Một giao dịch SQLite:<br/>lưu trạng thái + thêm outbox từng kênh"]
    state["Lưu trạng thái<br/>Không tạo tin lặp"]
    ui["Cập nhật dashboard<br/>Mất kết nối: đánh dấu số đo cũ"]
    wait["Chờ mốc chu kỳ tiếp theo<br/>Profile GNS3 5s; bỏ qua mốc quá trễ"]
    start --> read --> connected
    connected -->|"Có"| parse --> evaluate
    connected -->|"Không"| down --> evaluate
    evaluate --> change
    change -->|"Có"| tx --> ui
    change -->|"Không"| state --> ui
    ui --> wait --> read
    classDef normal fill:#eaf2ff,stroke:#2563eb,color:#0f172a;
    classDef warning fill:#fffbeb,stroke:#d97706,color:#78350f;
    classDef database fill:#ecfdf5,stroke:#059669,color:#064e3b;
    class read,parse,evaluate,ui normal;
    class down,connected,change warning;
    class tx,state database;
```

Tin mới chỉ được tạo khi có chuyển trạng thái cần thông báo. Trạng thái và tin cảnh báo được ghi cùng giao dịch SQLite. Lần đầu mọi chỉ số bình thường không tạo tin thử; chỉ số chủ động tắt không tham gia vòng đánh giá. Hybrid còn báo mất từng dịch vụ dù nguồn dự phòng hoạt động.

## Hình 5. Lưu đồ hàng đợi, gửi tin và thử lại

Một luồng gửi riêng duyệt từng kênh, lấy tin cũ nhất đến hạn, gọi API và chỉ xóa tin khi đã được xác nhận thành công. Mỗi kênh giữ thứ tự tin riêng.

```mermaid
flowchart TB
    start(["Luồng gửi hoạt động độc lập"])
    inspect["Duyệt từng kênh Telegram / Slack<br/>Đọc tin cũ nhất của kênh trong SQLite"]
    due{"Có tin và<br/>đã đến hạn gửi?"}
    send["HTTPS POST<br/>Timeout kết nối 5s / đọc 10s"]
    ack{"API xác nhận<br/>thành công?"}
    delete["Xóa tin đã xác nhận khỏi outbox<br/>Cập nhật dashboard: đã gửi"]
    fail["Giữ nguyên tin trong outbox<br/>attempts += 1"]
    backoff["Đặt next_attempt<br/>Backoff 2, 4, 8... tối đa 300s<br/>HTTP 429: tôn trọng retry_after dài hơn"]
    wait["Xét kênh kế tiếp<br/>Hết lượt: chờ 0,5s"]
    start --> inspect --> due
    due -->|"Có"| send --> ack
    due -->|"Không"| wait
    ack -->|"Telegram: HTTP 2xx và ok=true<br/>Slack: HTTP 2xx và nội dung ok"| delete --> wait
    ack -->|"Lỗi mạng / HTTP lỗi<br/>hoặc chưa có xác nhận"| fail --> backoff --> wait
    wait --> inspect
    classDef normal fill:#eaf2ff,stroke:#2563eb,color:#0f172a;
    classDef warning fill:#fffbeb,stroke:#d97706,color:#78350f;
    classDef success fill:#ecfdf5,stroke:#059669,color:#064e3b;
    class inspect,send normal;
    class due,ack,fail,backoff warning;
    class delete success;
```

Backoff bắt đầu 2 giây rồi tăng đến tối đa 300 giây; HTTP 429 dùng thời gian chờ máy chủ yêu cầu nếu dài hơn. Đây là at-least-once: mất phản hồi hoặc dừng trước khi ghi nhận thành công có thể tạo tin trùng.

## Hình 6. Biểu đồ trình tự: RAM vượt ngưỡng và phục hồi

Kịch bản minh họa: RAM 70% vượt ngưỡng 65%, lần gửi đầu lỗi kết nối, lần sau nhận HTTP 200 và ok=true. Khi RAM về 50%, hệ thống phát thông báo phục hồi vì đã xuống dưới mức 60%.

```mermaid
sequenceDiagram
    autonumber
    participant M as Windows / luồng đo
    participant L as Linux / SSH
    participant D as SQLite
    participant W as Luồng gửi
    participant T as Telegram / Slack API
    M->>L: Đọc CPU, RAM, interface
    L-->>M: RAM = 70%
    Note over M,D: Ngưỡng RAM 65%, trạng thái trước là OK
    M->>D: Một transaction: RAM → ALERT + tin cảnh báo
    W->>D: Lấy tin cũ nhất đến hạn
    D-->>W: Tin cảnh báo RAM
    W-xT: POST lần 1: lỗi kết nối
    W->>D: Giữ tin, attempts + 1, hẹn thử lại
    Note over M,W: Vòng đo tiếp tục, gửi lỗi không chặn thu thập
    W->>D: Đọc lại tin khi đến hạn
    W->>T: POST lần 2
    T-->>W: HTTP 200, ok=true
    W->>D: Xóa tin đã xác nhận
    M->>L: Chu kỳ sau: đọc RAM
    L-->>M: RAM = 50%
    Note over M,D: 50% ≤ 60%: đạt ngưỡng phục hồi
    M->>D: Một transaction: RAM → OK + tin phục hồi
    W->>D: Lấy tin phục hồi đến hạn
    W->>T: Gửi thông báo RAM bình thường
    T-->>W: HTTP 200, ok=true
    W->>D: Xóa tin đã xác nhận
```

Các số đo và thứ tự sự kiện trong hình là kịch bản minh họa, không phải bản ghi một lần thử RAM đã được xác nhận. Luồng thu thập tiếp tục độc lập khi luồng gửi đang chờ thử lại.

## Hình 7. Biểu đồ trạng thái và hysteresis

Áp dụng cho CPU, RAM và nhiệt độ khi đã bật. Vượt T chuyển sang ALERT; chỉ về OK khi xuống mức T−H. Thiếu dữ liệu chuyển UNKNOWN nhưng giữ last_known để đánh giá đúng khi dữ liệu quay lại.

```mermaid
stateDiagram-v2
    direction LR
    state "Bình thường (OK)" as OK
    state "Cảnh báo (ALERT)" as ALERT
    state "Không xác định (UNKNOWN)" as UNKNOWN
    [*] --> UNKNOWN
    OK --> ALERT: x > T
    ALERT --> OK: x ≤ T − H
    OK --> UNKNOWN: Thiếu / lỗi dữ liệu
    ALERT --> UNKNOWN: Thiếu / lỗi dữ liệu
    UNKNOWN --> UNKNOWN: Vẫn chưa có dữ liệu
    UNKNOWN --> OK: Có dữ liệu, thuộc miền OK theo L
    UNKNOWN --> ALERT: Có dữ liệu, thuộc miền ALERT theo L
    note right of UNKNOWN
      L = last_known, trạng thái hợp lệ gần nhất
      Giữ L khi thiếu dữ liệu
      Nếu L = ALERT: ranh giới là T − H
      Nếu L khác ALERT: ranh giới là T
    end note
    note right of ALERT
      T: ngưỡng cảnh báo
      H: biên phục hồi, mặc định 5
      RAM: T = 65%, phục hồi ≤ 60%
    end note
    classDef good fill:#ecfdf5,stroke:#059669,color:#064e3b;
    classDef bad fill:#fff1f2,stroke:#e11d48,color:#881337;
    classDef unknown fill:#fffbeb,stroke:#d97706,color:#78350f;
    class OK good;
    class ALERT bad;
    class UNKNOWN unknown;
```

H mặc định bằng 5: CPU cảnh báo >75%, phục hồi ≤70%; RAM >65%, phục hồi ≤60%; nhiệt độ >65°C, phục hồi ≤60°C. Interface dùng ánh xạ UP/DOWN/UNKNOWN riêng, không dùng ngưỡng số.

## Hình 8. Mô hình dữ liệu SQLite thực tế

Hai bảng thực tế là states và outbox. states lưu trạng thái kết nối và trạng thái từng chỉ số dưới dạng JSON; outbox lưu tin chưa gửi cùng số lần thử và thời điểm thử tiếp.

```mermaid
erDiagram
    direction LR
    states {
        TEXT key PK "Định danh thiết bị SHA-256"
        TEXT value "JSON: connection, status và last_known"
    }
    outbox {
        INTEGER id PK "Thứ tự tin trong hàng đợi"
        TEXT channel "Định danh kênh nhận tin"
        TEXT message "Nội dung cảnh báo và thời gian"
        INTEGER attempts "Số lần gửi thất bại"
        REAL next_attempt "Unix time của lần thử tiếp"
    }
```

Không có khóa ngoại giữa hai bảng. Tính nhất quán được đảm bảo bởi giao dịch ứng dụng trong Store.observe. Tin gửi thành công bị xóa; hiện chưa có bảng lưu lịch sử CPU/RAM theo thời gian hoặc lịch sử toàn bộ tin đã gửi.
