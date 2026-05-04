# Hướng dẫn đồng bộ OpenSync (TTC) → LMS API — mapping field & cách làm

**Nguồn tài liệu API:** `HuongDan_OpenSyncAPI_DoiTac.docx` (ASC SCHOOL — OpenSync).

**Codebase đối chiếu:** `~/dev/dtp/lms-api` (Spring Boot, module `vn.dtpsoft.modules.*`).

**Bài toán:** Khi LMS gọi OpenSync để đồng bộ danh mục, response JSON có tên field và cấu trúc riêng; cần biết **map sang entity/DTO nội bộ** thế nào và **chỗ nào cần quy ước thêm**.

---

## 1. Kết quả rà soát `lms-api`

- Trong source **chưa có** client hoặc constant gọi trực tiếp OpenSync (`opensync`, `/api/opensync/thongtinhocsinh`, `client_credentials` cho OpenSync, v.v.).
- HTTP gọi bên thứ ba dùng chung `vn.dtpsoft.service.HttpService` (RestTemplate). ObjectMapper dùng `FAIL_ON_UNKNOWN_PROPERTIES = false` khi đọc JSON → **có thể định nghĩa DTO chỉ gồm field cần dùng**, không bắt buộc mirror toàn bộ payload.
- Việc đồng bộ OpenSync nên triển khai như một **module/service mới** (ví dụ package `opensync` hoặc `integration.ttc`) + DTO response + lớp map → entity JPA hiện có.

**Collection Postman (đã tạo trong repo docs):** `tich-hop-ttc/postman/OpenSyncAPI_DoiTac.postman_collection.json` và environment kèm theo — dùng để gọi thử API trước khi code.

---

## 2. Luồng kỹ thuật tổng quát

1. **Lấy token (M2M):** `POST {Base_URL}/api/opensync/token` — OAuth2 `client_credentials`, header `Authorization: Basic base64(client_id:client_secret)`, body JSON `{"grant_type":"client_credentials"}`. Token ~8 giờ — **cache** theo `expires_at` / `expires_in`, không xin mới mỗi request.
2. **Gọi API dữ liệu:** header `Authorization: Bearer {access_token}`. Mỗi API cần **API Code** được ASC cấp (mở trong token/scope phía server — nếu thiếu code sẽ 403 theo tài liệu).
3. **Thứ tự sync đề xuất** (khớp `phan-tich-tich-hop.md`):
   - Niên học → khối → lớp (có `ma_nien`) → giáo viên → học sinh (có `ma_nien`) → phân công giảng dạy (cần `SoDinhDanhCaNhan` từng GV).

---

## 3. Envelope response chung (phân trang)

Theo doc, body dạng:

```json
{
  "success": true,
  "message": "...",
  "data": {
    "total_count": 320,
    "page": 1,
    "page_size": 100,
    "total_pages": 4,
    "items": [ ... ]
  }
}
```

**Map:** không có bảng DB tương ứng — chỉ cần **DTO** (ví dụ `OpenSyncPageResponse<T>`) deserialize `data`, sau đó vòng lặp `data.items` để upsert vào LMS.

Query chung: `ma_truong`, `ma_nien` (tuỳ API), `page`, `page_size` (doc ghi mặc định page_size lớn, max 5000).

---

## 4. Bảng map field theo từng API

### 4.1 API học sinh — `GET /api/opensync/thongtinhocsinh`

| Field OpenSync (`items[]`) | Gợi ý map LMS (`lms-api`) | Ghi chú |
|----------------------------|---------------------------|----------|
| `HoDem`, `Ten` | `User.lastName`, `User.firstName` | Có thể suy ra từ `HoTen` nếu cần |
| `HoTen` | Hiển thị / đối soát | Ghép từ last + first khi export |
| `NgaySinh` (ISO, có `T00:00:00`) | `User.birthday` (`LocalDate`) | Parse cắt phần giờ |
| `GioiTinh` (bool) | `EGender` | Doc: `true` = Nam → `MALE`, `false` = Nữ → `FEMALE` |
| `SoDinhDanhCaNhan` | `User.citizenIdentityCode` | CCCD / định danh |
| `MaTruong` | `School.code` | Resolve `School` trước khi gán `user.school` |
| `MaKhoi` | `Grade.code` (trong **branch** đã chọn) | Phụ thuộc quy ước branch (mục 6) |
| `MaLopHoc`, `TenLopHoc` | `Classroom.code`, `Classroom.name` | Cùng `schoolYear` + `grade` đã resolve |
| `MaNien` | `SchoolYear` | Cần khớp quy ước với `ma_nien` query (mục 6) |
| `TenTruong` | (không bắt buộc lưu) | LMS lấy tên từ `School` đã link |

**Ghi nhận nghiệp vụ doc:** chỉ trả học sinh **đã xếp lớp** trong niên học — map sang `ClassroomStudent` (học sinh ↔ lớp) + `User` học sinh.

---

### 4.2 API giáo viên / nhân sự — `GET /api/opensync/thongtingiaovien`

| Field OpenSync | Gợi ý map LMS | Ghi chú |
|------------------|---------------|--------|
| Họ tên, ngày sinh, giới tính, CCCD | `User` (tương tự học sinh) | |
| `Email` | `User.email` | |
| `MaTruong` | `School.code` | |
| `MaLoaiNhanSu`, `LoaiNhanSu` | **Không có cột riêng** trên `User` | Map sang **role** (`UserBranchRole` + `Role`) hoặc bảng phụ / quy ước nội bộ |
| `TrangThai` (chuỗi) | `EStatus` | Cần bảng map chuỗi (vd `Hoạt động` → `ACTIVE`) |

Doc: **không** bắt buộc `ma_nien`.

---

### 4.3 API khối lớp — `GET /api/opensync/thongtinkhoilop`

| Field OpenSync | Gợi ý map LMS |
|------------------|---------------|
| `MaKhoiLop` | `Grade.code` |
| `TenKhoiLop` | `Grade.name` |

---

### 4.4 API lớp học — `GET /api/opensync/thongtinlophoc`

| Field OpenSync | Gợi ý map LMS |
|------------------|---------------|
| `MaKhoi` | Liên kết `Classroom.grade` (theo `Grade.code`) |
| `MaLopHoc` | `Classroom.code` |
| `TenLopHoc` | `Classroom.name` |

Tham số tùy chọn `ma_khoi` — lọc lớp theo khối; đối chiếu `Grade` trong branch.

---

### 4.5 API niên học — `GET /api/opensync/thongtinnienhoc`

| Field OpenSync | Gợi ý map LMS |
|------------------|---------------|
| `MaNienHoc` | Mã niên phía TTC (vd `NH2025`) — cần map tới **khóa nội bộ** hoặc cột cấu hình |
| `TenNienHoc` | `SchoolYear.name` hoặc đối soát hiển thị |

**Lưu ý:** doc gợi ý gọi API niên học trước; tham số `ma_nien` ở API khác có thể là dạng khác (vd `2025-2026` trong ví dụ curl) — **thống nhất một quy tắc** map `MaNienHoc` ↔ `ma_nien` ↔ `SchoolYear` trong LMS.

---

### 4.6 API phân công giảng dạy — `GET /api/opensync/phanconggiangday`

Payload mẫu trong doc: `ChuNhiem` (object), `PhanCongMonHocHK1` / `PhanCongMonHocHK2` (mảng).

| Cấu trúc OpenSync | Gợi ý map LMS |
|--------------------|---------------|
| `ChuNhiem` (MaKhoi, MaLopHoc, TenLopHoc, …) | `TeacherAllocation` với `kind = HEAD` (`ETeacherAllocation.HEAD`), `teacher` + `classroom` đã resolve |
| Từng phần tử `PhanCongMonHocHK*` (MaMonHoc, TenMonHoc, MaLopHoc, …) | `TeacherAllocation` với `kind = SUBJECT`, `subject` resolve từ `Subject.code` ← `MaMonHoc`, `classroom` theo lớp |

**Học kỳ:** LMS có `Semester` gắn `SchoolYear` — khi import cần quy tắc **HK1 / HK2** → record `Semester` (hoặc chỉ dùng allocation theo năm nếu nghiệp vụ cho phép).

**Lưu ý:** `TeacherSubject` trong LMS là quan hệ giáo viên–môn theo **branch**, khác mức “môn theo lớp” của OpenSync; phân công **theo lớp + môn** nên ưu tiên **`TeacherAllocation`**.

---

## 5. Điểm cần quy ước trước khi code (tránh map sai)

1. **`ma_truong` và `Branch`:** OpenSync gắn theo **mã trường**. LMS có `School` và nhiều **`Branch`**; `Grade`, `Classroom`, `SchoolYear` thường theo branch. Cần quy ước: một `ma_truong` ↔ một **branch mặc định**, hoặc bảng cấu hình `ma_truong` + `branch_id`.
2. **`ma_nien` vs `MaNienHoc` vs tên niên:** Đồng bộ thứ tự và một bảng map (hoặc parse) để mọi API dùng cùng một khóa niên học nội bộ.
3. **Loại nhân sự / trạng thái chuỗi:** Map sang `Role` / `EStatus` có kiểm tra tưỡng minh, không hard-code rải rác.
4. **Nguồn dữ liệu:** `EUserSource` hiện có giá trị hạn chế — nếu cần đánh dấu user từ OpenSync, cân nhắc mở rộng enum hoặc metadata (vd `User.code`, bảng mapping riêng).
5. **Doc vs thực tế:** Kiểm tra lại với ASC endpoint chính xác của API phân công (tài liệu có chỗ ghi `opensync.phancong` / `phanconggiangday` và path typo tiềm ẩn) trước khi khóa URL production.

---

## 6. Gợi ý các bước triển khai trong `lms-api`

1. Thêm cấu hình: `Base_URL`, `client_id`, `client_secret`, `ma_truong`, mapping `branch_id` (application properties hoặc bảng `integration_config`).
2. Service **token cache** (memory hoặc Redis): chỉ refresh khi sắp hết hạn.
3. DTO Jackson cho envelope + từng kiểu `items` (học sinh, GV, …).
4. Service **sync theo thứ tự** mục 2; mỗi bước: fetch từng trang → idempotent upsert (theo `code` + khóa nghiệp vụ).
5. Logging: không log full `access_token` / `client_secret`.
6. Test: dùng Postman collection trong repo; integration test mock HTTP nếu cần.

---

## 7. Liên quan tài liệu khác trong thư mục

- `phan-tich-tich-hop.md` — phân tích SSO + job sync tổng thể, phụ thuộc UC.
- `so-do-tich-hop.md` — sơ đồ luồng.
- `SKILL.md` — checklist / convention cho agent.

File này tập trung **mapping field OpenSync ↔ model LMS** và **cách làm cụ thể** khi implement trong `lms-api`.
