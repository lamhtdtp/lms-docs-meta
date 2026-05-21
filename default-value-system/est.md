# Ước lượng manday — Thiết lập giá trị mặc định LCMS

**Cơ sở:** `default-value-system/Data_Default.md` (chuyển từ `Data_Default.pdf` — 13 slides).  
**Nguồn yêu cầu:** CMS LCMS (slide 2–7) và LCMS (slide 8–12).  
**Đội hình:** 1 Backend · 1 Frontend.

---

## Mã hạng mục

| Mã | Ý nghĩa |
|----|---------|
| **BE-1** | CMS: Filter loại gói tài nguyên |
| **BE-2** | CMS: Field mô tả gói tài nguyên |
| **BE-3** | CMS: Flag `is_default` + seed 24 tài nguyên mặc định |
| **BE-4** | LCMS: Phân quyền tài nguyên theo role (GV / HS) |
| **BE-5** | LCMS: Auto-assign tài nguyên theo khối lớp |
| **BE-6** | LCMS: Override tài nguyên theo Chi nhánh |
| **BE-7** | LCMS: Seed data mặc định khi tạo Chi nhánh |
| **BE-8** | LCMS: Seed tiết học mặc định |
| **BE-9** | LCMS: Phân bổ GV phụ trách lớp tại tạo người dùng |
| **BE-QA** | QA BE, regression, fix edge |
| **FE-1** | CMS: UI filter loại gói tài nguyên |
| **FE-2** | CMS: UI field mô tả + checkbox is_default |
| **FE-3** | LCMS: Hiển thị tài nguyên theo role |
| **FE-4** | LCMS: UI override tài nguyên theo Chi nhánh |
| **FE-5** | LCMS: Trường lớp phụ trách tại form tạo/sửa GV |
| **FE-QA** | API integration, polish, fix |

---

## Backend (`lms-api`) — manday

| Mã | Hạng mục | Nội dung chi tiết | Khoảng |
|----|----------|-------------------|--------|
| **BE-1** | Filter loại gói TN | Thêm enum `loai_goi` (6 giá trị: KSNL/K12/ĐH-CĐ/TTNN/Demo/Others) vào model gói tài nguyên; bổ sung param filter vào API list | **1–2** |
| **BE-2** | Mô tả gói TN | Migration thêm cột `description` (text, nullable); cập nhật API create/update gói tài nguyên | **0.5–1** |
| **BE-3** | is_default + seed 24 TN | Thêm trường `is_default` (bool) vào bảng tài nguyên; viết seeder/migration cho ~24 tài nguyên mặc định kèm mapping 7 category (slide 6–7); logic gán khi tạo gói mới | **3–5** |
| **BE-4** | Phân quyền TN theo role | Cấu hình rule: GV → toàn bộ TN; HS → TN học tập, bổ trợ, Phòng đọc, Vui học; middleware/guard kiểm tra role khi gọi API TN | **3–5** |
| **BE-5** | Auto-assign TN theo khối | Khi tạo/thêm lớp vào khối đã có gói TN → tự động gán TN mặc định; handle trường hợp thêm lớp muộn vào khối đã có | **3–5** |
| **BE-6** | Override TN theo Chi nhánh | Bảng/entity lưu cấu hình override per-branch; API cho phép Super Admin/Admin ghi đè quyền TN; logic resolve: branch override > default | **2–4** |
| **BE-7** | Seed data khi tạo Chi nhánh | Trigger sau khi tạo Chi nhánh: (1) sinh mã `CN_XX`; (2) tạo Năm học mặc định nếu K12 (HK1: 01/08, HK2: 01/02, kết thúc: 31/07 năm tiếp); (3) bật khối lớp theo loại CN; (4) bật môn học theo mapping chuyên môn *(chờ data)*; (5) bật gói TN theo mapping *(chờ data)*; (6) seed ngày lễ dương lịch | **5–9** |
| **BE-8** | Seed tiết học mặc định | Seed cấu hình tiết Sáng (1–5 + ra chơi) và Chiều (1–5 + ra chơi) áp dụng cho tất cả các ngày trong tuần *(chờ đủ giờ từ Mr. Phục)* | **1–2** |
| **BE-9** | Phân bổ GV theo lớp | API lấy danh sách lớp theo chi nhánh (cho dropdown); bổ sung quan hệ GV ↔ lớp phụ trách (không bắt buộc) vào create/update user | **2–3** |
| **BE-QA** | QA / fix / regression | Edge: khối lớp chưa có TN khi tạo lớp, branch override không khớp, năm học edge cuối năm, mã CN trùng | **3–6** |
| | **Tổng BE** | | **23–42 manday** |

> **Phụ thuộc chặn BE-7:** Cần mapping môn học + gói TN từ bộ phận chuyên môn trước khi hoàn thiện logic seed chi nhánh. Có thể implement skeleton trước, bổ sung data sau.

---

## Frontend — manday

| Mã | Hạng mục | Nội dung chi tiết | Khoảng |
|----|----------|-------------------|--------|
| **FE-1** | Filter loại gói TN (CMS) | Thêm dropdown filter `Loại gói` vào màn hình danh sách gói tài nguyên CMS; gọi API với param filter | **1–2** |
| **FE-2** | Mô tả + is_default (CMS) | Thêm field `Mô tả` (textarea) và checkbox `Tài nguyên mặc định` vào form Thêm mới / Chỉnh sửa; hiển thị trong danh sách (tooltip hoặc cột) | **1–2** |
| **FE-3** | Hiển thị TN theo role (LCMS) | Lọc/ẩn tài nguyên trong UI dựa trên role người dùng (GV xem tất cả, HS chỉ thấy nhóm được phép) | **2–3** |
| **FE-4** | Override TN theo Chi nhánh (LCMS) | UI trong trang cài đặt chi nhánh: bật/tắt quyền từng loại TN; gọi API override; hiển thị trạng thái default vs custom | **2–4** |
| **FE-5** | Lớp phụ trách GV (LCMS) | Thêm trường `Lớp phụ trách` (multi-select, không bắt buộc, có search/filter) vào form tạo/chỉnh sửa người dùng role GV; gọi API danh sách lớp theo chi nhánh | **2–3** |
| **FE-QA** | API integration, polish, fix | Kết nối đầy đủ các API, xử lý loading/error state, responsive, i18n nếu cần | **2–3** |
| | **Tổng FE** | | **10–17 manday** |

---

## Tổng hợp

| Hạng mục | Khoảng manday |
|----------|--------------|
| **Backend** | **23–42** |
| **Frontend** | **10–17** |
| **Tổng (tuần tự 1 dev mỗi role)** | **33–59 manday** |

---

## Song song dev (wall-clock gợi ý)

| Đội hình | Wall-clock ước tính |
|----------|---------------------|
| **1 BE + 1 FE** làm song song | `max(BE, FE) + 0.25–0.5` chờ API contract → **~25–45 md wall-clock** |

> FE có thể bắt đầu sớm CMS tasks (FE-1, FE-2) trong khi BE hoàn thiện LCMS core (BE-4 → BE-7).

---

## Điều kiện để số "nhỏ" trong dải

- Nhận đủ mapping môn học + gói TN từ bộ phận chuyên môn sớm (không chặn BE-7).
- Mr. Phục cung cấp đầy đủ giờ tiết học (unblock BE-8 ngay sprint đầu).
- Reuse tối đa UI component filter/form đã có trong CMS.
- Role-based access đã có middleware sẵn trong codebase → chỉ config thêm.

## Điều kiện để số "lớn" trong dải

- Data mapping chuyên môn về muộn → phải quay lại implement BE-7 nhiều lần.
- Override per-branch phức tạp hơn dự kiến (nhiều cấp kế thừa: system → loại CN → CN).
- Auto-assign (BE-5) cần xử lý edge case lớp thêm muộn vào khối đã hoạt động.
- FE-4 (override UI) lệch Figma nhiều → mất thêm thời gian polish.

---

## Điểm cần làm rõ trước khi chốt số

| # | Vấn đề | Người phụ trách | Ảnh hưởng |
|---|--------|-----------------|-----------|
| 1 | Thời gian đầy đủ các tiết học (Sáng 2–5, Chiều 1–5) | Mr. Phục | Chặn BE-8 |
| 2 | Mapping môn học & gói TN theo từng cấp học | Bộ phận chuyên môn | Chặn BE-7 (seed môn/TN) |
| 3 | Danh sách ngày lễ cần seed | BA / Product | Ảnh hưởng BE-7 |
| 4 | Rule mã Chi nhánh (prefix, padding, reset theo năm?) | Dev / BA | BE-7 |
| 5 | Override TN per-branch: cấp độ override (loại CN hay từng CN?) | BA / Product | Scope BE-6 + FE-4 |

---

*Ước lượng ballpark — cần breakdown sprint + spike sau khi có đủ data từ bộ phận chuyên môn và Mr. Phục.*
