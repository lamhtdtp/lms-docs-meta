# Gap Analysis: Leave Request + Attendance — Spec vs Code

> Đối chiếu `requestment.md` với code thực tế tại `lms-api`.  
> Cập nhật: 2026-05-13

---

## Tóm tắt nhanh

| FR | Tên | Trạng thái |
|----|-----|-----------|
| FR-01 | Xem danh sách đơn nghỉ | ✅ Đã làm |
| FR-02 | Tạo đơn nghỉ | ✅ Đã làm |
| FR-03 | Duyệt đơn | ⚠️ Làm một nửa |
| FR-04 | Duyệt hàng loạt | ✅ Đã làm |
| FR-05 | Update điểm danh theo đơn nghỉ | ❌ Chưa làm |
| FR-06 | Sửa điểm danh thủ công | ⚠️ Làm một nửa |
| FR-07 | Auto điểm danh | ⚠️ Làm một nửa |
| FR-08 | Thêm tiết quá khứ | ❌ Thiếu reconcile leave |
| FR-09 | Hủy tiết quá khứ | ✅ Đã làm |

---

## Chi tiết từng FR

### FR-01 — Xem danh sách đơn nghỉ ✅
`LeaveRequestService.findByCriteria` + `getDetail` có kiểm tra quyền đủ role (PH, HS, GVCN, GVBM, Admin, Super Admin).

---

### FR-02 — Tạo đơn nghỉ ✅
Validate ngày, buổi, overlap PENDING/APPROVED (BR-LEAVE-05), parent-student relationship, classroom đang hoạt động. Đúng spec.

---

### FR-03 — Duyệt đơn ⚠️
**Đã làm:**
- Cập nhật status APPROVED/REJECTED, lưu reviewer + timestamp
- Gửi notification PH/HS qua event

**Chưa làm:**
- `applyApprovedLeaveHook` tại `LeaveRequestService:220` là **stub rỗng** — toàn bộ bước 6–14 của SD-01 (gọi attendance module, cập nhật roll_call) chưa implement

```java
// LeaveRequestService.java:220-222
protected void applyApprovedLeaveHook(LeaveRequest lr) {
    log.debug("... attendance sync deferred");  // Không làm gì
}
```

**Rule vi phạm:** BR-ATT-16, 17, 18, 19, 20 — SD-01 bước 6–14

---

### FR-04 — Duyệt hàng loạt ✅
`review()` nhận `List<Integer> ids`, xử lý batch đúng spec.

---

### FR-05 — Update điểm danh theo đơn nghỉ ❌
**Toàn bộ chưa implement.** Cần:
- Tìm `roll_call` đang tồn tại trong phạm vi ngày/buổi của đơn
- Mapping buổi → tất cả tiết thuộc buổi (BR-ATT-30)
- Apply last-write-wins với MANUAL (so sánh `last_updated_at`)
- Ghi đè SYSTEM_AUTO trực tiếp
- Set `source = LEAVE_REQUEST`, `source_ref_id = leaveRequestId`
- Ghi audit log mỗi thay đổi

**Rule vi phạm:** BR-ATT-16, 17, 18, 19, 20, 30 — SD-01 bước 6–14

---

### FR-06 — Sửa điểm danh thủ công ⚠️
**Đã làm:** `RollCallService.updateRollCallAndNotes` cập nhật `attendanceStatus`.

**Chưa làm:**
- Không set `source = MANUAL` (field chưa tồn tại trong entity)
- Không có `last_updated_at` để làm last-write-wins với LEAVE_REQUEST
- Không ghi audit log

**Rule vi phạm:** BR-ATT-21, 22, 23, 28, 29

---

### FR-07 — Auto điểm danh ⚠️
**Đã làm:** `handleCreateTodayRollCall` chạy hàng ngày, tạo `roll_call` cho HS theo TKB hôm nay.

**Chưa làm:**
- `createRollCall` hardcode `attendanceStatus = PRESENT` (`RollCallService:96`) — không check APPROVED leave trước khi tạo
- Không có field `source` → không thể skip bản ghi tầng 1 khi chạy lại (BR-ATT-14)
- SD-05 bước 8–12: phải query leave module, nếu có APPROVED leave thì set `EXCUSED_ABSENCE + LEAVE_REQUEST`

**Rule vi phạm:** BR-ATT-13, 14, 15 — SD-05

---

### FR-08 — Thêm tiết quá khứ ❌
**Đã làm:** `createRollCallForNewPeriod` tạo roll_call cho HS trong classroom.

**Chưa làm:**
- Luôn set `PRESENT` — không hỏi leave module xem có APPROVED leave trong phạm vi không
- Vi phạm BR-ATT-24, BR-ATT-25: phải khởi tạo `EXCUSED_ABSENCE + LEAVE_REQUEST` nếu đã có leave duyệt

```java
// RollCallService.java:235 — sai với BR-ATT-24, 25
rollCall.setAttendanceStatus(EAttendanceStatus.PRESENT);
```

**Rule vi phạm:** BR-ATT-24, 25 — SD-03

---

### FR-09 — Hủy tiết quá khứ ✅
`deleteByTimetableValueWeekIdIn` → hard delete đúng spec (BR-ATT-07, 26, 27).

---

## Root cause: thiếu field trong `RollCall` entity

Tất cả FR còn gap (05, 06, 07, 08) đều block bởi thiếu các field sau trong bảng `roll_call`:

| Field | Mục đích | Rule liên quan |
|-------|----------|---------------|
| `source` (SYSTEM_AUTO / LEAVE_REQUEST / MANUAL) | Xác định tầng ưu tiên, skip khi auto job | BR-ATT-04, 08, 09, 14 |
| `source_ref_id` | Trỏ về `leave_request.id` khi source = LEAVE_REQUEST | BR-ATT-17 |
| `last_updated_at` | So sánh thời điểm để last-write-wins giữa LEAVE_REQUEST và MANUAL | BR-ATT-11, 12 |

Ngoài ra cần thêm **bảng audit log** attendance với các field tối thiểu: `action`, `actor/source`, `before/after status`, `before/after source`, `source_ref_id`, `timestamp`, `reason/note` (BR-ATT-28, 29).

---

## Việc cần làm (theo thứ tự ưu tiên)

1. **Migration DB** — thêm `source`, `source_ref_id`, `last_updated_at` vào `roll_call`; tạo bảng `roll_call_audit_log`
2. **FR-05 / FR-03** — implement `applyApprovedLeaveHook`: tìm slot tồn tại, apply source priority + last-write-wins, ghi audit
3. **FR-06** — sửa `updateRollCallAndNotes`: set `source = MANUAL`, so sánh timestamp với LEAVE_REQUEST, ghi audit
4. **FR-07** — sửa `handleCreateTodayRollCall` + `createRollCall`: check leave APPROVED trước khi set PRESENT; skip tầng 1 khi re-run
5. **FR-08** — sửa `createRollCallForNewPeriod`: query leave module, khởi tạo source đúng (BR-ATT-24, 25)
