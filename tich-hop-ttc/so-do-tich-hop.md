# Sơ đồ tích hợp — TTC (ASC SCHOOL) ↔ LMS

## Sơ đồ tổng quan (ASCII — đọc trực tiếp)

```text
            (SSO Authorization Code + OIDC)

 [User HS/PH/GV]
        |
        | 1) Click "Đăng nhập với TTC"
        v
 [LMS FE (lms-fe / lms-school)]
        |
        | 2) Redirect TTC /oauth/authorize (response_type=code + state)
        v
 [TTC SSO (OIDC)]
        |
        | 3) Redirect callback ?code=...&state=...
        v
 [LMS SSO broker (lms-sso)]
        |
        | 4) POST TTC /api/oauth/token (grant_type=authorization_code)
        v
 [TTC SSO (OIDC)] --> 5) access_token (JWT: sub, user_type, [identity], exp, ...)
        |
        v
 [LMS SSO broker (lms-sso)]
        |
        | 6) Resolve user (lookup by ttc_sub/sub; optionally by identity → SoDinhDanhCaNhan)
        v
 [LMS API (lms-api)] <------------------------------+
        |                                           |
        | 7) Read/Write mappings + session data      |
        v                                           |
 [LMS DB]                                           |
        ^                                           |
        |                                           |
        +-------------------- 8) Set session cookie -+
                              (user quay lại FE dùng LMS)


            (OpenSync M2M Client Credentials)

 [Cron/Job hoặc Admin trigger]
        |
        v
 [LMS API (lms-api)]
        |
        | A) POST TTC /api/opensync/token (grant_type=client_credentials)
        | B) GET  /opensync/thongtinnienhoc
        | C) GET  /opensync/thongtinkhoilop?ma_truong
        | D) GET  /opensync/thongtinlophoc?ma_truong&ma_nien
        | E) GET  /opensync/thongtingiaovien?ma_truong
        | F) GET  /opensync/thongtinhocsinh?ma_truong&ma_nien&page...
        | G) GET  /opensync/phanconggiangday?ma_truong&ma_nien&SoDinhDanhCaNhan
        v
 [TTC OpenSync API]
        |
        | Upsert danh mục TTC → LMS (HS/GV/Lớp/Khối/Niên/Phân công)
        v
 [LMS DB]


 Logout (RP-Initiated)
 [User] -> [FE] -> TTC /oauth/endsession?id_token_hint=<access_token>&post_logout_redirect_uri=...
```

## Sơ đồ tổng quan (Mermaid — nếu bật preview)

```mermaid
flowchart LR
  %% Actors
  user([Người dùng\nHS / PH / GV]):::actor
  admin([Admin LMS]):::actor

  %% LMS apps
  fe[LMS FE\n(lms-fe / lms-school)]:::app
  sso[LMS SSO broker\n(lms-sso)]:::svc
  api[LMS Backend API\n(lms-api)]:::svc
  db[(LMS Database)]:::db

  %% TTC systems
  ttcAuth[TTC SSO (OIDC)\nASC SCHOOL]:::ext
  ttcOs[TTC OpenSync API\nASC SCHOOL]:::ext

  %% --- SSO login flow ---
  user -->|1) Click \"Đăng nhập với TTC\"| fe
  fe -->|2) Redirect /oauth/authorize\nresponse_type=code + state| ttcAuth
  ttcAuth -->|3) Redirect callback\n?code=...&state=...| sso
  sso -->|4) POST /api/oauth/token\n(grant_type=authorization_code)| ttcAuth
  ttcAuth -->|5) access_token (JWT)\n{sub, user_type, ...}| sso
  sso -->|6) Resolve user (sub / identity)\ncreate JIT if policy allows| api
  api -->|7) Read/Write user mappings| db
  sso -->|8) Set session cookie| user
  user -->|9) Use LMS| fe
  fe --> api
  api --> db

  %% --- Logout flow ---
  user -.->|Logout| fe
  fe -.->|Redirect /oauth/endsession\n(id_token_hint=access_token)| ttcAuth

  %% --- OpenSync sync flow ---
  admin -->|Trigger sync (optional)| fe
  fe -->|Call admin endpoints| api

  api -->|A) POST /api/opensync/token\n(grant_type=client_credentials)| ttcOs
  api -->|B) GET /opensync/thongtinnienhoc| ttcOs
  api -->|C) GET /opensync/thongtinkhoilop?ma_truong| ttcOs
  api -->|D) GET /opensync/thongtinlophoc?ma_truong&ma_nien| ttcOs
  api -->|E) GET /opensync/thongtingiaovien?ma_truong| ttcOs
  api -->|F) GET /opensync/thongtinhocsinh?ma_truong&ma_nien&page...| ttcOs
  api -->|G) GET /opensync/phanconggiangday?ma_truong&ma_nien&SoDinhDanhCaNhan| ttcOs

  api -->|Upsert danh mục TTC → LMS\n(HS/GV/Lớp/Khối/Niên/Phân công)| db

  classDef actor fill:#fff,stroke:#111,stroke-width:1px;
  classDef app fill:#eef6ff,stroke:#1b64d8,stroke-width:1px;
  classDef svc fill:#f1fff5,stroke:#1f8a3b,stroke-width:1px;
  classDef ext fill:#fff7e6,stroke:#c77700,stroke-width:1px;
  classDef db fill:#f7f7f7,stroke:#444,stroke-width:1px;
```

## Ghi chú đọc sơ đồ

- **SSO (Authorization Code)**: User đi qua browser; `lms-sso` đổi `code` lấy JWT; `lms-api` resolve user theo `sub` (và `identity` nếu TTC cấp scope).
- **OpenSync (Client Credentials)**: Job M2M từ `lms-api` lấy token 8 giờ, gọi các API danh mục, upsert vào DB.
- **Điểm nối dữ liệu (bridge)**: ưu tiên dùng claim `identity` (nếu có) để match `SoDinhDanhCaNhan` trong OpenSync; luôn lưu `ttc_sub` để lookup login lần sau.

