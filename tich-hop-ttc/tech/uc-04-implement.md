---
title: UC-04 Implementation — Incremental sync 1 user (OpenSync on-demand)
scope: tich-hop-ttc
repos:
  - BE: ~/dev/dtp/lms-api
related:
  - tich-hop-ttc/phan-tich-tich-hop.md (UC-04, Bridge SSO ↔ OpenSync)
  - tich-hop-ttc/huong-dan-mapping-opensync-lms-api.md (field mapping)
  - tich-hop-ttc/tech/uc-01-implementation.md (SSO login calls UC-04 when miss)
status: draft
---

## 0) Mục tiêu UC-04

Khi LMS cần **đồng bộ nhanh 1 người** từ TTC → LMS (không chờ cron full-sync), hệ thống sẽ gọi OpenSync để lấy record theo định danh và upsert vào DB LMS.

Trigger chính (theo `phan-tich-tich-hop.md`):
- **On-demand từ UI** (admin bấm sync)
- **Trong UC-01 login SSO**: khi resolve theo `sub`/`identity` **không tìm thấy record đã sync**, có thể gọi UC-04 để “kéo” user về ngay (tuỳ provisioning policy)

---

## 1) Input “khóa tìm kiếm” cho UC-04

### 1.1 Khóa tốt nhất: `SoDinhDanhCaNhan`

Theo mapping guide:
- OpenSync học sinh (`GET /api/opensync/thongtinhocsinh`) có field **`SoDinhDanhCaNhan`** → map vào `User.citizenIdentityCode`.

Vì OpenSync **không có `sub`**, UC-04 nên dùng:
- `soDinhDanhCaNhan` (string) làm input chính

### 1.2 Hệ quả với SSO

Để UC-01 gọi UC-04 được, TTC SSO cần cấp scope `identity` để JWT có claim `identity = SoDinhDanhCaNhan`.

Nếu TTC không cấp `identity`, UC-04 chỉ chạy được khi:
- admin nhập tay CCCD/định danh, hoặc
- TTC bổ sung key bridge khác (mở rộng OpenSync có `sub`)

---

## 2) Phạm vi đồng bộ “1 user” (đề xuất)

UC-04 có thể hiểu theo 2 mức:

### Mức A — “Chỉ user record” (nhanh nhất)

- Upsert `User` (HS/GV) theo `citizenIdentityCode`
- Link `ttc_sub` (nếu đang gọi từ SSO) để lần sau login không cần OpenSync

Nhược: HS/GV có thể chưa đủ dữ liệu lớp/branch/role allocation.

### Mức B — “User + quan hệ tối thiểu để vào được LMS” (khuyến nghị)

Tuỳ role:
- **Student**:
  - gọi `thongtinhocsinh` để lấy `MaTruong`, `MaNien`, `MaLopHoc`, `MaKhoi`
  - đảm bảo upsert được `School/Branch` mapping, `SchoolYear`, `Grade`, `Classroom`
  - upsert quan hệ `ClassroomStudent` (HS ↔ lớp)
  - tạo `UserBranchRole` tối thiểu để login (role STUDENT + branch)
- **Teacher**:
  - gọi `thongtingiaovien`
  - tạo `UserBranchRole` role TEACHER + branch
  - (optional) trigger UC-05 sync phân công để có lớp/môn ngay

> Lưu ý: OpenSync học sinh chỉ trả HS **đã xếp lớp**. Nếu TTC chưa xếp lớp → UC-04 sẽ không tìm thấy HS.

---

## 3) Thiết kế BE trong `~/dev/dtp/lms-api`

### 3.1 API nội bộ đề xuất

Tạo controller (internal/admin guarded):

- `POST /ttc/opensync/sync-user`
  - body:
    - `soDinhDanhCaNhan: string` (required)
    - `userType?: STUDENT | TEACHER` (optional; nếu thiếu thì thử cả 2)
    - `maTruong?: string` (optional nếu cần narrow scope)
    - `maNien?: string` (optional; nếu không có thì lấy niên hiện hành theo config)
    - `reason?: "SSO_MISS" | "ADMIN_MANUAL" | ...`
  - response:
    - `synced: boolean`
    - `matchedRole: STUDENT|TEACHER|UNKNOWN`
    - `userId?: number`
    - `branchId?: number`
    - `details`: thống kê entity upsert (user/classroomStudent/classroom/grade/...)

### 3.2 Service orchestration

Tạo service `OpenSyncIncrementalSyncService`:

Pseudo:
1) `token = OpenSyncTokenCache.fetch()`
2) Determine `maNien`:
   - nếu request có `maNien` → dùng
   - else lấy “niên hiện hành” từ config (hoặc call `thongtinnienhoc` và chọn mới nhất)
3) Try student:
   - call `GET /api/opensync/thongtinhocsinh?ma_truong=...&ma_nien=...&page=1&page_size=...`
   - filter `items` theo `SoDinhDanhCaNhan == input`
   - nếu match:
     - upsert `User` (citizenIdentityCode, name, birthday, gender)
     - resolve branch theo `MaTruong` (cần bảng cấu hình `ma_truong -> branch_id`)
     - upsert `SchoolYear/Grade/Classroom` + `ClassroomStudent`
     - upsert `UserBranchRole` (STUDENT) ở branch tương ứng
     - return OK
4) Try teacher:
   - call `GET /api/opensync/thongtingiaovien?ma_truong=...`
   - filter theo `SoDinhDanhCaNhan`
   - upsert `User`, `UserBranchRole` (TEACHER)
   - (optional) enqueue UC-05 sync allocation theo `SoDinhDanhCaNhan`
5) Nếu không tìm thấy:
   - return `synced=false` với lý do:
     - “user not found in OpenSync” hoặc “student not assigned to class”

### 3.3 Idempotency

UC-04 phải safe để gọi lại nhiều lần:
- Upsert theo khóa tự nhiên:
  - `(MaTruong, SoDinhDanhCaNhan)` cho HS/GV (theo `phan-tich-tich-hop.md`)
- Không tạo duplicate `UserBranchRole` / `ClassroomStudent`
- Nếu gọi từ SSO, sau khi sync xong cần bước “link”:
  - update `user.ttc_sub = <sub>` (nếu đã có claim)

### 3.4 Retry & lỗi 401 OpenSync

Theo doc:
- Token cache ~8h, khi GET bị 401:
  - invalidate cache
  - fetch token 1 lần
  - retry request 1 lần (không retry vô hạn)

### 3.5 Observability

Log theo `sync_request_id`:
- input `soDinhDanhCaNhan` (mask một phần), `maTruong`, `maNien`, `reason`
- kết quả: matched student/teacher, userId, branchId
- latency từng API call
- count entity upsert

---

## 4) Gắn UC-04 vào UC-01 (SSO miss)

Trong flow `POST /ttc/login-via-code` (UC-01):
- Resolve theo `sub` → not found
- Nếu có claim `identity`:
  - call `OpenSyncIncrementalSyncService.syncUser(identity, reason=SSO_MISS)`
  - sau đó resolve lại theo `citizenIdentityCode`
  - nếu match → link `ttc_sub=sub`, issue token LMS
- Nếu không có `identity`:
  - không thể gọi UC-04 tự động → tùy policy: reject hoặc JIT (đặc biệt PH)

---

## 5) Test plan tối thiểu

- Case 1: HS đã có trong OpenSync + đã xếp lớp → UC-04 sync OK, tạo đủ user + classroom link + branch role
- Case 2: HS chưa xếp lớp → UC-04 không tìm thấy (expected)
- Case 3: GV có trong OpenSync → sync OK, tạo user + TEACHER role
- Case 4: gọi UC-04 2 lần → không tạo duplicate
- Case 5: UC-01 miss → gọi UC-04 → login thành công (khi có claim `identity`)

