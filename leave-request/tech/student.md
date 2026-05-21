# Tech — Luồng Học sinh (HS-01, HS-02)

Tài liệu triển khai đối chiếu `xin-nghỉ-phép/student/HS-01.md`, `xin-nghỉ-phép/student/HS-02.md` và `xin-nghỉ-phép/SKILL.md` (FRS: HS **xem** đơn, **không** tạo / không duyệt).

## Nguồn code

| Repo | Đường dẫn máy |
|------|----------------|
| Backend | `~/dev/dtp/lms-api` — `BaseController#isStudent()` + `getCurrentUserId()` cho scope HS |
| Frontend | `~/dev/dtp/lms-fe` — pattern tương tự màn read-only (ví dụ `pages/enrollment-requests.js` + `components/pages/EnrollmentRequest`) |

Module đơn nghỉ phép khi triển khai nên **dùng chung** entity / bảng / DTO với luồng phụ huynh; khác biệt chủ yếu ở **phân quyền** và **filter theo `student_id`** thay vì theo `created_by`. Chi tiết entity & API dùng chung: `xin-nghỉ-phép/tech/parent.md`.

## Phạm vi màn Học sinh (so với Phụ huynh)

| Mã | File đặc tả | Ý chính |
|----|-------------|---------|
| HS-01 | `xin-nghỉ-phép/student/HS-01.md` | Danh sách đơn **gắn với HS đang đăng nhập** (đơn do PH gửi cho HS đó). **Không** nút Thêm mới (mặc định theo FRS). Lọc thời gian gửi + trạng thái tương tự RR-01; cột nhấn mạnh **người gửi là PH** nếu annotation (`27574:202059`) quy định |
| HS-02 | `xin-nghỉ-phép/student/HS-02.md` | Chi tiết **read-only**, mở từ HS-01 — **Xem chi tiết**. Đồng bộ định dạng với RR-01 / RR-HS-01; biến thể theo Chờ / Đồng ý / Từ chối |

Điểm cố định FRS (SKILL): HS **không** thuộc nhóm **Tạo đơn nghỉ** — không expose `POST /leave-requests` cho role `STUDENT`; UI không hiển thị luồng tạo đơn trừ khi BA đổi spec có văn bản.

## Backend (`lms-api`)

### Cùng module `leaverequest` với PH

- Entity giữ `student_id`, `created_by` (PH), `status`, khung buổi/ngày, lý do, thông tin duyệt/từ chối — một bản ghi là “đơn của PH cho HS”, HS chỉ **đọc** theo `student_id`.

### Phân quyền & scope dữ liệu cho HS

| Role | Danh sách (`GET` … list) | Chi tiết (`GET` … `/{id}`) |
|------|---------------------------|-----------------------------|
| `STUDENT` | Chỉ các bản ghi có **`student_id = getCurrentUserId()`** (và thêm filter chi nhánh/năm học nếu repo bắt buộc như các API HS khác). Sort **mới trước** như RR-HS-01 | Chỉ khi `leaveRequest.getStudent().getId().equals(getCurrentUserId())`; sai → `403` / `404` |
| `PARENT` | Theo `created_by` như `tech/parent.md` | Theo chủ đơn PH |

### API gợi ý (tái sử dụng endpoint list/detail)

**Phương án A (khuyến nghị):** một cặp endpoint dùng chung, controller tự chọn criteria theo role:

- `GET /leave-requests` — nếu `isStudent()` thì `criteria.setStudentId(getCurrentUserId())` (+ query giống PH: khoảng ngày gửi, trạng thái, `page`/`size`). **Không** cho `STUDENT` gọi `POST`.
- `GET /leave-requests/{id}` — kiểm tra quyền: PH (chủ `created_by`) **hoặc** HS (chủ `student_id`) **hoặc** GV/Admin (phase sau theo lớp/chi nhánh).

**Phương án B:** tách `GET /students/me/leave-requests` chỉ cho HS — tương đương nghiệp vụ, tăng số route; chỉ cần khi muốn tách hẳn policy.

`@PreAuthorize` có thể dùng `hasAnyAuthority('PARENT','STUDENT',…)` trên `GET`; `POST` chỉ `PARENT` (và admin nếu sau này có backoffice tạo hộ).

### DTO list cho HS-01

- Trùng cấu trúc với PH ở mức “cùng một đơn”; bổ sung/đặt tên field để UI hiển thị **người gửi (PH)** rõ ràng (họ tên + thời gian gửi) theo mock / `RR-HS-01`.
- Không cần API riêng nếu DTO list đã có `requester` / `submittedAt` / `period` / `review` / `status` / `rejectReason`.

## Frontend (`lms-fe`)

### Hành vi màn (khác PH)

- **HS-01:** bảng + bộ lọc + phân trang + empty state — **không** block “Thêm mới”, **không** modal tạo đơn.
- **HS-02:** modal/chi tiết read-only — có thể **tái sử dụng** component chi tiết với màn PH (cùng field, cùng format), chỉ khác copy/tiêu đề theo Figma HS nếu có.
- **Routing:** thêm trang mới (ví dụ `pages/.../leave-requests.js` dưới menu HS) — cần gắn menu theo role `STUDENT` trong layout/navigation hiện có; tên file đặt thống nhất với team (ví dụ gần `pages/attendance/`, `pages/notify/`).
- **API:** cùng `apiConfig.leaveRequest.getList` / `getDetail` như PH; token/session đã phân role — BE trả đúng phạm vi. Component list HS có thể là biến thể `props.readOnly` / `props.showCreateAction={false}` so với màn PH.

### Đồng bộ UI

- Định dạng `HH:mm DD/MM/YYYY`, `dd/mm/yyyy`, buổi **Sáng / Chiều / Tối** — cùng helper format như màn PH (`BR-LEAVE-01`).
- Pop-up lý do từ chối — thống nhất icon/copy với list + chi tiết (giống FR-01 / FR-03).
- Footer **Tổng [x] dòng** khớp `totalElements` — tránh lệch như review trong đặc tả PH.

## Pattern tái sử dụng trong repo

| Mục đích | Tham chiếu |
|----------|------------|
| Kiểm tra role trong BE | `vn.dtpsoft.modules.BaseController` — `isStudent()`, `getCurrentUserId()` |
| Page read-only + filter + modal | `pages/enrollment-requests.js`, `components/pages/EnrollmentRequest/EnrollmentRequest.js` |
| Đăng ký API | `services/api/config.js`, hook React Query |

## Câu hỏi cần BA / PO / Design

1. **HS-01** cột nào khác hẳn FR-01 (ngoài ẩn Thêm mới)? Đối chiếu frame `27574:202059` để tránh lệch nhãn.
2. HS có xem được đơn của **mọi PH** đã gửi cho mình hay chỉ một PH “đại diện”? (Thường: mọi đơn có `student_id` = HS.)
3. Cùng URL hay khác URL giữa PH và HS? (Ảnh hưởng SEO/menu — kỹ thuật có thể hai route cùng một component.)

## Liên kết đặc tả

- `xin-nghỉ-phép/student/HS-01.md`
- `xin-nghỉ-phép/student/HS-02.md`
- `xin-nghỉ-phép/parent/FR-01.md` (logic lọc/chung)
- `xin-nghỉ-phép/parent/FR-03.md` (chi tiết — tham chiếu)
- `xin-nghỉ-phép/SKILL.md`
- `xin-nghỉ-phép/tech/parent.md` (entity & API dùng chung)
