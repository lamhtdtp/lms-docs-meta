---
name: lms-fe-dtpsoft
description: >-
  Guides work on the DTP LMS frontend (Next.js, lms-fe). Use when the user mentions
  lms-fe, ~/dev/dtp/lms-fe, Next.js LMS parent/student UI, or paths under pages/,
  components/, hooks/; when adding routes, React Query data fetching, axios calls,
  react-intl messages, auth cookies/middleware, or SCSS in this app.
---

# LMS FE (DTP) — agent skill

Canonical clone path: **`~/dev/dtp/lms-fe`**. Targets the **`lms-fe`** package (DTP Education).

## Stack (verify in repo, do not invent versions)

- **Next.js** 14.x (**Pages Router** — `pages/`, not App Router).
- **React** 18; **Node** `>=18.17.0` (`package.json` `engines`).
- **Data:** `@tanstack/react-query` v5, **axios**.
- **i18n:** `react-intl`; extract IDs via `yarn i18n` / `npm run i18n` (FormatJS CLI + `formatter.js` → `locales/en.json`).
- **Forms / UI:** `rc-field-form`, `yup`, Radix / Base UI, `sonner` toasts, **Sass** (`styles/*.scss`).
- **Auth session:** `cookies-next` + keys from **`constants/constant.js`** (`storageKeys`, `API_BASE_URL`, feature flags).

## Scripts & ports

- **Dev:** `yarn dev` / `npm run dev` → Next dev on **port `4060`** (`next dev -p 4060`).
- **Prod start:** `next start -p 3042`.
- **Lint:** `next lint --fix`.
- README may mention another port; **trust `package.json` scripts** for local URLs.

## Path alias

- **`jsconfig.json`:** `"@/*"` → repo root. Imports look like `@/components/...`, `@/constants/...`, `@/hooks/...`, `@/utils/...`.

## App shell

- **`pages/_app.js`:** wraps pages with **`QueryProvider`** (`contexts/QueryProvider.js` — TanStack Query defaults: no refetch on focus, `retry: false`; mutation `meta.invalidates` pattern), **`AppWrapper`**, global SCSS, **`sonner`** `<Toaster />`.
- **`middleware.js`:** delegates to **`middlewares/`** chain; matcher skips `api`, `_next/static`, `_next/image`.

## API & env

- Base URL: **`API_BASE_URL`** from `NEXT_PUBLIC_API_BASE_URL` (`constants/constant.js`). Integration host: **`INTEGRATION_API_BASE_URL`**.
- Do not commit real `.env`; follow **`.env.example`** for variable names.
- Backend response shape for LMS API aligns with **`ApiMessageDto`** (see skill **`lms-api-dtpsoft`** in `skill/lms-api/SKILL.md` in this meta repo).

## Auth / SSO helpers

- **`utils/auth.js`:** cookie helpers (`setAuthCookie`, `deleteAllAuthCookies`, `clearUserSession` → SSO URL), `roleValidator`, `extractMetaParam`.
- **`utils/url.js`** (and related): SSO URL / cookie domain helpers used by auth flows.

## Conventions for agents

- Prefer **existing hooks** under `hooks/` and **shared components** under `components/` before adding parallel abstractions.
- New strings: use **`react-intl`** (`defineMessages` / `useIntl`) and run **`yarn i18n`** when adding user-visible copy (per project workflow).
- Match **ESLint** (`.eslintrc.json`, `eslint-config-next` + plugins) and **Prettier** (`.prettierrc`); respect **`simple-import-sort`** if configured.
- **`next.config.js`:** `images.remotePatterns`, `rewrites`, `headers`, SVGR webpack rule — extend only when needed for assets or routing.
- Keep diffs scoped; avoid renaming routes or global providers without an explicit request.

## Quick verify after edits

From `~/dev/dtp/lms-fe`: **`yarn lint`** and/or **`yarn build`** when the change touches types, routing, or imports that Next resolves at build time.
