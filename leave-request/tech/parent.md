# Tech — Luồng Phụ huynh (FR-01 … FR-03)

Tài liệu triển khai đối chiếu đặc tả trong `xin-nghỉ-phép/parent/` và business rules trong `xin-nghỉ-phép/SKILL.md` (FRS module quản lý nghỉ phép).

## Nguồn code

| Repo | Đường dẫn máy |
|------|----------------|
| Backend | `~/dev/dtp/lms-api` — Spring Boot, JPA, pattern `modules/<feature>/` |
| Frontend | `~/dev/dtp/lms-fe` — Next.js (`pages/`), `services/api/config.js`, React Query |

Trạng thái hiện tại (đối chiếu khi đọc doc): trong hai repo **chưa có** module đơn nghỉ phép riêng; nên triển khai module mới và tái sử dụng pattern có sẵn (xem dưới).

## Phạm vi màn Phụ huynh

| Mã | File đặc tả | Ý chính |
|----|-------------|---------|
| FR-01 | `xin-nghỉ-phép/parent/FR-01.md` | Danh sách đơn của **chính PH đăng nhập**; lọc ngày gửi + trạng thái; phân trang; empty state; **Thêm mới** phụ thuộc năm học hiện tại |
| FR-02 | `xin-nghỉ-phép/parent/FR-02.md` | Modal tạo đơn: buổi + ngày bắt đầu/kết thúc, lý do; đồng bộ nhãn buổi với danh sách |
| FR-03 | `xin-nghỉ-phép/parent/FR-03.md` | Chi tiết đơn (pop-up từ **Thao tác → Xem chi tiết**): chỉ đọc; biến thể theo trạng thái; lý do từ chối; định dạng thời gian như RR-01 |

BR nghiệp vụ cần khớp (tóm tắt): **BR-LEAVE-01** (buổi + ngày), **BR-LEAVE-03** (`PENDING` không tác động điểm danh; `REJECTED` không auto nghỉ không phép), **BR-LEAVE-05** (không overlap với đơn `PENDING`/`APPROVED`), **NG-07**.

## Backend (`lms-api`)

### Vị trí & kiểu module

- Thêm package kiểu `vn.dtpsoft.modules.leaverequest` (hoặc tên đồng nhất convention repo): `Entity`, `Repository`, `Criteria` + `Specification`, `Service`, `Mapper`, `dto`, `form`, `LeaveRequestController`.
- Tham chiếu **luồng xét duyệt + reviewer + note** đã có ở `classroomjoinrequest` (ví dụ `ClassroomJoinRequestService`).
- Điểm danh hiện có `rollcall` (`EAttendanceStatus`: `PRESENT`, `EXCUSED_ABSENCE`, `UNEXCUSED_ABSENCE`). Phase sau khi có duyệt đơn: áp `EXCUSED_ABSENCE` + nguồn `LEAVE_REQUEST` theo FRS (không làm trong scope chỉ PH nếu chưa có API duyệt).

### Entity (gợi ý cột tối thiểu)

- Liên kết: `student_id`, `classroom_id`, `school_year_id`, `created_by` (PH).
- Khung nghỉ: `start_session`, `start_date`, `end_session`, `end_date` (enum buổi: Sáng / Chiều / Tối — map với hằng số Java).
- Nội dung: `reason` (text).
- Trạng thái: `PENDING` | `APPROVED` | `REJECTED`.
- Khi đã xử lý: `reviewed_by`, `reviewed_by_role_code`, `reviewed_at`, `reject_reason` (nullable).
- Timestamp tạo/sửa (Auditing nếu repo đã dùng).

### API gợi ý cho PH (Phase 1)

| Method | Path | Mục đích |
|--------|------|----------|
| `GET` | `/leave-requests` | Danh sách: **bắt buộc** filter theo `created_by = currentUserId` khi role `PARENT`; query lọc ngày gửi, trạng thái, phân trang; sort **mới trước** |
| `GET` | `/leave-requests/{id}` | Chi tiết (FR-03): kiểm tra PH chỉ đọc được đơn của chính mình |
| `POST` | `/leave-requests` | Tạo đơn (FR-02) |

**Không** tin `parentId`/`createdBy` từ client — luôn gán từ session.

### Validate khi tạo đơn

1. `studentId` thuộc quan hệ PH–HS (`studentparent` / service tương đương).
2. Năm học / lớp: chỉ cho phép khi `school_year` đang **GOING_ON** (tương đương logic disable nút Thêm mới trên FR-01) — có thể tái dùng ý kiểm tra như `ClassroomJoinRequestService.validateJoinRequest` (kiểm tra `ESchoolYear`).
3. Thứ tự ngày/buổi hợp lệ (cùng ngày: buổi bắt đầu ≤ buổi kết thúc).
4. **BR-LEAVE-05:** không trùng khoảng thời gian với đơn `PENDING`/`APPROVED` của cùng học sinh (thống nhất với BA nếu overlap có áp theo PH hay theo HS).

### DTO trả về (đồng bộ FE)

- List row: học sinh, người gửi, thời gian gửi, khung **Từ / Đến** (buổi + ngày), thông tin duyệt (hoặc `-` khi chờ), trạng thái, `rejectReason` khi cần preview.
- Detail: đủ field cho FR-03 + `reason` đầy đủ (không cắt ellipsis trừ khi design khác).

## Frontend (`lms-fe`)

### Vị trí file

- Trang: `pages/leave-requests.js` (theo pattern `pages/enrollment-requests.js`).
- Component: ví dụ `components/pages/LeaveRequest/` — form modal tạo đơn, modal/table chi tiết.
- API: `services/api/config.js` (thêm block endpoint), module `services/api/leave-request.js` + hook React Query (tham chiếu `services/api/enrollment-request.js`).

### FR-01 — Danh sách

- `DateRangePicker`: cho phép để trống một hoặc cả hai đầu (theo RR-01).
- Filter trạng thái: **single choice** (khác multi-select một số màn khác trong repo).
- Bảng: cột và định dạng `HH:mm DD/MM/YYYY`; tên **họ đệm + tên** + `TextClamp`/tooltip khi dài.
- Empty state theo mock; footer **Tổng N dòng** khớp dữ liệu thật.
- Menu **Thao tác → Xem chi tiết** → mở modal chi tiết (FR-03).
- Trạng thái **Từ chối**: icon/pop-up lý do thống nhất với FR-03.

### FR-02 — Thêm mới

- Nút **Thêm mới**: `disabled` khi không phải năm học hiện tại (dữ liệu năm học lấy từ API đã có cho PH, ví dụ `GET /parents/children-classroom` + `schoolYear.state`).
- Form: buổi + ngày (hai đầu), textarea lý do; submit `POST /leave-requests`; xử lý lỗi overlap (400 + mã lỗi thống nhất với BE).

### FR-03 — Chi tiết

- Chỉ đọc; **Chờ xét duyệt**: phần thông tin duyệt hiển thị `-`.
- **Đồng ý / Từ chối**: tên người duyệt + thời gian duyệt.
- **Từ chối**: hiển thị đủ lý do; đồng bộ với list.

## Pattern tái sử dụng trong repo

| Mục đích | Tham chiếu |
|----------|------------|
| Layout page + `Layout` + i18n | `pages/enrollment-requests.js` |
| Filter ngày + infinite list + modal lý do | `components/pages/EnrollmentRequest/EnrollmentRequest.js` |
| Đăng ký endpoint trong `config.js` | `services/api/config.js` (`enrollmentRequest`, `parent`, …) |
| Scope PH + danh sách HS/lớp | `ParentController` (`/parents/my-students`, `/parents/children-classroom`) |
| Luồng request có trạng thái + reviewer | `ClassroomJoinRequestService` |

## Câu hỏi cần BA / PO xác nhận trước code

1. PH nhiều con: modal chọn HS hay cố định theo ngữ cảnh trang (ví dụ `view-children`)?
2. Cho phép đơn có ngày bắt đầu là **hôm nay** / **quá khứ** hay chỉ tương lai?
3. **BR-LEAVE-05** áp theo **học sinh** (khuyến nghị) hay theo từng PH?
4. Trường lý do: bắt buộc hay tùy chọn?
5. Phase 1 có bắt buộc **audit log** attendance chưa hay chờ phase duyệt đơn phía GV/Admin?

## Liên kết đặc tả

- `xin-nghỉ-phép/parent/FR-01.md`
- `xin-nghỉ-phép/parent/FR-02.md`
- `xin-nghỉ-phép/parent/FR-03.md`
- `xin-nghỉ-phép/SKILL.md`
