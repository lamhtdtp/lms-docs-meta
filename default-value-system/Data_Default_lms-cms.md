# Data_Default — Việc cần làm trên `lms-cms`

**Nguồn yêu cầu:** `default-value-system/Data_Default.md`  
**Codebase:** `~/dtp/lms-cms` (React 18, Redux-Saga, Ant Design — package `i-test-cms`)  
**Backend liên quan:** `~/dtp/lms-api` — xem `Data_Default_lms-api.md`  
**Ngày rà soát:** 2026-05-21

## Phạm vi repo này

| Phạm vi spec | Trong `lms-cms`? |
|--------------|------------------|
| **CMS LCMS** (slide 2–7): gói TN, tài nguyên, filter, mô tả, mặc định | **Có** — phần lớn công việc FE nằm ở đây |
| **LCMS** (slide 8–12): chi nhánh, tiết học, GV–lớp, auto-assign theo khối | **Không** — không có màn tương ứng; dashboard chỉ **iframe** sang `dashboard.dtpsoft.vn/cms-lcms/school` |

**Ánh xạ UI:** menu **“Đóng gói nội dung”** → route `/sample-series-management` = **gói tài nguyên** (`Series` trên API).

---

## Tổng quan: đã có / thiếu

| # | Yêu cầu | Trạng thái trên `lms-cms` |
|---|---------|---------------------------|
| 1 | Filter **Loại gói** (6 giá trị) | **Chưa có** |
| 2 | **Mô tả** gói tài nguyên | **Chưa có** |
| 3 | Checkbox **tài nguyên mặc định** | **Chưa có** |
| 4 | Bảng ~24 TN mặc định + category | **Một phần** — matrix category khi đóng gói; không catalog/seed/auto |
| 5 | Phân quyền TN theo role GV/HS | **Một phần** — role trên gói trường (`ResourcePricingModal`) |
| 6 | Auto-assign theo khối / lớp mới | **Không** (LCMS) |
| 7 | Override theo chi nhánh | **Không** (LCMS) |
| 8 | Seed khi tạo chi nhánh | **Không** (LCMS) |
| 9 | Seed tiết học | **Không** (LCMS) |
| 10 | GV chọn lớp khi tạo user | **Không** (LCMS; API user có trong config nhưng **không có page**) |

---

## Chi tiết theo yêu cầu

### 1 — Filter Loại gói tài nguyên (slide 3)

**Hiện trạng**

- `ListPage.js` (đóng gói nội dung): lọc theo tên, môn, khối, series, nguồn — **không** có Loại gói.
- Không có constant enum KSNL / K12 / … trong `src/`.

**Cần làm trên `lms-cms`**

| Việc | File gợi ý |
|------|-------------|
| Constant `PACKAGE_TYPES` (6 label + value) | `src/constants/masterData.js` hoặc file mới |
| Thêm `Select` / filter vào `searchFields` | `src/containers/simple-series-management/ListPage.js` |
| Gửi query `packageType` (hoặc tên field BE thống nhất) khi `getList` | `redux/actions/series.js`, saga `redux/sagas/series.js` |
| Hiển thị cột Loại gói (tuỳ BA) | `ListPage.js` columns |

**Phụ thuộc BE:** field + filter trên `GET /series` — xem `Data_Default_lms-api.md` #1.

---

### 2 — Mô tả gói tài nguyên (slide 4)

**Hiện trạng**

- `SimpleSeriesManagementForm.js`: `name`, `nameEn`, `subjectId`, `gradeId`, `source`, `thirdPartySeriesId`, `priority` — **không** `description`.
- `handleSubmit` không gửi `description`.

**Cần làm**

| Việc | File gợi ý |
|------|-------------|
| `TextArea` / `Input` Mô tả (create + edit) | `SimpleSeriesManagementForm.js` |
| Map field vào payload | `handleSubmit` cùng file, `SavePage.js` nếu có map riêng |
| Optional: tooltip/cột trên list | `ListPage.js` |

**Phụ thuộc BE:** `series.description` — `Data_Default_lms-api.md` #2.

---

### 3 — Tick “Giá trị mặc định” khi thêm tài nguyên (slide 5)

**Hiện trạng**

- Checkbox category trên **dòng tài nguyên trong form đóng gói** (`TableListResource.js`) — là gán category cho **item trong series**, **không** phải `is_default` master resource.
- Form tạo KYNA: `KynaForm.js` — **không** có cờ mặc định.
- Không field `isDefault` trong payload resource.

**Cần làm**

| Việc | File gợi ý |
|------|-------------|
| Checkbox `Tài nguyên mặc định` trên form tạo/sửa TN | `KynaForm.js` (+ i-Test/Eduhome/Edufun nếu spec áp dụng chung) |
| Gửi `isDefault` trong body | Saga `redux/sagas/resource.js`, `apiConfig.resource.createResource` / `update` |
| (Tuỳ chọn) Badge/filter “chỉ TN mặc định” trên list catalog | Các `*ListPage.js` trong `containers/resource/` |

**Phụ thuộc BE:** `resource.is_default` — `Data_Default_lms-api.md` #3.

---

### 4 — Bảng ~24 tài nguyên mặc định (slide 6–7)

**Hiện trạng**

- **Có:** load `resource-categories` từ API; khi đóng gói, chọn TN + tick category (7 loại API: TEACHING, STUDYING, QUESTION, …).
- **Chưa có:** danh sách cố định 24 tên (DCR, DHA, …); nút “Thêm tất cả TN mặc định”; auto điền matrix khi tạo gói mới.

**Cần làm**

| Việc | File gợi ý |
|------|-------------|
| Config JSON 24 TN + map category (label VN) | `src/constants/defaultResources.js` (hoặc fetch từ BE sau seed) |
| Nút “Áp dụng tài nguyên mặc định” trên form gói | `SimpleSeriesManagementForm.js`, `DrawerSeriesManager.js` |
| Pre-check categories theo matrix | `TableListResource.js` / helper `utils/resource.js` |
| Hiển thị gợi ý 2 loại đề (KTTX vs test/midterm) | Copy + category `QUESTION` + subtype nếu BE hỗ trợ |

**Phụ thuộc BE:** seeder 24 bản ghi + `is_default` — `Data_Default_lms-api.md` #4.

---

### 5 — Phân quyền tài nguyên theo role (slide 9) — mức CMS có liên quan

**Hiện trạng**

- `ResourcePricingModal.js` + `OwnedResourceForm.js`: cấu hình **role** / trả phí trên **gói đã gán cho trường** (`school-resource-items`), bật bởi feature `configActiveRoles`.
- **Không** UI rule mặc định “GV = all, HS = 4 category” như slide 9.

**Cần làm (nếu product giao CMS)**

| Việc | File gợi ý |
|------|-------------|
| Mở rộng modal hoặc màn policy mặc định theo role | `ResourcePricingModal.js` hoặc màn mới |
| Đồng bộ label category VN với spec | `constants` + map từ `resource-categories` API |

**Phần lớn slide 9:** app **LCMS** (không repo này) + BE `classroomresource` — `Data_Default_lms-api.md` #5.

---

### 6–10 — LCMS (slide 8–12)

**Không triển khai trong `lms-cms`.** Cần app LCMS / school admin (repo khác hoặc iframe `cms-lcms`).

| # | Yêu cầu | Ghi chú |
|---|---------|---------|
| 6 | Auto-assign TN theo khối | BE + LCMS UI |
| 7 | Override TN chi nhánh | BE + LCMS UI |
| 8 | Seed khi tạo chi nhánh | BE orchestrator + LCMS form CN |
| 9 | Tiết học mặc định | LCMS + template period |
| 10 | GV ↔ lớp khi tạo user | LCMS user form + `teacherallocation` API |

Trong repo này chỉ có **tham chiếu gián tiếp:**

- `apiConfig.user.*` — `/Users/macbook/dtp/lms-cms/src/constants/apiConfig.js` — **không có container**.
- `key-code-history/ListPage.js` — hiển thị `user.classrooms` read-only.

---

## Màn hình / route hiện có (tham chiếu)

| Chức năng | Route | Thư mục chính |
|-----------|-------|----------------|
| Đóng gói nội dung (gói TN) | `/sample-series-management` | `containers/simple-series-management/` |
| Trường + gói đã gán | `/schools`, `/schools/:id` | `containers/school/` |
| TN i-Test / Eduhome / Edufun / KYNA | `/resource-*` | `containers/resource/` |
| Khối / môn hệ thống | `/grade-system`, `/subject-system` | `containers/grade-system/`, `subject-system/` |
| Dashboard trường (iframe LCMS) | `/dashboard-detail` | `containers/dashboard/dashboard-schools/` |

Menu: `src/constants/menuConfig.js`  
Routes: `src/constants/paths.js`, `src/routes/routes.js`

---

## Kết nối `lms-api`

| Cấu hình | File |
|----------|------|
| Base URL | `REACT_APP_CMS_API` → `cmsApiUrl` — `src/constants/index.js` |
| HTTP | `src/utils/api.js` (header `E-Token`, `ClientAppId`) |
| Endpoint map | `src/constants/apiConfig.js` |
| Saga | `src/redux/sagas/*.js` |

**Endpoint liên quan yêu cầu Data_Default:**

| Nghiệp vụ | Method + path (trên `cmsApiUrl`) |
|-----------|----------------------------------|
| List/create/update gói | `GET/POST/PUT /series`, `/series/:id` |
| Resource categories | `GET /resource-categories` |
| CMS resource (KYNA) | `GET/POST/PUT /cms/resources`, `/cms/resources/:id` |
| Catalog i-Test/Eduhome/Edufun | `/cms/resources/i-test-resources`, … |
| Gán gói cho trường | `POST /cms/resources/allocation` |
| School resource items + role | `GET/PUT /cms/resources/school-resource-items/...` |
| Roles (pricing modal) | `GET /roles` |

Sau khi BE bổ sung field: cập nhật **form payload + query params** tương ứng trong saga/ action.

---

## Thứ tự triển khai đề xuất (FE)

1. **#1 + #2** — filter + mô tả gói (chờ/ song song BE `series`).  
2. **#3** — checkbox `isDefault` trên form TN (chờ BE `resource`).  
3. **#4** — UX “áp dụng TN mặc định” trên form đóng gói (sau khi có data/flag từ BE).  
4. **#5** — chỉ nếu BA yêu cầu cấu hình role mặc định tại CMS trường; còn lại để LCMS.

**Ước lượng:** xem `default-value-system/est.md` (FE-1, FE-2, …).

---

## Điểm chặn

Giống `Data_Default_lms-api.md`: giờ tiết học, mapping môn/gói theo loại CN, danh sách ngày lễ, rule mã CN — **không chặn** hoàn thành CMS #1–4 nếu BE đã có field.

---

## Liên quan

- Spec: `default-value-system/Data_Default.md`  
- Backend: `default-value-system/Data_Default_lms-api.md`  
- Estimate: `default-value-system/est.md`
