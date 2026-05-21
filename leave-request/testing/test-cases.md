---
title: Test cases — Module xin nghỉ phép
scope: xin-nghỉ-phép (Leave Request + ảnh hưởng điểm danh)
sources:
  - xin-nghỉ-phép/SKILL.md (BR-LEAVE-*, BR-ATT-*, NG-*)
  - xin-nghỉ-phép/tech/parent.md
  - xin-nghỉ-phép/tech/student.md
  - xin-nghỉ-phép/tech/teacher.md
  - xin-nghỉ-phép/tech/admin.md
note: "Case 'khóa điểm' hiện là open-question trong tech doc; test case được viết theo 2 nhánh kỳ vọng."
---

## 1) Quy ước & dữ liệu chuẩn bị

### 1.1 Quy ước thuật ngữ

- **Đơn nghỉ**: Leave Request, trạng thái `PENDING | APPROVED | REJECTED`
- **Buổi**: Sáng/Chiều/Tối (theo hệ enum hệ thống)
- **Điểm danh**:
  - **Status**: `PRESENT | EXCUSED_ABSENCE | UNEXCUSED_ABSENCE`
  - **Source**: `SYSTEM_AUTO | LEAVE_REQUEST | MANUAL`
  - **Nguyên tắc**: tầng 1 = `LEAVE_REQUEST` + `MANUAL` (ngang quyền), tầng 2 = `SYSTEM_AUTO` (không ghi đè tầng 1), giữa tầng 1 dùng **last valid update wins** (timestamp/version)

### 1.2 Data setup tối thiểu

- Có ít nhất 1 **chi nhánh** `B1`
- Có ít nhất 1 **lớp** `C1` thuộc `B1`, có TKB tạo ra nhiều **tiết** trong 1 ngày (để test mapping buổi → tiết)
- Có 1 **học sinh** `S1` trong `C1`
- Có 2 account **PH** (P1 là phụ huynh của `S1`, P2 không liên quan)
- Có 2 account **GV**:
  - `T_HEAD` là **GVCN** lớp `C1` (ETeacherAllocation.HEAD)
  - `T_SUBJECT` là GV bộ môn / không phải HEAD
- Có account **ADMIN** (quyền chi nhánh `B1`) và **SUPER_ADMIN**
- Có dữ liệu điểm danh cho các tiết liên quan (tùy bài test có thể để job auto tạo trước)

### 1.3 Bộ ngày test gợi ý

- `D1`: ngày tương lai có đủ tiết buổi sáng & chiều
- `D0`: ngày hiện tại
- `D-1`: ngày quá khứ (để test reconcile khi thêm tiết quá khứ / hoặc approve đơn cho quá khứ)

---

## 2) Test cases — PH (Parent) (FR-01..FR-03)

### TC-P-01 — List: chỉ thấy đơn của chính PH

- **Precondition**: Có tối thiểu 2 đơn nghỉ: 1 của P1 (cho S1), 1 của PH khác (không phải P1)
- **Steps**: P1 mở danh sách đơn nghỉ
- **Expected**:
  - Chỉ hiển thị các đơn `created_by = P1`
  - Không lộ dữ liệu học sinh/đơn của người khác

### TC-P-02 — Filter theo ngày gửi & trạng thái

- **Steps**: Dùng filter ngày gửi (from/to) + trạng thái (mỗi trạng thái)
- **Expected**:
  - Kết quả đúng theo điều kiện filter
  - Sort “mới trước” (nếu spec FE/BE áp dụng)

### TC-P-03 — Tạo đơn: validate năm học hiện tại (GOING_ON)

- **Precondition**: Năm học không ở trạng thái hiện tại (hoặc giả lập API trả state khác)
- **Steps**: P1 bấm “Thêm mới” / gọi API tạo đơn
- **Expected**:
  - UI disable hoặc BE trả lỗi hợp lệ (400/403 theo policy)
  - Không tạo đơn

### TC-P-04 — Tạo đơn: validate khung ngày/buổi hợp lệ

- **Steps**:
  - Case A: cùng ngày, buổi bắt đầu > buổi kết thúc
  - Case B: ngày bắt đầu > ngày kết thúc
- **Expected**: BE trả lỗi validate; UI hiển thị thông báo; không tạo đơn

### TC-P-05 — BR-LEAVE-05: không cho overlap với `PENDING`/`APPROVED`

- **Precondition**: Tồn tại đơn `PENDING` hoặc `APPROVED` cho S1 trong khoảng (D1 sáng → D1 chiều)
- **Steps**: P1 tạo đơn mới cho S1 overlap một phần (ví dụ D1 sáng → D1 sáng)
- **Expected**:
  - Bị chặn tạo đơn (lỗi overlap)
  - Không tạo bản ghi mới

### TC-P-06 — Tạo đơn: cho phép nếu overlap với `REJECTED`? (theo BR-LEAVE-05)

- **Precondition**: Chỉ có đơn `REJECTED` cho S1 trong khoảng (D1 sáng → D1 chiều)
- **Steps**: P1 tạo đơn mới trùng khoảng
- **Expected**:
  - **Được phép tạo** (vì rule chỉ chặn `PENDING/APPROVED`)

### TC-P-07 — Chi tiết đơn (FR-03): hiển thị đúng theo trạng thái

- **Steps**: Mở chi tiết đơn theo từng trạng thái `PENDING/APPROVED/REJECTED`
- **Expected**:
  - `PENDING`: phần thông tin duyệt hiển thị “-” / chưa có người duyệt
  - `APPROVED`: có `reviewed_by`, `reviewed_at`
  - `REJECTED`: hiển thị `reject_reason` đầy đủ

### TC-P-08 — Security: PH không đọc được đơn của PH khác

- **Steps**: P1 gọi `GET /leave-requests/{id}` với id thuộc PH khác
- **Expected**: 403/404 (theo convention) và không lộ dữ liệu

---

## 3) Test cases — HS (Student) (HS-01/HS-02)

### TC-S-01 — List: HS chỉ thấy đơn của chính mình

- **Steps**: HS đăng nhập, mở list
- **Expected**: chỉ thấy đơn `student_id = currentStudent`

### TC-S-02 — HS không được tạo đơn (out of scope)

- **Steps**: HS gọi API tạo đơn hoặc tìm nút tạo trên UI
- **Expected**: không có UI / BE từ chối (403)

---

## 4) Test cases — GV (Teacher, GVCN) (GV-01/GV-02)

### TC-T-01 — List theo lớp: chỉ thấy đơn trong lớp đang xem

- **Precondition**: Có thêm đơn nghỉ của học sinh lớp khác `C2`
- **Steps**: `T_HEAD` vào tab đơn nghỉ của lớp `C1`
- **Expected**: chỉ thấy đơn `classroom_id = C1`

### TC-T-02 — Permission: chỉ GVCN (HEAD) được duyệt

- **Steps**:
  - `T_SUBJECT` thử duyệt đơn `PENDING` của `C1`
  - `T_HEAD` duyệt cùng đơn
- **Expected**:
  - `T_SUBJECT`: 403 hoặc không có nút duyệt
  - `T_HEAD`: duyệt thành công

### TC-T-03 — Review: chỉ xử lý đơn `PENDING`

- **Precondition**: Có 1 đơn `APPROVED` hoặc `REJECTED`
- **Steps**: gọi API review lại đơn đó
- **Expected**: bị chặn; không thay đổi trạng thái; trả lỗi hợp lệ

### TC-T-04 — Reject: bắt buộc `rejectReason`

- **Steps**: `T_HEAD` reject với body thiếu `rejectReason` hoặc rỗng
- **Expected**: bị chặn validate; không đổi trạng thái

### TC-T-05 — Batch review: nhiều id nhưng chỉ một lớp (policy doc)

- **Steps**: batch ids gồm đơn thuộc `C1` và `C2` (nếu BE cho phép query)
- **Expected**: bị chặn theo rule “Teacher chỉ duyệt trong một lớp / request”

---

## 5) Test cases — Admin/Super Admin (AD-01/AD-02)

### TC-A-01 — Admin list: scope theo `branchId` session

- **Precondition**: Có đơn thuộc `B2`
- **Steps**: ADMIN (B1) list
- **Expected**: không thấy đơn của `B2`

### TC-A-02 — Super Admin list: lọc đa chi nhánh (policy)

- **Steps**: SUPER_ADMIN list với/không filter `branchId`
- **Expected**: hành vi đúng theo policy (nếu bắt buộc chọn chi nhánh trước thì API/UI chặn)

### TC-A-03 — Batch review: chỉ một chi nhánh / request

- **Precondition**: Có 2 đơn thuộc 2 chi nhánh khác nhau
- **Steps**: ADMIN/SUPER_ADMIN review batch chứa cả 2 chi nhánh
- **Expected**: bị chặn (rule mirror join request)

### TC-A-04 — Admin review không cần HEAD

- **Steps**: ADMIN duyệt đơn lớp `C1`
- **Expected**: duyệt thành công dù không có teacher allocation

---

## 6) Test cases — Tác động điểm danh khi `APPROVED` (BR-ATT-16..20, BR-ATT-30, NG-05..07)

> Nhóm test này cần có dữ liệu tiết học/điểm danh tồn tại theo NG-01/NG-02.

### TC-ATT-01 — APPROVED: mapping buổi → tất cả tiết thuộc buổi (BR-ATT-30)

- **Precondition**: `D1` có nhiều tiết buổi sáng
- **Steps**: Approve đơn nghỉ `D1` buổi sáng
- **Expected**:
  - Tất cả tiết buổi sáng của `D1` (đang tồn tại) → `EXCUSED_ABSENCE`, `source=LEAVE_REQUEST`
  - Không ảnh hưởng các tiết ngoài phạm vi

### TC-ATT-02 — APPROVED: chỉ cập nhật bản ghi điểm danh “đang tồn tại” (BR-ATT-16..20)

- **Precondition**: Có tiết bị hủy / slot không tồn tại trong phạm vi nghỉ
- **Steps**: Approve đơn phủ lên tiết đó
- **Expected**:
  - Không tạo attendance mới cho slot không tồn tại
  - Các slot tồn tại trong phạm vi vẫn được cập nhật

### TC-ATT-03 — REJECTED: không auto sinh nghỉ không phép (NG-07, BR-LEAVE-03)

- **Steps**: Reject đơn
- **Expected**:
  - Attendance không bị set thành `UNEXCUSED_ABSENCE` chỉ vì đơn bị reject

### TC-ATT-04 — Approve ghi đè `SYSTEM_AUTO`

- **Precondition**: Attendance hiện tại là `PRESENT`/`SYSTEM_AUTO`
- **Steps**: Approve đơn nghỉ phủ lên tiết đó
- **Expected**: đổi thành `EXCUSED_ABSENCE`/`LEAVE_REQUEST`

### TC-ATT-05 — Conflict với MANUAL: last write wins (NG-05)

- **Precondition**:
  - Case A: manual edit xảy ra **sau** approve
  - Case B: approve xảy ra **sau** manual edit
- **Steps**: thực hiện 2 event theo từng case
- **Expected**:
  - Case A: kết quả cuối theo MANUAL (timestamp mới hơn)
  - Case B: kết quả cuối theo LEAVE_REQUEST (approve mới hơn)

### TC-ATT-06 — Auto job không ghi đè tầng 1 (NG-06, BR-ATT-13..15)

- **Precondition**: Attendance đã có `LEAVE_REQUEST` hoặc `MANUAL`
- **Steps**: chạy job auto attendance
- **Expected**: job skip, không ghi đè trạng thái/source tầng 1

### TC-ATT-07 — Thêm tiết quá khứ: reconcile leave đã APPROVED (BR-ATT-24..25)

- **Precondition**: Đã có leave `APPROVED` cho `D-1` buổi sáng, nhưng tiết buổi sáng `D-1` được tạo **sau** (thêm tiết quá khứ)
- **Steps**: thêm tiết quá khứ (tạo slot attendance)
- **Expected**:
  - Slot mới tạo được khởi tạo `EXCUSED_ABSENCE` + `LEAVE_REQUEST`

### TC-ATT-08 — Hủy tiết quá khứ: hard delete attendance (NG-02)

- **Steps**: hủy tiết đã có attendance
- **Expected**: attendance bị xóa cứng; không còn bản ghi

### TC-ATT-09 — Audit: mọi thay đổi attendance có log tối thiểu (BR-ATT-28..29)

- **Steps**: thực hiện approve leave, manual edit, auto job
- **Expected**:
  - Audit ghi đủ: action, actor/source, before/after status, before/after source, source_ref_id, timestamp, reason/note

---

## 7) Test cases — “Khóa điểm” (grade finalization) khi duyệt đơn (open-question)

> Tech doc có gợi ý “có thể gọi `semesterService.validateBranchInTimeGradeFinalization(branchId)`”, nhưng **FRS chưa chốt**. Vì vậy viết 2 nhánh kỳ vọng để BA/PO chọn.

### TC-LOCK-01 — Nhánh A (CHẶN): trong kỳ khóa điểm thì không cho review

- **Precondition**: chi nhánh `B1` đang trong thời gian “khóa điểm/chốt điểm”
- **Steps**: `T_HEAD` / `ADMIN` review đơn `PENDING`
- **Expected**:
  - Bị chặn với message rõ (ví dụ “Đang khóa điểm, không thể duyệt”)
  - Không đổi trạng thái đơn; không cập nhật attendance

### TC-LOCK-02 — Nhánh B (KHÔNG CHẶN): khóa điểm không ảnh hưởng duyệt đơn nghỉ

- **Precondition**: như TC-LOCK-01
- **Steps**: review đơn `PENDING`
- **Expected**:
  - Review vẫn thành công
  - Attendance xử lý theo BR-ATT bình thường

---

## 8) Regression checklist nhanh (smoke)

- [ ] Tạo đơn hợp lệ → thấy ngay trong list (PH) và tab/list (GV/Admin) đúng scope
- [ ] Overlap chặn đúng theo `PENDING/APPROVED` (không chặn `REJECTED`)
- [ ] Duyệt `APPROVED` → cập nhật attendance đúng buổi/tiết; không tạo slot không tồn tại
- [ ] Duyệt `REJECTED` → không auto UNEXCUSED
- [ ] Manual vs Leave: last-write-wins đúng
- [ ] Auto job không đè tầng 1
- [ ] Audit đầy đủ cho các thay đổi attendance

