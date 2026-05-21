---
title: UC-01 Implementation — TTC SSO Login (Authorize Code)
scope: tich-hop-ttc
repos:
  - FE broker: ~/dev/dtp/lms-sso
  - BE: ~/dev/dtp/lms-api
sources:
  - tich-hop-ttc/phan-tich-tich-hop.md (UC-01)
  - tich-hop-ttc/HuongDan_SSO_DoiTac.docx
reference_implementation:
  - lms-sso: pages/doe-sso/* (entry + redirect)
  - lms-api: vn.dtpsoft.modules.doe.DOEController, DOEService
  - lms-api: vn.dtpsoft.modules.account.AuthController (issue token LMS)
status: draft
---

## 0) Mục tiêu UC-01

Cho user TTC (GV/PH/HS) bấm “Đăng nhập với TTC” trên LMS → đăng nhập TTC → quay lại LMS và nhận **token LMS** (`accessToken`, `refreshToken`, `branchId`, `userRole`, `lmsSiteUrl`) để đi vào `lms-fe`/`lms-school`.

Nguyên tắc giống DOE SSO hiện có:
- Token TTC **không** dùng làm session LMS.
- Backend (`lms-api`) đổi TTC token → **JWT nội bộ LMS** + refresh token.

---

## 1) Kiến trúc tổng quan

### 1.1 Vai trò từng repo

- **`lms-sso`**: broker web flow
  - redirect sang TTC `/oauth/authorize`
  - nhận callback `code/state`
  - gọi BE `lms-api` để “login-via-code”
  - set cookie auth (access/refresh/tokenType/branch/meta) rồi redirect về app đích

- **`lms-api`**: TTC OAuth client + user resolver + token issuer
  - exchange `code` → `access_token`
  - verify JWT TTC
  - resolve/link user trong DB LMS
  - issue token LMS (JWT) + refresh token

### 1.2 Sequence chuẩn (happy path)

1. User → `lms-fe`/`lms-school` → click “Đăng nhập TTC” → redirect qua `lms-sso /ttc-sso`
2. `lms-sso /ttc-sso` tạo `state` → set cookie state → 302 sang TTC authorize URL
3. TTC login OK → 302 về `lms-sso /ttc-sso/callback?code=…&state=…`
4. `lms-sso` verify `state` → gọi `lms-api POST /ttc/login-via-code`
5. `lms-api` đổi code→token TTC + verify JWT + resolve user → trả `TokenAuthDto`
6. `lms-sso` set cookie auth → redirect về `lmsSiteUrl` đúng app/role (qua `createDestinationUrl`)

---

## 2) FE — `~/dev/dtp/lms-sso` (tích hợp giống DOE SSO)

### 2.1 Thêm paths

Sửa `constants/paths.js`:
- `ttcSso: "/ttc-sso"`
- `ttcSsoCallback: "/ttc-sso/callback"`

Add 2 paths vào `unauthenticatedPaths` để middleware không ép login.

### 2.2 Feature flag theo hostname

Tương tự DOE:

- Env: `NEXT_PUBLIC_HOSTS_ENABLE_TTC_SSO=<domain1,domain2,...>`
- Trong `utils/get-server-side-props.js`:
  - parse env thành mảng
  - set `allowedTtcSso` theo `hostname`

### 2.3 Login UI: nút “Đăng nhập TTC”

Trong `components/pages/CredentialLogin/CredentialLoginPage.js`:
- add button thứ 2 trong `ThirdPartyLogin`
- `href={paths.ttcSso}`
- chỉ render nếu `enableTtcSso` (prop) = true

Trong `pages/sign-in.js` truyền `allowedTtcSso` xuống `CredentialLoginPage`.

### 2.4 Page entry: `pages/ttc-sso/index.js`

Implement SSR redirect:
- Nếu `!allowedTtcSso` → redirect về `/sign-in`
- Generate `state` (random/UUID)
- Set cookie `ttc_sso_state`:
  - HttpOnly
  - SameSite=Lax
  - Secure (prod)
  - MaxAge 5–10 phút
- Build authorize URL TTC:
  - `response_type=code`
  - `client_id` (lấy từ env public nếu TTC cho phép; hoặc hardcode key public)
  - `redirect_uri = origin + paths.ttcSsoCallback`
  - `scope` (khuyến nghị: `openid identity` + các scope profile/email/phone nếu TTC cấp)
  - `state=<state>`
  - (optional) `nonce=<random>` nếu TTC yêu cầu
- 302 tới authorize URL

> Lưu ý: `client_secret` KHÔNG đặt ở FE.

### 2.5 Page callback: `pages/ttc-sso/callback.js`

SSR flow:
- Check `allowedTtcSso`
- Read `code`, `state` từ query
- Verify `state` == cookie `ttc_sso_state`:
  - mismatch → redirect `/sign-in?error=ttc-sso`
- Call BE:
  - `POST /ttc/login-via-code` body `{ code, redirectUri: origin + paths.ttcSsoCallback }`
- Receive `TokenAuthDto`: `accessToken`, `refreshToken`, `type`, `branchId`, `userRole`, `lmsSiteUrl`
- `setAllAuthCookies(...)`
- Nếu `userRole === TEACHER` có thể reuse logic hiện có:
  - gọi `getTeacherClasses({ branchId, ...context })` để lấy `classId` default
- Redirect sang `createDestinationUrl({ roleCode: userRole, branchId, destination: lmsSiteUrl, classId })`

### 2.6 API config FE

Thêm vào `services/api/config.js`:
- `ttcSso: { loginViaCode: { url: "/ttc/login-via-code", method: POST } }`

Thêm `services/api/ttc-sso.js` tương tự `services/api/doe-sso.js`.

---

## 3) BE — `~/dev/dtp/lms-api`

### 3.1 Endpoint mới

Tạo `vn.dtpsoft.modules.ttc.TTCController`:
- `POST /ttc/login-via-code`
  - input: `code`, `redirectUri`
  - output: `TokenAuthDto` (reuse)

### 3.2 TTC OAuth client (exchange code)

Tạo `TTCOAuthService`:
- `exchangeCode(code, redirectUri) -> TtcTokenResponse { access_token, expires_in, ... }`
- Config properties (application.yml):
  - `app.ttc.oidc.tokenUrl`
  - `app.ttc.oidc.clientId`
  - `app.ttc.oidc.clientSecret`
  - `app.ttc.oidc.issuer`
  - `app.ttc.oidc.jwksUrl` (nếu verify qua JWKS)
  - `app.ttc.oidc.allowedRedirectUris` (whitelist)

Use `HttpService` giống `DOEService`.

### 3.3 Verify JWT TTC

Tạo `TTCJwtVerifier`:
- verify signature (JWKS hoặc secret theo TTC)
- verify `iss` đúng cấu hình
- verify `exp` còn hạn
- (khuyến nghị) verify `jti` chưa dùng lại trong window ngắn (cache/DB) để chống replay

### 3.4 Resolve user (bridge SSO ↔ OpenSync)

Tạo `TTCSsoUserResolverService`:

Input: claims
- `sub` (bắt buộc)
- `user_type` (bắt buộc)
- `identity` (khuyến nghị bắt buộc cho HS/GV; optional cho PH)
- `name/given_name/family_name/email/phone/picture` (optional)

Lookup order (đúng `phan-tich-tich-hop.md`):
1) `find user where ttc_sub = sub`
2) nếu không có & `identity` có:
   - `find user where citizen_identity_code = identity`
   - nếu match → update `ttc_sub = sub`
3) nếu vẫn không có:
   - áp provisioning policy (xem 3.5)

### 3.5 Provisioning policy (đề xuất bám doc)

- **PARENT (user_type=4)**: JIT create (OpenSync không có PH)
- **STUDENT/TEACHER**:
  - ưu tiên pre-provision (match theo `citizenIdentityCode`)
  - nếu chưa có:
    - Option A (strict): reject login với message “chưa được cấp quyền”
    - Option B (hybrid+JIT): tạo user tạm + đánh cờ `needs_opensync_link=true` và trigger UC-04 incremental sync theo `identity`

Chốt policy theo BA/PO trước khi release.

### 3.6 Issue token LMS

Sau khi resolve được userId:
- `accessToken = jwtUtils.generateTokenFromUserId(userId)`
- `refreshToken = tokenService.createRefreshToken(userId)`
- `userRole/branchId`:
  - SUPER_ADMIN nếu `user.isAdmin()`
  - else `userBranchRoleService.findFirstByUserId(userId)` (reject nếu null)
- `lmsSiteUrl = lmsService.generateLmsSiteUrl(userRole, user.getSchool().getDomain())`
- return `TokenAuthDto` (giống `DOEController.loginViaToken`)

---

## 4) DB changes (lms-api)

### 4.1 Thêm cột `ttc_sub`

Trong bảng `"user"`:
- `ttc_sub` varchar (độ dài theo TTC)
- index `user_idx_ttc_sub`
- unique theo scope multi-tenant (đề xuất unique `(school_id, ttc_sub)` hoặc global tùy model)

Reuse `citizen_identity_code` để lưu `SoDinhDanhCaNhan` (identity) nếu TTC claim tương ứng.

---

## 5) Error handling & observability

### 5.1 Error codes (đề xuất)

Các lỗi nên trả 400/401 với mã rõ:
- `TTC_SSO_STATE_INVALID` (FE)
- `TTC_SSO_CODE_INVALID`
- `TTC_SSO_TOKEN_EXCHANGE_FAILED`
- `TTC_SSO_JWT_INVALID` (iss/exp/signature)
- `TTC_SSO_USER_TYPE_UNSUPPORTED`
- `TTC_SSO_USER_NOT_PROVISIONED` (strict mode)
- `TTC_SSO_USER_BRANCH_ROLE_MISSING`

### 5.2 Logging tối thiểu

Log theo request id:
- `sub`, `user_type`, `has_identity`, `schoolId`
- kết quả resolve path: bySub / byIdentity / jit / rejected
- token exchange latency + status code TTC (không log secret/token raw)

---

## 6) Security checklist (bắt buộc)

- [ ] `state` cookie HttpOnly + verify state
- [ ] whitelist `redirectUri` trong BE
- [ ] verify JWT signature + iss + exp
- [ ] không log `access_token` TTC
- [ ] không đưa `client_secret` ra FE
- [ ] rate limit endpoint `/ttc/login-via-code` (tránh brute force code)
- [ ] (khuyến nghị) `jti` anti-replay window

---

## 7) Test plan (tối thiểu)

- FE:
  - allowed host bật/tắt TTC SSO
  - state mismatch → fail
  - callback thiếu code → fail

- BE:
  - exchange fail → trả lỗi
  - jwt invalid iss/exp → 401
  - resolve by sub (đã link)
  - resolve by identity (link sub)
  - strict reject khi HS/GV chưa pre-provision
  - JIT parent tạo user (nếu bật)

