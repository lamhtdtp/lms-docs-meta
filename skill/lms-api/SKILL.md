---
name: lms-api-dtpsoft
description: >-
  Guides work on the DTP LMS backend (Spring Boot, vn.dtpsoft). Use when the user
  mentions lms-api, ~/dev/dtp/lms-api, dtpsoft LMS API, or edits Java under
  vn.dtpsoft; when adding REST endpoints, JPA entities, schedulers, or outbound
  HTTP; when integrating SSO (doe) or payroll sync into this codebase.
---

# LMS API (DTP) — agent skill

Canonical clone path: **`~/dev/dtp/lms-api`**. This skill applies when that tree is open or when the task clearly targets that project (artifact `lms-api`, group `dtpsoft.vn`).

## Stack (do not guess versions)

- **Spring Boot** 2.7.x, **Java** 17 (compiler target may align with parent), **packaging:** `war`.
- **Persistence:** Spring Data JPA, MySQL.
- **Security:** Spring Security + JWT (`jjwt` 0.9.x).
- **API docs:** Springfox Swagger 2.8.x.
- **Mapping / boilerplate:** MapStruct, Lombok.
- **App entry:** `vn.dtpsoft.SpringCoreApplication` — JVM default timezone set to **UTC** at startup; client display constants use `Asia/Ho_Chi_Minh` where relevant (`AppConstant`).

## Package layout

- Root: `vn.dtpsoft` — config, security, schedules, `service`, `constant`, `exception`, `util`, `model`.
- Features: **`vn.dtpsoft.modules.<feature>`** — typical pieces: `*Controller`, `*Service`, `*Repository`, entity, `dto/`, `form/`, optional `*Mapper`, `*Criteria`.
- Shared web base: **`vn.dtpsoft.modules.BaseController`** — helpers such as `makeSuccessResponse`, `makeErrorResponse`, session/current-user helpers; extend this for REST controllers unless the module already uses another base.

## REST & responses

- Controllers use `@RequestMapping` on class; return **`ApiMessageDto`**-style envelopes via `BaseController` helpers (`result`, `data`, `message`, `code`).
- List/pagination: follow existing **`ResponseListDto`**, **`ListBaseCriteria`** patterns in the same module or neighbors.
- Errors: **`BadRequestException`**, **`AppErrorCodes`** — match existing throw style.

## Security whitelist

- Unauthenticated paths live in **`vn.dtpsoft.constant.AppConstant`** — `AUTH_WHITELIST` and `PATH_BYPASS_DOMAIN`. Any new public endpoint must be added in **both** arrays when required by the existing security config (verify alongside `WebSecurityConfig` or equivalent if touching auth).

## Outbound HTTP

- Prefer **`vn.dtpsoft.service.HttpService`** (RestTemplate) for third-party GET/POST; it uses Jackson with **`FAIL_ON_UNKNOWN_PROPERTIES = false`** — DTOs for external APIs do not need every JSON field.
- Do not log secrets or full bearer tokens.

## Scheduling

- **`@EnableScheduling`** on application class; cron-style jobs live under **`vn.dtpsoft.schedules`** (e.g. `ScheduledTasks`). New sync jobs should follow existing logging and service-injection patterns.

## Domain anchors (for mapping / sync work)

- **Multi-tenant shape:** `School` → `Branch` → academic entities (`SchoolYear`, `Grade`, `Classroom`, …) often scoped by branch.
- **Users:** `User` (`firstName`, `lastName`, `citizenIdentityCode`, `gender`, `birthday`, `school`, …); roles via **`UserBranchRole`** + **`Role`**.
- **Enrollment:** `ClassroomStudent` links `User` (student) to `Classroom`.
- **Teacher–class–subject:** **`TeacherAllocation`** (`ETeacherAllocation`: `HEAD`, `SUBJECT`, `ASSISTANT`) with `Classroom` and optional `Subject`; distinguish from **`TeacherSubject`** (teacher–subject–branch without per-class row).

## Implementation rules for agents

- Match existing naming, layering, and annotation style in the touched module; do not introduce a second HTTP client stack without reason.
- Keep changes scoped to the requested feature; avoid unrelated refactors.
- After structural edits, run **`mvn -q -DskipTests compile`** from the repo root unless the user prefers tests on.
