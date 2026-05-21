---
title: Test cases — Tích hợp TTC (SSO + OpenSync)
scope: tich-hop-ttc
sources:
  - tich-hop-ttc/phan-tich-tich-hop.md
  - tich-hop-ttc/tech/uc-01-implementation.md
  - tich-hop-ttc/tech/uc-03-implement.md
  - tich-hop-ttc/tech/uc-03-run-modes.md
  - tich-hop-ttc/tech/uc-04-implement.md
  - tich-hop-ttc/huong-dan-mapping-opensync-lms-api.md
---

## 1) Quy ước & dữ liệu chuẩn bị

### 1.1 Thuật ngữ

- **TTC**: upstream IdP + OpenSync API
- **`sub`**: claim SSO (JWT)
- **`identity`**: claim SSO khi có scope `identity` → align `SoDinhDanhCaNhan`
- **`ma_truong`**: mã trường OpenSync
- **Tenant mapping**: `school_domain` → `ma_truong` + `default_branch_id`

### 1.2 Data setup tối thiểu

- Ít nhất 1 **school domain** + mapping `ma_truong` ↔ branch
- Credential OpenSync hợp lệ + API code đủ cho các endpoint dùng trong test
- Niên học hiện hành `ma_nien` khớp config
- Ít nhất 1 HS đã xếp lớp + 1 GV có trong OpenSync (môi trường staging hoặc mock)

---

## 2) UC-01 — Login SSO TTC (`lms-sso` + `lms-api`)

### TC-SSO-01 — Happy path: authorize → callback → token LMS

- **Precondition**: User TTC hợp lệ; mapping tenant đúng domain
- **Steps**: Bấm đăng nhập TTC → đăng nhập TTC → callback có `code` + `state`
- **Expected**: Cookie LMS (`accessToken`, `refreshToken`, `branchId`, …); redirect đúng `lmsSiteUrl`; không lộ `client_secret`

### TC-SSO-02 — State CSRF: mismatch `state`

- **Steps**: Callback với `state` không khớp cookie
- **Expected**: Từ chối; không phát hành token LMS; redirect lỗi rõ ràng

### TC-SSO-03 — Resolve user theo `ttc_sub`

- **Precondition**: User đã có `ttc_sub` trong DB
- **Expected**: Login OK không cần gọi OpenSync

### TC-SSO-04 — Resolve user theo `identity` → link `ttc_sub`

- **Precondition**: User đã sync OpenSync (`citizenIdentityCode`); chưa có `ttc_sub`
- **Expected**: Match theo CCCD; sau login có `ttc_sub` = JWT `sub`

### TC-SSO-05 — Không có `identity` claim

- **Precondition**: JWT không có `identity`
- **Expected**: Không match được OpenSync bằng CCCD; hành vi theo policy (reject hoặc JIT PH)

### TC-SSO-06 — `user_type` không hỗ trợ

- **Expected**: Từ chối login + log; không đoán role

### TC-SSO-07 — JWT TTC invalid (exp / iss / signature)

- **Expected**: 401/400; không issue token LMS

---

## 3) UC-04 — Incremental sync on-demand (`lms-api`)

### TC-INC-01 — Sync HS theo `SoDinhDanhCaNhan` (đã xếp lớp)

- **Precondition**: HS tồn tại trong OpenSync và đã có trong `thongtinhocsinh`
- **Steps**: Gọi API sync-user với CCCD
- **Expected**: Upsert user + `ClassroomStudent` + `UserBranchRole` STUDENT

### TC-INC-02 — HS chưa xếp lớp

- **Expected**: Không tìm thấy trong OpenSync HS list; `synced=false`; message rõ

### TC-INC-03 — Sync GV

- **Expected**: Upsert user + `UserBranchRole` TEACHER

### TC-INC-04 — Idempotency: gọi sync 2 lần

- **Expected**: Không duplicate `User` / `UserBranchRole` / `ClassroomStudent`

### TC-INC-05 — Gọi sau UC-01 miss (có `identity`)

- **Steps**: Login SSO không thấy user → trigger UC-04 → login lại
- **Expected**: User được tạo/link; login thành công

---

## 4) UC-03 — Full sync cron (`lms-api`)

### TC-FULL-01 — Thứ tự pipeline

- **Expected**: token → niên học → khối → lớp → GV → HS (paged); không gọi HS trước khi có lớp nếu phụ thuộc policy code

### TC-FULL-02 — Phân trang `thongtinhocsinh`

- **Precondition**: `total_pages` > 1
- **Expected**: Quét đủ trang; không duplicate upsert

### TC-FULL-03 — Token cache + 401 retry

- **Steps**: Giả lập 401 trên GET sau khi token hết hạn
- **Expected**: Invalidate cache; token mới; retry đúng 1 lần cho request đó

### TC-FULL-04 — Job partial fail (5xx giữa chừng)

- **Expected**: Job FAILED/PARTIAL; **không** chạy inactive-by-sync trên snapshot thiếu

### TC-FULL-05 — HTTP 200 nhưng `success: false`

- **Expected**: Không đọc `data`; fail job; log `message`

### TC-FULL-06 — HTTP 403 thiếu API code

- **Expected**: Fail-fast; alert; không spam retry

### TC-FULL-07 — Inactive-by-sync (snapshot)

- **Precondition**: HS có trong kỳ sync trước; kỳ sau không còn trong OpenSync
- **Expected**: Record đánh `INACTIVE_BY_SYNC` (không hard-delete)

---

## 5) Tenant mapping — domain ↔ `ma_truong` ↔ branch

### TC-TENANT-01 — Mapping đúng domain

- **Expected**: Job và SSO resolve đúng `school_id`, `ma_truong`, `default_branch_id`

### TC-TENANT-02 — Domain chưa cấu hình

- **Expected**: Lỗi rõ; không upsert nhầm branch khác

---

## 6) UC-05 — Phân công (nếu trong scope full-sync)

### TC-ALLOC-01 — Sau sync GV + lớp, gọi `phanconggiangday`

- **Expected**: `TeacherAllocation` HEAD/SUBJECT khớp doc; không duplicate composite key

### TC-ALLOC-02 — 403 chỉ trên phân công

- **Expected**: UC-03 core vẫn OK nếu policy cho degrade; log cờ “allocation failed”

---

## 7) UC-03 run modes (ngoài cron)

### TC-RUN-01 — Manual full-sync API

- **Expected**: Chạy được khi admin trigger; lock không cho 2 job chồng nhau

### TC-RUN-02 — Webhook (nếu có)

- **Expected**: Verify signature; map event → UC-04 hoặc sync nhánh allocation

---

## 8) Field edge cases (doc)

### TC-EDGE-01 — `MaKhoi` vs `MaKhoiLop`

- **Expected**: Không join cứng sai; có cờ unresolved hoặc lưu raw

### TC-EDGE-02 — Rate limit / timeout OpenSync

- **Expected**: Backoff + fail có kiểm soát; không retry vô hạn

---

## 9) Regression smoke checklist

- [ ] SSO happy path + cookie LMS
- [ ] State mismatch bị chặn
- [ ] Identity bridge → link `ttc_sub`
- [ ] Full sync paging HS đủ trang
- [ ] Partial fail không inactive nhầm
- [ ] `success:false` không crash parser
- [ ] UC-04 idempotent
- [ ] Tenant mapping theo domain đúng branch
