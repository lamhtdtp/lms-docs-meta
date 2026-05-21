# Thiết lập giá trị mặc định cho LCMS

> Nguồn: `Data_Default.pdf` — 13 slides

---

## Slide 1 — Tiêu đề

**Thiết lập giá trị mặc định cho LCMS**

---

## Slide 2 — Phạm vi điều chỉnh: CMS LCMS

### Nội dung
Nhóm thay đổi đầu tiên nằm ở **CMS LCMS** (portal quản trị nội dung học liệu).

### Phân tích yêu cầu
- Phân biệt rõ 2 phạm vi thay đổi: **CMS LCMS** (slide 2–7) và **LCMS** (slide 8–12).
- Cần xác định quyền triển khai thay đổi CMS thuộc team nào (Content / Platform).

---

## Slide 3 — Thêm filter Loại gói tài nguyên

### Nội dung
Bổ sung bộ lọc **Loại gói** trên màn hình quản lý gói tài nguyên trong CMS:

| Giá trị filter |
|---|
| KSNL |
| Trường K12 |
| ĐH/CĐ |
| TTNN |
| Demo |
| Others |

### Phân tích yêu cầu
- **UI**: Thêm dropdown/checkbox filter `Loại gói` vào màn hình danh sách gói tài nguyên CMS.
- **Data**: Trường `loai_goi` cần tồn tại ở model gói tài nguyên với enum 6 giá trị trên.
- **API**: Filter danh sách gói tài nguyên theo `loai_goi`.
- **Ảnh hưởng**: Màn hình list, search gói tài nguyên trong CMS.

---

## Slide 4 — Thêm field Mô tả gói tài nguyên

### Nội dung
- Giữ filter Loại gói tài nguyên (như slide 3).
- Bổ sung thêm field **Mô tả gói tài nguyên** (`Description`).

### Phân tích yêu cầu
- **DB**: Thêm cột `description` (text) vào bảng gói tài nguyên.
- **UI CMS**: Hiển thị field `Mô tả` trong form Thêm mới / Chỉnh sửa gói tài nguyên.
- **UI list**: Có thể hiển thị tooltip/cột mô tả trong danh sách nếu cần.
- **API**: Bổ sung `description` vào payload create/update gói tài nguyên.

---

## Slide 5 — Thêm tick chọn mặc định tài nguyên

### Nội dung
Thêm checkbox **"Giá trị mặc định"** khi thêm mới tài nguyên.  
Các giá trị mặc định cụ thể được định nghĩa ở slide 6 và 7.

### Phân tích yêu cầu
- **UI**: Thêm checkbox `Tài nguyên mặc định` tại form thêm mới tài nguyên trong CMS.
- **Logic**: Nếu được tick, tài nguyên này sẽ được tự động gắn vào các gói/lớp mới theo cấu hình ở slide 6–7.
- **DB**: Cần trường `is_default` (boolean) ở bảng tài nguyên.
- **Liên kết**: Xem bảng mapping tài nguyên mặc định ở slide 6–7.

---

## Slide 6 — Bảng Tài nguyên mặc định (phần 1)

### Nội dung

| Tên tài nguyên | Tài nguyên giảng dạy | Tài nguyên học tập | Ngân hàng luyện tập | Ngân hàng đề thi | Tài nguyên bổ trợ | Phòng đọc | Vui học |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| DCR | X | | | | | | |
| DHA | X | X | X | | | | |
| ITS | | X | | | | | |
| ESB | X | | X | | | | |
| EWB | X | | X | | | | |
| Online workbook | X | X | | | | | |
| Audio SB/ WB | X | X | | | | | |
| Teacher's Book | X | | | | | | |
| Syllabus | X | | | | | | |
| Lesson Plan | X | | | | | | |
| Bài giảng trình chiếu | X | | | | | | |
| Flash Card | X | | | | | | |

### Phân tích yêu cầu
- Bảng định nghĩa tài nguyên nào thuộc **loại (category)** nào mặc định.
- **DB**: Bảng mapping `resource_default_category` hoặc enum `category` trên tài nguyên.
- **Logic khởi tạo**: Khi tạo mới gói tài nguyên, seed các tài nguyên theo bảng này.

---

## Slide 7 — Bảng Tài nguyên mặc định (phần 2)

### Nội dung

| Tên tài nguyên | Tài nguyên giảng dạy | Tài nguyên học tập | Ngân hàng luyện tập | Ngân hàng đề thi | Tài nguyên bổ trợ | Phòng đọc | Vui học |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| IWB | X | | | | | | |
| Answer key/ Scripts | X | | | | | | |
| Video/ Video Lesson | X | | | | | | |
| Video Song | X | X | | | | | |
| Lyrics/ Wordlist | X | X | | | | | |
| Cẩm nang phụ huynh | X | X | | | | | |
| Từ điển | X | X | | | | | |
| Online Practice | | X | | | | | |
| Notebook | X | X | | | | | |
| eReader | X | | | | | | |
| Đề có chữ Kiểm tra thường xuyên | | | | X | | | |
| Đề test, midterm, endterm | | | | X | | | |

### Phân tích yêu cầu
- Tiếp nối bảng slide 6, hoàn thiện danh sách tài nguyên mặc định.
- **Lưu ý Ngân hàng đề thi**: Cần phân biệt 2 loại đề (`Kiểm tra thường xuyên` vs `test/midterm/endterm`).
- **Tổng hợp**: Cần seed/data migration đầy đủ ~24 tài nguyên mặc định từ slide 6 + 7.

---

## Slide 8 — Phạm vi điều chỉnh: LCMS

### Nội dung
Nhóm thay đổi thứ hai nằm ở **LCMS** (hệ thống học trực tuyến chính).

### Phân tích yêu cầu
- Phân biệt với phần CMS ở trên; các thay đổi từ slide 9 trở đi áp dụng cho LCMS.

---

## Slide 9 — Tài nguyên – Vai trò sử dụng mặc định

### Nội dung
- **Giáo viên**: Truy cập toàn bộ tài nguyên.
- **Học sinh**: Chỉ truy cập `Tài nguyên học tập`, `Tài nguyên bổ trợ`, `Phòng đọc`, `Vui học`.
- Gói tài nguyên của **khối nào** thì mặc định áp dụng **toàn khối đó**.
- Nếu sau này thêm lớp mới vào khối, lớp đó cũng mặc định có tài nguyên này.
- Có thể edit tùy theo từng Chi nhánh.

### Phân tích yêu cầu
- **Phân quyền**: Cần cấu hình role-based access cho tài nguyên (`teacher`, `student`).
- **Logic scope**: Gói tài nguyên gắn với khối → tất cả lớp trong khối được kế thừa.
- **Auto-assign**: Khi tạo lớp mới trong khối đã có gói tài nguyên, tự động gán tài nguyên mặc định.
- **Override**: Chi nhánh có thể tùy chỉnh quyền tài nguyên riêng (ghi đè cấu hình mặc định).
- **API**: Cần endpoint lấy tài nguyên theo role + khối + chi nhánh.

---

## Slide 10 — Data mặc định khi tạo Chi nhánh

### Nội dung

| Bước | Mô tả | Ví dụ |
|---|---|---|
| Tạo Chi nhánh | Mã: `[CN]-[STT]`, Tên: `Chi nhánh [STT]`, chọn Loại chi nhánh | Mã: `CN_01`, Tên: `Chi nhánh 01`, Loại: Mầm non / Tiểu học / THCS / THPT / CĐ-ĐH / TTNN |
| Tạo Năm học mặc định *(chỉ K12)* | HK1: 01/08 năm hiện tại, HK2: 01/02 năm tiếp, Kết thúc: 31/07 năm tiếp | Năm 2026 → HK1: 01/08/2026, HK2: 01/02/2027, Kết thúc: 31/07/2027 |
| Khối lớp | Bật khối theo loại chi nhánh | Mầm non: Mầm–Chồi–Lá; Tiểu học: K1–K5; THCS: K6–K9; THPT: K10–K12 |
| Môn học | Bật môn theo loại chi nhánh *(cần thông tin từ bộ phận chuyên môn)* | Mầm non: Tiếng Anh, Tiếng Việt |
| Tài nguyên | Bật gói tài nguyên tương ứng với loại chi nhánh | Theo mapping từ bộ phận chuyên môn |
| Ngày lễ | Tạo sẵn các ngày lễ dương lịch | Tết Dương lịch, 30/4–1/5, 2/9, 24/11, … |

### Phân tích yêu cầu
- **Trigger**: Khi Admin tạo Chi nhánh mới → hệ thống tự động seed data mặc định.
- **Điều kiện rẽ nhánh**: Loại chi nhánh (`K12` vs `ĐH/CĐ` vs `TTNN`) quyết định data seed.
- **Năm học**: Chỉ tạo tự động cho loại K12; tính toán dựa vào năm hiện tại hệ thống.
- **Khối lớp / Môn học / Tài nguyên**: Cần file mapping từ bộ phận chuyên môn trước khi implement.
- **Ngày lễ**: Seed cứng danh sách ngày lễ dương lịch (hoặc cấu hình từ admin).
- **Mã chi nhánh**: Cần logic tự sinh số thứ tự tăng dần (`CN_01`, `CN_02`, …).

---

## Slide 11 — Quản lý Tiết học (Mr. Phục)

### Nội dung
Bảng thời khóa biểu tiết học mặc định:

| Buổi | Tiết | Thời gian |
|---|---|---|
| Sáng | 1 | 07:00 – 07:45 |
| Sáng | 2 | *(cần bổ sung)* |
| Sáng | 3 | *(cần bổ sung)* |
| Sáng | Ra chơi | *(cần bổ sung)* |
| Sáng | 4 | *(cần bổ sung)* |
| Sáng | 5 | *(cần bổ sung)* |
| Chiều | 1 | *(cần bổ sung)* |
| Chiều | 2 | *(cần bổ sung)* |
| Chiều | Ra chơi | *(cần bổ sung)* |
| Chiều | 3 | *(cần bổ sung)* |
| Chiều | 4 | *(cần bổ sung)* |
| Chiều | 5 | *(cần bổ sung)* |

> Áp dụng cho tất cả các ngày: Thứ 2 – Chủ nhật.

### Phân tích yêu cầu
- **Thiếu thông tin**: Slide chỉ có thời gian tiết Sáng 1 (07:00–07:45); các tiết còn lại chưa có giờ cụ thể → **cần Mr. Phục cung cấp đầy đủ**.
- **Seed data**: Tạo sẵn cấu hình tiết học mặc định khi khởi tạo chi nhánh.
- **Tuần 7 ngày**: Cấu hình áp dụng cho tất cả các ngày trong tuần (Thứ 2 → Chủ nhật).
- **Override**: Chi nhánh có thể chỉnh sửa lại bảng tiết học sau khi tạo.

---

## Slide 12 — Phân bổ Giáo viên theo tên

### Nội dung
- Phân bổ GV theo lớp hiện tại gặp khó khăn khi số lượng lớp quá nhiều.
- **Đề xuất**: Phân bổ giáo viên phụ trách lớp **ngay tại màn hình tạo người dùng** (danh sách các lớp hiện có để chọn).
- Trường chọn lớp **không bắt buộc** (để tránh trường hợp chưa tạo lớp thì không tạo được GV).

### Phân tích yêu cầu
- **UI**: Thêm trường `Lớp phụ trách` (multi-select, không bắt buộc) vào form tạo/chỉnh sửa người dùng với role Giáo viên.
- **Data source**: Dropdown lấy danh sách lớp hiện có của chi nhánh.
- **Validation**: Không validate bắt buộc; GV có thể được tạo mà chưa gán lớp.
- **Sync**: Khi GV được gán lớp sau đó, cần đồng bộ lại danh sách phụ trách.
- **UX**: Giải quyết bài toán performance khi chi nhánh có nhiều lớp (cần tìm kiếm/lọc trong dropdown).

---

## Slide 13 — Kết thúc

*Thank you!*

---

## Tổng hợp yêu cầu & điểm cần làm rõ

### Yêu cầu chính

| # | Hạng mục | Phạm vi | Độ ưu tiên |
|---|---|---|---|
| 1 | Thêm filter Loại gói tài nguyên | CMS | Cao |
| 2 | Thêm field Mô tả gói tài nguyên | CMS | Trung bình |
| 3 | Tick chọn mặc định cho tài nguyên | CMS | Cao |
| 4 | Seed tài nguyên mặc định (24 loại) | CMS + LCMS | Cao |
| 5 | Phân quyền tài nguyên theo role (GV / HS) | LCMS | Cao |
| 6 | Auto-assign tài nguyên theo khối lớp | LCMS | Cao |
| 7 | Override tài nguyên theo Chi nhánh | LCMS | Trung bình |
| 8 | Seed data mặc định khi tạo Chi nhánh | LCMS | Cao |
| 9 | Seed tiết học mặc định | LCMS | Trung bình |
| 10 | Phân bổ GV theo lớp tại màn hình tạo người dùng | LCMS | Trung bình |

### Điểm cần làm rõ / phụ thuộc

| # | Vấn đề | Người phụ trách |
|---|---|---|
| 1 | Thời gian chi tiết các tiết học (Sáng 2–5, Chiều 1–5) | Mr. Phục |
| 2 | Mapping môn học & gói tài nguyên theo từng cấp học | Bộ phận chuyên môn |
| 3 | Danh sách đầy đủ ngày lễ cần seed | BA / Product |
| 4 | Rule tự sinh mã chi nhánh (prefix, padding số) | Dev / BA |
