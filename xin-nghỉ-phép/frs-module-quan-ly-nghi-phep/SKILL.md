---
name: frs-module-quan-ly-nghi-phep
description: >-
  Áp dụng FRS module Xin nghỉ phép + liên đới Điểm danh (business rules, ma trận
  trạng thái/nguồn, sequence). Dùng khi thiết kế/triển khai/review leave request,
  attendance source (SYSTEM_AUTO, LEAVE_REQUEST, MANUAL), duyệt đơn, sửa điểm
  danh thủ công, auto job, thêm/hủy tiết quá khứ, TKB, audit log; hoặc khi user
  nhắc FRS nghỉ phép, BR-ATT-*, BR-LEAVE-*, SD-01–SD-05.
---

# FRS — Module quản lý nghỉ phép & tác động điểm danh

Nguồn chuẩn: `xin-nghỉ-phép/FRS - Module-quan-ly-nghi-phep.docx` (BA Spec: Attendance + Leave Request).

## Mục tiêu khi dùng skill

- Giữ **đồng bộ** nghỉ phép ↔ điểm danh, xử lý **lịch sử/quá khứ**, **truy vết** đủ qua audit.
- Không suy diễn ngoài phạm vi FRS (xem mục Phạm vi).

## Phạm vi

**Bao gồm:** tạo/quản lý đơn nghỉ; duyệt đơn (lẻ & hàng loạt); cập nhật điểm danh theo đơn; sửa điểm danh thủ công; auto điểm danh; ảnh hưởng TKB (thêm/hủy tiết quá khứ).

**Không bao gồm:** tính công/lương; học phí; báo cáo nâng cao; xin nghỉ **theo tiết** trên UI; HS tự gửi đơn; trang cấu hình chi nhánh cho phép HS tự gửi.

## Actor & phân quyền (tóm tắt)

| Chức năng | PH | HS | GVCN | GVBM | Admin | Super Admin |
|-----------|:--:|:--:|:----:|:----:|:-----:|:-------------:|
| Xem đơn nghỉ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Tạo đơn nghỉ | ✓ | — | — | — | — | — |
| Duyệt đơn / hàng loạt | — | — | ✓ | — | ✓ | ✓ |
| Sửa điểm danh | — | — | — | ✓ | ✓ | ✓ |
| Thêm/hủy tiết quá khứ | — | — | — | — | ✓ | ✓ |

**Mã chức năng:** FR-01 … FR-09 (danh sách đơn, tạo đơn, duyệt, batch, update theo đơn, manual, auto, thêm/hủy tiết quá khứ).

## Nguyên tắc hệ thống (NG)

| Mã | Ý nghĩa |
|----|---------|
| NG-01 | Điểm danh chỉ tồn tại khi **tiết học** tồn tại trên TKB |
| NG-02 | **Xóa cứng** bản ghi điểm danh khi không còn tiết |
| NG-03 | Nguồn điểm danh: **Tự động / Đơn nghỉ / Thủ công** |
| NG-04 | Đơn nghỉ được xử lý như luồng **thủ công** ở tầng ưu tiên (cùng tầng với MANUAL) |
| NG-05 | **Cập nhật hợp lệ đến sau** được dùng (last valid update wins giữa LEAVE_REQUEST & MANUAL) |
| NG-06 | **Tự động không ghi đè tầng 1** (không đè LEAVE_REQUEST/MANUAL) |
| NG-07 | **Đơn từ chối ≠ nghỉ không phép** — không auto map REJECTED → UNEXCUSED_ABSENCE |
| NG-08 | Log ghi **trực tiếp DB** |

## Enum — Trạng thái điểm danh

- `PRESENT` — Có mặt  
- `EXCUSED_ABSENCE` — Nghỉ có phép  
- `UNEXCUSED_ABSENCE` — Nghỉ không phép  

## Enum — Nguồn điểm danh (source)

- `SYSTEM_AUTO` — Job hệ thống (**tầng 2**, mặc định nền)  
- `LEAVE_REQUEST` — Phiếu nghỉ phép hiệu lực (**tầng 1**)  
- `MANUAL` — User cập nhật thủ công (**tầng 1**)  

**Ưu tiên:** Tầng 1 = `LEAVE_REQUEST` + `MANUAL` (ngang quyền). Tầng 2 = `SYSTEM_AUTO` (không bao giờ thắng tầng 1). Giữa LEAVE_REQUEST và MANUAL: **`last_updated_at` / version — event sau thắng** (last write wins).

## Leave request — Phase 1

- **BR-LEAVE-01:** Chỉ nghỉ theo **buổi** và **ngày** (UI không hỗ trợ theo tiết).  
- **BR-LEAVE-02:** Trạng thái đơn: vòng đời với leave action → leave status (chi tiết trong spec).  
- **BR-LEAVE-03:** `PENDING` — không tác động attendance; `APPROVED` — tác động; `REJECTED` — **không** auto sinh UNEXCUSED_ABSENCE.  
- **BR-LEAVE-04 / NG-07:** Rejected chỉ là trạng thái đơn; nghỉ không phép phải đến từ **điểm danh thực tế/manual**.  
- **BR-LEAVE-05:** Không cho **overlap** thời gian nghỉ với đơn đã tồn tại (`PENDING` / `APPROVED`).

## Bản ghi điểm danh — tồn tại & TKB

- Chỉ tạo cho tiết **còn hiệu lực**; tiết hủy → bản ghi **không tồn tại**, điểm danh **xóa cứng** (BR-ATT-02, BR-ATT-05–07, BR-ATT-26–27).  
- **Thêm tiết quá khứ:** tạo điểm danh mới cho HS liên quan; nếu không có HS thì không tạo (BR-ATT-06).  
- **Khởi tạo khi thêm tiết quá khứ:** nếu có leave **APPROVED** trong phạm vi → `EXCUSED_ABSENCE` + `LEAVE_REQUEST`; ngược lại → mặc định auto (`SYSTEM_AUTO` / có mặt theo luồng job) — **BR-ATT-24, BR-ATT-25** (không mặc định sai khi đã có leave).

## Auto attendance (BR-ATT-13 … 15)

- Chỉ xử lý bản ghi **đang tồn tại**.  
- Nếu đã có nguồn **tầng 1** (`LEAVE_REQUEST` hoặc `MANUAL`) → **skip** (không ghi đè).  
- Bản ghi chưa có tầng 1 → có thể gán `SYSTEM_AUTO` (nền).

## Approve leave → attendance (BR-ATT-16 … 20)

- Chỉ cập nhật slot **đang tồn tại** trong phạm vi nghỉ; **không tạo** attendance cho slot không tồn tại.  
- Approve là event **tầng 1:** `EXCUSED_ABSENCE`, source = `LEAVE_REQUEST`, lưu **source_ref_id**.  
- Ghi đè `SYSTEM_AUTO` trực tiếp.  
- Với `MANUAL`: **approve mới hơn** có thể thành kết quả cuối (last write wins).  
- Không bắt buộc “conflict” cứng giữa LEAVE_REQUEST và MANUAL — ưu tiên kết quả + **audit**.

## Manual edit (BR-ATT-21 … 23)

- Manual = event tầng 1, source → `MANUAL`.  
- Ghi đè `SYSTEM_AUTO` trực tiếp.  
- Với `LEAVE_REQUEST`: **manual mới hơn** có thể thắng (không khóa cứng theo leave).

## Audit (BR-ATT-28 … 29)

Mọi thay đổi attendance phải có audit: **action**, **actor/source**, before/after **status**, before/after **source**, **source_ref_id**, **timestamp**, **reason/note** (phục vụ last-write-wins và tra soát).

## Mapping buổi → tiết (BR-ATT-30)

`APPROVED` leave theo **buổi** áp dụng cho **tất cả tiết** thuộc buổi đã approve.

## Ma trận “Trạng thái đơn × nguồn điểm danh” (tóm tắt hành vi)

| Đơn | Nguồn / điều kiện | Hành động | Kết quả |
|-----|-------------------|-----------|---------|
| PENDING / REJECTED | Mọi | Không xử lý | Giữ nguyên |
| APPROVED | Chưa có bản ghi | Tạo (trong phạm vi tồn tại) | EXCUSED / LEAVE_REQUEST |
| APPROVED | SYSTEM_AUTO | Ghi đè | EXCUSED / LEAVE_REQUEST |
| APPROVED | LEAVE_REQUEST | Đồng bộ nếu cần | EXCUSED / LEAVE_REQUEST |
| APPROVED | MANUAL | So sánh thời điểm | Leave mới hơn → LEAVE_REQUEST; manual mới hơn → giữ MANUAL |
| APPROVED | Không có slot / tiết hủy | Không tạo / xóa slot | Không tồn tại |
| APPROVED | SYSTEM_AUTO + auto job | Không ghi đè auto | Giữ LEAVE_REQUEST hoặc MANUAL |

## Sequence diagram — luồng triển khai

**SD-01 — Duyệt đơn → cập nhật điểm danh**  
Leave module: kiểm tra đơn còn PENDING → APPROVED + meta duyệt → gọi attendance module. Attendance: tìm bản ghi **tồn tại** trong phạm vi; áp dụng quy tắc nguồn/timestamp; ghi **audit**; leave module ghi log duyệt + **thông báo** PH/HS.  
*Ngoại lệ:* không có slot tồn tại → chỉ cập nhật đơn + log; nghỉ **tương lai** có thể chỉ hiện điểm danh khi đến ngày hiện hành.

**SD-02 — Cập nhật điểm danh thủ công**  
Chỉ khi bản ghi **tồn tại**; áp dụng BR manual; audit; không quyền → 403.

**SD-03 — Thêm tiết quá khứ → tạo điểm danh**  
TKB tạo tiết → attendance lặp HS, hỏi leave module có APPROVED khớp → khởi tạo LEAVE_REQUEST hoặc nhánh auto; log.

**SD-04 — Hủy tiết quá khứ**  
Hủy tiết → xóa cứng attendance liên quan; log.

**SD-05 — Job auto điểm danh**  
Duyệt bản ghi tồn tại; **bỏ qua** MANUAL và LEAVE_REQUEST; với chưa có tầng 1: tra leave APPROVED → nếu có thì LEAVE_REQUEST, không thì SYSTEM_AUTO (có mặt); log; lỗi query leave → log + skip bản ghi.

## Ghi chú mã rule trong tài liệu gốc

Trong DOC có chỗ dùng tiền tố **BR-NP-** / **BR-ĐD-** trong mục SD; phần bảng Business Rules chuẩn dùng **BR-LEAVE-***, **BR-ATT-***. Khi đối chiếu code/spec, map theo **bảng Business Rules** và ma trận trong DOC; coi BR-ATT/BR-LEAVE là ID chính.

## Checklist nhanh cho agent (implement / review)

- [ ] Reject đơn **không** làm attendance thành nghỉ không phép tự động  
- [ ] Auto job **không** đè LEAVE_REQUEST/MANUAL  
- [ ] LEAVE_REQUEST vs MANUAL: **timestamp/version**, không ưu tiên cứng một phía  
- [ ] Approve chỉ trên slot **tồn tại**; thêm tiết quá khứ **reconcile** leave đã duyệt  
- [ ] Hủy tiết → **hard delete** attendance; báo cáo loại bản ghi không tồn tại  
- [ ] Mọi thay đổi attendance → **audit đủ field** tối thiểu  
- [ ] Không overlap đơn PENDING/APPROVED theo BR-LEAVE-05  
- [ ] Phase 1: buổi/ngày, không UI theo tiết / không HS tự gửi (out of scope)
