---
name: tich-hop-ttc-sso-opensync
description: >-
  Áp dụng hướng dẫn tích hợp đối tác TTC (ASC SCHOOL) vào LMS — BA luồng tách
  rời: (1) TTC SSO cho PH/HS theo OAuth 2.0 Authorization Code + OIDC (claim
  sub/user_type/scope/jti/exp); (2) Office 365 / Microsoft Entra ID SSO RIÊNG
  cho GV (TTC tách riêng phần đăng nhập GV) — claim oid/tid/email/upn; (3)
  OpenSync API đồng bộ máy-máy theo OAuth 2.0 Client Credentials (học sinh,
  giáo viên/nhân sự, khối lớp, lớp học, niên học, phân công giảng dạy). Dùng
  khi thiết kế/triển khai/review việc đăng nhập SSO qua TTC hoặc qua O365,
  đồng bộ học sinh/giáo viên từ TTC sang LMS, map user_type → role LMS, bridge
  GV (O365 oid) ↔ OpenSync (SoDinhDanhCaNhan), cache token, xử lý phân
  trang/lỗi 401/403, hoặc khi user nhắc TTC, ASC SCHOOL, OpenSync, Office 365,
  Microsoft Entra, Azure AD, opensync.hocsinh, opensync.giaovien, ma_truong,
  ma_nien, SoDinhDanhCaNhan, thongtinhocsinh, thongtingiaovien, RP-Initiated
  Logout, /oauth/authorize, /api/oauth/token, /api/opensync/token,
  /oauth2/v2.0/authorize, login.microsoftonline.com.
---

# TTC (ASC SCHOOL) — SSO (TTC + O365) + OpenSync API

Nguồn chuẩn:
- `tich-hop-ttc/HuongDan_SSO_DoiTac.docx` — luồng SSO Authorization Code (OIDC) cho PH/HS.
- `tich-hop-ttc/HuongDan_OpenSyncAPI_DoiTac.docx` — đồng bộ data học sinh / giáo viên / khối lớp / lớp / niên học / phân công.
- (Không có DOC riêng) — Office 365 SSO cho GV: dùng chuẩn Microsoft Entra ID OIDC; cấu hình do TTC IT cấp.

**BA luồng tách biệt — KHÔNG dùng chung:**

| Luồng | Mục đích | IdP | Actor | Grant type | Có user click? | Token sống |
|-------|----------|-----|-------|-----------|----------------|------------|
| **TTC SSO** (UC-01a) | Đăng nhập PH/HS | TTC OAuth | PH, HS | `authorization_code` | ✅ (mở browser) | 1h (3600s) |
| **O365 SSO** (UC-01b) | Đăng nhập GV | Microsoft Entra ID (Azure AD) | GV | `authorization_code` | ✅ (mở browser) | 1h (default Entra) |
| **OpenSync** | Đồng bộ data máy-máy (M2M) | TTC OAuth | (server) | `client_credentials` | ❌ (server-to-server) | 8h (28800s) |

> ⚠️ **GV KHÔNG đăng nhập qua TTC SSO** — TTC tách riêng phần này sang O365. Nếu nhận `user_type=1` từ TTC SSO → REJECT với message "Giáo viên vui lòng đăng nhập qua Office 365" (chống tạo trùng record).
>
> ⚠️ **Không nhập** giá trị TTC/O365 cấp (Client ID/Secret/Redirect URI/Tenant ID/API Codes/`ma_truong`/`ma_nien`) vào source — phải đọc từ env / KMS.

## Mục tiêu khi dùng skill

- Nhất quán cách xác thực, cấu trúc claim/JSON, và cách xử lý lỗi giữa ba luồng.
- Map đúng nguồn xác thực (TTC SSO / O365 SSO) ↔ `MaLoaiNhanSu` / xếp lớp HS (OpenSync) ↔ vai trò trong LMS.
- Cache token đúng vòng đời, không gọi token endpoint mỗi request.
- Truy vết người dùng bằng định danh **bền vững**:
  - PH/HS: OIDC `sub` (TTC) ↔ `SoDinhDanhCaNhan` (OpenSync).
  - GV: `oid`+`tid` (Entra) ↔ `Email` hoặc `employeeId` claim (OpenSync).

## Phạm vi

**Bao gồm:** TTC SSO đăng nhập PH/HS, đăng xuất RP-Initiated TTC; O365 SSO đăng nhập GV qua Microsoft Entra ID, đăng xuất Microsoft logout; lấy + cache OpenSync token; gọi 6 API OpenSync; map record TTC → entity LMS; xử lý lỗi 400/401/403 và `success:false`; bridge GV (Entra `oid`) ↔ OpenSync `thongtingiaovien` (`SoDinhDanhCaNhan`/`Email`).

**Không bao gồm:** chỉnh sửa data ngược về TTC (OpenSync **chỉ đọc**); push notification từ TTC; tính phí/lương; logic nội bộ của TTC; cấu hình App Registration trên Entra (do TTC IT làm); Microsoft Graph API ngoài `User.Read`.

---

## 1. TTC SSO (PH/HS) — OAuth 2.0 Authorization Code + OIDC

> **Áp dụng:** Phụ huynh (`user_type=4`), Học sinh (`user_type=6`). **GV (`user_type=1`) → REJECT** ở callback, hướng dẫn user dùng O365 (xem §1b).

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

## 1b. Office 365 SSO (GV) — Microsoft Entra ID + OIDC

> **Áp dụng:** Giáo viên / nhân sự. TTC tách riêng phần đăng nhập GV bằng O365 — KHÔNG đi qua TTC SSO. Chi tiết kiến trúc, sequence, bridge: **`tich-hop-ttc/phan-tich-tich-hop.md` §3b** + **`tich-hop-ttc/tech/sso-o365-implement.md`**.

### Endpoint (Microsoft Entra)

| Mục đích | Method | URL |
|---------|--------|-----|
| Discovery | `GET` | `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` |
| Authorize | `GET` | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize` |
| Token | `POST` | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token` |
| JWKS | `GET` | `https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys` |
| Logout | `GET` | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout` |

> Gọi discovery 1 lần lúc start service + cache 24h. KHÔNG hard-code endpoint.

### Tham số `/oauth2/v2.0/authorize`

| Tham số | Bắt buộc | Ghi chú |
|---------|:--------:|---------|
| `client_id` | ✅ | TTC IT cấp khi tạo App Registration |
| `response_type` | ✅ | `code` |
| `redirect_uri` | ✅ | Khớp tuyệt đối URI đã đăng ký trên Entra |
| `scope` | ✅ | Tối thiểu `openid profile email`. Thêm `offline_access` nếu cần `refresh_token`. Thêm `User.Read` nếu cần Graph |
| `state` | nên có | Random ≥16 byte — chống CSRF |
| `response_mode` | tuỳ chọn | `query` (default) hoặc `form_post` |
| `prompt` | tuỳ chọn | `select_account` để Entra hiện chooser kể cả khi đã login |

### Đổi code lấy token (`POST /oauth2/v2.0/token`)

- `Content-Type: application/x-www-form-urlencoded`
- Body: `grant_type=authorization_code`, `code`, `client_id`, `client_secret`, `redirect_uri`, `scope` (giống lúc authorize)
- Response: `{ access_token, id_token, token_type:"Bearer", expires_in, refresh_token?, scope }`

> **id_token** mới là JWT chứa user claim — verify qua JWKS. **access_token** là JWT của Microsoft Graph (nếu request `User.Read`), KHÔNG verify để lấy claim user.

### JWT id_token — claim chuẩn

| Claim | Có khi | Ý nghĩa |
|-------|--------|---------|
| `oid` | luôn | **Object ID** trong tenant — định danh bền vững GV; khoá lookup chính (`user.o365_oid`) |
| `tid` | luôn | Tenant ID — verify cứng = `O365_TENANT_ID` env |
| `sub` | luôn | Per-app pairwise — KHÔNG dùng làm khoá ngoại (đổi App = đổi `sub`) |
| `aud` | luôn | Phải khớp `O365_CLIENT_ID` |
| `iss` | luôn | `https://login.microsoftonline.com/{tid}/v2.0` — verify cứng |
| `exp` / `iat` / `nbf` | luôn | Thời gian token |
| `email` | scope `email` (thường có) | Bridge với `thongtingiaovien.Email` |
| `upn` | thường | User Principal Name (vd `gv001@truongttc.edu.vn`) |
| `preferred_username` | thường | Thường là email — fallback nếu thiếu `email` |
| `name` | scope `profile` | Họ tên đầy đủ |
| `given_name` / `family_name` | scope `profile` | Tên / Họ |
| `employeeId` | optional claim (TTC bật trong Token configuration) | **Bridge tốt nhất** với OpenSync `SoDinhDanhCaNhan` |
| `extension_*` | nếu HR đẩy CCCD vào extensionAttribute | Thay thế cho `employeeId` |

### RP-Initiated Logout O365

`GET /oauth2/v2.0/logout?post_logout_redirect_uri=…&id_token_hint=<id_token>&state=…`

Sau callback: clear session/cookie LMS, verify `state`, redirect về `/sign-in`.

### Bridge GV (O365) ↔ OpenSync (`thongtingiaovien`)

Token Entra **không có** `SoDinhDanhCaNhan`. Resolver theo thứ tự:

1. `users.find(o365_oid=oid, o365_tid=tid)` → nếu có → trả về (login lần 2+).
2. Nếu có claim `employeeId` → `giao_vien.find(so_dinh_danh=employeeId)` → match → upsert `o365_oid`/`o365_tid` → trả về.
3. Nếu có `email` → `giao_vien.find(email__iexact=email, source='TTC_OPENSYNC')` → match → upsert → trả về.
4. Không match → ghi `pending_o365_users`, REJECT 403, hiển thị "Tài khoản chưa được đồng bộ vào LMS — liên hệ admin".

> ⚠️ **KHÔNG JIT cho GV** — phải pre-provision qua UC-03 (cron OpenSync) trước. Nếu cho JIT → ai có email O365 thuộc tenant TTC đều thành GV trong LMS.

### Cấu hình bắt buộc

| Env | Nguồn | Ghi chú |
|-----|-------|---------|
| `O365_TENANT_ID` | TTC IT | GUID tenant Microsoft Entra của TTC |
| `O365_CLIENT_ID` | TTC IT | Application ID của App Registration |
| `O365_CLIENT_SECRET` | TTC IT (Vault) | Mặc định Entra hết hạn 24 tháng — rotate lịch |
| `O365_REDIRECT_URI` | LMS đăng ký | Vd `https://lms-sso.dtp.vn/o365-sso/callback` |
| `O365_SCOPES` | LMS config | `openid profile email` (+`offline_access` nếu cần) |

### Mã lỗi cốt lõi (Entra)

| Code Entra | Nghĩa | Hành động |
|------------|-------|-----------|
| `AADSTS50011` | Redirect URI mismatch | Check khớp tuyệt đối URI đăng ký |
| `AADSTS65001` | Admin consent chưa bấm | Yêu cầu TTC IT bấm consent |
| `AADSTS70001` | App not found / disabled | TTC IT enable lại App Registration |
| `AADSTS7000215` | Invalid client secret | Secret hết hạn hoặc sai → rotate |
| `AADSTS50105` | User chưa được assign vào app | TTC IT assign user/group |
| `AADSTS500133` | Token hết hạn | Refresh hoặc redirect login lại |

### Bảo mật O365 SSO

- `client_secret` từ env / Vault; **không** commit.
- Verify `id_token` qua JWKS (signature + `iss` + `aud` + `exp` + `tid`).
- **Lock tenant**: verify `tid` claim = `O365_TENANT_ID` env (chống cross-tenant attack).
- Verify `state` khớp request.
- Mọi giao tiếp HTTPS.
- KHÔNG log nội dung `id_token` / `access_token` / `refresh_token`.
- Lên lịch alert trước expiry của `client_secret` 30 ngày.

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

## 3. Định danh người dùng — bridge giữa các SSO và OpenSync

| Hệ | Định danh chính | Bền vững? | Có sẵn ở đâu |
|----|-----------------|----------|---------------|
| TTC SSO (OIDC) | `sub` | ✅ ổn định, không đổi khi đổi tên | JWT TTC |
| TTC SSO (scope `identity`) | `identity` | ✅ trùng `SoDinhDanhCaNhan` | JWT TTC (chỉ khi cấp scope) |
| **O365 SSO (Entra)** | **`oid` + `tid`** | **✅ ổn định trong tenant** | **id_token** |
| **O365 SSO (optional claim)** | **`employeeId`** | **✅ trùng `SoDinhDanhCaNhan`** | **id_token (chỉ khi TTC bật trong Token configuration)** |
| OpenSync | `SoDinhDanhCaNhan` | ✅ CCCD/CMND (số định danh cá nhân) | Mọi record |
| OpenSync (`thongtingiaovien`) | `Email` | ⚠️ tuỳ data sạch | Bridge phụ với O365 `email` |

**Khuyến nghị:** Lưu **các** trong LMS user record:
- `ttc_sub` (unique, từ TTC SSO `sub`) — khoá lookup khi PH/HS login.
- `o365_oid` + `o365_tid` (unique pair, từ Entra) — khoá lookup khi GV login.
- `so_dinh_danh_ca_nhan` (unique theo `MaTruong`) — khoá lookup khi đồng bộ OpenSync.
- `email` — fallback bridge với GV (O365 ↔ `thongtingiaovien.Email`).

Cách bridge:
- **PH/HS**: cấp scope `identity` cho TTC SSO client → claim `identity` = `SoDinhDanhCaNhan` → match thẳng record OpenSync.
- **GV**: ưu tiên (1) optional claim `employeeId` từ Entra; (2) fallback `email` Entra ↔ `thongtingiaovien.Email`; (3) fallback admin map qua bảng `pending_o365_users`.

---

## 4. Map nguồn xác thực ↔ vai trò LMS

| Nguồn xác thực | Khoá định danh | OpenSync nguồn | Role LMS đề xuất | Provisioning |
|----------------|----------------|----------------|-------------------|--------------|
| **O365 SSO (UC-01b)** — GV | `o365_oid`+`o365_tid` | `thongtingiaovien` (`MaLoaiNhanSu`=`GV`) | `TEACHER` (HEAD nếu chủ nhiệm trong `phanconggiangday.ChuNhiem`) | **Strict pre-provision** |
| **O365 SSO (UC-01b)** — Cán bộ | `o365_oid`+`o365_tid` | `thongtingiaovien` (`MaLoaiNhanSu`≠`GV`) | `STAFF` / `ADMIN` | Strict |
| **TTC SSO (UC-01a)** `user_type=4` | `ttc_sub` | (không có endpoint PH) | `PARENT` | **JIT** |
| **TTC SSO (UC-01a)** `user_type=6` | `ttc_sub` + `identity` | `thongtinhocsinh` | `STUDENT` | Pre-provision (ưu tiên), JIT fallback |
| **TTC SSO (UC-01a)** `user_type=1` | — | — | **REJECT** — phải dùng O365 | n/a |

> Phụ huynh chỉ có ở SSO; OpenSync **không** trả PH → không thể full-sync trước. Phải JIT khi PH login lần đầu.
> Giáo viên KHÔNG đi qua TTC SSO; nếu nhận `user_type=1` từ TTC → REJECT để tránh tạo trùng record.

---

## 5. Checklist nhanh cho agent (implement / review)

### TTC SSO (UC-01a — PH/HS)
- [ ] `redirect_uri` trong code **trùng tuyệt đối** URI đã đăng ký với TTC (kể cả trailing slash).
- [ ] Sinh `state` ngẫu nhiên (≥ 16 byte entropy), verify ở callback.
- [ ] Verify `exp` và `iss` trước khi tin payload JWT TTC.
- [ ] Sau logout: clear cookie/session LMS + redirect `endsession`.
- [ ] Map `user_type` đúng role LMS; `user_type=1` (GV) → **REJECT** với message "đăng nhập qua O365".
- [ ] **Không** rộng quyền hơn cần thiết.

### O365 SSO (UC-01b — GV)
- [ ] `redirect_uri` khớp tuyệt đối URI đã đăng ký trên Entra App Registration.
- [ ] Sinh `state` ngẫu nhiên ≥16 byte, verify ở callback.
- [ ] Verify `id_token` qua **JWKS** (signature + `iss` + `aud` + `exp`).
- [ ] **Lock tenant**: verify `tid` claim = `O365_TENANT_ID` env.
- [ ] Resolver theo thứ tự: `o365_oid` → `employeeId` → `email` → `pending_o365_users`.
- [ ] **KHÔNG JIT** cho GV — REJECT 403 nếu không match.
- [ ] Sau logout: clear cookie LMS + redirect `https://login.microsoftonline.com/{tid}/oauth2/v2.0/logout`.
- [ ] Cache discovery 24h; KHÔNG hard-code endpoint Microsoft.
- [ ] Alert lịch trước expiry `O365_CLIENT_SECRET` 30 ngày.

### OpenSync
- [ ] Cache token theo `expires_at` (refresh sớm 5–10 phút trước hết hạn).
- [ ] Gọi `opensync.nienhoc` trước → lấy `MaNienHoc` cho HS/lớp/phân công.
- [ ] Loop `page` đến `total_pages` cho full-sync; idempotent upsert theo `(MaTruong, SoDinhDanhCaNhan)`.
- [ ] HS chưa xếp lớp **không** có trong response — chấp nhận, không retry.
- [ ] HTTP 403 → là vấn đề **API Code** (cấp quyền), không phải token; alert ops thay vì refresh token.
- [ ] `200 + success:false` → đọc `message`; không treat như 5xx.
- [ ] Không log token; redact `Authorization` trong log middleware.
- [ ] Đảm bảo `thongtingiaovien.Email` được sync đúng → bridge với O365 (UC-01b) hoạt động.

### Chung
- [ ] `client_secret` (TTC + O365) từ env / Vault; trên prod dùng KMS.
- [ ] Sau khi đổi secret TTC: verify secret cũ đã ngừng dùng trong 24h (TTC giữ rolling window).
- [ ] HTTPS bắt buộc.
- [ ] Lưu `ttc_sub` (PH/HS) + `o365_oid`+`o365_tid` (GV) + `so_dinh_danh_ca_nhan` + `email` trong user record để bridge ba luồng.
- [ ] `lms-sso` thiết kế dạng broker đa-IdP với routing theo provider (`/ttc-sso/*`, `/o365-sso/*`).

## Kế hoạch dùng skill

Chi tiết phân tích kiến trúc, sequence, mapping entity và rủi ro use case **“login SSO TTC + đồng bộ HS/GV qua OpenSync”** trong file riêng:

- [`tich-hop-ttc/phan-tich-tich-hop.md`](./phan-tich-tich-hop.md)
