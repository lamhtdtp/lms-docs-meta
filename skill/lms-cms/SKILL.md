---
name: lms-cms-dtpsoft
description: >-
  Guides work on the DTP LMS CMS admin UI (Create React App + Craco, lms-cms).
  Use when the user mentions lms-cms, ~/dev/dtp/lms-cms, i-test-cms package, Ant
  Design CMS, or paths under src/containers, src/components, src/redux, src/routes;
  when adding Redux actions/sagas, react-router-dom v6 routes, Ant Design Pro
  Layout, or Chart.js / react-quill screens in this codebase.
---

# LMS CMS (DTP) — agent skill

Canonical clone path: **`~/dev/dtp/lms-cms`**. NPM package name in `package.json` is **`i-test-cms`** (legacy); the repo folder is **`lms-cms`**.

## Stack (verify in repo)

- **Create React App** (`react-scripts` 5.x) with **Craco** (`@craco/craco` 7.x) — not Next.js.
- **React** 18.2, **react-router-dom** v6.
- **State:** **Redux** 4.x + **redux-saga** + **redux-actions**; store from **`src/redux/store.js`**.
- **UI:** **Ant Design** 5.x + **`@ant-design/pro-layout`**; **Sass**; CSS modules via Craco (`auto: true`, `camelCaseOnly` locals).
- **Other:** **Chart.js** / **react-chartjs-2**, **react-quill**, **jwt-decode**, **dayjs**, **query-string**.

## Scripts

- **Dev:** `npm start` / `yarn start` → **`craco start`** (default CRA port **3000** unless overridden).
- **Build:** `npm run build` / `yarn build` → **`craco build`** (output under **`build/`**).
- **Test:** `craco test`.

## Path alias

- **`jsconfig.json`** + **`craco.config.js`:** `@` → **`src/`** (e.g. `@/redux/store`, `@/routes`).

## Source layout (high level)

- **`src/index.js`** — mounts `<App />`, imports global SCSS from **`src/assets/scss/index.scss`**.
- **`src/App.js`** — **`<Provider store={store}>`** + **`RootRoutes`** from **`@/routes`**.
- **`src/routes/`** — route table (e.g. `routes.js`).
- **`src/containers/`** — page-level / connected views.
- **`src/components/`** — reusable UI.
- **`src/redux/`** — `actions/`, `reducers/`, `sagas/`, `store.js`, `helper.js`.

## Conventions for agents

- Follow existing **redux-saga** and **router** patterns; do not introduce a second global store (e.g. Zustand) without an explicit request.
- Use **Ant Design** APIs consistent with v5 already in the tree; check existing form/table patterns before inventing new ones.
- ESLint extends **`react-app`**; `react-hooks/exhaustive-deps` is **off** in `package.json` — do not “fix” that globally unless asked.
- Keep changes scoped; match import style and folder layout under `src/`.

## Env

- Use **`.env.sample`** as the variable checklist; do not commit secrets.

## Related repos (DTP LMS)

- **`lms-api`** — backend consumed by CMS (see **`skill/lms-api/SKILL.md`** in this meta repo).

## Verify after edits

From `~/dev/dtp/lms-cms`: **`yarn build`** or **`npm run build`** to catch Craco/webpack and import issues.
