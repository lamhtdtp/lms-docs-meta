---
title: UC-03 Implementation — Full sync danh mục TTC → LMS (OpenSync cron)
scope: tich-hop-ttc
repos:
  - BE: ~/dev/dtp/lms-api
related:
  - tich-hop-ttc/phan-tich-tich-hop.md (UC-03/04, ordering, idempotency, soft-delete)
  - tich-hop-ttc/huong-dan-mapping-opensync-lms-api.md (field mapping)
  - tich-hop-ttc/tech/uc-04-implement.md (incremental sync, shared services)
status: draft
---

## 0) Mục tiêu UC-03

Chạy job định kỳ (đề xuất `0 2 * * *`) để **đồng bộ snapshot** danh mục từ TTC OpenSync → DB LMS, đảm bảo:
- dữ liệu HS/GV/lớp/khối/niên học luôn “đã có sẵn” trước khi user login SSO
- job **idempotent** (chạy lại không nhân đôi)
- có chiến lược “mất khỏi snapshot” → **inactive** (soft-delete) thay vì hard delete

---

## 1) Input / cấu hình bắt buộc

### 1.1 Credential & endpoint OpenSync

- `baseUrl` OpenSync
- `clientId`, `clientSecret` (client_credentials)
- `api codes` đã được ASC cấp để không bị 403

### 1.2 Quy ước tenant: `ma_truong` ↔ LMS branch

OpenSync dùng **`ma_truong`**. LMS có `School` và nhiều `Branch`.

**Quy ước theo domain (khuyến nghị):** domain (host) của LMS là khóa tenant chuẩn → suy ra `school_id`, sau đó lấy mapping TTC để biết `ma_truong` và `branch_id` mặc định.

**Cần 1 bảng cấu hình (hoặc app config) tối thiểu theo domain:**
- `school_domain` → `ma_truong`
- `school_domain` → `default_branch_id`
- (optional) `enabled`, `env`, `note`

**Lý do:** các luồng SSO/OpenSync đều gắn với “trường” theo domain; nếu chỉ map `ma_truong → branch` mà không neo theo domain thì khó vận hành khi có nhiều trường/môi trường.

**Quy tắc v1:** 1 `school_domain` ↔ 1 `ma_truong` ↔ 1 `default_branch_id` (tránh ambiguity). Nếu 1 trường có nhiều cơ sở/branch thì cần TTC cung cấp key tương ứng (vd `ma_co_so`) mới tách được.

> Nếu không có mapping này, không thể upsert đúng `Grade/Classroom/SchoolYear/UserBranchRole`.

### 1.3 Quy ước niên học: `ma_nien`

Theo doc:
- API niên học trả `MaNienHoc`
- Các API khác dùng query `ma_nien` (có thể khác format)

Chốt 1 chuẩn:
- `currentMaNien` lấy từ config (khuyến nghị cho v1), hoặc
- gọi `thongtinnienhoc` và chọn record “hiện hành” theo rule nội bộ

---

## 2) Thứ tự gọi API trong cron (canonical ordering)

Theo `phan-tich-tich-hop.md`:

1. `POST /api/opensync/token` → cache token (TTL ~8h)
2. `GET /api/opensync/thongtinnienhoc` → upsert niên học
3. `GET /api/opensync/thongtinkhoilop?ma_truong=...` → upsert khối lớp (grade)
4. `GET /api/opensync/thongtinlophoc?ma_truong=...&ma_nien=...` → upsert lớp học (classroom)
5. `GET /api/opensync/thongtingiaovien?ma_truong=...` → upsert giáo viên/nhân sự (teacher)
6. `GET /api/opensync/thongtinhocsinh?ma_truong=...&ma_nien=...` (paged) → upsert học sinh + quan hệ lớp
7. UC-05 (tách riêng nhưng thường chạy liền sau): `GET /api/opensync/phanconggiangday?...&SoDinhDanhCaNhan=...` → upsert phân công/HEAD

---

## 3) Thiết kế BE trong `~/dev/dtp/lms-api`

### 3.1 Module/package đề xuất

Tạo module kiểu:
- `vn.dtpsoft.modules.ttc.opensync.*`

Các thành phần tối thiểu:
- `OpenSyncTokenCache` (shared với UC-04)
- `OpenSyncHttpClient` (wrap `HttpService`)
- DTO envelope phân trang `OpenSyncPageResponse<T>`
- DTO `items` theo từng API (HS/GV/Lớp/Khối/Niên/Phân công)
- `OpenSyncFullSyncJob` (scheduler)
- `OpenSyncUpsertService` (map DTO → entity LMS)

### 3.2 Scheduler & locking

Vì full-sync có thể chạy lâu, cần tránh chạy song song:
- DB lock (ví dụ bảng `sync_job_lock`), hoặc
- distributed lock (Redis) nếu có

Log job start/end + duration.

### 3.3 Token cache & retry 401

Theo doc:
- cache token đến `expires_at - 5 phút`
- nếu gặp 401:
  - invalidate cache
  - fetch token 1 lần
  - retry request 1 lần

Không retry vô hạn để tránh storm khi credential hỏng.

---

## 4) Idempotency & khóa tự nhiên (bắt buộc)

Theo `phan-tich-tich-hop.md`:
- HS: `(MaTruong, SoDinhDanhCaNhan)`
- GV: `(MaTruong, SoDinhDanhCaNhan)`
- Khối: `(MaTruong, MaKhoiLop)`
- Lớp: `(MaTruong, MaNien, MaLopHoc)`
- Niên: `MaNienHoc`
- Phân công: `(MaTruong, MaNien, SoDinhDanhCaNhan, HocKy, MaMonHoc, MaLopHoc)`

Upsert chuẩn:
1) SELECT theo natural key
2) có → UPDATE + `source=TTC_OPENSYNC`
3) không → INSERT + `source=TTC_OPENSYNC`

---

## 5) Soft-delete / Inactive-by-sync (snapshot diff)

OpenSync không có delta, full-sync là snapshot.

Chiến lược đề xuất:
- Có `current_sync_id` tăng dần theo `(ma_truong, ma_nien)`
- Mỗi record upsert set `last_seen_sync_id = current_sync_id`
- Sau khi sync xong:
  - các record `source=TTC_OPENSYNC` nhưng `last_seen_sync_id < current_sync_id` → set `status=INACTIVE_BY_SYNC` (hoặc `ACTIVE=false`)

Không hard-delete để giữ lịch sử (điểm danh, đơn nghỉ, audit).

---

## 6) Mapping dữ liệu về model LMS (tối thiểu để login được)

Tham chiếu chi tiết ở `huong-dan-mapping-opensync-lms-api.md`. Checklist map tối thiểu:

### 6.1 Student (HS)
- Upsert `User` (role STUDENT):
  - `citizenIdentityCode = SoDinhDanhCaNhan`
  - `firstName/lastName`, `birthday`, `gender`
  - `school` theo mapping `ma_truong`
- Upsert `Grade` theo `MaKhoi`/`MaKhoiLop` (lưu ý mismatch doc)
- Upsert `Classroom` theo `MaLopHoc`
- Upsert `ClassroomStudent` liên kết HS ↔ lớp (vì OpenSync chỉ trả HS đã xếp lớp)
- Upsert `UserBranchRole` (STUDENT + branch mapping)

### 6.2 Teacher (GV/nhân sự)
- Upsert `User` (role TEACHER/STAFF theo policy):
  - `citizenIdentityCode`
  - `email`, `status` (map chuỗi)
- Upsert `UserBranchRole` (TEACHER + branch mapping)

### 6.3 Allocation (UC-05) — chạy sau full-sync
- Upsert `TeacherAllocation`:
  - `HEAD` từ `ChuNhiem`
  - `SUBJECT` từ `PhanCongMonHocHK1/HK2`

---

## 7) Observability & báo cáo sync

### 7.1 Log tối thiểu
- jobId, ma_truong, ma_nien, current_sync_id
- số lượng item nhận & số record upsert theo từng entity
- số record set inactive
- lỗi API (HTTP code + message), đặc biệt case `success:false` dù HTTP 200

### 7.2 Metric/alert
- duration full-sync vượt ngưỡng
- tỷ lệ lỗi/403 (thiếu API code)
- token refresh quá nhiều (dấu hiệu cache lỗi)

---

## 8) Error handling strategy

### 8.1 Lỗi network / timeout / 5xx (TTC chập chờn / down)

- Retry theo từng request với backoff (ví dụ 3 lần: 1s → 5s → 15s).
- Nếu vẫn lỗi:
  - đánh dấu job `FAILED` hoặc `PARTIAL` (tuỳ thiết kế tracking)
  - **dừng các bước phụ thuộc** (vd fail `lophoc` thì không sync `hocsinh`)
  - alert ops.
- **Không chạy bước “inactive-by-sync”** nếu job không hoàn tất thành công (tránh inactive nhầm vì snapshot thiếu).

### 8.2 HTTP 401 (token hết hạn / cache sai)

- Invalidate token cache → xin token mới → retry đúng **1 lần**.
- Nếu vẫn 401: coi là lỗi credential/config → stop job + alert (không retry vô hạn).

### 8.3 HTTP 403 (thiếu API code / không có quyền)

- Fail-fast cho endpoint bị 403; retry không giúp.
- Log rõ API nào bị 403 + params (`ma_truong`, `ma_nien`).
- Cho phép degrade nếu 403 ở phần “mở rộng” (vd UC-05 phân công), nhưng nếu 403 ở các API nền (niên/khối/lớp/HS/GV) thì fail job.

### 8.4 HTTP 200 nhưng `success: false`

- Bắt buộc check `success` trước khi đọc `data`.
- Xử lý như lỗi nghiệp vụ/param sai:
  - log `message` + request params
  - hạn chế retry (thường do `ma_truong/ma_nien` sai)
  - fail job, không chạy bước phụ thuộc.

### 8.5 Lỗi parse / schema thay đổi

- Nếu JSON parse fail: stop job + alert (cần cập nhật DTO).
- Nên cấu hình DTO theo hướng “ignore unknown” để giảm break khi TTC thêm field.

### 8.6 Quy tắc an toàn dữ liệu

- Không “inactive-by-sync” khi full-sync thất bại/partial.
- Lock job để không chạy song song.
- Upsert idempotent theo natural key để retry không tạo duplicate.

---

## 9) Test plan tối thiểu

- Token cache: hết hạn/401 → refresh đúng 1 lần
- Paging HS: nhiều trang → upsert đủ và không duplicate
- Idempotency: chạy 2 lần liên tiếp → số record không tăng bất thường
- Soft-delete: bỏ 1 HS khỏi snapshot → record bị set inactive (không delete)
- Mismatch `MaKhoi` vs `MaKhoiLop`: lưu được data mà không crash; không hard-join sai

