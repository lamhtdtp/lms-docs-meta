# Phân tích — LMS đăng nhập SSO TTC + đồng bộ HS/GV qua OpenSync

**Nguồn:** `tich-hop-ttc/HuongDan_SSO_DoiTac.docx`, `tich-hop-ttc/HuongDan_OpenSyncAPI_DoiTac.docx`, đối chiếu `tich-hop-ttc/SKILL.md`.

**Ngữ cảnh:** TTC (ASC SCHOOL) là hệ thống thông tin trường (SIS) phía đối tác. LMS muốn:

1. Cho **người dùng TTC** đăng nhập **một lần** vào LMS:
   - **PH/HS** → SSO qua TTC OAuth/OIDC (`HuongDan_SSO_DoiTac.docx`).
   - **GV** → SSO qua **Office 365 (Microsoft Entra ID)** *trực tiếp* — TTC tách riêng, KHÔNG gộp vào TTC SSO.
2. Đồng bộ danh mục **học sinh / giáo viên / khối / lớp / niên học / phân công** từ TTC → LMS định kỳ để LMS có sẵn dữ liệu (không chờ user login mới có).

Đây là **ba luồng độc lập về kỹ thuật** nhưng **gắn chặt về dữ liệu** — bridge bằng định danh người dùng. Phân tích dưới đây chia ba luồng, sau đó gộp vào kiến trúc tổng.

---

## 1. Tóm tắt use case

| # | Use case | Actor | Tần suất | Trigger |
|---|----------|-------|----------|---------|
| UC-01a | Login SSO TTC vào LMS (PH/HS) | PH / HS | Mỗi lần login | Click "Đăng nhập với TTC" trên LMS |
| **UC-01b** | **Login SSO Office 365 vào LMS (GV)** | **GV** | **Mỗi lần login** | **Click "Đăng nhập với Office 365" trên LMS** |
| UC-02a | Logout RP-Initiated TTC | PH / HS | Mỗi lần logout | Click "Đăng xuất" trên LMS |
| UC-02b | Logout RP-Initiated O365 | GV | Mỗi lần logout | Click "Đăng xuất" trên LMS |
| UC-03 | Full-sync danh mục TTC → LMS | Job hệ thống | 1 lần/ngày (đêm) | Cron `0 2 * * *` |
| UC-04 | Incremental-sync 1 user khi cần | LMS app | On-demand | UI gọi sync, hoặc khi login SSO không tìm thấy record |
| UC-05 | Sync phân công giảng dạy | Job hệ thống | 1 lần/ngày + on-demand | Sau full-sync GV+lớp |

**Phụ thuộc giữa các UC:**

```
UC-01a (login SSO TTC — PH/HS)
   └── lookup user theo `sub` / `SoDinhDanhCaNhan`
         ├── tìm thấy   → set session, vào LMS
         └── không thấy → JIT (UC-04) hoặc redirect màn báo lỗi
                          tuỳ provisioning policy

UC-01b (login SSO O365 — GV)
   └── lookup GV theo `o365_oid` (Entra) → fallback `email` → fallback `employeeId` claim
         ├── tìm thấy   → set session, vào LMS với role TEACHER
         └── không thấy → REJECT (KHÔNG JIT cho GV — phải có sẵn từ UC-03)

UC-03 (cron full-sync)
   ├── opensync.nienhoc                    (gốc)
   ├── opensync.khoilop                    (theo trường)
   ├── opensync.lophoc      (cần ma_nien)
   ├── opensync.giaovien   ← cung cấp Email + SoDinhDanhCaNhan để bridge với UC-01b
   ├── opensync.hocsinh     (cần ma_nien)  (chỉ HS đã xếp lớp)
   └── UC-05 — opensync.phanconggiangday   (mỗi GV cần SoDinhDanhCaNhan)
```

---

## 2. Kiến trúc thành phần (đề xuất)

| Repo | Trách nhiệm liên quan TTC |
|------|---------------------------|
| `lms-sso` | **Federation broker đa-IdP**: (a) là OAuth client của **TTC** (PH/HS); (b) là OAuth/OIDC client của **Microsoft Entra ID** (GV); (c) nhận callback từ cả hai, đổi code → token, verify JWT, set cookie/session, gọi `lms-api` để lookup/tạo user; (d) host 2 endpoint logout (TTC `endsession` + Microsoft `logout`). |
| `lms-api` | Chứa: (a) bảng user và ánh xạ `ttc_sub` (PH/HS), `o365_oid`+`o365_tid` (GV), `so_dinh_danh_ca_nhan` (chung); (b) **OpenSync client** (token cache + 6 API call); (c) job scheduler full-sync; (d) entity Học sinh/Giáo viên/Lớp/Niên học/Phân công với cờ `source = TTC_OPENSYNC`. Chi tiết map field OpenSync → entity LMS và các bước triển khai: **`huong-dan-mapping-opensync-lms-api.md`**. |
| `lms-fe` (PH/HS) | Có nút "Đăng nhập bằng TTC" → redirect tới `lms-sso /ttc-sso`. |
| `lms-school` (GV/Admin) | Có nút "Đăng nhập bằng Office 365" → redirect tới `lms-sso /o365-sso`. **Thêm** trang admin để: trigger sync thủ công, xem báo cáo sync, map ánh xạ thủ công khi conflict (đặc biệt quan trọng cho bridge GV ↔ OpenSync khi email O365 không khớp). |

> `lms-sso` đóng vai trò **federation broker** ngay từ ngày đầu — chuẩn bị cho việc thêm IdP thứ 3 (vd VNeID, Google Workspace) sau này. Routing theo provider: `/ttc-sso/*` (TTC), `/o365-sso/*` (Microsoft Entra). Schema user lưu cả `ttc_sub` lẫn `o365_oid` — một GV về lý thuyết có thể có cả hai (lịch sử cũ qua TTC, mới qua O365) nhưng *production policy chỉ cho login O365*.

---

## 3. Luồng UC-01a — Login SSO TTC (PH/HS)

> Áp dụng cho **Phụ huynh** (`user_type=4`) và **Học sinh** (`user_type=6`). Giáo viên dùng UC-01b (O365) — KHÔNG dùng luồng này.

### 3.1 Sequence (mức triển khai)

```
User (PH/HS) → lms-fe → lms-sso → TTC /oauth/authorize
                                            ↓ (đăng nhập + cấp quyền)
User trình duyệt          ← redirect      ← TTC redirect_uri ?code=… &state=…
lms-sso (callback handler):
  1. verify state khớp request đã lưu (CSRF)
  2. POST TTC /api/oauth/token
       grant_type=authorization_code, code, client_id, client_secret, redirect_uri
  3. nhận access_token (JWT) → decode + verify (exp, iss)
  4. extract sub, user_type, name, identity (nếu có)
  5. gọi lms-api: POST /internal/sso/resolve { sub, user_type, identity, profile }
        ↓
        a. SELECT user WHERE ttc_sub = :sub → nếu có, return user_id + role
        b. nếu không, fallback SELECT user WHERE so_dinh_danh_ca_nhan = :identity
           (chỉ khi có scope identity) → nếu match → UPDATE ttc_sub, return
        c. nếu vẫn không → tuỳ provisioning policy:
              JIT-CREATE  → tạo user (role theo user_type), source=TTC_SSO,
                            đánh cờ `needs_opensync_link=true`
              REJECT      → trả 404, lms-sso show "Tài khoản chưa được cấp quyền vào LMS"
  6. lms-sso set cookie session → 302 về URL gốc
```

### 3.2 Mapping JWT → user LMS

| JWT claim | Field LMS | Lưu ý |
|-----------|-----------|-------|
| `sub` | `user.ttc_sub` (UNIQUE) | Khóa lookup chính — bền vững |
| `user_type` | `user.role` | `1`→`TEACHER`, `4`→`PARENT`, `6`→`STUDENT` (xem §4) |
| `name` / `given_name` / `family_name` | `user.full_name`, `first_name`, `last_name` | Cập nhật mỗi lần login (overwrite) |
| `picture` | `user.avatar_url` | Path tương đối — cần prefix CDN của TTC |
| `email` | `user.email` | Chỉ có khi scope `email` được cấp |
| `identity` | `user.so_dinh_danh_ca_nhan` | **Bridge sang OpenSync** — chỉ có khi scope `identity` |
| `phone` | `user.phone` | Scope `phone` |
| `address` | `user.address` | Scope `address` |
| `jti` | log audit `last_login_jti` | Chống replay — reject nếu trùng |
| `exp` | session expiry hint | Session LMS không nên dài hơn `exp` |

> ℹ️ TTC không trả `refresh_token` trong response chuẩn của hướng dẫn. Khi `access_token` hết hạn → user đăng nhập lại; nếu cần long-lived session thì LMS quản session độc lập, KHÔNG dùng JWT TTC làm session token.

### 3.3 Provisioning policy (chốt với BA)

| Policy | Mô tả | Ưu | Nhược |
|--------|------|----|-------|
| **JIT** (Just-in-Time) | Login lần đầu → LMS tự tạo user theo `user_type` + claim profile | UX mượt, không chặn user | LMS có thể có user "rỗng" data lớp/môn cho HS chưa được full-sync |
| **Pre-provision strict** | LMS chỉ cho login nếu `ttc_sub` hoặc `so_dinh_danh_ca_nhan` đã tồn tại trong DB (do full-sync đẩy lên trước) | Quản trị tập trung; tránh ghost user | Cron lỗi → user bị từ chối; PH (TTC không sync qua OpenSync) sẽ luôn fail → buộc phải JIT cho PH |
| **Hybrid (đề xuất)** | HS: pre-provision (ưu tiên record từ OpenSync); PH: JIT (vì OpenSync không trả PH); cả hai cập nhật profile mỗi login | Cân bằng | Phức tạp hơn — cần policy theo `user_type` |

> **Đề xuất:** Hybrid (cho UC-01a). Code policy theo `user_type` để dễ review. **Lưu ý:** GV không nằm trong UC-01a — xem UC-01b (O365 SSO) bên dưới với policy strict pre-provision.

### 3.4 UC-02a — Logout TTC

```
User click Logout (LMS) → lms-sso /logout:
  1. lấy access_token đã cache trong session
  2. clear session/cookie LMS local
  3. 302 → TTC /oauth/endsession
            ?id_token_hint=<access_token>
            &post_logout_redirect_uri=https://lms-sso/logout-callback
            &state=<random>
  TTC revoke session bên TTC, redirect về:
  /logout-callback?state=<random>
  → lms-sso verify state, redirect user về trang công khai (vd /login)
```

> ⚠️ DOC TTC dùng `id_token_hint=<ACCESS_TOKEN>`. Đây là biến thể (chuẩn OIDC dùng `id_token`). Tôn trọng tài liệu TTC: gửi access_token vào tham số này.

---

## 3b. Luồng UC-01b — Login SSO Office 365 (Giáo viên)

> **Bối cảnh:** TTC tách riêng phần đăng nhập GV bằng O365 — KHÔNG đi qua TTC OAuth/OIDC. LMS phải nối **trực tiếp** với Microsoft Entra ID (Azure AD) tenant của TTC. Đây là OAuth client thứ hai trong `lms-sso`, độc lập hoàn toàn với UC-01a.

### 3b.1 Sequence (mức triển khai)

```
GV → lms-school → lms-sso → Microsoft Entra /oauth2/v2.0/authorize
                                            ↓ (đăng nhập O365 + MFA nếu có)
GV trình duyệt          ← redirect      ← Entra redirect_uri ?code=… &state=…
lms-sso (callback handler):
  1. verify state khớp request đã lưu (CSRF)
  2. POST Entra /oauth2/v2.0/token
       grant_type=authorization_code, code, client_id, client_secret, redirect_uri, scope
  3. nhận id_token (JWT) + access_token + (refresh_token nếu có offline_access)
  4. verify id_token bằng JWKS của Entra (signature + iss + aud + exp + tid)
  5. extract oid, tid, email, upn, preferred_username, name, (optional) employeeId
  6. gọi lms-api: POST /internal/sso/o365/resolve
       { oid, tid, email, upn, employeeId?, profile }
        ↓
        a. SELECT user WHERE o365_oid = :oid AND o365_tid = :tid → nếu có, return user_id (role=TEACHER)
        b. nếu không, fallback SELECT GiaoVien WHERE so_dinh_danh = :employeeId
           (chỉ khi có optional claim) → nếu match → UPDATE o365_oid/o365_tid, return
        c. nếu không, fallback SELECT GiaoVien WHERE LOWER(email) = LOWER(:email)
           → nếu match (và GV có source=TTC_OPENSYNC) → UPDATE o365_oid/o365_tid, return
        d. nếu vẫn không → REJECT 403 "Tài khoản chưa được cấp quyền vào LMS — liên hệ admin"
           (KHÔNG JIT — GV phải có sẵn từ OpenSync sync)
  7. lms-sso set cookie session → 302 về URL gốc của lms-school
```

### 3b.2 Mapping JWT Entra → user LMS

| Claim Entra | Field LMS | Lưu ý |
|-------------|-----------|-------|
| `oid` | `user.o365_oid` (UNIQUE per `o365_tid`) | **Khoá lookup chính** — ổn định trong tenant; không thay đổi khi đổi tên/email |
| `tid` | `user.o365_tid` | Lock theo tenant TTC — verify khớp `O365_TENANT_ID` env |
| `sub` | (không lưu) | Per-app pairwise — không bền vững khi đổi App Registration |
| `upn` | `user.upn` (optional) | User Principal Name — thường là `gv001@truongttc.edu.vn` |
| `email` | `user.email` | **Bridge bổ sung** với `thongtingiaovien.Email` của OpenSync |
| `preferred_username` | (fallback nếu thiếu `email`) | Thường là email |
| `name` / `given_name` / `family_name` | `user.full_name`, `first_name`, `last_name` | Cập nhật mỗi login (overwrite) |
| `employeeId` (optional claim) | `user.so_dinh_danh_ca_nhan` | **Bridge tốt nhất** với OpenSync — chỉ có khi TTC config Entra Token configuration → Optional claims |
| `extension_*` | `user.so_dinh_danh_ca_nhan` (nếu CCCD đẩy vào extensionAttribute) | Thay thế cho `employeeId` claim |
| `iat` / `exp` | session expiry hint | Session LMS không nên dài hơn `exp` |
| `aud` | verify | Phải khớp `O365_CLIENT_ID` |
| `iss` | verify | Phải là `https://login.microsoftonline.com/{tid}/v2.0` |

> ℹ️ Không như TTC, Entra **có** trả `refresh_token` nếu scope `offline_access` được cấp. LMS có thể giữ session lâu hơn 1h mà không cần redirect. Tuy nhiên session LMS độc lập (JWT nội bộ) vẫn được đề xuất cho an toàn.

### 3b.3 Provisioning policy — **STRICT, không JIT**

| Lý do | Hệ quả |
|-------|--------|
| GV là vai trò có quyền (chấm điểm, duyệt nghỉ phép, sửa thời khoá biểu) | Không được phép tự tạo qua login |
| GV là source-of-truth từ OpenSync `thongtingiaovien` | Phải pre-provision qua UC-03 trước |
| Nếu cho JIT → ai có email O365 thuộc tenant TTC đều thành GV trong LMS | Nguy cơ ghost teacher cực cao |

→ Login O365 callback → **REJECT** nếu không tìm thấy GV đã sync. Hiển thị message UX rõ:

> "Tài khoản của bạn chưa được đồng bộ vào LMS. Vui lòng liên hệ admin trường để được kiểm tra."

Trigger thêm: log alert ops + tạo record trong `pending_o365_users` để admin xem được ai đã thử login.

### 3b.4 UC-02b — Logout O365

```
GV click Logout (LMS) → lms-sso /o365-sso/logout:
  1. clear session/cookie LMS local
  2. 302 → https://login.microsoftonline.com/{tid}/oauth2/v2.0/logout
            ?post_logout_redirect_uri=https://lms-sso.dtp.vn/o365-sso/logout-callback
            &id_token_hint=<id_token>     # khuyến nghị có để Entra biết user nào
            &state=<random>
  Entra revoke session bên O365, redirect về:
  /o365-sso/logout-callback?state=<random>
  → lms-sso verify state, redirect user về /sign-in
```

> ⚠️ Nếu chỉ clear session LMS mà KHÔNG redirect Entra logout → GV vẫn còn session O365 trên browser → click "Đăng nhập" lại sẽ vào ngay không cần nhập mật khẩu. Tuỳ yêu cầu UX, có thể chấp nhận (single-sign-out partial) hoặc force full logout.

### 3b.5 Bridge GV (O365) ↔ OpenSync (`thongtingiaovien`)

Vấn đề lõi: token Entra **không có** `SoDinhDanhCaNhan`. Cần bridge giữa `oid` (Entra) ↔ `SoDinhDanhCaNhan` (OpenSync) để liên kết với phân công giảng dạy, lớp chủ nhiệm, etc.

Ba phương án xếp theo độ ưu tiên:

| # | Cách | Yêu cầu cấu hình | Đánh giá |
|---|------|------------------|---------|
| **B** | TTC bổ sung **optional claim** `employeeId` (hoặc đẩy CCCD vào `extensionAttribute_X`) trong token Entra | TTC config App Registration → Token configuration; đồng thời HR đẩy CCCD vào Entra user attribute | **Sạch nhất** — bridge ổn định, không phụ thuộc data email |
| **A** | Match bằng `email` (claim Entra ↔ `Email` OpenSync), case-insensitive | GV trên O365 phải có email khớp tuyệt đối với HR | **Khả thi nhất** — nhưng phải đảm bảo data sạch |
| **C** | Bảng map thủ công admin LMS (`o365_oid` ↔ `so_dinh_danh_ca_nhan`) | UI admin trong `lms-school` + workflow first-time login (admin xác nhận pending request) | UX kém, dùng làm **fallback an toàn** khi A/B chưa sẵn sàng |

**Đề xuất triển khai:**
1. Build Phương án A ngay (chi phí thấp, hoạt động được nếu data O365/HR đồng bộ).
2. Build Phương án C (admin map UI) song song — bắt buộc, không bỏ.
3. Đàm phán Phương án B với TTC — nếu có thì A trở thành dự phòng, C chỉ dùng cho edge case hiếm.

```python
# Pseudo-code resolver
def resolve_o365(oid, tid, email, employee_id):
    assert tid == config.O365_TENANT_ID  # lock tenant

    user = users.find(o365_oid=oid, o365_tid=tid)
    if user: return user

    if employee_id:  # Phương án B
        gv = giao_vien.find(so_dinh_danh=employee_id)
        if gv:
            user = users.upsert_from_gv(gv, o365_oid=oid, o365_tid=tid)
            return user

    if email:  # Phương án A
        gv = giao_vien.find(email__iexact=email, source='TTC_OPENSYNC')
        if gv:
            user = users.upsert_from_gv(gv, o365_oid=oid, o365_tid=tid)
            return user

    # Phương án C — không match, ghi pending để admin map sau
    pending_o365_users.upsert(oid=oid, tid=tid, email=email, attempted_at=now())
    raise UserNotProvisionedException(
        "Tài khoản chưa được đồng bộ vào LMS — liên hệ admin"
    )
```

### 3b.6 Schema user (cập nhật)

```
users
  id
  ttc_sub                  (UNIQUE, NULL)   ← từ UC-01a (PH/HS)
  o365_oid                 (UNIQUE, NULL)   ← từ UC-01b (GV)  ★ mới
  o365_tid                 (NULL)           ← lock theo tenant Entra  ★ mới
  email                    (UNIQUE)
  so_dinh_danh_ca_nhan     (UNIQUE per ma_truong)
  source                   ('TTC_SSO' | 'O365_SSO' | 'TTC_OPENSYNC')
  role                     ('TEACHER' | 'PARENT' | 'STUDENT' | …)
  upn                      (NULL)            ← UPN O365 (vd gv001@truongttc.edu.vn)
  ...

pending_o365_users          ← danh sách GV thử login O365 nhưng chưa map  ★ mới
  id
  o365_oid                 (UNIQUE)
  o365_tid
  email
  upn
  attempted_at
  attempt_count
  resolved_user_id         (NULL — set khi admin map xong)
  resolved_at
```

### 3b.7 Cấu hình bắt buộc (env / Vault)

| Key | Nguồn | Ghi chú |
|-----|-------|---------|
| `O365_TENANT_ID` | TTC IT cấp | GUID tenant Microsoft Entra của TTC |
| `O365_CLIENT_ID` | TTC IT cấp | Application ID của App Registration |
| `O365_CLIENT_SECRET` | TTC IT cấp | Vault — có expiry, lên lịch rotate |
| `O365_REDIRECT_URI` | LMS đăng ký với TTC | Vd `https://lms-sso.dtp.vn/o365-sso/callback` |
| `O365_SCOPES` | LMS cấu hình | Tối thiểu `openid profile email`; nếu cần dài session: `+ offline_access`; nếu cần Graph: `+ User.Read` |
| `O365_AUTHORITY` | Derive | `https://login.microsoftonline.com/{O365_TENANT_ID}/v2.0` |
| `O365_DISCOVERY_URL` | Derive | `{O365_AUTHORITY}/.well-known/openid-configuration` — gọi 1 lần lúc start, cache 24h |
| `O365_ALLOWED_TID` | Derive từ `O365_TENANT_ID` | Verify `tid` claim phải khớp |

> Bảng câu hỏi đầy đủ cần hỏi TTC IT: xem §9 (đã cập nhật).

---

## 4. Luồng UC-03/04 — Đồng bộ data qua OpenSync

### 4.1 Thứ tự gọi API trong cron full-sync

```
[1] POST /api/opensync/token         → cache TTC_OS_TOKEN (TTL ~8h)
[2] GET  /api/opensync/thongtinnienhoc       → upsert NienHoc[]
       chọn ma_nien hiện tại (theo cấu hình LMS hoặc mặc định bản mới nhất)
[3] GET  /api/opensync/thongtinkhoilop?ma_truong=…      → upsert KhoiLop[]
[4] GET  /api/opensync/thongtinlophoc?ma_truong=…&ma_nien=… (loop ma_khoi nếu cần)
                                                          → upsert LopHoc[]
[5] GET  /api/opensync/thongtingiaovien?ma_truong=…       → upsert GiaoVien[]
[6] GET  /api/opensync/thongtinhocsinh?ma_truong=…&ma_nien=… (paged)
                                                          → upsert HocSinh[]
                                                          → upsert quan-hệ (HS, LopHoc, NienHoc)
[7] với mỗi GV ở [5]:
    GET /api/opensync/phanconggiangday?ma_truong=…&ma_nien=…&SoDinhDanhCaNhan=…
                                                          → upsert PhanCong[]
                                                          → set cờ HEAD nếu có ChuNhiem
```

### 4.2 Khoá tự nhiên & idempotency

| Entity LMS | Khoá tự nhiên (unique từ TTC) | Note |
|------------|-------------------------------|------|
| HocSinh | `(MaTruong, SoDinhDanhCaNhan)` | Cùng người ở 2 trường = 2 record (mô hình multi-tenant theo trường) |
| GiaoVien | `(MaTruong, SoDinhDanhCaNhan)` | |
| KhoiLop | `(MaTruong, MaKhoiLop)` | Lưu ý field name — xem §4.3 |
| LopHoc | `(MaTruong, MaNien, MaLopHoc)` | |
| NienHoc | `MaNienHoc` | Global theo TTC |
| PhanCong | `(MaTruong, MaNien, SoDinhDanhCaNhan, HocKy, MaMonHoc, MaLopHoc)` | Composite — tránh duplicate |
| User (kết quả) | `ttc_sub` (SSO) ∪ `(MaTruong, SoDinhDanhCaNhan)` (OpenSync) | Một user có thể có cả hai sau lần login đầu |

Thuật toán upsert mỗi entity:
```
SELECT … WHERE natural_key = :key
  ↓ có       → UPDATE field; set updated_at = now(); set source = TTC_OPENSYNC
  ↓ không có → INSERT; set created_at, source = TTC_OPENSYNC
```

### 4.3 Mâu thuẫn field & contract bug đã thấy trong DOC

1. **`MaKhoi` vs `MaKhoiLop`:**
   - `thongtinhocsinh` trả `MaKhoi: "KL01"`.
   - `thongtinkhoilop` trả `MaKhoiLop: "K1"`.
   - **Hai giá trị khác format** → khả năng cao là **2 codespace khác nhau** (mã nội bộ vs mã hiển thị) HOẶC là bug doc.
   - **Hành động:** xác nhận với TTC. Trước khi rõ → khi map HS vào KhoiLop, KHÔNG join trực tiếp `HS.MaKhoi == KhoiLop.MaKhoiLop`. Lưu nguyên cả hai field, đặt cờ `khoi_resolved = false` cho đến khi xác nhận quy ước.

2. **API code phân công:** Bảng tổng ghi `opensync.phanconggiangday`; mục chi tiết ghi `opensync.phancong`. Khi cấp credential → đối chiếu lại với TTC để tránh 403 lúc chạy thật.

3. **Endpoint phân công:** DOC ghi `/api/opensync/phanconggianday` (thiếu chữ "g") trong một curl, nhưng đường dẫn chính là `phanconggiangday`. Code dùng đúng spelling đầy đủ; báo TTC sửa doc nếu typo gây ambiguity.

4. **API 5 lặp:** DOC có hai mục đều đánh số "API 5" (Niên học và Phân công giảng dạy). Đây là Phân công nên là **API 6**. Không ảnh hưởng tích hợp, nhưng note để giao tiếp với TTC tránh nhầm.

5. **Học sinh chưa xếp lớp:** API `thongtinhocsinh` chỉ trả HS **đã xếp lớp**. Hệ quả: nếu LMS cần quản HS chưa xếp (vd lớp 1 đầu năm) → phải có cơ chế khác hoặc chấp nhận thiếu.

### 4.4 Quản lý token OpenSync

```
class OpenSyncTokenCache:
  fetch():
    if cache.token and now < cache.expires_at - 5min:
      return cache.token
    POST /api/opensync/token (grant_type=client_credentials, Basic Auth)
    cache = (resp.access_token, parse(resp.expires_at))
    return cache.token

  on 401 from any GET:
    cache.invalidate()
    fetch()  # 1 lần — không retry vô hạn để tránh storm khi credential hỏng
    re-call API
```

### 4.5 Phân trang — full-sync học sinh

```
page = 1
total_pages = ∞
while page <= total_pages:
  resp = GET /thongtinhocsinh?…&page={page}&page_size=1000
  if not resp.success:
    log + alert; break  # ma_truong/ma_nien sai → đừng spam
  upsert resp.data.items
  total_pages = resp.data.total_pages
  page += 1
```

`page_size`: chọn 500–1000 (DOC mặc định 1000, max 5000). Quá lớn → timeout/JSON parse chậm; quá nhỏ → nhiều round-trip.

### 4.6 Xử lý xoá / soft-delete

OpenSync **không** có endpoint diff/changed-since → mỗi sync là **snapshot**. Để xử lý HS rời trường / chuyển lớp:

- Thêm cột `last_seen_sync_id` cho HS/GV/LopHoc.
- Trước sync: tăng `current_sync_id += 1`.
- Trong sync: mỗi upsert set `last_seen_sync_id = current_sync_id`.
- Sau sync (cùng `MaTruong`, `MaNien`):  
  `WHERE last_seen_sync_id < current_sync_id AND source = 'TTC_OPENSYNC'` → đánh `status = 'INACTIVE_BY_SYNC'` (KHÔNG hard-delete; giữ tham chiếu lịch sử cho điểm danh, đơn nghỉ phép, audit).

> Quy ước này tương đồng với cách `xin-nghỉ-phép/SKILL.md` xử lý attendance khi tiết bị huỷ — nhưng ở đây cần **soft delete** (không hard) để giữ liên kết FK.

---

## 5. Bridge SSO ↔ OpenSync (điểm khó nhất)

Mục tiêu: khi user TTC/O365 login, LMS biết ngay user đó là **HS lớp nào / GV trường nào** mà không phải gọi TTC API thêm.

### 5.1 Bridge UC-01a (TTC SSO — PH/HS) ↔ OpenSync

| # | Cách bridge | Yêu cầu cấu hình | Đánh giá |
|---|-------------|------------------|---------|
| A | Cấp scope `identity` cho client SSO → JWT có `identity` = `SoDinhDanhCaNhan` → match thẳng record OpenSync đã sync | Yêu cầu TTC bật scope `identity` cho client | **Đề xuất** — đơn giản, không cần API thứ 7 |
| B | Hỏi TTC định nghĩa `sub` (có thể là PK user TTC) → dùng `sub` làm key đồng bộ luôn (OpenSync trả thêm `sub` cùng `SoDinhDanhCaNhan`) | TTC mở rộng schema OpenSync | Sạch nhất nhưng phụ thuộc TTC |
| C | Map thủ công khi user login lần đầu — UI hỏi "bạn là HS lớp nào?" → admin xác nhận | Không phụ thuộc TTC | UX kém, nhiều thao tác admin |

**Phương án A** là tối ưu thực tế:

```
TTC SSO callback (PH/HS):
  jwt = decode(access_token)
  user_lookup_keys = [
    ('ttc_sub', jwt.sub),
    ('so_dinh_danh_ca_nhan', jwt.identity)   # khi scope identity được cấp
  ]
  user = users.find_by_any(user_lookup_keys)
  if user is None and policy in (JIT, HYBRID where applicable):
    user = users.create_jit(jwt)
  users.set(user.id, ttc_sub = jwt.sub)   # đảm bảo có sau lần đầu
```

### 5.2 Bridge UC-01b (O365 SSO — GV) ↔ OpenSync

Token Entra **không có** `SoDinhDanhCaNhan`. Phương án bridge xem **§3b.5** — tóm tắt:

| Ưu tiên | Cách | Phụ thuộc |
|---------|------|-----------|
| 1 (best) | Optional claim `employeeId` từ Entra | TTC config Entra App Registration |
| 2 (đề xuất build trước) | Match bằng `email` (Entra ↔ `thongtingiaovien.Email`) | Data O365/HR sạch & đồng bộ |
| 3 (fallback) | Bảng map thủ công admin (`pending_o365_users`) | UI admin trong `lms-school` |

**Khác biệt căn bản với 5.1:** UC-01b **không có JIT**. Không match được = REJECT login + đẩy vào `pending_o365_users` để admin xử lý.

---

## 6. Map nguồn xác thực → vai trò LMS

| Nguồn xác thực | Định danh | OpenSync nguồn | LMS role | Provisioning |
|----------------|-----------|----------------|----------|--------------|
| **O365 SSO** (UC-01b) | `o365_oid` + `o365_tid` | `thongtingiaovien` (`MaLoaiNhanSu` = `GV`) | `TEACHER` (HEAD nếu chủ nhiệm — xem `phanconggiangday.ChuNhiem`) | **Strict pre-provision** — REJECT nếu chưa có |
| **O365 SSO** (UC-01b) | `o365_oid` + `o365_tid` | `thongtingiaovien` (`MaLoaiNhanSu` ≠ `GV`, vd `CB`, `KT`) | `STAFF` / `ADMIN` (theo policy nội bộ) | Strict — REJECT nếu chưa có |
| **TTC SSO** (UC-01a) `user_type=4` | `ttc_sub` | (không có endpoint PH) | `PARENT` | **JIT** từ SSO |
| **TTC SSO** (UC-01a) `user_type=6` | `ttc_sub` + `identity` | `thongtinhocsinh` | `STUDENT` | Pre-provision (ưu tiên), JIT fallback |
| **TTC SSO** (UC-01a) `user_type=1` | — | — | **REJECT** — phải dùng O365 | n/a (GV không qua TTC SSO) |

> ⚠️ Nếu LMS nhận được `user_type=1` từ TTC SSO → REJECT với message "Giáo viên vui lòng đăng nhập qua Office 365". Đây là biện pháp phòng vệ data integrity — tránh trường hợp một GV vô tình tạo 2 record (qua cả TTC SSO lẫn O365 SSO).

**Edge case PH:** Phụ huynh chỉ tồn tại ở SSO. LMS muốn liên kết PH ↔ con (HS) thì cần:
- Hoặc TTC bổ sung endpoint trả relation (PH → HS) — đề xuất với TTC.
- Hoặc PH tự khai báo CCCD con (`SoDinhDanhCaNhan`) trong LMS, LMS verify bằng cách so với HS đã sync.

**Edge case GV chưa có O365:** GV mới hoặc GV thỉnh giảng có thể chưa được cấp account O365. Lựa chọn:
- (a) Bắt IT TTC cấp O365 trước khi GV vào LMS — quy trình chuẩn.
- (b) Cho phép admin LMS tạo "manual teacher account" với password local — chỉ dùng cho hợp đồng ngắn hạn; phải có audit + auto-disable sau N ngày.

---

## 7. Sequence diagram — luồng đầy đủ "lần đầu HS login + LMS đã có record nhờ cron"

```
          Browser    lms-fe     lms-sso          TTC (SSO)         lms-api          TTC (OpenSync)
            │          │           │                  │                │                  │
[CRON]      │          │           │                  │  ──► token (CC)─►                 │
trước đó    │          │           │                  │  ◄── access_token ──              │
            │          │           │                  │  ──► thongtinhocsinh ─►            │
            │          │           │                  │  ◄── HS items ──                   │
            │          │           │                  │     upsert HocSinh, set ttc_sub=NULL│
            │          │           │                  │
[USER]      ├─Login──► │           │                  │                │                  │
            │          ├─/login───►│                  │                │                  │
            │          │           ├─302 /oauth/authorize?…─►          │                  │
            ◄────────────────────  │  TTC login UI   ◄───              │                  │
            ├─submit──►│           │                  │                │                  │
            ◄────────────────────  302 callback?code=…&state=…         │                  │
            │          │           │  POST /api/oauth/token ─►         │                  │
            │          │           │  ◄── JWT (sub, user_type=6, identity, name) ──       │
            │          │           │  verify state, exp, iss          │                  │
            │          │           │  ──resolve(jwt)──►                │                  │
            │          │           │                                  │ SELECT user WHERE ttc_sub=jwt.sub
            │          │           │                                  │ → not found
            │          │           │                                  │ SELECT user WHERE so_dinh_danh=jwt.identity
            │          │           │                                  │ → MATCH (HS đã sync) → set ttc_sub
            │          │           │  ◄── user_id, role=STUDENT ──    │                  │
            │          │           │  set cookie session              │                  │
            │          │  ◄────────302 /home (đã login) ─             │                  │
            ◄──────────────────────                                                       │
```

---

## 8. Bảng rủi ro & biện pháp

| Rủi ro | Khả năng | Tác động | Biện pháp |
|--------|:--------:|:--------:|----------|
| TTC không cấp scope `identity` → không bridge được SSO ↔ OpenSync | Trung bình | Cao | Đàm phán scope; fallback Phương án C (manual map) trong giai đoạn tạm thời |
| `MaKhoi` ≠ `MaKhoiLop` (xem §4.3) gây join lệch | Trung bình | Trung bình | Lưu nguyên cả hai, không hard-join trước khi xác nhận quy ước |
| OpenSync 403 do thiếu API Code | Cao khi onboard | Trung bình | Trước khi build, lấy danh sách API Code đã cấp; healthcheck mỗi API trước khi vào prod |
| Token TTC SSO chỉ sống 1h, không có refresh_token | Cao | Thấp | Session LMS quản lý độc lập; redirect lại SSO khi cần làm mới claim |
| Cron full-sync chạy quá thời gian (HS rất đông) | Trung bình | Trung bình | Dùng `page_size=1000`, chạy song song theo `MaTruong`; metric thời gian sync |
| Snapshot không có "delta" → không biết HS rời trường | Cao | Trung bình | Chiến lược `last_seen_sync_id` (§4.6); soft delete |
| User đăng nhập SSO nhưng OpenSync chưa kịp sync → JIT thiếu data lớp | Trung bình | Trung bình | Sau JIT, trigger incremental sync **ngay lập tức** cho `SoDinhDanhCaNhan` đó |
| Secret bị lộ | Thấp | Cao | Vault + rotate; secret cũ còn 24h theo TTC để rollover |
| Replay JWT (network tap) | Thấp | Cao | Verify `jti` chưa thấy trong window; HTTPS bắt buộc |
| `user_type` xuất hiện giá trị mới (vd `2`, `3`, `5`) | Thấp | Trung bình | Reject login + alert ops; không guess role |
| Phụ huynh login nhưng không liên kết HS → app PH "trống" | Cao (giai đoạn đầu) | Cao | UI yêu cầu PH nhập CCCD con; verify với HS đã sync |
| OpenSync trả `200 success:false` bị treat như success | Trung bình | Cao | Library client phải kiểm tra `success` trước khi đọc `data` |
| Endpoint phân công có typo (`phanconggianday` vs `phanconggiangday`) | Thấp | Cao (404) | Hard-code đúng path đầy đủ + healthcheck CI |
| **GV email O365 không khớp `thongtingiaovien.Email` → bridge fail (UC-01b)** | **Cao (giai đoạn đầu)** | **Cao** | Build admin map UI (`pending_o365_users`) song song; data audit trước go-live |
| **`O365_CLIENT_SECRET` hết hạn (Entra mặc định 24 tháng)** | **Trung bình** | **Cao** | Lên lịch rotate trước 30 ngày; alert monitor; cân nhắc dùng Certificate thay Secret |
| **`tid` trong token Entra ≠ `O365_TENANT_ID`** | **Thấp** | **Cao** | Verify cứng `tid` trong callback — reject nếu lệch (chống cross-tenant attack) |
| **GV bị Entra Conditional Access block** (vd login từ IP lạ) | **Trung bình** | **Trung bình** | Hiển thị message Entra rõ ràng; không che lỗi để IT TTC trace được |
| **App Registration trên Entra bị admin TTC vô hiệu** | **Thấp** | **Cao** | Health check periodic gọi authorize endpoint với client_id; alert nếu trả `AADSTS70001` (app not found) |
| **GV thử login O365 trước khi UC-03 sync xong → REJECT lần đầu** | **Cao (ngày triển khai)** | **Trung bình** | Trigger UC-04 incremental sync ngay khi có `pending_o365_users` mới; UI gợi ý "thử lại sau 5 phút" |
| **GV có cả `ttc_sub` và `o365_oid` (lịch sử cũ + mới) → 2 record** | **Trung bình** | **Trung bình** | Reject `user_type=1` trên UC-01a (xem §6); script migration một lần để merge GV cũ |

---

## 9. Đề xuất câu hỏi gửi TTC trước khi build

### 9.1 TTC SSO (UC-01a — PH/HS) + OpenSync

1. Cấp scope `identity` cho client SSO của LMS được không? Claim `identity` có **chính xác** trùng `SoDinhDanhCaNhan` của OpenSync không?
2. Ý nghĩa `sub` của OIDC — có phải PK user trên TTC, ổn định mãi mãi, kể cả khi user chuyển trường?
3. Quy ước giữa `MaKhoi` (trong `thongtinhocsinh`) và `MaKhoiLop` (trong `thongtinkhoilop`) — cách join chính tắc?
4. API code chuẩn cho phân công giảng dạy là `opensync.phanconggiangday` hay `opensync.phancong`?
5. Có endpoint nào trả delta (changed-since) không? Hay chấp nhận snapshot diff phía client?
6. Có endpoint quan hệ Phụ huynh ↔ Học sinh không?
7. Issuer (`iss`) chính xác trong JWT TTC là gì để verify cứng?
8. TTC có gửi `refresh_token` trong response không, hay LMS bắt buộc redirect SSO mỗi lần expire?
9. Webhook hoặc cơ chế notify khi data TTC thay đổi (HS nghỉ học, GV nghỉ việc) — có không?
10. Rate limit của OpenSync và SSO endpoint là bao nhiêu? Có giới hạn concurrent token request?

### 9.2 Office 365 SSO (UC-01b — GV)

11. **Tenant Microsoft Entra ID của TTC** — Tenant ID (GUID) là gì? Là tenant chung cho tất cả trường thuộc TTC hay mỗi trường có tenant riêng?
12. **App Registration** — TTC tạo riêng cho LMS, hay LMS đăng ký multi-tenant app rồi TTC admin consent? Cấp `client_id` + `client_secret` (hoặc Certificate)?
13. **Redirect URI** chính thức cho từng môi trường (dev/staging/prod) sẽ đăng ký trên Entra?
14. **Allowed account types** — `AzureADMyOrg` (single tenant TTC) hay `AzureADMultipleOrgs`?
15. **Optional claim `employeeId`** — TTC có thể bật trong Token configuration của App Registration không? HR có đẩy CCCD/mã NV vào `employeeId` của Entra user không? Hoặc dùng `extensionAttribute_X` thay thế?
16. **Field `Email` trong OpenSync `thongtingiaovien`** — có chắc chắn trùng với UPN/email O365 của GV không (cùng domain `@truongttc.edu.vn`)? Có thể cung cấp 5–10 sample data để verify?
17. **Conditional Access / MFA** — bật cho app của LMS không? IP allowlist có không? Token lifetime mặc định?
18. **Scope `offline_access`** — có cấp không (để LMS giữ refresh_token, không phải redirect login mỗi 1h)?
19. **Admin consent** đã được bấm chưa? Nếu chưa, ai sẽ bấm và khi nào?
20. **GV mới chưa có O365** — quy trình cấp account O365 mất bao lâu? Có fallback nào (vd cho phép admin LMS tạo manual teacher account ngắn hạn)?
21. **GV nghỉ việc** — Entra account bị disable tức thì hay sau bao lâu? Có webhook không, hay LMS phải tự detect qua sync OpenSync `TrangThai`?
22. **Client Secret expiry** — mặc định Entra 24 tháng. TTC có policy rotate ngắn hơn không? Có thể dùng Certificate (5 năm) thay không?
23. **Policy block third-party app** trong tenant — nếu có, App Registration của LMS phải được whitelist như thế nào?

---

## 10. Manday ballpark (nếu cần)

| Hạng mục | Phạm vi | Khoảng (md) |
|----------|---------|-------------|
| **TTC-SSO-A** — `lms-sso` integration TTC (UC-01a) | Authorize redirect + callback + token exchange + JWT verify + state CSRF | 4–7 |
| **TTC-SSO-B** — Logout RP-Initiated TTC + session sync với LMS | Logout flow + cookie clean | 1–2 |
| **O365-SSO-A** — `lms-sso` integration Office 365 (UC-01b) | OIDC discovery + authorize + callback + JWKS verify + tid lock | 3–6 |
| **O365-SSO-B** — Logout RP-Initiated O365 | Logout endpoint Microsoft + redirect callback + session clear | 1–2 |
| **O365-BR** — Bridge GV (O365) ↔ OpenSync | Resolver theo `oid`/`employeeId`/`email`; bảng `pending_o365_users`; admin map UI | 3–5 |
| **SSO-BROKER** — refactor `lms-sso` thành multi-IdP | Routing theo provider (`/ttc-sso/*`, `/o365-sso/*`); IdP picker UI; schema user thêm cột `o365_oid`/`o365_tid`/`upn` | 2–4 |
| **TTC-OS-A** — OpenSync client core | Token cache + retry + 6 API client + paging | 4–7 |
| **TTC-OS-B** — Schema + upsert | Entity (HS/GV/Lop/Khoi/Nien/PhanCong) + migration + idempotent upsert + soft-delete strategy | 6–12 |
| **TTC-OS-C** — Cron orchestration | Job scheduler + thứ tự gọi + lock + retry + metric | 3–6 |
| **TTC-BR** — Bridge TTC SSO (PH/HS) ↔ OpenSync | Resolve user theo `sub`/`identity`, JIT, on-demand sync khi miss | 3–6 |
| **TTC-FE** — UI 2 nút SSO + trang admin (sync status + map pending O365) | `lms-fe` (nút TTC) + `lms-school` (nút O365 + admin tools) | 4–7 |
| **TTC-QA / INT** | E2E cả 2 SSO flow + sync stability + edge case (HS chuyển lớp, GV nghỉ việc, O365 secret rotate) | 5–10 |
| **Tổng** | Một dev full-stack tuần tự | **39–74 md** |

> Buffer +20–30% nếu TTC trả lời câu hỏi §9 chậm hoặc cần đàm phán scope/API code mới / config Entra optional claim.
> Khi vibe coding với Cursor (scaffold OAuth/OIDC client, OpenAPI client, repo upsert pattern): có thể giảm ~20–30%; phần **TTC-OS-C** + **TTC-QA** giảm ít nhất.
> Nếu TTC bật được optional claim `employeeId` ngay từ đầu → **O365-BR** giảm còn 1–2 md (không cần phương án A + admin map fallback).

---

## 11. Tham chiếu chéo trong repo

- `tich-hop-ttc/SKILL.md` — bảng endpoint, claim, error code, checklist nhanh (TTC + O365).
- `tich-hop-ttc/HuongDan_SSO_DoiTac.docx` — bản gốc DOC TTC SSO (UC-01a).
- `tich-hop-ttc/HuongDan_OpenSyncAPI_DoiTac.docx` — bản gốc DOC OpenSync.
- `tich-hop-ttc/tech/uc-01-implementation.md` — implementation chi tiết UC-01a (TTC SSO).
- `tich-hop-ttc/tech/sso-o365-implement.md` — implementation chi tiết UC-01b (O365 SSO cho GV) — **kế hoạch + sequence**.
- `tich-hop-ttc/tech/sso-o365-code.md` — **code snippet thực thi** UC-01b (Spring + Next.js + migration + test).
- `tich-hop-ttc/tech/uc-03-implement.md` — implementation chi tiết UC-03 (cron full-sync OpenSync).
- `tich-hop-ttc/tech/uc-04-implement.md` — implementation chi tiết UC-04 (incremental sync).
- Đối chiếu repo:
  - `~/dev/dtp/lms-sso` — entry SSO (Next.js) — federation broker đa-IdP.
  - `~/dev/dtp/lms-api` — backend Java/Spring; nơi đặt OpenSync client + scheduled job + entity sync + 2 user resolver (TTC + O365).
  - `~/dev/dtp/lms-fe` — UI nút "Đăng nhập với TTC" (PH/HS).
  - `~/dev/dtp/lms-school` — UI nút "Đăng nhập với Office 365" (GV) + trang admin sync + admin map `pending_o365_users`.

---

*Cập nhật khi: TTC phản hồi câu §9, chốt scope, hoặc thay đổi cấu trúc API; sau spike cron full-sync trên môi trường kiểm thử.*
