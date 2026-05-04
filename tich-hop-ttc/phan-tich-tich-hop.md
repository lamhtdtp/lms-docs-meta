# Phân tích — LMS đăng nhập SSO TTC + đồng bộ HS/GV qua OpenSync

**Nguồn:** `tich-hop-ttc/HuongDan_SSO_DoiTac.docx`, `tich-hop-ttc/HuongDan_OpenSyncAPI_DoiTac.docx`, đối chiếu `tich-hop-ttc/SKILL.md`.

**Ngữ cảnh:** TTC (ASC SCHOOL) là hệ thống thông tin trường (SIS) phía đối tác. LMS muốn:

1. Cho **người dùng TTC** (giáo viên / phụ huynh / học sinh) đăng nhập **một lần** vào LMS bằng tài khoản TTC (SSO).
2. Đồng bộ danh mục **học sinh / giáo viên / khối / lớp / niên học / phân công** từ TTC → LMS định kỳ để LMS có sẵn dữ liệu (không chờ user login mới có).

Đây là **hai luồng độc lập về kỹ thuật** nhưng **gắn chặt về dữ liệu** — bridge bằng định danh người dùng. Phân tích dưới đây chia hai luồng, sau đó gộp vào kiến trúc tổng.

---

## 1. Tóm tắt use case

| # | Use case | Actor | Tần suất | Trigger |
|---|----------|-------|----------|---------|
| UC-01 | Login SSO TTC vào LMS | GV / PH / HS | Mỗi lần login | Click "Đăng nhập với TTC" trên LMS |
| UC-02 | Logout RP-Initiated | GV / PH / HS | Mỗi lần logout | Click "Đăng xuất" trên LMS |
| UC-03 | Full-sync danh mục TTC → LMS | Job hệ thống | 1 lần/ngày (đêm) | Cron `0 2 * * *` |
| UC-04 | Incremental-sync 1 user khi cần | LMS app | On-demand | UI gọi sync, hoặc khi login SSO không tìm thấy record |
| UC-05 | Sync phân công giảng dạy | Job hệ thống | 1 lần/ngày + on-demand | Sau full-sync GV+lớp |

**Phụ thuộc giữa các UC:**

```
UC-01 (login SSO)
   └── lookup user theo `sub` / `SoDinhDanhCaNhan`
         ├── tìm thấy   → set session, vào LMS
         └── không thấy → JIT (UC-04) hoặc redirect màn báo lỗi
                          tuỳ provisioning policy

UC-03 (cron full-sync)
   ├── opensync.nienhoc                    (gốc)
   ├── opensync.khoilop                    (theo trường)
   ├── opensync.lophoc      (cần ma_nien)
   ├── opensync.giaovien
   ├── opensync.hocsinh     (cần ma_nien)  (chỉ HS đã xếp lớp)
   └── UC-05 — opensync.phanconggiangday   (mỗi GV cần SoDinhDanhCaNhan)
```

---

## 2. Kiến trúc thành phần (đề xuất)

| Repo | Trách nhiệm liên quan TTC |
|------|---------------------------|
| `lms-sso` | Là **OAuth client** đối với TTC. Nhận callback, đổi code → token, verify JWT, set cookie/session, gọi `lms-api` để lookup/tạo user. Cũng host endpoint `/logout` → forward `endsession` về TTC. |
| `lms-api` | Chứa: (a) bảng user và ánh xạ `ttc_sub`/`so_dinh_danh_ca_nhan`; (b) **OpenSync client** (token cache + 6 API call); (c) job scheduler full-sync; (d) entity Học sinh/Giáo viên/Lớp/Niên học/Phân công với cờ `source = TTC_OPENSYNC`. Chi tiết map field OpenSync → entity LMS và các bước triển khai: **`huong-dan-mapping-opensync-lms-api.md`**. |
| `lms-fe` (PH/HS) | Có nút "Đăng nhập bằng TTC" → redirect tới `lms-sso`. |
| `lms-school` (GV/Admin) | Tương tự `lms-fe`. **Thêm** trang admin để: trigger sync thủ công, xem báo cáo sync, map ánh xạ thủ công khi conflict. |

> Nếu LMS đã có `lms-sso` riêng cho domain DTP (kiểu hub IdP nội bộ), TTC là **upstream IdP** — `lms-sso` đóng vai trò *broker* (federation): TTC ↔ `lms-sso` ↔ các app FE. Nếu chưa, `lms-sso` chính là OAuth client trực tiếp.

---

## 3. Luồng UC-01 — Login SSO

### 3.1 Sequence (mức triển khai)

```
User → lms-fe / lms-school → lms-sso → TTC /oauth/authorize
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
| **Hybrid (đề xuất)** | HS/GV: pre-provision (ưu tiên record từ OpenSync); PH: JIT (vì OpenSync không trả PH); cả hai cập nhật profile mỗi login | Cân bằng | Phức tạp hơn — cần policy theo `user_type` |

> **Đề xuất:** Hybrid. Code policy theo `user_type` để dễ review.

### 3.4 UC-02 — Logout

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

Mục tiêu: khi user TTC login, LMS biết ngay user đó là **HS lớp nào / GV trường nào** mà không phải gọi TTC API thêm.

### Phương án

| # | Cách bridge | Yêu cầu cấu hình | Đánh giá |
|---|-------------|------------------|---------|
| A | Cấp scope `identity` cho client SSO → JWT có `identity` = `SoDinhDanhCaNhan` → match thẳng record OpenSync đã sync | Yêu cầu TTC bật scope `identity` cho client | **Đề xuất** — đơn giản, không cần API thứ 7 |
| B | Hỏi TTC định nghĩa `sub` (có thể là PK user TTC) → dùng `sub` làm key đồng bộ luôn (OpenSync trả thêm `sub` cùng `SoDinhDanhCaNhan`) | TTC mở rộng schema OpenSync | Sạch nhất nhưng phụ thuộc TTC |
| C | Map thủ công khi user login lần đầu — UI hỏi "bạn là HS lớp nào?" → admin xác nhận | Không phụ thuộc TTC | UX kém, nhiều thao tác admin |

**Phương án A** là tối ưu thực tế:

```
SSO callback:
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

---

## 6. Map `user_type` → vai trò LMS

| `user_type` (SSO) | `MaLoaiNhanSu` (OpenSync) | LMS role | Nguồn data của user |
|-------------------|---------------------------|----------|---------------------|
| `1` Giáo viên / cán bộ | `GV` (giáo viên) | `TEACHER` (HEAD nếu chủ nhiệm — xem `phanconggiangday.ChuNhiem`) | `thongtingiaovien` |
| `1` Giáo viên / cán bộ | khác `GV` (vd `CB`, `KT`) | `STAFF` / `ADMIN` (theo policy nội bộ) | `thongtingiaovien` |
| `4` Phụ huynh | (không có endpoint) | `PARENT` | Chỉ JIT từ SSO |
| `6` Học sinh | (không có cột riêng) | `STUDENT` | `thongtinhocsinh` |

**Edge case PH:** Phụ huynh chỉ tồn tại ở SSO. LMS muốn liên kết PH ↔ con (HS) thì cần:
- Hoặc TTC bổ sung endpoint trả relation (PH → HS) — đề xuất với TTC.
- Hoặc PH tự khai báo CCCD con (`SoDinhDanhCaNhan`) trong LMS, LMS verify bằng cách so với HS đã sync.

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

---

## 9. Đề xuất câu hỏi gửi TTC trước khi build

1. Cấp scope `identity` cho client SSO của LMS được không? Claim `identity` có **chính xác** trùng `SoDinhDanhCaNhan` của OpenSync không?
2. Ý nghĩa `sub` của OIDC — có phải PK user trên TTC, ổn định mãi mãi, kể cả khi user chuyển trường?
3. Quy ước giữa `MaKhoi` (trong `thongtinhocsinh`) và `MaKhoiLop` (trong `thongtinkhoilop`) — cách join chính tắc?
4. API code chuẩn cho phân công giảng dạy là `opensync.phanconggiangday` hay `opensync.phancong`?
5. Có endpoint nào trả delta (changed-since) không? Hay chấp nhận snapshot diff phía client?
6. Có endpoint quan hệ Phụ huynh ↔ Học sinh không?
7. Issuer (`iss`) chính xác trong JWT là gì để verify cứng?
8. TTC có gửi `refresh_token` trong response không, hay LMS bắt buộc redirect SSO mỗi lần expire?
9. Webhook hoặc cơ chế notify khi data TTC thay đổi (HS nghỉ học, GV nghỉ việc) — có không?
10. Rate limit của OpenSync và SSO endpoint là bao nhiêu? Có giới hạn concurrent token request?

---

## 10. Manday ballpark (nếu cần)

| Hạng mục | Phạm vi | Khoảng (md) |
|----------|---------|-------------|
| **TTC-SSO-A** — `lms-sso` integration | Authorize redirect + callback + token exchange + JWT verify + state CSRF | 4–7 |
| **TTC-SSO-B** — Logout RP-Initiated + session sync với LMS | Logout flow + cookie clean | 1–2 |
| **TTC-OS-A** — OpenSync client core | Token cache + retry + 6 API client + paging | 4–7 |
| **TTC-OS-B** — Schema + upsert | Entity (HS/GV/Lop/Khoi/Nien/PhanCong) + migration + idempotent upsert + soft-delete strategy | 6–12 |
| **TTC-OS-C** — Cron orchestration | Job scheduler + thứ tự gọi + lock + retry + metric | 3–6 |
| **TTC-BR** — Bridge SSO ↔ OpenSync | Resolve user theo `sub`/`identity`, JIT, on-demand sync khi miss | 3–6 |
| **TTC-FE** — UI nút "Đăng nhập với TTC" + trang admin xem trạng thái sync | `lms-fe` + `lms-school` | 3–6 |
| **TTC-QA / INT** | E2E SSO flow, sync stability, edge case (HS chuyển lớp giữa kỳ, GV nghỉ việc) | 4–8 |
| **Tổng** | Một dev full-stack tuần tự | **28–54 md** |

> Buffer +20–30% nếu TTC trả lời câu hỏi §9 chậm hoặc cần đàm phán scope/API code mới.
> Khi vibe coding với Cursor (scaffold OAuth client, OpenAPI client, repo upsert pattern): có thể giảm ~20–30%; phần **TTC-OS-C** + **TTC-QA** giảm ít nhất.

---

## 11. Tham chiếu chéo trong repo

- `tich-hop-ttc/SKILL.md` — bảng endpoint, claim, error code, checklist nhanh.
- `tich-hop-ttc/HuongDan_SSO_DoiTac.docx` — bản gốc DOC SSO.
- `tich-hop-ttc/HuongDan_OpenSyncAPI_DoiTac.docx` — bản gốc DOC OpenSync.
- Đối chiếu repo:
  - `~/dev/dtp/lms-sso` — entry SSO (Next.js).
  - `~/dev/dtp/lms-api` — backend Java/Spring; nơi đặt OpenSync client + scheduled job + entity sync.
  - `~/dev/dtp/lms-fe`, `~/dev/dtp/lms-school` — UI nút SSO + trang admin sync.

---

*Cập nhật khi: TTC phản hồi câu §9, chốt scope, hoặc thay đổi cấu trúc API; sau spike cron full-sync trên môi trường kiểm thử.*
