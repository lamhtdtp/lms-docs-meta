# Implementation plan — Leave Request (Teacher + Admin)

Tài liệu này tổng hợp giải pháp triển khai luồng **Giáo viên (GV-01/GV-02)** và **Admin/Super Admin (AD-01/AD-02)** dựa trên:

- Tech doc: `xin-nghỉ-phép/tech/teacher.md`, `xin-nghỉ-phép/tech/admin.md`
- Đặc tả màn: `xin-nghỉ-phép/teacher/GV-01.md`, `xin-nghỉ-phép/teacher/GV-02.md`, `xin-nghỉ-phép/admin/AD-01.md`, `xin-nghỉ-phép/admin/AD-02.md`
- Nghiệp vụ (FRS): `xin-nghỉ-phép/SKILL.md`

> Phạm vi: bao gồm cả **đồng bộ điểm danh** sau khi duyệt `APPROVED` — chi tiết kiến trúc + code skeleton + test plan ở **[`implementation-attendance-sync.md`](./implementation-attendance-sync.md)** (chốt: sync in-transaction, defer slot tương lai, audit table riêng, batch ≤ 50).

## 1. Mục tiêu

- **Teacher (GVCN)**: xem danh sách đơn nghỉ trong phạm vi **lớp đang xem**, duyệt **đồng ý/từ chối** (có thể batch theo thiết kế).
- **Admin/Super Admin**: xem danh sách đơn nghỉ ở kênh quản trị (đa lớp/đa chi nhánh theo quyền), duyệt **đồng ý/từ chối** (có thể batch theo thiết kế).
- Dùng **cùng entity + service** để tránh lệch rule giữa Teacher và Admin.

## 2. Backend (`~/dev/dtp/lms-api`) — API & phân quyền

### 2.1 API list / detail (dùng chung cho Teacher + Admin)

- **GET** `/leave-requests`
  - **Teacher**: bắt buộc query `classroomId` (đúng theo phạm vi GV-01).
  - **Admin**: tự động ràng buộc `branchId` theo session.
  - **Super Admin**: không ép `branchId`, cho phép lọc đa chi nhánh (theo policy).
- **GET** `/leave-requests/{id}`
  - Dùng để xem chi tiết trước khi duyệt (nếu UI cần).

**Filter criteria (đã có trong API):**

- `branchId` (super admin optional, admin lấy theo session)
- `classroomId`
- `status[]`
- `submittedFrom`, `submittedTo`
- `leaveOverlapFrom`, `leaveOverlapTo` (lọc đơn có khoảng nghỉ giao với khoảng ngày)

### 2.2 API review (dùng chung cho Teacher + Admin)

- **PUT** `/leave-requests/review`
  - Body:
    - `ids: number[]` (batch)
    - `status: APPROVED | REJECTED`
    - `rejectReason?: string` (bắt buộc khi `REJECTED`)
  - Rule:
    - Chỉ duyệt các đơn đang `PENDING`.
    - Batch chỉ xử lý **một chi nhánh** trong một request.
    - **Teacher** chỉ duyệt trong **một lớp** trong một request.

### 2.3 Phân quyền

- **Teacher**:
  - List: chỉ cần là GV có phân công trong lớp (subject/head/assistant theo policy repo), và đúng `branchId`.
  - Review: bắt buộc là **GVCN** của lớp (`ETeacherAllocation.HEAD`).
- **Admin**:
  - List/Review: chỉ trong `branchId` session.
- **Super Admin**:
  - List: theo school scope, không ép `branchId`.
  - Review: theo school scope.

### 2.4 Đồng bộ điểm danh sau `APPROVED`

- Khi duyệt `APPROVED`: trong cùng transaction `LeaveRequestService.review`, gọi `LeaveAttendanceSyncService.applyApprovedLeaves(leaves, ctx)` (sync, không async ở phase 1).
- Khi `REJECTED`: **không** auto map sang nghỉ không phép (NG-07) — service không được gọi.
- Slot ngày **tương lai** (`date > today`): **defer** cho job auto / SD-03 reconcile khi đến ngày.
- `MANUAL` mới hơn `reviewedAt`: **giữ MANUAL** (NG-05 last-write-wins) + audit `SKIPPED_NEWER_MANUAL`.
- Idempotency: review lặp lại cùng một `leave_request.id` → no-op nếu RC đã có `source=LEAVE_REQUEST` và `source_ref_id=leave.id`.
- Audit: ghi vào bảng riêng `attendance_audit` (xem schema + decision tree trong file `implementation-attendance-sync.md`).
- Response API `PUT /leave-requests/review` trả thêm payload `attendance: { applied, idempotent, noSlot, deferredFuture, skippedNewerManual }` để FE hiển thị toast.
- Batch tối đa **50 đơn / request**; vượt → 400 `LEAVE_REVIEW_BATCH_TOO_LARGE`, FE chia chunk.

→ Code + migration + test plan đầy đủ: **[`implementation-attendance-sync.md`](./implementation-attendance-sync.md)**.

## 3. Frontend (`~/dev/dtp/lms-school`) — Teacher (GV-01/GV-02)

### 3.1 Vị trí route & layout

Theo pattern màn chi tiết lớp tương tự “Yêu cầu tham gia lớp”:

- Route đề xuất: `pages/manage-class/[id]/leave-request.js`
- Layout: bọc `ClassDetailLayout` + breadcrumb theo role (copy từ `pages/manage-class/[id]/enrollment-request.js`)
- Thêm tab trong `components/layouts/ClassDetailLayout/ClassDetailLayout.js`
- Thêm path trong `constants/paths.js` (ví dụ `paths.classDetailLeaveRequest`)

### 3.2 UI & hành vi

- Danh sách đơn theo **classroomId** (đang xem).
- Chỉ enable duyệt với trạng thái **PENDING/Chờ xét duyệt**.
- Duyệt:
  - **Đồng ý**: modal confirm → gọi review `APPROVED`
  - **Từ chối**: modal nhập/chọn lý do → gọi review `REJECTED` + `rejectReason`
- Nếu user không phải GVCN: có thể ẩn nút hoặc để BE trả `403` và UI hiển thị thông báo phù hợp.

### 3.3 API module FE

- Thêm `services/api/leave-request.js`:
  - `getLeaveRequests` (query `classroomId`, filter, paging)
  - `getLeaveRequestDetail`
  - `reviewLeaveRequests` (mutation)
- Add config endpoints vào `services/api/config.js` (nhóm `leaveRequest` hoặc reuse `leave-requests`).

## 4. Frontend (`~/dev/dtp/lms-school`) — Admin/Super Admin (AD-01/AD-02)

### 4.1 Vị trí route (hub manage-system)

Theo pattern `ManageSystem`:

- Route đề xuất: `pages/manage-system/leave-request.js`
- Thêm `paths.managerSystemLeaveRequest`
- Thêm ô menu trong `components/Pages/ManageSystem/data.js` (`manageList`) với `roles: [ SUPER_ADMIN, ADMIN ]`
- Bổ sung route guard trong `constants/paths.js`

### 4.2 UI & filter

- Filter:
  - **Branch** (bắt buộc cho Super Admin nếu policy yêu cầu; Admin default theo cookie/session)
  - Classroom
  - Status
  - Submitted date range / Leave overlap date range
- Duyệt:
  - Đồng ý / Từ chối (lẻ hoặc batch theo thiết kế)
  - Lý do từ chối theo thiết kế

## 5. Figma / MCP reference (để đối chiếu UI)

### 5.1 Teacher

- **GV-01** (bảng danh sách trong chi tiết lớp)
  - `fileKey`: `C4iJx93ofU0JdPqcOfGK9i`
  - Mock: `27534:101368`
  - Annotation: `27574:201019`
- **GV-02** (modal duyệt)
  - `fileKey`: `C4iJx93ofU0JdPqcOfGK9i`
  - Annotation tổng: `27574:201409`
  - Popup từ chối: mock `27534:94772`, RR `27574:201505`
  - Lý do từ chối: mock `27567:207478`, RR `27574:201566`
  - Popup đồng ý: mock `27534:94782`, RR `27574:201437`

### 5.2 Admin

- **AD-01** (bảng danh sách)
  - `fileKey`: `8Tx35RosfIXsvhXG36QWtl`
  - Mock: `27172:314979`
  - Annotation: `27206:288214`
- **AD-02** (modal duyệt)
  - `fileKey`: `8Tx35RosfIXsvhXG36QWtl`
  - Annotation tổng: `27211:291316`
  - Popup từ chối: mock `27172:320431`, RR `27218:294262`
  - Lý do từ chối: mock `27207:550864`, RR `27218:294388`
  - Popup đồng ý: mock `27172:320441`, RR `27218:294193`

## 6. Checklist triển khai

- Backend (review + scope):
  - [ ] Confirm query/criteria cho Admin/SuperAdmin đúng performance policy (Super Admin có bắt chọn branch trước hay không).
  - [ ] Hoàn thiện response fields theo cột bảng (RR-GV-01 / RR-AD-01).
  - [ ] Duyệt batch + validate `rejectReason` theo UI; reject vượt 50 đơn → 400.
- Backend (đồng bộ điểm danh — xem `implementation-attendance-sync.md`):
  - [ ] Liquibase: bảng `attendance_audit` + bổ sung cột `rollcall.source/source_ref_id` (nếu chưa có).
  - [ ] `LeaveAttendanceSyncService.applyApprovedLeaves` + unit test 8 case (TC-ATT).
  - [ ] Tích hợp trong `LeaveRequestService.review` (sync in-tx).
  - [ ] Response API thêm `attendance` outcome.
  - [ ] (Phase 1B) Hook `reconcileOnNewSlot` từ TKB tạo tiết quá khứ.
- Frontend:
  - [ ] Teacher: page + tab + table + modals.
  - [ ] Admin: manage-system page + filters + table + modals.
  - [ ] Handle `403` (Teacher không phải GVCN) theo UX quyết định.
  - [ ] Toast sau review: hiển thị số liệu `attendance.applied / deferredFuture / noSlot` từ payload BE.

