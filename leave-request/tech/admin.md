# Tech — Luồng Admin / Super Admin (AD-01, AD-02)

Tài liệu triển khai đối chiếu `xin-nghỉ-phép/admin/AD-01.md`, `xin-nghỉ-phép/admin/AD-02.md` và `xin-nghỉ-phép/SKILL.md` (Admin và Super Admin được **duyệt đơn**; phạm vi thường **đa chi nhánh / đa lớp** hơn màn GVCN).

## Nguồn code

| Repo | Đường dẫn máy | Ghi chú |
|------|----------------|---------|
| Backend | `~/dev/dtp/lms-api` | Cùng module đơn nghỉ phép & API **review** như luồng GV; khác **điều kiện phân quyền** (không ràng buộc GVCN/HEAD) |
| Frontend | `~/dev/dtp/lms-school` | Màn **quản trị** — pattern `pages/manage-system/…`, hub `components/Pages/ManageSystem` |

Ứng dụng `lms-fe` (PH/HS) **không** dùng cho AD-01/AD-02.

Trạng thái hiện tại: module leave request chưa có trong API — build entity/API theo `xin-nghỉ-phép/tech/parent.md`, sau đó mở rộng list/review cho Admin như dưới.

## Phạm vai & phạm vi màn

| Mã | File đặc tả | Ý chính |
|----|-------------|---------|
| AD-01 | `xin-nghỉ-phép/admin/AD-01.md` | **Danh sách** đơn nghỉ ở kênh quản trị: lọc/cột/bảng (đa chi nhánh, đa lớp — chi tiết theo mock `27172:314979` + RR-AD-01 `27206:288214`); duyệt lẻ hoặc **hàng loạt** tùy thiết kế |
| AD-02 | `xin-nghỉ-phép/admin/AD-02.md` | **Đồng ý** / **Từ chối** + pop-up xác nhận / lý do từ chối (frame Admin `fileKey` `8Tx35RosfIXsvhXG36QWtl`); nghiệp vụ giống GV-02: **APPROVED** → attendance theo FRS; **REJECTED** → không auto nghỉ không phép (**NG-07**) |

**Không** có “Admin tạo đơn thay PH” trong FRS mặc định (ma trận SKILL: tạo đơn chỉ PH).

## Backend (`lms-api`)

### Dùng chung entity, duyệt & điểm danh

- Thực thể, trường `branch_id` / `classroom_id`, `status`, `reviewed_by`, `reject_reason`, … — thống nhất `xin-nghỉ-phép/tech/parent.md` và `xin-nghỉ-phép/tech/teacher.md`.
- Logic sau **Đồng ý** / **Từ chối** (cập nhật đơn + đồng bộ `EXCUSED_ABSENCE` + nguồn `LEAVE_REQUEST` khi `APPROVED`) — giống luồng GVCN; tái sử dụng **cùng service** `LeaveRequestService.review(...)` (sync in-tx, sau đó gọi `LeaveAttendanceSyncService.applyApprovedLeaves`) để tránh lệch BR. Slot tương lai defer; MANUAL mới hơn được giữ (NG-05). Chi tiết: **[`implementation-attendance-sync.md`](./implementation-attendance-sync.md)**.

### Phân quyền Admin vs GVCN

| Role | List (`GET`) | Review (`PUT`/`PATCH`) |
|------|----------------|-------------------------|
| `TEACHER` | Theo **lớp** + **HEAD** (GVCN) — xem `xin-nghỉ-phép/tech/teacher.md` | Chỉ khi **GVCN** của lớng của đơn |
| `ADMIN` | Theo **chi nhánh** (`branchId` session / criteria); có thể lọc `classroomId`, khoảng ngày, trạng thái | Đơn thuộc chi nhánh được phép; **không** kiểm tra `ETeacherAllocation.HEAD` |
| `SUPER_ADMIN` | Có thể **không** gán `branchId` cố định trong criteria (pattern các controller hiện có: `if (!SUPER_ADMIN) criteria.setBranchId(...)`) — cho phép lọc chi nhánh trên UI | Kiểm tra quyền trường học / chi nhánh tùy policy; đối chiếu `ClassroomJoinRequestController#list` và `BaseController#checkBranchPermission` |

**Đề xuất:** trong `LeaveRequestService.review`, nhánh `ERole.TEACHER` gọi `isTeacherKindOfClassroom(..., HEAD)`; nhánh `ADMIN`/`SUPER_ADMIN` chỉ kiểm tra `classroom.getBranch().getId()` (và school id nếu cần) khớp quyền user.

### API gợi ý (tái sử dụng endpoint GV)

Dùng chung:

- `GET /leave-requests` — query: `branchId` (optional cho Super Admin), `classroomId`, trạng thái, khoảng ngày gửi / ngày nghỉ (theo RR-AD-01), `page`, `size`.
- `GET /leave-requests/{id}` — chi tiết trước khi duyệt.
- `PUT /leave-requests/review` (hoặc tương đương) — body batch: `ids`, `status`, `rejectReason`.

**Batch:** `ClassroomJoinRequestService.updateJoinRequest` chỉ cho phép một **chi nhánh** trong một lần xử lý (`branchIds.size() != 1` → lỗi). **Đề xuất giữ quy tắc tương tự** cho duyệt đơn nghỉ (tránh phức tạp khóa điểm / notify đa chi nhánh) trừ khi BA yêu cầu khác.

**Khóa điểm:** có thể gọi `semesterService.validateBranchInTimeGradeFinalization(branchId)` như join request khi duyệt trong kỳ chốt điểm — thống nhất với GV.

### So sánh nhanh với join request admin

`ClassroomJoinRequestController`: `GET` list cho `SUPER_ADMIN`, `ADMIN`, `TEACHER` với `criteria.setBranchId` khi không phải Super Admin — **mirror** cho leave list.

## Frontend (`lms-school`)

### Vị trí màn AD-01 (hub Quản trị hệ thống)

Pattern có sẵn:

- Trang hub: `pages/manage-system/index.js` → `components/Pages/ManageSystem/ManageSystem.js`.
- Danh mục ô lớn + icon: `components/Pages/ManageSystem/data.js` (`manageList`) — mỗi item có `path`, `roles` (ví dụ chỉ `SUPER_ADMIN`, hoặc `SUPER_ADMIN` + `ADMIN`).
- Đường dẫn: `constants/paths.js` (`managerSystem*`); map role–route trong `paths.js` (mảng route guard).

**Đề xuất triển khai AD-01:**

1. Thêm route ví dụ `pages/manage-system/leave-request.js` (hoặc `leave-request/index.js`) — layout `Layout` giống các trang `manage-system/school-year`, …
2. Thêm `paths.managerSystemLeaveRequest` (tên chốt với team).
3. Thêm một ô trong `manageList` (`data.js`) trỏ tới path mới, `roles: [ SUPER_ADMIN, ADMIN ]` (hoặc đúng ma trận triển khai).
4. Bổ sung entry guard trong `constants/paths.js` cho route mới.
5. Component trang: bảng + filter **chi nhánh** (autocomplete branch nếu Super Admin), **lớp**, trạng thái, ngày — có thể tái sử dụng `Select`, `DateRangePicker`, table pattern từ các màn manage khác hoặc từ bảng enrollment (đã có filter `classroomIds`).

### AD-02 — Pop-up trên cùng màn hoặc route con

- Tái sử dụng **logic mutation** giống `xin-nghỉ-phép/tech/teacher.md` (đồng ý / từ chối, `rejectReason`).
- Copy/layout theo file Figma **Admin** (`8Tx35RosfIXsvhXG36QWtl`), không dùng nhầm asset GV.

### Khác biệt UX so với GV (GV-01)

| Khía cạnh | GV (tab trong chi tiết lớp) | Admin (AD-01) |
|-----------|-----------------------------|----------------|
| Ngữ cảnh | `manage-class/[id]/leave-request` — đã có `classroomId` | Toàn school / nhiều lớp — **filter** `branchId` + `classroomId` |
| Default filter | Một lớp | Theo chi nhánh đang chọn (cookie `branchId` trên `lms-school`) |

## Pattern tái sử dụng trong repo

| Mục đích | `lms-school` | `lms-api` |
|----------|--------------|-----------|
| Hub manage-system | `ManageSystem`, `data.js`, `paths.managerSystem*` | — |
| List có filter chi nhánh | Các màn `manage-system/*` (School year, Branch, …) | `prepareCriteria`, `checkBranchPermission` |
| Duyệt batch + một chi nhánh | — | `ClassroomJoinRequestService.updateJoinRequest` |
| Review không cần HEAD | — | Điều kiện role trong `LeaveRequestService` |

## Liên kết chéo

- Entity & API cốt lõi: `xin-nghỉ-phép/tech/parent.md`
- GVCN / tab lớp: `xin-nghỉ-phép/tech/teacher.md`
- Đặc tả nghiệp vụ: `xin-nghỉ-phép/SKILL.md`

## Câu hỏi cần BA / PO / Design

1. Super Admin: mặc định xem **tất cả chi nhánh** hay bắt buộc chọn chi nhánh trước (ảnh hưởng performance & query)?
2. **Batch duyệt** có cho phép **nhiều chi nhánh** trong một request không? (Khuyến nghị: không — giống join class.)
3. Cột bắt buộc trên bảng admin (mã lớp, tên HS, PH gửi, …) — đối chiếu `27206:288214`.
4. Admin có bị chặn duyệt trong kỳ **khóa điểm** giống GVCN không?

## Liên kết đặc tả

- `xin-nghỉ-phép/admin/AD-01.md`
- `xin-nghỉ-phép/admin/AD-02.md`
- `xin-nghỉ-phép/SKILL.md`
