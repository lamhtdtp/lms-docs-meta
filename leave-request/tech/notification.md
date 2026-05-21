# Tech — Thông báo (notification) module xin nghỉ phép

Đối chiếu FRS: `xin-nghỉ-phép/SKILL.md` (**SD-01** — sau duyệt đơn: log + **thông báo PH/HS**) và các file `xin-nghỉ-phép/tech/parent.md`, `teacher.md`, `admin.md`.

**Nền backend:** pattern hiện có trong `~/dev/dtp/lms-api`:
- **`NotificationService`**: `createNotification(...)`, `addNotificationRecipient(...)` — persist bản ghi `notification` + mapping người nhận (`NotificationBranchRole`, `NotificationUser`, `NotificationClassroom`, …).
- **`AutoNotificationService`**: các flow tự động; nhiều chỗ đồng thời gọi **`OneSignalService.sendMessage`** + lưu `NotificationUser` / `NotificationClassroom` để inbox đúng phạm vi.
- **`GET /notifications/inbox`** (`NotificationController`): PH/HS lọc theo `branchId`, `classroomId`, `grade`, role; có thêm filter `objectId` cho PARENT (qua `criteria.getObjectId()`).

Tài liệu này mô tả **cách triển khai đơn nghỉ phép bám các pattern trên**, không làm luồng email riêng (join class vẫn dùng `EmailService`; leave có thể bổ sung sau nếu BA yêu cầu).

---

## 1) Nguyên tắc

1. **In-app notification là nguồn chính**: mọi sự kiện quan trọng đều tạo bản ghi trong bảng `notification` và mapping recipient để user xem trong **Inbox**.
2. **Push (optional, khuyến nghị)**: tái dùng **`OneSignalService`** + **`UserDeviceService.findByBranchIdAndRoleCodeAndUserIdIn`**, giống `notifyNewClassroomExam` / `notifyStudentAttendanceToParent` trong `AutoNotificationService`.
3. **Đa ngữ**: tiêu đề / mô tả ngắn lấy từ **`MessageSource`** (keys trong `messages*.properties`), truyền `{0}`/`{1}`… cho tên HS, khung ngày nghỉ, trạng thái.
4. **Không làm chủ đạo của luồng review**: notify nên **`@Async`** hoặc gọi sau khi transaction `review`/`create` đã commit, để không rollback khi push lỗi.
5. **Idempotency / batch**: mỗi lần chuyển trạng thái đơn (`PENDING` → `APPROVED`/`REJECTED`) gửi tối đa **một** thông báo “kết quả” cho một `leave_request_id`; batch review có thể tạo nhiều notification (mỗi đơn một bản ghi hoặc gom tin — xem §6).

---

## 2) Các hằng số nên thêm (`lms-api`)

### 2.1 `ENotificationKind`

Hiện `ENotificationKind` chưa có loại cho nghỉ phép; cần bổ sung (tên chỉ là đề xuất, có thể rút gọn khi merge):

```text
LEAVE_REQUEST_CREATED          // PH tạo đơn → thông báo GVCN/Admin reviewer
LEAVE_REQUEST_APPROVED         // Duyệt đồng ý → PH/HS (và có thể copy cho người gửi chỉ một lần)
LEAVE_REQUEST_REJECTED        // Từ chối → PH/HS
```

### 2.2 `ENotificationSource`

Dùng **`ENotificationSource.INTERNAL`** (giống publish timetable / exam / attendance-to-parent trong `AutoNotificationService`).

---

## 3) Recipient patterns (bám code hiện có)

### 3.1 Giao thức chung sau `createNotification`

**Cách A — Theo branch + role + classroom (OBJECTS)**

- Tạo `Notification` qua `notificationService.createNotification(source, kind, title, titleEn, shortDescription, shortDescriptionEn, extraData, objectId)`  
  (`objectId` dùng khi cần filter inbox PARENT theo **con/ghi học**, xem §4).
- Tạo `NotificationBranchRole` (`createNotificationBranchRole` trong `AutoNotificationService` hoặc tương đương):
  - `branch` = `Branch` của lớp/đơn
  - `role` = `ERole.TEACHER` | `ERole.PARENT` | `ERole.STUDENT` | …
  - `targetType` = **`ENotificationTargetType.OBJECTS`**
- Gắn **`NotificationClassroom`** nếu inbox TEACHER/PARENT/STUDENT cần giới hạn theo **`classroomId`** (đúng cơ chế `NotificationController#getNotificationsForTeacher/Parent/Student` đọc `classroomIds`).

**Cách B — Theo danh sách user cụ thể (`NotificationUser`)**

- Sau khi có `notificationBranchRole`, tạo từng `NotificationUser` với `userId` của GVCN / PH / HS (như luồng **chuyển lớp** `transferringClasses`, **exam**, **STATS_STUDENT_ATTENDANCE**).
- Ưu tiên khi cần chính xác một vài người (đặc biệt **GVCN HEAD** chỉ của một lớp).

**Cách C — Broadcast branch + roles (`addNotificationRecipient`)**

- `notificationService.addNotificationRecipient(notification, null, singletonList(branchId), ENotificationTargetType.OBJECTS, List.of(ERole.ADMIN, ERole.TEACHER), …)` như **`notifyGradeFinalizationTimeUpdated`**.  
- Dùng khi BA muốn thông báo “có đơn mới” cho **ADMIN** của chi nhánh; với GV nên **hạn chế** chỉ HEAD + filter classroom để không spam.

### 3.2 Push OneSignal

Sau khi đã có `notificationId`:

1. Chuẩn bị `Map<String, Object> extraData`:
   - `type` = tên enum `ENotificationKind` (chuỗi)
   - `notificationId`
   - `leaveRequestId`, `classroomId`, `studentUserId`, … để FE mở màn chi tiết.
2. Lấy thiết bị:
   - `userDeviceService.findByBranchIdAndRoleCodeAndUserIdIn(branchId, ERole.xxx, userIds)`
3. Gọi:
   - `oneSignalService.sendMessage(title, titleEn, shortDescription, shortDescriptionEn, extraData, oneSignalIds, schoolId)`

`sendMessage` dùng `include_aliases.onesignal_id` và `schoolId` để chọn config app (bao gồm trường hợp iCourse trong `OneSignalService`).

---

## 4) Mapping sự kiện → recipients + objectId

| Sự kiện | Ai nhận (đề xuất) | Ghi chú recipient / inbox |
|---------|-------------------|----------------------------|
| **PH tạo đơn** (`POST` leave-request, `PENDING`) | **GVCN** lớp `classroom_id` | `NotificationUser` cho user HEAD của lớp; `NotificationClassroom`; role TEACHER. Có thể thêm ADMIN chi nhánh nếu BA yêu cầu (`addNotificationRecipient` TEACHER+ADMIN không classroom thì có thể rộng — cần chốt). |
| **GVCN/Admin duyệt APPROVED** | **PH** (người tạo) + **HS** (nếu app HS có inbox) | PARENT: set `notification.object_id` = **`classroomStudentId`** của con liên quan (nếu có) để khớp filter `criteria.getObjectId()` giống `findNotificationParentUnread`. STUDENT: `NotificationUser(studentUserId)`, `NotificationClassroom`. |
| **GVCN/Admin duyệt REJECTED** | **PH** + **HS** (read-only như approve) | Mô tả có thể gắn lý do từ `reject_reason` (rút gọn trong shortDescription). |

Nếu chỉ có một PH liên quan học sinh, resolve `parentUserId(s)` và `studentUserId` từ các service hiện có (`studentparent`, `classroomstudent` — tương tự `AbsenceStudentQueryDto` trong attendance notify).

---

## 5) Vị trí gọi trong code (đề xuất)

| Flow | Hook |
|------|------|
| Tạo đơn PH | Sau `leaveRequestRepository.save(...)` và transaction commit → `leaveRequestNotificationService.notifyCreated(...)`. |
| Review batch đơn | Trong **`LeaveRequestService.review`** (dùng chung GV/Admin): sau khi cập nhật entity + attendance (BR-ATT) thành công → loop từng đơn **hoặc** gửi một lần theo đơn; gọi `notifyApproved` / `notifyRejected`. |

**Lưu ý:** Nếu review bị rollback, không được gửi notify — nên **`@TransactionalEventListener(phase = AFTER_COMMIT)`** hoặc enqueue message sau commit.

---

## 6) Batch review (đa đơn)

- **Đề xuất mặc định:** **một notification per leave request** để inbox/push có `leaveRequestId` rõ và user bấm đúng deeplink.
- **Gom tin (optional):** “Bạn có N đơn đã được duyệt” — phức tạp hơn deeplink và i18n; chỉ làm khi BA bắt buộc.

Giới hạn **một chi nhánh một request** (đã có trong `teacher.md`/`admin.md`) giúp gom `schoolId`, `branchId`, `token` nhất quán cho OneSignal query.

---

## 7) `extraData` (JSON string hoặc map khi push)

Đề xuất tối thiểu (FE đọc từ push + có thể merge vào inbox DTO):

```json
{
  "type": "LEAVE_REQUEST_APPROVED",
  "notificationId": 12345,
  "leaveRequestId": 678,
  "classroomId": 10,
  "studentUserId": 1001,
  "status": "APPROVED",
  "fromDate": "...",
  "toDate": "...",
  "sessions": "...",
  "reviewerRole": "HEAD"
}
```

Giữ các key **stable** để không vỡ app khi mở từ push.

---

## 8) i18n (`MessageSource`)

Thêm các key dạng (ví dụ):

- `notification.leave.created.title` / `.description`
- `notification.leave.approved.title` / `.description` (placeholder: họ tên HS, khung ngày/buổi)
- `notification.leave.rejected.title` / `.description` (placeholder: có thể thêm excerpt lý do từ chối)

Song ngữ VI/EN như các notification khác trong `AutoNotificationService`.

---

## 9) Test & quan sát

- Inbox PH/HS/TEACHER: vào **`GET /notifications/inbox`** đúng `branchId` + `classroomId`; PARENT test thêm **`objectId`** nếu dùng.
- Push: có `UserDevice.oneSignalId`; verify `schoolId` khớp trường.
- Regression: không gửi khi chỉ **`PENDING`** (trừ event “đơn mới”).
- **`REJECTED`**: không gắn nghỉ không phép tự động vào attendance (**NG-07**) — chỉ nội dung thông báo.

---

## 10) Liên kết tài liệu trong repo docs

| File | Ý |
|------|---|
| `xin-nghỉ-phép/SKILL.md` | SD-01, ma trận trạng thái |
| `xin-nghỉ-phép/tech/parent.md` | Tạo đơn |
| `xin-nghỉ-phép/tech/teacher.md` / `admin.md` | Review, batch một chi nhánh |
| Backend | `vn.dtpsoft.modules.notification.*`, `AutoNotificationService`, `OneSignalService`, `UserDeviceService` |

---

*Phiên bản doc: căn chỉnh với `lms-api` tại thời điểm đọc mã (`ENotificationKind` có thể cần mở rộng khi implement).*
