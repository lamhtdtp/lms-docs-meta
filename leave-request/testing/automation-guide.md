---
title: Hướng dẫn tự động hoá test — Module xin nghỉ phép
scope: xin-nghỉ-phép/testing
related:
  - xin-nghỉ-phép/testing/test-cases.md
  - xin-nghỉ-phép/SKILL.md
  - xin-nghỉ-phép/tech/parent.md
  - xin-nghỉ-phép/tech/student.md
  - xin-nghỉ-phép/tech/teacher.md
  - xin-nghỉ-phép/tech/admin.md
---

## Mục tiêu

- Tự động chạy được phần lớn test case trong `test-cases.md` theo 3 lớp:
  - **API tests** (ổn định, chạy nhanh, dễ gắn CI)
  - **E2E UI tests** (ít nhưng cover luồng thật trên 2 app)
  - **BE integration tests** cho phần **điểm danh** (cần DB + nghiệp vụ last-write-wins, job auto, audit)

## 1) Nên tự động hoá theo 3 lớp như thế nào?

### 1.1 API automation (khuyến nghị làm trước)

- **Phù hợp để cover**:
  - List/detail theo scope (PH/HS/GV/Admin)
  - Validate tạo đơn (khung ngày/buổi, năm học hiện tại)
  - Rule overlap BR-LEAVE-05
  - Review (PENDING-only, rejectReason, batch constraint)
  - Permission (HEAD-only cho teacher, branch scope cho admin)
- **Công cụ gợi ý**:
  - Postman + Newman (dễ dựng collection, chạy CI)
  - Playwright API tests (nếu đã dùng Playwright cho UI)
  - k6 (nếu muốn kèm tải/hiệu năng)
- **Điểm cần chuẩn hoá**:
  - Cách lấy token/login cho từng role (PH/HS/TEACHER/ADMIN/SUPER_ADMIN)
  - Seed data (chi nhánh/lớp/HS/TKB) để test không phụ thuộc dữ liệu thật

### 1.2 E2E UI automation (chỉ nên chọn smoke quan trọng)

Do có **2 app FE**:
- `lms-fe`: PH/HS
- `lms-school`: GV/Admin

- **Khuyến nghị**: chỉ chọn khoảng **5–10** luồng smoke (happy path + 1–2 negative path), ví dụ:
  - PH tạo đơn → thấy trong list → xem chi tiết
  - GV (HEAD) duyệt approve/reject → trạng thái thay đổi
  - Admin duyệt theo filter chi nhánh/lớp
- **Công cụ gợi ý**: Playwright hoặc Cypress
- **Mẹo giảm flake**:
  - Login bằng API/token (tránh UI login)
  - Dùng `data-testid` cho nút/modal/row action
  - Cố định timezone / mock time (vì có format `HH:mm DD/MM/YYYY`)

### 1.3 BE integration automation cho phần điểm danh (quan trọng nhất cho FRS)

Nhóm test “approve → attendance” thường không nên làm bằng UI/E2E vì:
- Cần seed dữ liệu TKB/tiết/attendance/audit
- Cần assert DB state chính xác (source/status/source_ref_id/audit)

- **Khuyến nghị**:
  - Viết integration tests trong `lms-api` (Spring Boot)
  - Dùng DB chạy trong test (Testcontainers hoặc DB test profile)
  - Seed: TKB + slots + leave request + audit baseline
  - Gọi trực tiếp service (ví dụ `LeaveRequestService.review(...)`, job auto attendance) rồi assert DB

## 2) Mapping nhanh test-case → loại automation

Tham chiếu các nhóm test trong `xin-nghỉ-phép/testing/test-cases.md`:

- **TC-P-01..08 (PH)**:
  - Chủ yếu: **API tests**
  - Smoke quan trọng: **E2E** cho FR-01/02/03
- **TC-S-01..02 (HS)**:
  - Chủ yếu: **API tests**
- **TC-T-01..05 (GV/GVCN)**:
  - Chủ yếu: **API tests** (permission/validate/review)
  - Smoke: **E2E** duyệt approve/reject
- **TC-A-01..04 (Admin/Super Admin)**:
  - Chủ yếu: **API tests**
  - Smoke: **E2E** filter + duyệt
- **TC-ATT-01..09 (Attendance)**:
  - Chủ yếu: **BE integration tests**
- **TC-LOCK-01/02 (Khóa điểm)**:
  - Chỉ tự động hoá “đúng 1 nhánh” sau khi BA/PO chốt rule (chặn hay không chặn)

## 3) Seed data & môi trường test (khuyến nghị)

Để test tự động ổn định, nên có 1 trong 2 hướng:

### Hướng A — Seed DB chuyên cho test

- Test runner reset DB về snapshot trước mỗi suite (hoặc trước mỗi test)
- Seed cố định:
  - Branch `B1`, Classroom `C1`, Student `S1`, các account role
  - TKB tạo slot cho `D1`, `D0`, `D-1`
  - Attendance baseline (nếu cần)

### Hướng B — Factory + tạo dữ liệu qua API/service trong test

- Mỗi test tự tạo dữ liệu cần dùng và tự dọn (teardown)
- Ưu điểm: ít phụ thuộc snapshot
- Nhược: chậm hơn, cần endpoint/fixture hỗ trợ

## 4) Checklist đưa vào CI

- [ ] **API suite**: chạy trên mỗi PR (nhanh)
- [ ] **BE integration suite (attendance)**: chạy trên mỗi PR (có thể tách job riêng vì nặng hơn)
- [ ] **E2E smoke**: chạy nightly hoặc chạy theo tag khi có thay đổi UI lớn
- [ ] Báo cáo kết quả (JUnit/HTML report) + artifact log/video (E2E)

## 5) Gợi ý thứ tự triển khai (tối ưu effort)

1. Làm **API tests** cover CRUD/permission/overlap/review
2. Làm **BE integration tests** cover TC-ATT (đây là phần rủi ro nhất của FRS)
3. Chọn **E2E smoke** ít nhưng “đúng luồng” cho 2 app

