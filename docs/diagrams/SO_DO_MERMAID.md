# Sơ đồ Mermaid

Các hình mô tả mô hình Windows giám sát Linux qua SSH. Phần tùy chọn và giới hạn được nêu trong README và chú thích từng hình.

## Hình 1. Kiến trúc tổng thể hệ thống

Windows chạy Python để thu thập từ Linux VM, đánh giá trạng thái, lưu SQLite và gửi cảnh báo bằng luồng riêng. SNMP là phương án thu thập thay thế; Slack là kênh gửi tùy chọn.

```mermaid
flowchart LR
    admin["Người quản trị"]
    subgraph pc["MÁY THẬT WINDOWS"]
        env["Cấu hình .env<br/>Không đưa secret vào mã"]
        core["Python monitor_ssh.py<br/>Lập lịch + đánh giá trạng thái"]
        ui["Dashboard Terminal<br/>CPU / RAM / interface"]
        db[("SQLite<br/>Trạng thái + outbox")]
        sender["Luồng gửi cảnh báo<br/>Retry + xác nhận API"]
        env --> core
        core --> ui
        core <--> db
        db --> sender
    end
    linux["MÁY ẢO LINUX<br/>192.168.73.129<br/>OpenSSH Server"]
    agent["SNMP agent / thiết bị hỗ trợ<br/>Tùy chọn; chưa xác minh trong demo"]
    telegram["Telegram Bot API"]
    slack["Slack Incoming Webhook<br/>Tùy chọn"]
    app["Ứng dụng nhắn tin<br/>Người quản trị nhận cảnh báo"]
    admin -->|"Cấu hình / khởi chạy / xem"| core
    core -->|"SSH • TCP 22<br/>Đọc chỉ số mỗi 30 giây"| linux
    linux -->|"Kết quả lệnh"| core
    core -. "SNMP • UDP 161<br/>Phương án thay thế SSH" .-> agent
    sender -->|"HTTPS • TCP 443"| telegram
    sender -. "HTTPS • TCP 443" .-> slack
    telegram --> app
    slack -.-> app
    classDef primary fill:#eaf2ff,stroke:#2563eb,color:#0f172a;
    classDef storage fill:#ecfdf5,stroke:#059669,color:#064e3b;
    classDef optional fill:#fffbeb,stroke:#d97706,stroke-dasharray:6 4,color:#78350f;
    class core,linux,telegram,ui primary;
    class db storage;
    class agent,slack optional;
```

Luồng liền mô tả mô hình SSH + Telegram đang triển khai. Nét đứt màu vàng là phần tùy chọn đã có trong mã, chưa được xác minh trên môi trường demo của người dùng.

## Hình 2. Mô hình triển khai và mạng VMware NAT

Linux 192.168.73.129 và adapter Windows VMnet8 192.168.73.1 cùng subnet 192.168.73.0/24. Windows dùng SSH TCP 22 để giám sát Linux, đồng thời gửi Telegram qua kết nối Internet của Windows.

```mermaid
flowchart TB
    subgraph physical["MỘT MÁY VẬT LÝ: WINDOWS + VMWARE"]
        subgraph windows["WINDOWS HOST"]
            monitor["Python + VS Code<br/>Chạy script giám sát"]
            vmnet8["Adapter VMnet8<br/>192.168.73.1/24"]
            wifi["Wi-Fi Windows<br/>192.168.1.227/24"]
        end
        subgraph nat["MẠNG NAT VMNET8: 192.168.73.0/24"]
            linux["LINUX VM • ens33<br/>192.168.73.129/24<br/>OpenSSH Server • TCP 22"]
            gateway["VMware NAT Gateway<br/>192.168.73.2"]
        end
        monitor -->|"SSH: gửi lệnh"| vmnet8
        vmnet8 <-->|"Kết nối nội bộ cùng subnet"| linux
        linux -->|"Default route của Linux"| gateway
        gateway -. "Đường Internet của VM" .-> wifi
        monitor -->|"Đường gửi Telegram của Windows"| wifi
    end
    router["Router LAN<br/>192.168.1.1"]
    internet["Internet"]
    api["Telegram API<br/>api.telegram.org • HTTPS 443"]
    wifi --> router --> internet --> api
    classDef host fill:#eaf2ff,stroke:#2563eb,color:#0f172a;
    classDef vm fill:#ecfdf5,stroke:#059669,color:#064e3b;
    classDef network fill:#f1f5f9,stroke:#64748b,color:#0f172a;
    class monitor,vmnet8,wifi host;
    class linux vm;
    class gateway,router,internet network;
```

192.168.73.2 là gateway NAT của Linux, không phải IP máy Windows. Windows và Linux VM nằm trên cùng một máy vật lý; host tắt hoặc ngủ có thể làm VM dừng. Các IP theo thông tin đã cung cấp, có thể đổi khi cấu hình mạng thay đổi.

## Hình 3. Biểu đồ ca sử dụng

Người quản trị cấu hình, chạy/dừng, xem dashboard và nhận cảnh báo. Linux cung cấp chỉ số; Telegram API chuyển thông báo ra ứng dụng nhắn tin.

```mermaid
flowchart LR
    admin["«actor»<br/>Người quản trị"]
    linux["«hệ thống ngoài»<br/>Linux / OpenSSH"]
    telegram["«hệ thống ngoài»<br/>Telegram API"]
    subgraph system["HỆ THỐNG GIÁM SÁT VÀ CẢNH BÁO"]
        config(["Cấu hình thiết bị<br/>ngưỡng và kênh nhận tin"])
        monitor(["Khởi chạy / dừng<br/>giám sát định kỳ"])
        view(["Xem trạng thái<br/>và hàng đợi cảnh báo"])
        collect(["Thu thập chỉ số<br/>qua SSH"])
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

«include» là chức năng được dùng trong giám sát. «extend» biểu diễn nhánh chỉ phát sinh khi điều kiện thỏa: có chuyển trạng thái cần báo hoặc gửi tin thất bại. Hình tập trung vào ca SSH + Telegram hiện tại.

## Hình 4. Lưu đồ thu thập và đánh giá trạng thái

Mỗi chu kỳ mặc định 30 giây, hệ thống thu thập chỉ số, phân biệt lỗi kết nối với lỗi dữ liệu, đánh giá ngưỡng và so sánh trạng thái đã lưu.

```mermaid
flowchart TB
    start(["Bắt đầu chu kỳ kiểm tra"])
    read["Thu thập chỉ số qua SSH<br/>CPU / RAM / interface<br/>Nhiệt độ nếu đã bật"]
    connected{"Đường SSH<br/>hoạt động?"}
    parse["Chuẩn hóa dữ liệu<br/>Lỗi từng chỉ số → UNKNOWN"]
    down["Kết nối → DOWN<br/>Không suy diễn chỉ số thành 0"]
    evaluate["So sánh với trạng thái đã lưu<br/>Ngưỡng + hysteresis + mất dữ liệu"]
    change{"Có chuyển trạng thái<br/>cần thông báo?"}
    tx["Một giao dịch SQLite:<br/>lưu trạng thái + thêm outbox từng kênh"]
    state["Lưu trạng thái<br/>Không tạo tin lặp"]
    ui["Cập nhật dashboard<br/>Mất kết nối: đánh dấu số đo cũ"]
    wait["Chờ mốc chu kỳ tiếp theo<br/>Mặc định 30s; bỏ qua mốc quá trễ"]
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

Tin mới chỉ được tạo khi có chuyển trạng thái cần thông báo. Trạng thái và tin cảnh báo được ghi cùng giao dịch SQLite. Lần đầu mọi chỉ số bình thường không tạo tin thử; chỉ số chủ động tắt không tham gia vòng đánh giá.

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
    participant T as Telegram API
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
