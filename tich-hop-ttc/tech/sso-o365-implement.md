---
title: UC-01b Implementation — Office 365 SSO Login (Microsoft Entra ID, riêng cho GV)
scope: tich-hop-ttc
repos:
  - FE broker: ~/dev/dtp/lms-sso
  - BE: ~/dev/dtp/lms-api
  - FE app: ~/dev/dtp/lms-school
sources:
  - tich-hop-ttc/phan-tich-tich-hop.md (UC-01b, §3b, §5.2)
  - tich-hop-ttc/SKILL.md (§1b)
  - Microsoft Identity Platform — OIDC reference
reference_implementation:
  - lms-sso: pages/doe-sso/* (entry + redirect)
  - lms-sso: pages/ttc-sso/* (sẽ build trong UC-01a — patterns chia sẻ)
  - lms-api: vn.dtpsoft.modules.doe.DOEController, DOEService
  - lms-api: vn.dtpsoft.modules.account.AuthController (issue token LMS)
related:
  - tich-hop-ttc/tech/uc-01-implementation.md (TTC SSO PH/HS — pattern broker chia sẻ)
  - tich-hop-ttc/tech/uc-03-implement.md (cron sync GV — bắt buộc chạy trước UC-01b)
  - tich-hop-ttc/tech/sso-o365-code.md (code snippet thực thi — copy theo)
status: draft
---

## 0) Mục tiêu UC-01b

Cho **giáo viên** (và cán bộ) bấm "Đăng nhập với Office 365" trên LMS → login qua Microsoft Entra ID (tenant của TTC) → quay lại LMS và nhận **token LMS** (`accessToken`, `refreshToken`, `branchId`, `userRole=TEACHER`, `lmsSiteUrl`) để vào `lms-school`.

Nguyên tắc:
- **Tách riêng** với UC-01a (TTC SSO cho PH/HS) — TTC quyết định tách phần GV sang O365.
- **id_token Entra KHÔNG dùng làm session LMS** — `lms-api` đổi id_token Entra → JWT nội bộ LMS + refresh token (giống pattern DOE/TTC).
- **Strict pre-provision** — REJECT nếu GV chưa có trong DB LMS (sync từ OpenSync `thongtingiaovien` qua UC-03).
- **Lock tenant** — verify `tid` claim phải khớp `O365_TENANT_ID` env (chống cross-tenant attack).

---

## 1) Kiến trúc tổng quan

### 1.1 Vai trò từng repo

- **`lms-sso`**: broker web flow cho O365
  - host route mới `/o365-sso` (entry) + `/o365-sso/callback` + `/o365-sso/logout` + `/o365-sso/logout-callback`
  - redirect sang Entra `/oauth2/v2.0/authorize`
  - nhận callback `code/state`
  - gọi BE `lms-api` để "login-via-code" với provider=`o365`
  - set cookie auth (access/refresh/tokenType/branch/meta) rồi redirect về app đích (mặc định `lms-school`)

- **`lms-api`**: O365 OAuth client + GV resolver + token issuer
  - exchange `code` → `id_token` + `access_token` qua Entra token endpoint
  - verify id_token bằng JWKS Microsoft (signature + `iss` + `aud` + `exp` + `tid`)
  - resolve GV trong DB LMS theo thứ tự `o365_oid` → `employeeId` → `email`
  - REJECT (ghi `pending_o365_users`) nếu không match
  - issue token LMS (JWT) + refresh token

- **`lms-school`**: app GV
  - thêm nút "Đăng nhập với Office 365" trên trang login → redirect tới `lms-sso /o365-sso`
  - admin tools: trang xem `pending_o365_users` + map thủ công

### 1.2 Sequence chuẩn (happy path)

1. GV → `lms-school` → click "Đăng nhập với Office 365" → redirect qua `lms-sso /o365-sso`
2. `lms-sso /o365-sso` tạo `state` (+ optional `nonce`) → set cookie state → 302 sang Entra authorize URL
3. Entra login OK (có thể chèn MFA / Conditional Access) → 302 về `lms-sso /o365-sso/callback?code=…&state=…`
4. `lms-sso` verify `state` → gọi `lms-api POST /o365/login-via-code`
5. `lms-api` exchange code→token Entra + verify id_token (JWKS) + lock `tid` + resolve GV → trả `TokenAuthDto`
6. `lms-sso` set cookie auth → redirect về `lmsSiteUrl` (qua `createDestinationUrl`)

### 1.3 Sequence "GV chưa được sync"

1. → 4. giống happy path
5. `lms-api` resolve không match → INSERT/UPSERT `pending_o365_users(oid, tid, email, upn, attempted_at, attempt_count++)` → trả `403 TTC_SSO_USER_NOT_PROVISIONED` (tái dùng error code chung)
6. `lms-sso` redirect `/sign-in?error=o365-not-provisioned`
7. UI `lms-school` hiển thị message: *"Tài khoản Office 365 của bạn chưa được đồng bộ vào LMS. Vui lòng liên hệ admin trường."*
8. Admin login `lms-school` → trang **Pending O365 Users** → match `pending_o365_users.id` ↔ `GiaoVien.id` → confirm → record được merge, GV thử login lại sẽ vào được.

---

## 2) FE — `~/dev/dtp/lms-sso` (broker O365)

### 2.1 Thêm paths

Sửa `constants/paths.js`:

- `o365Sso: "/o365-sso"`
- `o365SsoCallback: "/o365-sso/callback"`
- `o365SsoLogout: "/o365-sso/logout"`
- `o365SsoLogoutCallback: "/o365-sso/logout-callback"`

Add cả 4 paths vào `unauthenticatedPaths` để middleware không ép login.

### 2.2 Feature flag theo hostname

Tương tự DOE/TTC:

- Env: `NEXT_PUBLIC_HOSTS_ENABLE_O365_SSO=<domain1,domain2,...>`
- Trong `utils/get-server-side-props.js`:
  - parse env thành mảng
  - set `allowedO365Sso` theo `hostname`

> Khuyến nghị: chỉ bật O365 SSO cho domain `lms-school.*` (app GV). Tắt cho `lms-fe.*` (PH/HS) để UI không có nút thừa.

### 2.3 Login UI: nút "Đăng nhập với Office 365"

Trong `components/pages/CredentialLogin/CredentialLoginPage.js`:

- Add button trong `ThirdPartyLogin`:
  - Icon Microsoft (logo 4 ô màu)
  - Label: "Đăng nhập với Office 365"
  - `href={paths.o365Sso}`
  - Chỉ render nếu `enableO365Sso` (prop) = true
- Đặt **trên** nút TTC SSO khi cùng visible (GV thường login nhiều hơn).

Trong `pages/sign-in.js` truyền `allowedO365Sso` xuống `CredentialLoginPage`.

### 2.4 Page entry: `pages/o365-sso/index.js`

Implement SSR redirect:

```js
// Pseudo
- Nếu !allowedO365Sso → redirect /sign-in
- state = randomBytes(16).hex
- nonce = randomBytes(16).hex   // OIDC anti-replay
- Set cookies:
    o365_sso_state  HttpOnly SameSite=Lax Secure(prod) MaxAge 600s
    o365_sso_nonce  HttpOnly SameSite=Lax Secure(prod) MaxAge 600s
- Build authorize URL:
    https://login.microsoftonline.com/{O365_TENANT_ID}/oauth2/v2.0/authorize
      ?client_id={O365_CLIENT_ID}
      &response_type=code
      &redirect_uri={origin}{paths.o365SsoCallback}
      &scope=openid profile email offline_access
      &response_mode=query
      &state={state}
      &nonce={nonce}
      &prompt=select_account     // optional, force chooser
- 302 tới authorize URL
```

> `O365_TENANT_ID` đọc từ env public (`NEXT_PUBLIC_O365_TENANT_ID`) nếu cần build URL ở FE; HOẶC FE chỉ trỏ `/o365-sso` (server route), backend Next.js build URL từ env private. Khuyến nghị **option 2** để không expose tenant id ra browser bundle.

### 2.5 Page callback: `pages/o365-sso/callback.js`

SSR flow:

```js
- Check allowedO365Sso
- Read code, state từ query
- Verify state == cookie o365_sso_state → mismatch → /sign-in?error=o365-state
- Read cookie o365_sso_nonce → forward xuống BE để verify trong id_token
- Call BE:
    POST /o365/login-via-code
    body { code, redirectUri: origin + paths.o365SsoCallback, expectedNonce: nonce }
- Receive TokenAuthDto: accessToken, refreshToken, type, branchId, userRole, lmsSiteUrl
- setAllAuthCookies(...)
- Nếu userRole === TEACHER → reuse logic cũ:
    getTeacherClasses({ branchId, ...context }) lấy classId default
- Redirect createDestinationUrl({ roleCode: userRole, branchId, destination: lmsSiteUrl, classId })
- Clear cookies o365_sso_state + o365_sso_nonce
```

Error handling:
- `code` thiếu / `state` mismatch → `/sign-in?error=o365-sso`
- BE trả `TTC_SSO_USER_NOT_PROVISIONED` → `/sign-in?error=o365-not-provisioned`
- BE trả `O365_TENANT_MISMATCH` → `/sign-in?error=o365-tenant`

### 2.6 Page logout: `pages/o365-sso/logout.js`

```js
- Read id_token từ session cookie LMS (nếu có)
- Clear cookies LMS
- 302 → https://login.microsoftonline.com/{O365_TENANT_ID}/oauth2/v2.0/logout
         ?post_logout_redirect_uri={origin}{paths.o365SsoLogoutCallback}
         &id_token_hint={id_token}      // khuyến nghị có
         &state={random}
```

### 2.7 Page logout callback: `pages/o365-sso/logout-callback.js`

```js
- Verify state khớp (nếu set)
- Redirect /sign-in
```

### 2.8 API config FE

Thêm vào `services/api/config.js`:
- `o365Sso: { loginViaCode: { url: "/o365/login-via-code", method: POST } }`

Thêm `services/api/o365-sso.js` tương tự `services/api/doe-sso.js`.

---

## 3) BE — `~/dev/dtp/lms-api`

### 3.1 Endpoint mới

Tạo `vn.dtpsoft.modules.o365.O365Controller`:

- `POST /o365/login-via-code`
  - input: `code`, `redirectUri`, `expectedNonce`
  - output: `TokenAuthDto` (reuse)
- `GET /o365/pending` (admin only) — list `pending_o365_users` để admin map
- `POST /o365/pending/{id}/resolve` (admin only) — body `{ giaoVienId }` → merge

### 3.2 O365 OAuth client (exchange code)

Tạo `O365OAuthService`:

- `exchangeCode(code, redirectUri) -> O365TokenResponse { id_token, access_token, refresh_token?, expires_in }`
- Config properties (application.yml):
  ```yaml
  app.o365.oidc:
    tenantId: ${O365_TENANT_ID}
    clientId: ${O365_CLIENT_ID}
    clientSecret: ${O365_CLIENT_SECRET}
    scopes: openid profile email offline_access
    discoveryUrl: https://login.microsoftonline.com/${O365_TENANT_ID}/v2.0/.well-known/openid-configuration
    allowedRedirectUris:                # whitelist
      - https://lms-sso.dtp.vn/o365-sso/callback
      - https://lms-sso-staging.dtp.vn/o365-sso/callback
  ```
- Discovery cache: gọi `discoveryUrl` 1 lần lúc startup → cache 24h → có `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `end_session_endpoint`.
- Use `HttpService` giống `DOEService`.

### 3.3 Verify id_token Entra

Tạo `O365JwtVerifier`:

```java
public OidcClaims verify(String idToken, String expectedNonce) {
    // 1. Parse JWT header to get `kid`
    // 2. Fetch JWKS từ cache (discovery jwks_uri); refresh nếu kid không có
    // 3. Verify signature with matched JWK (RS256)
    // 4. Verify claims:
    //    - iss == "https://login.microsoftonline.com/" + tenantId + "/v2.0"
    //    - aud == clientId
    //    - exp > now (allow skew 60s)
    //    - nbf <= now (allow skew 60s)
    //    - tid == tenantId          ← LOCK TENANT
    //    - nonce == expectedNonce   ← anti-replay
    // 5. Return decoded claims
}
```

Library: dùng **nimbus-jose-jwt** (đã có trong stack Spring) hoặc **java-jwt** với `JwkProvider`.

### 3.4 Resolve GV (bridge O365 ↔ OpenSync)

Tạo `O365SsoUserResolverService`:

Input: claims
- `oid` (bắt buộc)
- `tid` (bắt buộc, đã verify)
- `email` (khuyến nghị)
- `upn` (optional)
- `employeeId` (optional, nếu Entra config)
- `name`/`given_name`/`family_name` (optional)

Lookup order (đúng `phan-tich-tich-hop.md` §3b.5):

```java
public ResolveResult resolve(O365Claims claims) {
    // 1. By oid + tid
    Optional<User> u = users.findByO365(claims.oid, claims.tid);
    if (u.isPresent()) {
        users.touchProfileFromO365(u.get(), claims);   // refresh name/email
        return ResolveResult.ok(u.get());
    }

    // 2. By employeeId claim → match GiaoVien.SoDinhDanhCaNhan
    if (claims.employeeId != null) {
        Optional<GiaoVien> gv = giaoVienRepo.findBySoDinhDanh(claims.employeeId);
        if (gv.isPresent()) {
            User user = users.upsertFromGiaoVien(gv.get(), claims);
            return ResolveResult.ok(user);
        }
    }

    // 3. By email (case-insensitive) → match GiaoVien.Email với source=TTC_OPENSYNC
    if (claims.email != null) {
        Optional<GiaoVien> gv = giaoVienRepo
            .findByEmailIgnoreCaseAndSource(claims.email, Source.TTC_OPENSYNC);
        if (gv.isPresent()) {
            User user = users.upsertFromGiaoVien(gv.get(), claims);
            return ResolveResult.ok(user);
        }
    }

    // 4. Reject + log pending
    pendingO365UsersRepo.upsert(claims);  // tăng attempt_count
    metrics.counter("o365_sso.user_not_provisioned").increment();
    return ResolveResult.rejected(ErrorCode.TTC_SSO_USER_NOT_PROVISIONED);
}
```

> ⚠️ **KHÔNG JIT cho GV**. Nếu sau này bật JIT cho cán bộ thường (`MaLoaiNhanSu` ≠ `GV`) → cần PO/BA phê duyệt riêng.

### 3.5 Trigger incremental sync khi reject

Khi rơi vào branch `pending_o365_users`, có thể schedule trigger UC-04 (incremental sync GV theo `email`/`employeeId`) — vì có thể GV mới được tạo trong TTC nhưng cron đêm chưa chạy:

```java
if (claims.employeeId != null) {
    asyncOpenSyncService.triggerSyncGiaoVienBySoDinhDanh(claims.employeeId);
}
// Hoặc: triggerSyncGiaoVienByEmail(claims.email)
// → user thử login lại sau 1-2 phút có thể thành công
```

Hiển thị UI hint: *"Hệ thống đang đồng bộ thông tin của bạn. Vui lòng thử lại sau 5 phút."*

### 3.6 Issue token LMS

Sau khi resolve thành công:

```java
String accessToken = jwtUtils.generateTokenFromUserId(userId);
String refreshToken = tokenService.createRefreshToken(userId);

UserBranchRole ubr = user.isAdmin()
    ? UserBranchRole.superAdmin()
    : userBranchRoleService.findFirstByUserId(userId)
        .orElseThrow(() -> new ApiException(ErrorCode.TTC_SSO_USER_BRANCH_ROLE_MISSING));

String userRole = ubr.getRoleCode();   // TEACHER / STAFF / ADMIN
Long branchId = ubr.getBranchId();
String lmsSiteUrl = lmsService.generateLmsSiteUrl(userRole, user.getSchool().getDomain());

return TokenAuthDto.builder()
    .accessToken(accessToken)
    .refreshToken(refreshToken)
    .type("Bearer")
    .branchId(branchId)
    .userRole(userRole)
    .lmsSiteUrl(lmsSiteUrl)
    .build();
```

Reuse `TokenAuthDto` y hệt `DOEController.loginViaToken` / `TTCController.loginViaCode`.

---

## 4) DB changes (lms-api)

### 4.1 Bảng `"user"` — thêm cột

```sql
ALTER TABLE "user"
  ADD COLUMN o365_oid       VARCHAR(64),
  ADD COLUMN o365_tid       VARCHAR(64),
  ADD COLUMN upn            VARCHAR(255);

-- Unique pair (oid, tid) — null-safe
CREATE UNIQUE INDEX user_idx_o365_oid_tid
  ON "user" (o365_oid, o365_tid)
  WHERE o365_oid IS NOT NULL;

CREATE INDEX user_idx_upn ON "user" (LOWER(upn));
```

> **Không** unique riêng `o365_oid` global — tránh conflict nếu sau này LMS hỗ trợ multi-tenant Entra (lý thuyết). Compound unique `(oid, tid)` an toàn.

### 4.2 Bảng mới `pending_o365_users`

```sql
CREATE TABLE pending_o365_users (
  id                BIGSERIAL PRIMARY KEY,
  o365_oid          VARCHAR(64) NOT NULL,
  o365_tid          VARCHAR(64) NOT NULL,
  email             VARCHAR(255),
  upn               VARCHAR(255),
  display_name      VARCHAR(255),
  attempted_at      TIMESTAMP NOT NULL DEFAULT NOW(),
  first_attempted_at TIMESTAMP NOT NULL DEFAULT NOW(),
  attempt_count     INTEGER NOT NULL DEFAULT 1,
  resolved_user_id  BIGINT REFERENCES "user"(id),
  resolved_at       TIMESTAMP,
  resolved_by       BIGINT REFERENCES "user"(id),
  CONSTRAINT pending_o365_uq UNIQUE (o365_oid, o365_tid)
);

CREATE INDEX pending_o365_idx_unresolved
  ON pending_o365_users (attempted_at DESC)
  WHERE resolved_user_id IS NULL;
```

Upsert pattern khi reject:

```sql
INSERT INTO pending_o365_users (o365_oid, o365_tid, email, upn, display_name)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (o365_oid, o365_tid) DO UPDATE SET
  attempted_at = NOW(),
  attempt_count = pending_o365_users.attempt_count + 1,
  email = EXCLUDED.email,
  upn = EXCLUDED.upn,
  display_name = EXCLUDED.display_name;
```

Khi admin resolve:

```sql
-- 1. Set o365_oid/o365_tid lên user (= giao_vien.user_id)
UPDATE "user" SET o365_oid = :oid, o365_tid = :tid, upn = :upn
  WHERE id = :user_id;

-- 2. Mark pending resolved
UPDATE pending_o365_users
   SET resolved_user_id = :user_id, resolved_at = NOW(), resolved_by = :admin_id
 WHERE id = :pending_id;
```

### 4.3 Reuse cột có sẵn

- `citizen_identity_code` ← `claims.employeeId` (nếu có)
- `email` ← `claims.email`
- `full_name` / `first_name` / `last_name` ← claims `name` / `given_name` / `family_name`

---

## 5) Admin UI — `lms-school`

### 5.1 Trang Pending O365 Users

Path đề xuất: `/admin/o365-pending`

Bảng:

| Cột | Source |
|-----|--------|
| Email | `pending.email` |
| UPN | `pending.upn` |
| Display name | `pending.display_name` |
| Lần đầu thử | `pending.first_attempted_at` |
| Lần gần nhất | `pending.attempted_at` |
| Số lần thử | `pending.attempt_count` |
| Hành động | "Map vào GV" |

Khi click "Map vào GV":
- Modal search GV theo CCCD / email / họ tên (gọi `GET /admin/giao-vien/search?q=…`)
- Admin chọn 1 GV → confirm
- Call `POST /o365/pending/{id}/resolve` body `{ giaoVienId }`
- Reload list

### 5.2 Trang Sync Status (đã có ở UC-03 admin tools)

Thêm panel "O365 SSO health":
- Số lần login O365 / 24h (success vs reject)
- Số `pending_o365_users` chưa resolve
- Ngày hết hạn `O365_CLIENT_SECRET` (đếm ngược)
- Nút "Test discovery endpoint" (gọi BE healthcheck)

---

## 6) Error handling & observability

### 6.1 Error codes (đề xuất)

Reuse codes UC-01a + thêm:

- `O365_SSO_STATE_INVALID` (FE)
- `O365_SSO_NONCE_INVALID`
- `O365_SSO_CODE_INVALID`
- `O365_SSO_TOKEN_EXCHANGE_FAILED`
- `O365_SSO_JWT_INVALID` (signature/iss/aud/exp)
- `O365_TENANT_MISMATCH` (`tid` ≠ `O365_TENANT_ID`)
- `TTC_SSO_USER_NOT_PROVISIONED` (reuse — cùng UX message)
- `TTC_SSO_USER_BRANCH_ROLE_MISSING` (reuse)

### 6.2 Logging tối thiểu

Log theo request id:
- `oid`, `tid`, `has_email`, `has_employeeId`, `schoolId`
- Kết quả resolve path: `byOid` / `byEmployeeId` / `byEmail` / `pendingNew` / `pendingExisting`
- Token exchange latency + status code Entra (KHÔNG log `id_token`/`access_token` raw)
- Discovery cache hit/miss

### 6.3 Metrics (Micrometer / Prometheus)

| Metric | Type | Tags |
|--------|------|------|
| `o365_sso.login.attempt` | counter | `result=success/reject/error` |
| `o365_sso.login.latency` | histogram | (none) |
| `o365_sso.resolve.path` | counter | `path=byOid/byEmployeeId/byEmail/pending` |
| `o365_sso.token_exchange.latency` | histogram | (none) |
| `o365_sso.jwks_cache.refresh` | counter | `reason=startup/missing_kid/expired` |
| `o365_sso.pending_users.gauge` | gauge | (number of unresolved) |

### 6.4 Alert rules đề xuất

- `o365_sso.login.attempt{result=reject}` rate > 5/min (10 phút) → alert ops (có thể sync chưa chạy)
- `o365_sso.token_exchange.latency` p95 > 3s → alert ops (Entra slow)
- `o365_sso.pending_users.gauge` > 20 → notify admin trường (cần map bằng tay)
- Cron daily: alert nếu `O365_CLIENT_SECRET` còn < 30 ngày tới expiry

---

## 7) Security checklist (bắt buộc)

- [ ] `state` cookie HttpOnly + verify state ở callback
- [ ] `nonce` cookie HttpOnly + verify trong id_token (anti-replay)
- [ ] Whitelist `redirectUri` trong BE (`app.o365.oidc.allowedRedirectUris`)
- [ ] Verify id_token signature qua JWKS (KHÔNG skip)
- [ ] Verify `iss` = `https://login.microsoftonline.com/{tid}/v2.0`
- [ ] Verify `aud` = `clientId`
- [ ] Verify `exp` còn hạn (skew ≤60s)
- [ ] **Verify `tid` = `O365_TENANT_ID` env** ← lock tenant
- [ ] KHÔNG log `id_token` / `access_token` / `refresh_token`
- [ ] KHÔNG đưa `client_secret` ra FE
- [ ] Rate limit `/o365/login-via-code` (vd 30 req/min/IP)
- [ ] Rate limit `/o365/pending/{id}/resolve` (admin only) — guard role
- [ ] HTTPS bắt buộc
- [ ] CSP header trên FE: cho phép `frame-ancestors` của Microsoft (nếu dùng popup)

---

## 8) Test plan (tối thiểu)

### FE (`lms-sso`)

- [ ] Allowed host bật/tắt O365 SSO theo `NEXT_PUBLIC_HOSTS_ENABLE_O365_SSO`
- [ ] Click "Đăng nhập với Office 365" → redirect đúng authorize URL với `client_id`/`redirect_uri`/`scope`/`state`/`nonce`
- [ ] State mismatch ở callback → `/sign-in?error=o365-sso`
- [ ] Callback thiếu code → fail
- [ ] Callback với `error=…` từ Entra → display message Entra rõ ràng (vd `AADSTS65001`)
- [ ] Logout → redirect `https://login.microsoftonline.com/{tid}/oauth2/v2.0/logout` đúng

### BE (`lms-api`)

- [ ] Exchange code thành công → trả id_token có claims đúng
- [ ] id_token sai signature → 401 `O365_SSO_JWT_INVALID`
- [ ] id_token sai `iss` → 401
- [ ] id_token sai `aud` → 401
- [ ] id_token hết `exp` → 401
- [ ] **id_token `tid` lệch** → 401 `O365_TENANT_MISMATCH`
- [ ] id_token `nonce` lệch → 401 `O365_SSO_NONCE_INVALID`
- [ ] Resolve byOid (đã link, lần 2 login)
- [ ] Resolve byEmployeeId (lần đầu login, claim có `employeeId`)
- [ ] Resolve byEmail (lần đầu login, không có `employeeId`, email khớp)
- [ ] Resolve không match → 403 `TTC_SSO_USER_NOT_PROVISIONED` + ghi `pending_o365_users`
- [ ] Resolve không match lần 2 → `attempt_count` tăng, không INSERT mới
- [ ] Admin resolve pending → user được set `o365_oid`/`o365_tid`, lần login sau byOid match
- [ ] Discovery cache TTL hoạt động (mock thời gian)
- [ ] JWKS cache refresh khi `kid` mới (Entra rotate key)
- [ ] Token exchange Entra timeout → trả `O365_SSO_TOKEN_EXCHANGE_FAILED` (không treo)

### E2E

- [ ] GV đã sync OpenSync + có O365 → login thành công, vào `/teacher` đúng `branchId`
- [ ] GV chưa sync OpenSync → REJECT, hiển thị message hướng dẫn liên hệ admin
- [ ] GV nghỉ việc (TrangThai=Inactive ở OpenSync sync sau) → BE check `user.status=INACTIVE_BY_SYNC` → REJECT
- [ ] PH thử login O365 (không nên có) → reject vì không tìm thấy trong `thongtingiaovien`
- [ ] Concurrent login 2 tab cùng GV → chỉ 1 session active (tuỳ implement session)

### Smoke / migration

- [ ] Sau khi migrate DB, cột `o365_oid` NULL với toàn bộ user cũ → không break TTC SSO
- [ ] Reverse: rollback migration không mất data
- [ ] GV cũ đã có `ttc_sub` (lịch sử trước khi tách O365) → login O365 lần đầu, resolver byEmail match đúng GV cũ → set `o365_oid` mà KHÔNG tạo record mới

---

## 9) Triển khai theo giai đoạn

### Giai đoạn 1 — Foundation (1 tuần)

- DB migration (`user`.`o365_*`, `pending_o365_users`)
- `lms-sso` paths + entry/callback page (basic redirect — chưa lock tenant)
- `lms-api` `O365OAuthService` + `O365JwtVerifier` (basic — chưa resolver)
- Smoke test: redirect đến Entra + nhận callback + decode id_token

### Giai đoạn 2 — Resolver + UI nút (1 tuần)

- `O365SsoUserResolverService` đầy đủ 3 nhánh + `pending_o365_users`
- Nút "Đăng nhập với Office 365" trong `lms-school`
- Error pages thân thiện
- Lock tenant + verify nonce

### Giai đoạn 3 — Admin tools + observability (3–5 ngày)

- Trang Pending O365 Users (`lms-school`)
- Endpoint admin map
- Metrics + alert rules
- Auto-trigger UC-04 incremental sync khi reject

### Giai đoạn 4 — Hardening + go-live (3–5 ngày)

- Penetration test (state/nonce/tid replay)
- Load test endpoint token exchange
- Rotation playbook cho `O365_CLIENT_SECRET`
- Documentation cho IT vận hành (rotate secret, debug Entra error codes)
- Pilot 5–10 GV trước khi mở rộng

---

## 10) Câu hỏi mở (chốt với TTC IT trước khi build Giai đoạn 1)

Tham chiếu `phan-tich-tich-hop.md` §9.2:

1. **Tenant ID** Entra của TTC?
2. **App Registration**: ai tạo (TTC hay LMS)? `client_id` + `client_secret` (hoặc Certificate)?
3. **Redirect URI** đăng ký trên Entra cho dev/staging/prod?
4. **Optional claim `employeeId`** có được bật không? HR có đẩy CCCD vào Entra `employeeId`?
5. **Email** trong OpenSync `thongtingiaovien` có khớp UPN/email O365 GV không? Có sample data?
6. **Conditional Access / MFA** có bật cho app LMS không?
7. **Scope `offline_access`** có cấp không?
8. **Admin consent** đã bấm chưa?
9. GV nghỉ việc: Entra account disable bao lâu? Có webhook hay phải tự detect qua OpenSync?
10. Client Secret expiry policy? Có thể dùng Certificate (5 năm) thay không?

---

*Cập nhật khi: TTC IT phản hồi câu §10, Entra config xong, hoặc sau khi pilot 5–10 GV.*
