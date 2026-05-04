# Ước lượng manday (revise) — module xin nghỉ phép

**Cơ sở:** các file trong `xin-nghỉ-phép/tech/` — `parent.md`, `student.md`, `teacher.md`, `admin.md` — cùng đặc tả `xin-nghỉ-phép/` và `SKILL.md`.  
Đối chiếu bản gốc: `xin-nghỉ-phép/est1.md`.

## Bảng tham chiếu doc (`tech/`) → hạng mục manday

Mỗi file tech mô tả một **luồng/vai**; cột **§ est2** trỏ tới **mã hạng mục** trong mục «Thang manday theo khối» bên dưới (**BE-A** … **BE-D**, **FE-fe-P**, **FE-fe-S**, **FE-sch-T**, **FE-sch-A**, **INT**).

| Đường dẫn doc | Trọng tâm nội dung | § est2 (hạng mục) | Khoảng manday *(planning theo doc)* |
|----------------|-------------------|-------------------|-------------------------------------|
| `xin-nghỉ-phép/tech/parent.md` | PH — FR-01…03; API list/create/detail scope PH; `lms-fe` | **FE-fe-P**; **BE-A** (nhánh PH); xử lý overlap → **BE-D** | FE **9–15**; BE **5–10** *(phần PH trong BE-A; không cộng trùng vào tổng BE đã gộp)* |
| `xin-nghỉ-phép/tech/student.md` | HS — HS-01/02 chỉ đọc; scope `student_id`; `lms-fe` | **FE-fe-S**; **BE-A** (nhánh STUDENT) | FE **3–6**; BE **2–4** |
| `xin-nghỉ-phép/tech/teacher.md` | GVCN — tab lớp, duyệt HEAD; review + attendance; `lms-school` | **FE-sch-T**; **BE-B** (TEACHER/HEAD); **BE-C** (sau duyệt); regression → **BE-D** | FE **9–16**; BE **15–30** *(tương ứng phần GV trong B+C — **dùng chung service** với Admin)* |
| `xin-nghỉ-phép/tech/admin.md` | Admin/Super Admin — list đa chi nhánh, duyệt; `lms-school` | **FE-sch-A**; **BE-B** (ADMIN/SUPER_ADMIN); dùng chung job **BE-C** | FE **7–14**; BE **6–12** *(nhánh Admin trong B; C không implement lần hai nếu đã có từ teacher)* |
| `xin-nghỉ-phép/tech/est2.md` | *(meta)* Chỉ tổng hợp ước lượng — **không** là manday riêng | — | **—** |

**Cách đọc:** các ô **BE** trong bảng trên là **phân bổ theo góc nhìn sản phẩm** để trace doc; **tổng BE 33–66 md** vẫn lấy theo bảng tổng hợp **BE-A … BE-D** (một lần implement API review + attendance). Không cộng nguyên các ô BE của từng dòng doc để tránh nhân đôi **BE-B/BE-C**.

**Mã § (đồng nhất trong file):**

| Mã | Ý nghĩa |
|----|---------|
| **BE-A** | Nền leave (entity, CRUD/list/detail theo vai PH/HS) |
| **BE-B** | Review / duyệt (role HEAD / Admin / batch) |
| **BE-C** | Attendance sau APPROVED |
| **BE-D** | QA BE, overlap, khóa điểm, regression |
| **FE-fe-P** | `lms-fe` — Parent |
| **FE-fe-S** | `lms-fe` — Student |
| **FE-sch-T** | `lms-school` — Teacher / tab lớp |
| **FE-sch-A** | `lms-school` — Admin manage-system |
| **INT** | Tích hợp đa vai & UAT (mục riêng trong est2) |

## Điều chỉnh so với est1 (tại sao revise)

| Điểm | Ảnh hưởng ước lượng |
|------|---------------------|
| **Hai ứng FE:** PH/HS trên `lms-fe`, GV/Admin trên `lms-school` | FE không gộp một codebase; cần **hai nhánh UI** + hai lần gắn route/menu (ước lượng tách rõ bên dưới). |
| **BE một domain** + filter/quyền theo vai | Trùng với giả định est1 — **không** nhân 4 API lõi. |
| **Tích hợp điểm danh** (`rollcall`, BR-ATT-16…20) khi `APPROVED` | Thấy rõ trong `teacher.md` / `admin.md` — **BE core** chiếm phần lớn rủi ro/thời gian (test + edge TKB). |
| **GVCN vs Admin** | Teacher: tab `manage-class/[id]` + `TeacherAllocation.HEAD`. Admin: `manage-system` + filter đa chi nhánh — **Admin FE** có thể nhỉnh hơn “chỉ copy GV” vì filter/bảng rộng. |

Vẫn là **ballpark**; chốt số cần backlog task + spike attendance.

## Thang manday theo khối (sau khi đọc tech/)

### Backend (`lms-api`) — manday

| Mã § | Hạng mục | Nội dung (theo tech) | Khoảng |
|------|----------|------------------------|--------|
| **BE-A** | Nền leave | Entity, migration, repo, criteria, mapper, `GET/POST` PH, `GET` list/detail theo scope PH/HS/STUDENT | **10–18** |
| **BE-B** | Review | `PUT`/`PATCH` duyệt; guard TEACHER=HEAD; guard ADMIN/SUPER_ADMIN + branch; batch một chi nhánh; validate `PENDING`, reject reason | **8–14** |
| **BE-C** | Attendance | Sau `APPROVED`: map buổi→tiết, chỉ slot tồn tại, `EXCUSED_ABSENCE` + source `LEAVE_REQUEST`, không đè MANUAL mới hơn (theo SKILL) | **10–22** |
| **BE-D** | QA BE / fix | Overlap BR-LEAVE-05, khóa điểm (nếu bật), regression rollcall | **5–12** |
| | **Tổng BE** | | **33–66 manday** |

*Nếu phase 1 **chỉ** duyệt đơn + cập nhật trạng thái **chưa** đụng attendance: trừ **BE-C** xuống ~**3–8** manday (nhưng **lệch FRS** — chỉ interim.)*

### Frontend — `lms-fe` (PH + HS) — manday

| Mã § | Hạng mục | Nội dung | Khoảng |
|------|----------|----------|--------|
| **FE-fe-P** | Parent | FR-01 list + filter + empty + pagination; FR-02 modal tạo; FR-03 chi tiết; `schoolYear` guard | **9–15** |
| **FE-fe-S** | Student | HS-01/02 chủ yếu reuse list/detail (không tạo đơn) | **3–6** |
| *(chung)* | Chung FE | `config.js`, hooks, i18n, polish | **1–3** |
| | **Tổng lms-fe** | | **13–24 manday** |

### Frontend — `lms-school` (GV + Admin) — manday

| Mã § | Hạng mục | Nội dung | Khoảng |
|------|----------|----------|--------|
| **FE-sch-T** | Teacher | Tab `ClassDetailLayout`, trang `manage-class/[id]/leave-request`, bảng + GV-02 modal approve/reject | **9–16** |
| **FE-sch-A** | Admin | Trang `manage-system`, entry `ManageSystem/data.js`, AD-01 filter chi nhánh/lớp + AD-02 (reuse modal logic) | **7–14** |
| *(chung)* | Chung FE | API layer, permission/breadcrumb | **1–2** |
| | **Tổng lms-school** | | **17–32 manday** |

### Tích hợp đa vai & UAT

| Mã § | Nội dung | Khoảng |
|------|----------|--------|
| **INT** | E2E flow PH tạo → GV/Admin duyệt → HS/PH xem; lệch spec Figma | **4–10 manday** *(thường chia FE/QA; ghi nhận ở đây như buffer chức năng)* |

## Tổng hợp (est2)

| Cách đọc | Khoảng manday |
|----------|----------------|
| **BE** | **33–66** |
| **FE** (`lms-fe` + `lms-school`) | **30–56** *(13–24 + 17–32)* |
| **Buffer tích hợp / UAT** | **4–10** |
| **Tổng (một dev full-stack tuần tự)** | **67–132 manday** |

So với **est1** (64–130 tổng): **trùng bậc**; est2 **tách rõ** BE attendance, **tách hai FE**, nên dùng est2 khi planning team có **2 repo FE**.

## Song song dev (wall-clock gợi ý)

| Đội hình | Ghi chú |
|----------|---------|
| **1 BE + 1 FE** (FE làm cả hai app hoặc 2 FE chia `lms-fe` / `lms-school`) | Wall-clock ~**max(BE, FE tổng) + 0,25–0,5** cho chờ API contract + merge |
| **1 BE + 2 FE** (một người `lms-fe`, một `lms-school`) | FE wall-clock ~**max(13–24, 17–32)** ≈ **17–32 md** song song; tổng dự án thường **~2–4 tháng** tùy scope attendance & polish |

## Điều kiện để số “nhỏ” trong dải

- Spike xong mapping buổi → tiết + xác nhận với TKB hiện tại.
- Reuse tối đa bảng/modal từ enrollment request / manage-system.
- Batch duyệt **một chi nhánh** / lần — không mở rộng multi-branch trong v1.

## Điều kiện để số “lớn” trong dải

- Attendance + audit đầy đủ ngay v1.
- BR overlap / khóa điểm / nhiều edge từ BA.
- Hai Figma (GV vs Admin) lệch nhiều → không reuse modal.

## Điều chỉnh khi dùng AI (Cursor)

Khi **vibe coding** với Cursor (scaffold, boilerplate, pattern sẵn có trong repo), có thể coi tổng **est2** rút bớt tương đối — **FE** và **BE-A** thường giảm mạnh nhất; **BE-C** (attendance theo FRS) và **INT** / **BE-D** (QA, E2E, sửa edge) thường **giảm ít hơn** vì vẫn cần review con người, spike nghiệp vụ, và chạy UAT.

- **Gợi ý hệ số tổng (ballpark):** nhân tổng **67–132 manday** với **~0,65–0,85** → khoảng **~45–95 md** một dev full-stack tuần tự, tùy độ phức tạp BR và chất lượng prompt/review.
- **Không** giảm mạnh các phần: spike buổi→tiết & TKB, PR review, chỉnh lệch BA/Figma, attendance + audit đúng SKILL.

---

*Ước lượng revise: đồng bộ với folder `xin-nghỉ-phép/tech/`. Cập nhật khi có sprint breakdown hoặc quyết định phase attendance.*
