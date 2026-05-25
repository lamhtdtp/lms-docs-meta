# Data_Default — Việc cần làm trên `lms-api`

**Nguồn yêu cầu:** `default-value-system/Data_Default.md`  
**Codebase:** `~/dtp/lms-api` (Java/Spring, `vn.dtpsoft.modules.*`)  
**Ngày rà soát:** 2026-05-21

## Ánh xạ domain (quan trọng)

Trong `lms-api`, **“gói tài nguyên” (CMS/LCMS)** tương ứng chủ yếu với entity **`Series`** (bảng `series`), không có bảng `resource_package` riêng.

| Khái niệm (spec) | Module / entity |
|------------------|-----------------|
| Gói tài nguyên | `series/` — `Series`, `SeriesResourceItem` |
| Tài nguyên | `resource/`, `myresource/` — `Resource` |
| Loại TN (7 cột slide 6–7) | `resourcecategory/` — `EResourceCategory` |
| Bật gói theo trường | `schoolresource/` — `SchoolResource` |
| Override theo chi nhánh | `branchresource/` — `BranchResource` |
| TN theo lớp + role | `classroomresource/` — `ClassRoomResource`, `ClassRoomResourceItemClassification` |
| Chi nhánh | `branch/` — `Branch` |
| Seed thủ công (template) | `templatedata/` — `ApplyTemplateDataService`, `POST /template-data/apply` |
| Tiết học | `period/`, `periodscope/` |
| Ngày lễ | `holiday/` |
| GV ↔ lớp | `teacherallocation/` — `TeacherAllocation` |

**Lưu ý:** `Branch.is_default` là **chi nhánh mặc định của trường**, không phải “tài nguyên mặc định”.

---

## Tổng quan: đã có / thiếu

| # | Yêu cầu (`Data_Default.md`) | Trạng thái trên `lms-api` |
|---|------------------------------|---------------------------|
| 1 | Filter **Loại gói** (6 giá trị) | **Chưa có** |
| 2 | Field **Mô tả** gói TN | **Chưa có** trên `Series` |
| 3 | Checkbox **tài nguyên mặc định** (`is_default`) | **Chưa có** trên `Resource` |
| 4 | Seed ~24 TN + matrix category | **Nền có** (enum category, type); **chưa seed / chưa auto-gán** |
| 5 | Phân quyền TN theo role GV/HS | **Một phần** — gán theo từng item lớp, không có rule mặc định toàn hệ thống |
| 6 | Auto-assign TN theo **khối** / lớp mới | **Một phần** — phân bổ thủ công, `fullGrade`; **không hook** khi tạo lớp |
| 7 | Override TN theo chi nhánh | **Một phần** — bật/tắt **Series** theo CN; **chưa** override role/category |
| 8 | Seed khi **tạo chi nhánh** | **Chưa có** orchestration; có template apply **thủ công** |
| 9 | Seed **tiết học** mặc định | **Một phần** — CRUD + template PERIOD; **chưa** auto khi tạo CN |
| 10 | GV chọn lớp khi **tạo user** | **Chưa có** trên `CreateUserForm`; có API `teacherallocation` riêng |

---

## Chi tiết theo yêu cầu

### 1 — Filter Loại gói tài nguyên (CMS)

**Hiện trạng**

- `Series` không có `loai_goi` / `package_type` (`Series.java` chỉ: name, grade, subject, source, status, priority, items).
- `SeriesCriteria` filter: `name`, `subjectId`, `gradeId`, `seriesId`, `source`, `status` — không có loại gói.
- `ESeriesGroup` (BOOK, PRIMARY, …) **không** map 6 giá trị spec (KSNL, K12, ĐH/CĐ, TTNN, Demo, Others).

**Cần làm trên `lms-api`**

| Việc | Vị trí gợi ý |
|------|----------------|
| Enum `EPackageType` (6 giá trị) | `modules/series/` hoặc `constant/` |
| Migration `series.package_type` (VARCHAR) | `src/main/resources/db/migration/` |
| Entity + DTO + form create/update | `Series.java`, `CreateSeriesForm`, `UpdateSeriesForm`, `SeriesCMSDto` |
| Filter list CMS/LMS | `SeriesCriteria.findByCriteria`, `SeriesController` GET list |
| API query param | Swagger + validation `@EnumFormat` |

---

### 2 — Mô tả gói tài nguyên

**Hiện trạng**

- `Resource` có `description` (cấp **tài nguyên**), không phải cấp **gói**.
- `Series` **không** có cột mô tả.

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| Migration `series.description` (TEXT, nullable) | DB migration |
| Map form/DTO | `CreateSeriesForm`, `UpdateSeriesForm`, mapper CMS |
| Create/update API | `SeriesService`, `SeriesController` |

---

### 3 — Tick “Giá trị mặc định” (tài nguyên)

**Hiện trạng**

- Không có `resource.is_default` (grep chỉ thấy `branch.is_default`).

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| Migration `resource.is_default` TINYINT | `resource/Resource.java` |
| CMS create/update | `ResourceCMSController`, form CMS |
| Logic: khi tạo `Series` mới → gợi ý / auto thêm item từ TN `is_default=true` | `SeriesService` + `SeriesResourceItemService` (sau #4) |

---

### 4 — Bảng ~24 tài nguyên mặc định (slide 6–7)

**Hiện trạng**

- `EResourceCategory`: `TEACHING`, `STUDYING`, `QUESTION`, `SUPPLEMENTARY`, `READING_ROOM`, `FUN_LEARNING`, `UNIT_TEST` — **gần** 7 cột spec (tên khác tiếng Việt).
- `EResourceType` (DCR, DHA, ESB, …) — **một phần** tên spec, không đủ 24 bản ghi master có sẵn.
- `SeriesResourceItem` + `series_resource_item_category` — sẵn sàng gắn category.
- **Không** có migration/seeder 24 dòng + matrix X/O như slide.

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| Seeder/migration: 24 `Resource` (+ `is_default=true`) | SQL hoặc `ApplicationRunner` / Flyway data script |
| Bảng mapping tên → category (có thể JSON/config) | `resources/seed/default-resources.json` + service |
| Phân biệt 2 loại **Ngân hàng đề thi** | Gắn `QUESTION` + subtype/tag nếu cần |
| Khi tạo gói (`Series`): copy item mặc định theo matrix | `SeriesService.create` |

**Phụ thuộc BA:** map chính xác tên slide (Teacher's Book, …) ↔ `EResourceType` / bản ghi mới.

---

### 5 — Phân quyền tài nguyên theo role (LCMS)

**Hiện trạng**

- `ClassRoomResourceItemClassification`: mỗi item gắn `Role` + `ResourceCategory` khi **phân bổ lớp**.
- `ResourceService` / `ResourceController`: lọc theo `ERole.TEACHER` / `STUDENT` khi đọc.
- **Không** có rule cố định: GV = tất cả; HS = STUDYING, SUPPLEMENTARY, READING_ROOM, FUN_LEARNING.

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| `ResourceRoleDefaultPolicy` (constants hoặc config) | Module mới hoặc `resourcecategory/` |
| Khi `ClassRoomResourceService` tạo classification → áp default nếu chưa chỉnh | `classroomresource/ClassRoomResourceService` |
| API list TN theo role + khối + CN | `ResourceController`, `ResourceService`, criteria |
| Test regression phân quyền HS/GV | Integration tests |

---

### 6 — Auto-assign tài nguyên theo khối; lớp mới kế thừa

**Hiện trạng**

- `ResourceController.getAllocateClassRoomResource`: nhận diện `fullGrade` khi đã phân bổ hết lớp trong khối.
- Tạo lớp (`ClassroomController` / `ClassroomService`) **không** gọi copy TN từ khối.
- `Series` gắn `grade_id` — có thể dùng làm khóa khối.

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| Sau `ClassroomService.save` (lớp mới trong khối đã có `ClassRoomResource` fullGrade) → clone allocation | `classroomresource/` + listener hoặc service orchestration |
| Hoặc: job đồng bộ khi thêm lớp vào khối | `ClassRoomResourceService` |
| Đảm bảo prerequisite: `SchoolResource` + `BranchResource` đã bật series | `schoolresource/`, `branchresource/` |

---

### 7 — Override tài nguyên theo chi nhánh

**Hiện trạng**

- `BranchResource`: bật/tắt **series** (school resource) theo `branch_id`.
- API: `GET/POST /resources/branch/allocation` (`ResourceController`).
- **Chưa** override quyền category/role theo CN (slide: “edit tùy theo từng Chi nhánh”).

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| (Tối thiểu) Giữ nguyên bật series theo loại CN khi seed #8 | `BranchResourceService` |
| (Mở rộng) Bảng/config `branch_resource_policy` hoặc JSON trên `Branch` | Migration + service đọc khi allocate/list |
| API admin chỉnh override | Controller mới hoặc mở rộng `ResourceController` |

---

### 8 — Data mặc định khi tạo chi nhánh

**Hiện trạng**

- `BranchController.create` → `branchService.saveBranch` — **chỉ lưu branch**, không seed.
- `CreateBranchForm`: client gửi `code` (không auto `CN_01`, `CN_02`…).
- **Không** có `branch_type` (Mầm non / Tiểu học / …).
- Có sẵn **cơ chế template** (không tự chạy):
  - `POST /template-data/apply` — SCHOOL_YEAR, GRADE, SUBJECT, PERIOD (`templatedata/ApplyTemplateDataService`).
  - `HolidayController` — CRUD, không seed.
  - `AppConstant.BRANCH_CODE_DEFAULT = "CN_01"` chỉ khi tạo **school** (`SchoolMapper`), không khi tạo branch mới.

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| `BranchCreatedOrchestrator` (service) sau `saveBranch` | `branch/BranchService` hoặc event listener |
| `branch_type` enum + field trên `Branch` + form | Migration, `CreateBranchForm`, `BranchMapper` |
| Auto mã CN: `CN_{seq}` theo school | `BranchRepository` + generator trong `BranchService` |
| Năm học K12: HK1 01/08, HK2 01/02, kết thúc 31/07 năm sau | Gọi `SchoolYearService.createBulk` với form tính từ `Year.now()` |
| Bật khối/môn theo loại CN | `GradeSystemVisibleService`, `SubjectSystemVisibleService` hoặc template GRADE/SUBJECT |
| Bật gói TN theo loại CN | `SchoolResourceService` + `BranchResourceService` (cần **mapping từ chuyên môn**) |
| Seed ngày lễ dương lịch | `HolidayService.seedDefaults(branchId, schoolYearId)` |
| Feature flag / idempotent (tránh seed lại khi update branch) | Trong orchestrator |

**Phụ thuộc:** mapping môn + gói TN theo cấp (# slide 10); danh sách ngày lễ đầy đủ (BA).

---

### 9 — Tiết học mặc định

**Hiện trạng**

- `Period` + `PeriodScope`; `PeriodService.createBulk`; template type `PERIOD` trong `ApplyTemplateDataService`.
- **Không** bundle thời gian đầy đủ (spec chỉ có Sáng tiết 1: 07:00–07:45).
- **Không** gọi khi tạo chi nhánh.

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| Template PERIOD đầy đủ (Thứ 2–CN, Sáng/Chiều, tiết + ra chơi) | `templatedata` + JSON seed |
| Gọi từ orchestrator #8 | `ApplyTemplateDataService.handleApplyPeriodTemplate` |
| Cho phép CN chỉnh sau (đã có CRUD) | `PeriodController` |

**Phụ thuộc:** Mr. Phục — giờ các tiết còn lại.

---

### 10 — Phân bổ GV theo lớp tại màn tạo người dùng

**Hiện trạng**

- `CreateUserForm` — **không** có `classroomIds` / head teacher / subject teacher.
- `UserController.create` — chỉ tạo user.
- `POST /users/assign-branch-role` — gán **môn** cho GV (`TeacherSubjectService`), không lớp.
- `teacherallocation/TeacherAllocationController` — `/teacher-allocations/subject-teacher`, `/head-teacher` (bước riêng).

**Cần làm**

| Việc | Vị trí gợi ý |
|------|----------------|
| Optional `List<Integer> headClassroomIds`, `subjectTeacherAllocations` trên form | `user/form/CreateUserForm`, `UpdateUserForm` |
| Trong `UserService` sau tạo user + role TEACHER → gọi allocation | `UserService`, `TeacherAllocationService` |
| Validation: **không bắt buộc** lớp | Bỏ `@NotNull` trên classroom fields |
| API autocomplete lớp theo `branchId` (nếu chưa đủ) | `ClassroomController` / existing list API + pagination/search |

---

## API / module tham chiếu nhanh

| Chức năng | Endpoint / class (đã có) |
|-----------|---------------------------|
| Series CMS | `/series` — `SeriesController` |
| Resource CMS | `/cms/resources` — `ResourceCMSController` |
| Phân bổ CN | `GET/POST /resources/branch/allocation` |
| Phân bổ lớp | `GET/POST /resources/classroom/allocation` |
| Category theo role | `GET /resources/resource-categories` |
| Tạo CN | `POST /branches` — `BranchController` |
| Apply template | `POST /template-data/apply` |
| Tiết học | `/periods` |
| Ngày lễ | `/holidays` |
| GV allocation | `/teacher-allocations/*` |

---

## Thứ tự triển khai đề xuất (BE)

1. **Schema nền:** #1 `package_type`, #2 `description`, #3 `resource.is_default` (migration).  
2. **Seed data:** #4 (24 resources + matrix).  
3. **Policy & allocate:** #5, #6, #7 (mở rộng dần).  
4. **Branch bootstrap:** #8 (orchestrator) → gắn #9 period + holiday.  
5. **User flow:** #10 (tách PR nhỏ, ít phụ thuộc seed).

**Song song FE/CMS:** filter + form mô tả + checkbox (xem `est.md` — FE-1, FE-2, …).

---

## Điểm chặn (không chỉ dev)

| # | Nội dung | Owner |
|---|----------|--------|
| 1 | Giờ đầy đủ bảng tiết (Sáng 2–5, Chiều …) | Mr. Phục |
| 2 | Mapping môn + gói TN theo loại chi nhánh | Chuyên môn |
| 3 | Danh sách ngày lễ seed | BA / Product |
| 4 | Rule mã `CN_XX` (prefix, padding) | BA / Dev |

---

## Liên quan

- Ước lượng manday: `default-value-system/est.md`  
- Spec gốc: `default-value-system/Data_Default.md`
