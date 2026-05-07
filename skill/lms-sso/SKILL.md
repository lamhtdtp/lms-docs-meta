---
name: lms-sso-dtpsoft
description: >-
  Guides work on the DTP LMS SSO broker app (Next.js, lms-sso). Use when the user
  mentions lms-sso, ~/dev/dtp/lms-sso, OAuth login broker, DOE HCM SSO, or paths
  under pages/, components/, utils/; when wiring authorization_code flows, token
  cookies, redirects to lms-fe/lms-school, or env flags like HOSTS_ENABLE_DOE_SSO.
---

# LMS SSO (DTP) — agent skill

Canonical clone path: **`~/dev/dtp/lms-sso`**. **`lms-sso`** is the **OAuth / SSO front** used to broker login for LMS apps (e.g. redirect, callback, session cookies) — slimmer than **`lms-fe`** / **`lms-school`**.

## Stack (verify in repo)

- **Next.js** 14.x, **Pages Router** (`pages/`).
- **React** 18; **Node** `>=18.17.0` (`package.json` `engines`).
- **Data:** `@tanstack/react-query` v5, **axios**; **`QueryClient` is created inline in `pages/_app.js`** (same defaults style as other DTP Next apps: `retry: false`, `refetchOnWindowFocus: false`, mutation `meta.invalidates`).
- **Forms / UI:** `rc-field-form`, `rc-picker`, `rc-select`, **yup**, **Radix** dialog/collapsible, **sonner**, **Sass** (`styles/`).
- **i18n:** `react-intl`; extract: **`yarn i18n`** → `locales/en.json` (FormatJS CLI + `formatter.js`).

## Scripts & ports

- **Dev:** `yarn dev` → **port `3004`** (`next dev -p 3004`).
- **Prod start:** `next start -p 3040`.
- **Lint:** `next lint --fix`.

## Path alias

- **`jsconfig.json`:** `"@/*"` → project root (no `src/`; code at repo root like other Next LMS apps).

## App shell

- **`pages/_app.js`:** `QueryClientProvider` + `HydrationBoundary` + **`AppWrapper`** + `Toaster` + **ReactQueryDevtools**; global **`@/styles/globals.scss`**, **`select.scss`**.
- **`middleware.js`:** delegates to **`middlewares/`** chain (same pattern as `lms-fe` / `lms-school`).

## API & SSO-related env

- **`constants/constant.js`:** `API_BASE_URL`, `INTEGRATION_API_BASE_URL`, `storageKeys` (access/refresh/tokenType/redirect/meta/branch/role), **`ROLES_CODE`**, **`CLASSROOM_CATEGORY`**, …
- **DOE / HCM:** `HOSTS_ENABLE_DOE_SSO`, `DOE_HCM_API_BASE_URL`, `DOE_HCM_USERNAME`, `DOE_HCM_PASSWORD` — used for **DOE HCM** integration paths; treat as **secrets** on the server side where applicable.
- Follow **`.env.local.example`** for local setup; never commit real `.env`.

## Relationship to other apps

- **`lms-api`** — user resolution / internal APIs after SSO (see **`skill/lms-api/SKILL.md`**).
- **`lms-fe`**, **`lms-school`** — SPs that users return to post-login (see **`skill/lms-fe`**, **`skill/lms-school`**).

## Conventions for agents

- Preserve **cookie key names** and redirect URL contracts shared with FE apps; changing them requires coordinated updates across repos.
- Do not log raw tokens or passwords.
- Match existing **axios** and **react-query** usage in this repo before adding new HTTP layers.

## Verify after edits

From `~/dev/dtp/lms-sso`: **`yarn lint`** and **`yarn build`** when auth flow, middleware, or env-driven branches change.
