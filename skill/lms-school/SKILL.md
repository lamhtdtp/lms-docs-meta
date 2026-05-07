---
name: lms-school-dtpsoft
description: >-
  Guides work on the DTP LMS school admin app (Next.js, lms-school). Use when the
  user mentions lms-school, ~/dev/dtp/lms-school, school admin LMS, or paths under
  pages/, components/Pages/, services/api/, hooks/; when adding admin routes,
  TanStack Query + axios APIs, react-intl, timetable/teaching-plan UI, DOE sync
  tools, FullCalendar, Quill, or DnD Kit in this codebase.
---

# LMS School (DTP) — agent skill

Canonical clone path: **`~/dev/dtp/lms-school`**. Targets the **`lms-school`** package (DTP Education) — **admin / school** web app (teachers, staff), distinct from parent-student **`lms-fe`** (`skill/lms-fe/SKILL.md`).

## Authoritative in-repo guide

Read **`AGENTS.md`** at the root of `lms-school` first for structure, conventions, API service patterns, and i18n workflow. This skill only captures what agents need **before** opening that tree.

## Stack (verify in repo)

- **Next.js** 14.x, **Pages Router** (`pages/`), **JavaScript only** (no TypeScript).
- **React** 18.3.x; **Node** `>=18.17.0`.
- **Data:** `@tanstack/react-query` v5, **axios**; API modules under **`services/api/`** (`config.js` → `apiConfig`, `fetcher.js`, per-domain `*.js`).
- **i18n:** `react-intl`; extract: **`yarn intl-extract-messages`** (FormatJS → `locales/en.json`).
- **UI:** Radix / Base UI, `rc-field-form`, `rc-picker`, `rc-select`, **Sass** (incl. **`.module.scss`**), `sonner`, **nprogress** (`NavigateProgress` in `_app`).
- **Domain libs:** **FullCalendar**, **Quill** (global CSS imported in `pages/_app.js`), **@dnd-kit**, **ApexCharts**, **exceljs**.

## Scripts & ports

- **Dev:** `yarn dev` → **port `3003`** (`next dev -p 3003`).
- **Prod start:** `next start -p 3041`.
- **Lint:** `next lint --fix`.

## Path alias

- **`jsconfig.json`:** `"@/*"` → project root (no `src/` folder).

## App shell

- **`pages/_app.js`:** `QueryProvider` + `AppWrapper`, global SCSS + Quill + editor SCSS, **`NavigateProgress`**, `sonner` toaster.
- **`contexts/index.js`:** exports `AppProvider`, `QueryProvider`, `useAppContext` (from `utils/create-ctx`).
- **`middleware.js`:** chain in **`middlewares/`**; matcher skips `api`, `_next/static`, `_next/image`.

## API & env

- **`constants/constant.js`:** `API_BASE_URL`, `INTEGRATION_API_BASE_URL`, date formats, **`ENABLED_FEATURES`**, site flags (`siteEnableOnlineClass`, dashboard embed, …), optional **`DOE_SYNC_DATA_PAYLOAD`** from env.
- Prefer **central `services/api/config.js`** for endpoint keys; use domain files + **`fetcher.js`** patterns already in the repo.
- Backend envelope aligns with **`lms-api`** (`ApiMessageDto`) — see **`skill/lms-api/SKILL.md`** in this meta repo.

## Layout vs `lms-fe`

- **`components/Pages/`** is grouped by domain (`ManageClass`, `ManageUser`, `Assign`, `Tool`, …) per **`AGENTS.md`**.
- **`services/`** layer is first-class here; do not bypass it with ad-hoc axios in pages unless the codebase already does for that feature.

## After edits

From `~/dev/dtp/lms-school`: **`yarn lint`** and **`yarn build`** when routing, env usage, or imports change materially.
