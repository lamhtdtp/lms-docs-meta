---
name: tich-hop-ttc-sso-opensync
description: >-
  Áp dụng hướng dẫn tích hợp đối tác TTC (ASC SCHOOL) vào LMS — hai luồng tách
  rời: (1) SSO đăng nhập một lần theo OAuth 2.0 Authorization Code + OIDC
  (claim sub/user_type/scope/jti/exp), (2) OpenSync API đồng bộ máy-máy theo
  OAuth 2.0 Client Credentials (học sinh, giáo viên/nhân sự, khối lớp, lớp
  học, niên học, phân công giảng dạy). Dùng khi thiết kế/triển khai/review
  việc đăng nhập SSO qua TTC, đồng bộ học sinh/giáo viên từ TTC sang LMS, map
  user_type → role LMS, cache token, xử lý phân trang/lỗi 401/403, hoặc khi
  user nhắc TTC, ASC SCHOOL, OpenSync, opensync.hocsinh, opensync.giaovien,
  ma_truong, ma_nien, SoDinhDanhCaNhan, thongtinhocsinh, thongtingiaovien,
  RP-Initiated Logout, /oauth/authorize, /api/oauth/token, /api/opensync/token.
---

# TTC (ASC SCHOOL) — SSO + OpenSync API

Nguồn chuẩn:
- `tich-hop-ttc/HuongDan_SSO_DoiTac.docx` — luồng SSO Authorization Code (OIDC).
- `tich-hop-ttc/HuongDan_OpenSyncAPI_DoiTac.docx` — đồng bộ data học sinh / giáo viên / khối lớp / lớp / niên học / phân công.

**Hai luồng tách biệt — KHÔNG dùng chung:**

| Luồng | Mục đích | Grant type | Có user click? | Token sống |
|-------|----------|-----------|----------------|------------|
| SSO | Đăng nhập người dùng | `authorization_code` | ✅ (mở browser) | 1h (3600s) |
| OpenSync | Đồng bộ data máy-máy (M2M) | `client_credentials` | ❌ (server-to-server) | 8h (28800s) |

> ⚠️ **Không nhập** giá trị TTC cấp (Client ID/Secret/Redirect URI/API Codes/`ma_truong`/`ma_nien`) vào source — phải đọc từ env / KMS.

## Mục tiêu khi dùng skill

- Nhất quán cách xác thực, cấu trúc claim/JSON, và cách xử lý lỗi giữa hai luồng.
- Map đúng `user_type` (SSO) ↔ `MaLoaiNhanSu` / xếp lớp HS (OpenSync) ↔ vai trò trong LMS.
- Cache token đúng vòng đời, không gọi token endpoint mỗi request.
- Truy vết người dùng bằng định danh **bền vững** (OIDC `sub` cho SSO; `SoDinhDanhCaNhan` cho OpenSync).

## Phạm vi

**Bao gồm:** SSO đăng nhập, đăng xuất RP-Initiated; lấy + cache OpenSync token; gọi 6 API OpenSync; map record TTC → entity LMS; xử lý lỗi 400/401/403 và `success:false`.

**Không bao gồm:** chỉnh sửa data ngược về TTC (OpenSync **chỉ đọc**); push notification từ TTC; tính phí/lương; logic nội bộ của TTC.

---

## 1. SSO — OAuth 2.0 Authorization Code + OIDC

### Endpoint

| Mục đích | Method | URL |
|---------|--------|-----|
| Authorization | `GET` | `https://{Base_URL}/oauth/authorize` |
| Token | `POST` | `https://{Base_URL}/api/oauth/token` |
| Revoke | `POST` | `https://{Base_URL}/api/oauth/revoke` |
| End Session (logout) | `GET` | `https://{Base_URL}/oauth/endsession` |

### Tham số `/oauth/authorize` (bước redirect)

| Tham số | Bắt buộc | Ghi chú |
|---------|:--------:|---------|
| `response_type` | ✅ | Cố định `code` |
| `client_id` | ✅ | TTC cấp |
| `redirect_uri` | ✅ | Phải khớp **chính xác** URI đã đăng ký |
| `scope` | ✅ | `openid` (bắt buộc) ± `profile`, `email`, `phone`, `address`, `identity` |
| `state` | nên có | Random string, chống CSRF — verify khi callback |

Callback: `…/callback?code=<AUTHORIZATION_CODE>&state=<YOUR_STATE>`.

### Đổi code lấy token (`POST /api/oauth/token`)

- `Content-Type: application/x-www-form-urlencoded`
- Body form: `grant_type=authorization_code`, `code`, `client_id`, `client_secret`, `redirect_uri`.
- Response: `{ access_token, token_type:"Bearer", expires_in:3600, scope }`.

### JWT — claim chuẩn (decode tại jwt.io)

| Claim | Có khi | Ý nghĩa |
|-------|--------|---------|
| `sub` | luôn | **Định danh bền vững** user trên TTC — dùng làm khoá ngoại trong DB LMS |
| `user_type` | luôn | `1` = Giáo viên/cán bộ, `4` = Phụ huynh, `6` = Học sinh |
| `scope` | luôn | Danh sách scope đã được cấp |
| `jti` | luôn | UUID — chống replay |
| `exp` | luôn | Unix timestamp hết hạn |
| `given_name` | scope `profile` | Tên |
| `family_name` | scope `profile` | Họ đệm (rỗng với Phụ huynh) |
| `name` | scope `profile` | Họ tên đầy đủ |
| `picture` | scope `profile` | Path avatar (CDN do TTC cung cấp) |
| `email` | scope `email` | |
| `identity` | scope `identity` | Số định danh — **đối chiếu** với `SoDinhDanhCaNhan` của OpenSync |
| `phone` | scope `phone` | |
| `address` | scope `address` | |

> ℹ️ Phụ huynh: `family_name = ""`, `name` chứa toàn bộ họ tên.

### RP-Initiated Logout

`GET /oauth/endsession?id_token_hint=<ACCESS_TOKEN>&post_logout_redirect_uri=…&state=…`. Sau callback: xoá session/cookie LMS, verify `state`, redirect về trang đăng nhập.

### Bảo mật SSO

- `client_secret` đọc từ env / Vault — **không** commit, **không** hard-code.
- Verify `state` khớp request.
- Verify `exp` trước khi tin token; verify `iss` = TTC issuer.
- Mọi giao tiếp HTTPS.
- Khi secret lộ: TTC cấp lại; secret cũ còn hiệu lực **24h** để rolling cấu hình.

---

## 2. OpenSync — OAuth 2.0 Client Credentials (M2M)

### Lấy token (`POST {Base_URL}/api/opensync/token`)

- Header `Authorization: Basic <base64(client_id:client_secret)>`.
- Header `Content-Type: application/json`.
- Body JSON: `{"grant_type":"client_credentials"}`.
- Response: `{ success, access_token, token_type:"Bearer", expires_in:28800, expires_at }`.

> ℹ️ **Cache** access_token và refresh khi gần `expires_at`. Không gọi token endpoint mỗi request.

### Bảng API (cần thêm `Authorization: Bearer <access_token>`)

| API Code | Endpoint | Params bắt buộc | Tuỳ chọn | Trả về |
|----------|----------|------------------|----------|--------|
| `opensync.hocsinh` | `GET /api/opensync/thongtinhocsinh` | `ma_truong`, `ma_nien` | `SoDinhDanhCaNhan`, `page`, `page_size` | Học sinh **đã xếp lớp** trong niên học |
| `opensync.giaovien` | `GET /api/opensync/thongtingiaovien` | `ma_truong` | `SoDinhDanhCaNhan`, `page`, `page_size` | Giáo viên / nhân sự (không phân theo niên học) |
| `opensync.khoilop` | `GET /api/opensync/thongtinkhoilop` | `ma_truong` | `page`, `page_size` | Khối lớp |
| `opensync.lophoc` | `GET /api/opensync/thongtinlophoc` | `ma_truong`, `ma_nien` | `ma_khoi`, `page`, `page_size` | Lớp học theo niên |
| `opensync.nienhoc` | `GET /api/opensync/thongtinnienhoc` | (không) | `page`, `page_size` | Toàn bộ niên học |
| `opensync.phanconggiangday` | `GET /api/opensync/phanconggiangday` | `ma_truong`, `ma_nien`, `SoDinhDanhCaNhan` | `page`, `page_size` | Chủ nhiệm + phân công môn HK1/HK2 |

> ⚠️ Mỗi API yêu cầu **API Code** tương ứng đã được TTC cấp cho client. Thiếu code → HTTP 403.

### Cấu trúc response chung (paged)

```json
{
  "success": true,
  "message": "…",
  "data": {
    "total_count": 320,
    "page": 1,
    "page_size": 100,
    "total_pages": 4,
    "items": [ /* … */ ]
  }
}
```

`page_size` mặc định **1000**, tối đa **5000**. Loop tới `page > total_pages` để full-sync.

### Schema chính (chỉ field đáng map)

**Học sinh** — `HoDem`, `Ten`, `HoTen`, `NgaySinh`, `GioiTinh` (`true`=Nam), `SoDinhDanhCaNhan`, `MaTruong`, `TenTruong`, `MaKhoi`, `MaLopHoc`, `TenLopHoc`, `MaNien`. *HS chưa xếp lớp KHÔNG xuất hiện.*

**Giáo viên / nhân sự** — `HoDem`, `Ten`, `HoTen`, `NgaySinh`, `GioiTinh`, `SoDinhDanhCaNhan`, `Email`, `MaLoaiNhanSu` (`GV` = giáo viên), `LoaiNhanSu`, `MaTruong`, `TenTruong`, `TrangThai`.

**Khối lớp** — `MaKhoiLop`, `TenKhoiLop`. *(Lưu ý: trong API học sinh dùng tên field `MaKhoi` chứa giá trị như `KL01`; trong API khối lớp dùng `MaKhoiLop` như `K1` — kiểm tra contract khi map.)*

**Lớp học** — `MaKhoi`, `MaLopHoc`, `TenLopHoc`.

**Niên học** — `MaNienHoc` (vd `NH2025`), `TenNienHoc`. *Gọi trước, lấy `MaNienHoc` làm `ma_nien` cho HS / lớp / phân công.*

**Phân công giảng dạy** — `HoTen`, `SoDinhDanhCaNhan`, `ChuNhiem` (object `MaKhoi`/`MaLopHoc`/`TenLopHoc`), `PhanCongMonHocHK1[]`, `PhanCongMonHocHK2[]` (mỗi phần tử: `HocKy`, `MaMonHoc`, `TenMonHoc`, `MaKhoi`, `MaLopHoc`, `TenLopHoc`).

> ⚠️ Trong DOC có chỗ ghi `API Code cần có: opensync.phancong` nhưng bảng đầu tiên ghi `opensync.phanconggiangday`. **Khi cấp quyền, đối chiếu lại với TTC** — coi `opensync.phanconggiangday` là chuẩn cho đến khi có xác nhận khác.

### Mã lỗi cốt lõi

| HTTP | `success` | Nguyên nhân | Hành động |
|------|-----------|-------------|-----------|
| 401 | — | Token thiếu / hết hạn | Lấy token mới qua `/api/opensync/token` |
| 403 | — | Token hợp lệ, thiếu API Code | Liên hệ TTC cấp thêm API Code |
| 400 | — | `grant_type` sai / Basic Auth sai | Sửa body + header |
| 200 | `false` | `ma_truong`/`ma_nien` không tồn tại | Đọc `message` |
| 200 | `false` | `ma_khoi` không thuộc `ma_truong` | Gọi `opensync.khoilop` để lấy danh sách hợp lệ |

### Bảo mật OpenSync

- `client_secret` từ env / Vault.
- **Cache** `access_token`, kiểm tra `expires_at` trước khi dùng.
- HTTPS toàn bộ.
- **Không** log nội dung token ra file/monitoring.
- Secret lộ → TTC cấp lại; secret cũ vẫn còn hiệu lực **24h**.

---

## 3. Định danh người dùng — bridge giữa SSO và OpenSync

| Hệ | Định danh chính | Bền vững? | Có sẵn ở đâu |
|----|-----------------|----------|---------------|
| SSO (OIDC) | `sub` | ✅ ổn định, không đổi khi đổi tên | JWT |
| SSO (scope `identity`) | `identity` | ✅ trùng `SoDinhDanhCaNhan` | JWT (chỉ khi cấp scope) |
| OpenSync | `SoDinhDanhCaNhan` | ✅ CCCD/CMND (số định danh cá nhân) | Mọi record |

**Khuyến nghị:** Lưu **cả hai** trong LMS user record:
- `ttc_sub` (unique, từ SSO `sub`) — khoá lookup khi login.
- `so_dinh_danh_ca_nhan` (unique theo `MaTruong`) — khoá lookup khi đồng bộ OpenSync.

Cách bridge `sub` ↔ `SoDinhDanhCaNhan`:
- Cấp scope `identity` cho client → JWT có claim `identity` = `SoDinhDanhCaNhan` → match thẳng record OpenSync;
- HOẶC để TTC tài liệu hoá quy ước `sub` (ví dụ `sub` chính là PK của TTC) → hỏi TTC cách join (có thể cần API thứ 7 để map `sub` → CCCD).

---

## 4. Map `user_type` (SSO) ↔ `MaLoaiNhanSu` (OpenSync) ↔ Role LMS

| SSO `user_type` | OpenSync nguồn | Role LMS đề xuất |
|-----------------|----------------|-------------------|
| `1` Giáo viên / cán bộ | `thongtingiaovien` (`MaLoaiNhanSu` = `GV`/khác) | `TEACHER` (HEAD nếu là chủ nhiệm trong `phanconggiangday.ChuNhiem`) hoặc `STAFF` |
| `4` Phụ huynh | (không có endpoint riêng — phụ huynh chưa nằm trong 6 API) | `PARENT` — provisioning JIT khi SSO |
| `6` Học sinh | `thongtinhocsinh` | `STUDENT` |

> Phụ huynh chỉ có ở SSO; OpenSync **không** trả PH → không thể full-sync trước. Phải JIT khi PH login lần đầu.

---

## 5. Checklist nhanh cho agent (implement / review)

### SSO
- [ ] `redirect_uri` trong code **trùng tuyệt đối** URI đã đăng ký với TTC (kể cả trailing slash).
- [ ] Sinh `state` ngẫu nhiên (≥ 16 byte entropy), verify ở callback.
- [ ] Verify `exp` và `iss` trước khi tin payload JWT.
- [ ] Sau logout: clear cookie/session LMS + redirect `post_logout_redirect_uri`.
- [ ] Map `user_type` đúng role LMS; **không** rộng quyền hơn cần thiết.

### OpenSync
- [ ] Cache token theo `expires_at` (refresh sớm 5–10 phút trước hết hạn).
- [ ] Gọi `opensync.nienhoc` trước → lấy `MaNienHoc` cho HS/lớp/phân công.
- [ ] Loop `page` đến `total_pages` cho full-sync; idempotent upsert theo `(MaTruong, SoDinhDanhCaNhan)`.
- [ ] HS chưa xếp lớp **không** có trong response — chấp nhận, không retry.
- [ ] HTTP 403 → là vấn đề **API Code** (cấp quyền), không phải token; alert ops thay vì refresh token.
- [ ] `200 + success:false` → đọc `message`; không treat như 5xx.
- [ ] Không log token; redact `Authorization` trong log middleware.

### Chung
- [ ] `client_secret` từ env / Vault; trên prod dùng KMS.
- [ ] Trên 24h sau khi đổi secret: verify secret cũ đã ngừng dùng (log endpoint token).
- [ ] HTTPS bắt buộc.
- [ ] Lưu `ttc_sub` + `so_dinh_danh_ca_nhan` trong user record để bridge hai luồng.

## Kế hoạch dùng skill

Chi tiết phân tích kiến trúc, sequence, mapping entity và rủi ro use case **“login SSO TTC + đồng bộ HS/GV qua OpenSync”** trong file riêng:

- [`tich-hop-ttc/phan-tich-tich-hop.md`](./phan-tich-tich-hop.md)
