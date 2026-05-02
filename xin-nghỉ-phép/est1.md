# Ước lượng manday — module xin nghỉ phép (4 vai: Admin, Parent, Student, Teacher)

Phạm vi tham chiếu: tài liệu trong `xin-nghỉ-phép/` (FR-01…03, HS-01/02, GV-01/02, AD-01/02) + FRS trong `frs-module-quan-ly-nghi-phep/SKILL.md`.  
**FE + BE** (manday dev). Đây là **ballpark** — không thể chốt số chính xác nếu chưa có backlog chi tiết, stack, và mức tái sử dụng API/UI.

## Giả định (ảnh hưởng mạnh tới số ngày)

- **BE dùng chung** một domain “leave request + duyệt + lý do từ chối”; nhiều màn chỉ khác **filter / quyền / ngữ cảnh** → BE **không** nhân 4 lần.
- Đã có sẵn: auth/role, trường/lớp/HS, năm học, component bảng/lọc/phân trang, modal → giảm mạnh FE.
- **Chưa có** API leave, job attendance, audit → BE tăng rõ.
- **FRS** (overlap đơn, trạng thái, tác động điểm danh) implement đúng spec → BE + test + xử lý bug tăng.

## Thang ước lượng theo khối (FE | BE) manday

| Khối | Nội dung gần với doc | FE (tham chiếu) | BE (tham chiếu) |
|------|----------------------|-----------------|-----------------|
| **Chung / nền** | Model đơn, state machine, quyền theo vai, API cốt lõi, đồng bộ attendance (theo BR) | — | **12–25** |
| **Parent** | FR-01 (list, filter, empty, RR-01), FR-02 (tạo đơn), FR-03 (chi tiết) | **8–14** | **6–12** *(nhẹ hơn nếu API đã có)* |
| **Student** | HS-01, HS-02 (chủ yếu đọc) | **3–6** | **2–5** |
| **Teacher** | GV-01 (lớp + danh sách đơn), GV-02 (đồng ý/từ chối + popup) | **8–14** | **6–12** |
| **Admin** | AD-01 (list admin), AD-02 (flow duyệt + popup) — thường tương tự GV, filter/phạm vi rộng hơn | **6–12** | **5–10** |
| **Tích hợp & QA chức năng** | E2E các vai, fix lệch spec, edge cases | **3–8** *(có thể gộp FE)* | **5–12** |

## Tổng hợp manday

| Cách đọc | Khoảng |
|----------|--------|
| **FE** (4 phần UI + chỉnh vòng) | **28–54 manday** |
| **BE** (core + theo vai + tích hợp) | **36–76 manday** |
| **Cộng FE + BE** (một người làm tuần tự cả hai) | **64–130 manday** |

Nếu **2 dev song song** (1 FE + 1 BE), **thời gian wall-clock** thường ~**max(FE, BE) + buffer** (overlap, review, bug), ví dụ **~2,5–4 tháng** làm việc tùy team — **không** bằng tổng FE+BE.

## Cách chốt số sát hơn

1. Tách **BE core** (một lần) vs **mỗi màn** (chỉ integration).
2. Ghi rõ **API đã có / chưa có** (điểm danh, TKB, năm học).
3. Ước **% reuse** component design system.
4. Làm rõ **batch duyệt** (admin/GV) hay chỉ từng đơn — nếu có batch thì cộng thêm FE/BE.

## Kết luận ngắn (planning)

- **~65–90 manday tổng (FE+BE)** khi LMS đã có nền khá đầy, BE leave/attendance **không phải làm mới hoàn toàn**.
- **~90–130+ manday** nếu backend leave/attendance **phải làm mới nhiều** hoặc BR phức tạp + test kỹ.

---

*Ngày ghi: có thể cập nhật khi có thêm đầu vào từ BA/tech lead.*
