# Tech — Luồng Giáo viên (GV-01, GV-02)

Tài liệu triển khai đối chiếu `xin-nghỉ-phép/teacher/GV-01.md`, `xin-nghỉ-phép/teacher/GV-02.md` và `xin-nghỉ-phép/SKILL.md` (FRS: GVCN/Admin **duyệt đơn**; GVBM **không** duyệt trong ma trận actor — chỉ xem nếu BA mở rộng).

## Nguồn code

| Repo | Đường dẫn máy | Ghi chú |
|------|----------------|---------|
| Backend | `~/dev/dtp/lms-api` | Cùng module đơn nghỉ phép với PH/HS; thêm API **theo lớp** + **duyệt** + tác động điểm danh khi `APPROVED` |
| Frontend | `~/dev/dtp/lms-school` | App quản trị/giáo viên — chi tiết lớp dưới `pages/manage-class/[id]/…`, layout tab `ClassDetailLayout` |

Ứng dụng phụ huynh/học sinh (`lms-fe`) **không** dùng trong doc này; GV xử lý đơn trên **`lms-school`**.

Trạng thái hiện tại: module leave request chưa có trong API — cần implement theo `xin-nghỉ-phép/tech/parent.md` (entity chung), rồi bổ sung endpoint & UI GV.

## Phạm vai & phạm vi màn

| Mã | File đặc tả | Ý chính |
|----|-------------|---------|
| GV-01 | `xin-nghỉ-phép/teacher/GV-01.md` | **Chi tiết lớp**, tab/khối **Đơn xin nghỉ phép**: danh sách đơn **trong phạm vi lớp đang xem**; lọc/sort/cột theo mock `27534:101368` + RR-GV-01 `27574:201019` |
| GV-02 | `xin-nghỉ-phép/teacher/GV-02.md` | **Đồng ý** / **Từ chối** (có thể lẻ hoặc chọn nhiều — theo thiết kế); pop-up xác nhận đồng ý; pop-up từ chối + **lý do** (có thể bắt buộc — theo `27574:201566`); sau duyệt: **APPROVED** → áp BR attendance; **REJECTED** → không auto nghỉ không phép (**NG-07**) |

**Không** có luồng “GV tạo đơn thay PH” trên UI mặc định (theo GV-01).

## Backend (`lms-api`)

### Dùng chung entity & bảng leave request

- Cấu trúc thực thể, trường `classroom_id`, `student_id`, `status`, … — thống nhất với `xin-nghỉ-phép/tech/parent.md`.
- Khi **duyệt Đồng ý**: cập nhật `status = APPROVED`, `reviewed_by`, `reviewed_by_role_code`, `reviewed_at`; sau đó gọi tầng **điểm danh** (module `rollcall` hiện có `EAttendanceStatus.EXCUSED_ABSENCE`) theo **BR-ATT-16 … 20**, **BR-LEAVE-03**, nguồn `LEAVE_REQUEST`, chỉ trên slot/tiết **đang tồn tại** — chi tiết trong SKILL (`SD-01`, ma trận trạng thái).
- Khi **Từ chối**: `status = REJECTED`, lưu `reject_reason` (text); **không** gán tự động `UNEXCUSED_ABSENCE` vì đơn bị từ chối.

### Phân quyền GV — GVCN (ETeacherAllocation.HEAD)

Repo đã có kiểm tra giáo viên có phải **GVCN** của lớp:

- `vn.dtpsoft.modules.teacherallocation.TeacherAllocationService#isTeacherKindOfClassroom(teacherId, classroomId, ETeacherAllocation.HEAD)`
- `vn.dtpsoft.constant.ETeacherAllocation`: `HEAD`, `SUBJECT`, `ASSISTANT`

**Đề xuất:** API duyệt đơn nghỉ chỉ cho phép khi `isTeacher(...)` và user là **HEAD** của `leaveRequest.classroomId` (trùng với FRS “GVCN duyệt”). Admin/Super Admin xử lý theo policy riêng (xem `xin-nghỉ-phép/admin/` nếu có).

Tham chiếu pattern **duyệt yêu cầu theo lớp** trên `lms-api`: `ClassroomJoinRequestController` — `PUT /classroom-join-request` với `@PreAuthorize` cho `TEACHER` (và Admin). `ClassroomJoinRequestService.updateJoinRequest` kiểm tra **TEACHER phải là GVCN** (`ETeacherAllocation.HEAD`) của lớp tương ứng. **Leave request** nên **mirror** cùng kiểu guard trước khi chấp nhận `APPROVED` / `REJECTED`.

### API gợi ý cho GV (bổ sung vào `LeaveRequestController` hoặc tách controller theo convention repo)

| Method | Path | Mục đích |
|--------|------|----------|
| `GET` | `/leave-requests` | Query **`classroomId`** (bắt buộc cho luồng GV): lọc `entity.classroomId` + `branchId`; role `TEACHER` → kiểm tra quyền xem lớp (ít nhất subject/head tùy BA — *duyệt* thì chặt **HEAD**); `ADMIN` theo chi nhánh |
| `GET` | `/leave-requests/{id}` | Chi tiết đơn (để pop-up “Xem chi tiết” trước khi duyệt): đảm bảo `classroomId` thuộc quyền GV |
| `PUT` hoặc `PATCH` | `/leave-requests/review` (hoặc `PUT /leave-requests`) | Body dạng batch: `ids[]`, `status` (`APPROVED` \| `REJECTED`), `rejectReason` (khi reject). Chỉ xử lý bản ghi `PENDING`; validate HEAD + (tuỳ chọn) `semesterService.validateBranchInTimeGradeFinalization` giống join request khi duyệt trong kỳ khóa điểm |

**Gợi ý bảo mật:** không tin `classroomId` từ body khi duyệt — suy ra từ entity đơn hoặc đối chiếu `id` với DB rồi kiểm tra lớp.

### Header `classroomId` (tuỳ chọn)

`BaseController#getCurrentClassroomId()` đọc header HTTP `classroomId`. `lms-school` hiện **không** set global trong `services/api/fetcher.js` (chỉ `branchId`, token, `language`). Tab chi tiết lớp thường truyền `classroomId` qua **query** (`classroomIds` trong enrollment request). Với leave request, **ưu tiên** queryParam `classroomId` rõ ràng trong API list để khớp GV-01 (phạm vi lớp), không phụ thuộc header trừ khi team chuẩn hoá sau.

## Frontend (`lms-school`)

### Vị trí trang (song song “Yêu cầu tham gia lớp”)

Luồng tham chiếu có sẵn:

- Trang: `pages/manage-class/[id]/enrollment-request.js` — bọc `ClassDetailLayout`, `getServerSideProps` load `getDetailClassroom`.
- Component: `components/Pages/ManageClass/ClassDetail/EnrollmentRequest/` — truyền `classroomIds: [ query.id ]` vào bảng.

**Đề xuất triển khai GV-01/GV-02:**

1. Thêm route ví dụ `pages/manage-class/[id]/leave-request.js` (tên file/slug thống nhất với team & i18n).
2. Thêm `paths.classDetailLeaveRequest` trong `constants/paths.js`.
3. Trong `components/layouts/ClassDetailLayout/ClassDetailLayout.js`, thêm một tab mới vào mảng `dataTabs` (có thể bọc feature flag kiểu `ENROLLMENT_REQUEST_FEATURE_ENABLED` nếu cần rollout từng phase).
4. Tạo `components/Pages/ManageClass/ClassDetail/LeaveRequest/` (hoặc tên đồng bộ): bảng danh sách + filter + checkbox chọn nhiều (nếu Figma có batch) + nút Đồng ý / Từ chối + modal GV-02.
5. Đăng ký API trong `services/api/config.js` (khối `classrooms` hoặc `leaveRequests`) và module `services/api/leave-request.js` với `useFetch` / `useMutation` giống `services/api/enrollment-request.js`.

### Hành vi UI (GV-02)

- **Đồng ý:** modal xác nhận (frame `27534:94782`, RR `27574:201437`) → gọi API review `APPROVED`.
- **Từ chối:** modal nhập/chọn lý do (`27534:94772`, `27567:207478`, RR `27574:201505`, `27574:201566`) → gọi API `REJECTED` + `rejectReason`.
- Chỉ enable thao tác duyệt với dòng **Chờ xét duyệt** (và khi user có quyền GVCN — có thể ẩn nút cho GVBM nếu BE trả `403`).

### Breadcrumb

`enrollment-request.js` phân nhánh breadcrumb theo `SUPER_ADMIN`/`ADMIN` vs `TEACHER`. Tab leave request nên **copy pattern** đó để đồng bộ UX.

## Pattern tái sử dụng trong repo

| Mục đích | Tham chiếu `lms-school` | Tham chiếu `lms-api` |
|----------|-------------------------|----------------------|
| Tab trong chi tiết lớp | `ClassDetailLayout.js` — `dataTabs`, `paths.classDetail*` | — |
| Trang con theo `[id]` + SSR classroom | `pages/manage-class/[id]/enrollment-request.js` | — |
| Bảng + filter + mutation duyệt | `EnrollmentRequest.js`, `StudentEnrollmentRequestTable`, `services/api/enrollment-request.js` | `ClassroomJoinRequestController`, `ClassroomJoinRequestService.updateJoinRequest` |
| Kiểm tra GVCN | — | `TeacherAllocationService.isTeacherKindOfClassroom(..., HEAD)` |
| Điểm danh sau duyệt | — | `RollCallService`, `EAttendanceStatus`, SKILL BR-ATT-* |

## Liên kết chéo tài liệu tech

- Entity & API nền: `xin-nghỉ-phép/tech/parent.md`
- HS chỉ xem: `xin-nghỉ-phép/tech/student.md`
- Đặc tả nghiệp vụ: `xin-nghỉ-phép/SKILL.md`

## Câu hỏi cần BA / PO / Design

1. GVBM có được **chỉ xem** danh sách đơn lớp (không nút duyệt) hay ẩn hẳn tab? (Ma trận SKILL: duyệt = GVCN/Admin.)
2. Duyệt **hàng loạt** có trong scope phase 1 không (checkbox + một lần gọi API)?
3. Lý do từ chối: danh sách cố định + “Khác”, hay chỉ textarea?
4. Kỳ **khóa điểm** có chặn duyệt đơn nghỉ giống join class không? (Tham chiếu `semesterService.validateBranchInTimeGradeFinalization` trong join request.)

## Liên kết đặc tả

- `xin-nghỉ-phép/teacher/GV-01.md`
- `xin-nghỉ-phép/teacher/GV-02.md`
- `xin-nghỉ-phép/SKILL.md`
