---
title: UC-03 — Các cơ chế chạy ngoài cron
scope: tich-hop-ttc
related:
  - tich-hop-ttc/tech/uc-03-implement.md
  - tich-hop-ttc/tech/uc-04-implement.md
  - tich-hop-ttc/phan-tich-tich-hop.md
status: draft
---

## Mục tiêu

Ngoài lịch cron (ví dụ `0 2 * * *`), mô tả các cơ chế khác để chạy đồng bộ TTC OpenSync nhằm:
- chủ động vận hành (khi cần resync ngay)
- giảm rủi ro “cron chưa kịp chạy” với user đăng nhập SSO
- mở đường cho gần real-time nếu TTC hỗ trợ

---

## 1) Manual run (Admin trigger)

### Khi dùng
- Sau khi TTC vừa cấp thêm API code / vừa sửa dữ liệu lớn
- Sau deploy thay đổi mapping
- Khi cần resync 1 trường/1 niên học ngay lập tức

### Cách làm (đề xuất)
- Tạo API nội bộ trong BE:
  - `POST /ttc/opensync/full-sync/run`
  - body gợi ý: `{ schoolDomain?, maTruong?, maNien?, dryRun?, reason? }`
- Có lock giống cron để tránh chạy song song.
- Có response tóm tắt: số record upsert/inactive + duration.

> Khuyến nghị: v1 nên có manual run để xử lý sự cố mà không phải chờ cron.

---

## 2) Login-triggered on-demand (Hybrid với UC-04)

### Khi dùng
- User login SSO nhưng chưa có record do full-sync (cron chậm, mới onboard, hoặc cron lỗi)

### Cách làm
- Trong UC-01 (SSO login) nếu resolve theo `sub/identity` không thấy user:
  - gọi UC-04 incremental sync theo `SoDinhDanhCaNhan`
  - resolve lại và link `ttc_sub`

### Ưu/nhược
- **Ưu**: cứu UX đăng nhập, không phụ thuộc cron.
- **Nhược**: không thay thế được full snapshot (vì chỉ sync 1 user), phụ thuộc TTC cấp claim `identity`.

---

## 3) Event-driven / Webhook (nếu TTC hỗ trợ)

### Khi dùng
- Muốn gần real-time: HS chuyển lớp, GV nghỉ việc, thay đổi phân công.

### Cách làm (high-level)
- TTC gửi webhook event (có `SoDinhDanhCaNhan` + loại sự kiện)
- LMS nhận event → gọi UC-04 sync-user hoặc sync-allocation (UC-05) tuỳ event

### Lưu ý
- Doc hiện chưa xác nhận TTC có webhook; chỉ làm khi TTC có contract + security (HMAC signature, replay protection).

---

## 4) Job queue / worker (scheduler “mềm” hơn cron)

### Khi dùng
- Full-sync chạy lâu, cần retry/backoff tốt hơn cron
- Muốn chạy nhiều lần/ngày theo “window”
- Muốn chạy song song theo `ma_truong` nhưng vẫn kiểm soát tải

### Cách làm
- Thay cron OS bằng “enqueue job” vào queue (hoặc bảng job DB).
- Worker xử lý:
  - lock theo `(schoolDomain/maTruong, maNien)`
  - retry có backoff
  - metric + alert tốt hơn

> Bản chất vẫn scheduled, nhưng vận hành tốt hơn cron đơn thuần.

---

## 5) Delta sync / changed-since (chỉ khi TTC có)

### Khi dùng
- Nếu TTC cung cấp API delta (`updated_since`, change feed) thì có thể thay snapshot bằng incremental batch.

### Trạng thái
- Theo phân tích hiện tại, OpenSync là snapshot; mục này chỉ là hướng mở rộng.

---

## Khuyến nghị cho v1

- **Bắt buộc**: cron full-sync (UC-03)
- **Nên có**: manual run (admin trigger)
- **Nên có**: login-triggered UC-04 để “cứu” SSO miss
- **Chờ TTC**: webhook / delta sync

