---
title: FRS - Module-quan-ly-nghi-phep
source: FRS - Module-quan-ly-nghi-phep.docx (converted)
language: vi
---

> **Nguồn:** `FRS - Module-quan-ly-nghi-phep.docx` — chuyển tự động từ Word (OOXML). Hình ảnh trong file gốc không được nhúng; cần mở `.docx` để xem diagram.

# Thông tin chung

<p align="center">Attendance + Leave Request</p>

<p align="center">BA Spec</p>

<p align="center">This document covers Business Rules, State / Source Matrix, and Sequence Diagram Spec for Attendance + Leave Request.</p>

# 1. Giới thiệu

## 1.1. Mục tiêu

Tài liệu này mô tả chi tiết các yêu cầu chức năng cho module:

- Xin nghỉ phép

- Liên đới chức năng sang module Điểm danh

- Ghi log thay đổi

Đảm bảo:

- Đồng bộ giữa nghỉ phép và điểm danh

- Xử lý đúng lịch sử (quá khứ)

- Truy vết đầy đủ thay đổi

## 1.2. Phạm vi

Bao gồm

- Tạo và quản lý đơn nghỉ phép

- Duyệt đơn (đơn lẻ & hàng loạt)

- Cập nhật điểm danh theo đơn nghỉ

- Cập nhật điểm danh thủ công

- Xử lý tự động điểm danh

- Ảnh hưởng từ thay đổi thời khóa biểu

Không bao gồm

- Tính công/lương

- Tính học phí

- Báo cáo nâng cao

- Xin nghỉ phép từng tiết lẻ

- HS tự gửi đơn nghỉ phép

- Trang cấu hình mỗi chi nhánh cho phép HS được tự gửi đơn nghỉ phép hay không

# 2. Actor

| Actor |
| --- |
| Phụ huynh |
| Học sinh |
| GVCN |
| GVBM |
| Admin |
| Super Admin |
| Hệ thống |

# 3. Nguyên tắc hệ thống

| Mã | Nguyên tắc |
| --- | --- |
| NG-01 | Điểm danh chỉ tồn tại khi tiết học tồn tại |
| NG-02 | Xóa cứng điểm danh |
| NG-03 | Nguồn điểm danh: Tự động / Đơn nghỉ / Thủ công |
| NG-04 | Đơn nghỉ = Thủ công |
| NG-05 | Cập nhật hợp lệ đến sau sẽ được dùng |
| NG-06 | Tự động không ghi đè tầng 1 |
| NG-07 | Đơn từ chối ≠ nghỉ không phép |
| NG-08 | Log ghi trực tiếp DB |

# 4. Ma trận phân quyền

| Chức năng | PH | HS | GVCN | GVBM | Admin | Super Admin |
| --- | --- | --- | --- | --- | --- | --- |
| Xem đơn nghỉ | Yes | Yes | Yes | Yes | Yes | Yes |
| Tạo đơn nghỉ | Yes | No | No | No | No | No |
| Duyệt đơn | No | No | Yes | No | Yes | Yes |
| Duyệt hàng loạt | No | No | Yes | No | Yes | Yes |
| Sửa điểm danh | No | No | No | Yes | Yes | Yes |
| Thêm tiết quá khứ | No | No | No | No | Yes | Yes |
| Hủy tiết quá khứ | No | No | No | No | Yes | Yes |

# 5. Danh sách chức năng

| Mã | Tên |
| --- | --- |
| FR-01 | Xem danh sách đơn nghỉ |
| FR-02 | Tạo đơn nghỉ |
| FR-03 | Duyệt đơn |
| FR-04 | Duyệt hàng loạt |
| FR-05 | Update điểm danh theo đơn nghỉ phép |
| FR-06 | Sửa điểm danh thủ công |
| FR-07 | Auto điểm danh |
| FR-08 | Thêm tiết quá khứ |
| FR-09 | Hủy tiết quá khứ |

# Business Rules

# 1. Nhóm rule tổng quát

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-01 | Định nghĩa bản ghi điểm danh | Bản ghi điểm danh là dữ liệu điểm danh gắn với 1 tiết học cụ thể trên TKB của 1 học sinh/ 1 lớp học | Khi phát sinh/xử lý điểm danh | Học sinh, tiết học trên TKB | Bản ghi điểm danh |  |
| BR-ATT-02 | Trạng thái tồn tại của bản ghi điểm danh | bản ghi điểm danh chỉ có 2 trạng thái logic: tồn tại (khi có tiết học trên TKB) hoặc không tồn tại (Không có tiết học hoặc tiết hủy trên TKB) | Khi tạo/hủy tiết học trong TKB | Trạng thái tiết | bảng ghi điểm danh tồn tại / không tồn tại | Khi hủy tiết => xóa thông tin điểm danh => xóa cứng |
| BR-ATT-03 | Trạng thái điểm danh | Attendance status gồm: PRESENT: Có mặt EXCUSED_ABSENCE: Nghỉ có phép UNEXCUSED_ABSENCE: Nghỉ không phép | Khi cập nhật thông tin điểm danh | Thao tác điểm danh | Trạng thái điểm danh hiện hành |  |
| BR-ATT-04 | Nguồn dữ liệu điểm danh | Nguồn dữ liệu điểm danh gồm: SYSTEM_AUTO: Thông tin điểm danh được tạo bởi job hệ thống LEAVE_REQUEST: Thông tin điểm danh được tạo bởi hiệu lực phiếu nghỉ phép MANUAL: Thông tin điểm danh được tạo bởi user tự cập nhật thủ công | Khi bản ghi điểm danh được tạo/cập nhật | Sự kiện update bản ghi điểm danh | Nguồn hiện hành | Nguồn dùng để xác định quyền ghi đè |

# 2. Nhóm rule về xin nghỉ phép

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-LEAVE-01 | Phạm vi hỗ trợ phase 1 | Chỉ hỗ trợ nghỉ theo buổi và theo ngày | Khi nhập đơn nghỉ | Loại nghỉ | Đơn hợp lệ / không hợp lệ | Không hỗ trợ theo tiết trên UI |
| BR-LEAVE-02 | Trạng thái leave request | Leave request chỉ có 3 trạng thái: | Trong suốt vòng đời đơn | Leave action | Leave status |  |
| BR-LEAVE-03 | Tác động của leave status | PENDING không tác động attendance APPROVED tác động attendance REJECTED không tự động sinh UNEXCUSED_ABSENCE | Khi trạng thái đơn thay đổi | Leave status | Attendance action / no action | REJECTED chỉ là trạng thái đơn |
| BR-LEAVE-04 | Rejected không đồng nghĩa nghỉ không phép | Đơn bị từ chối không tự map sang UNEXCUSED_ABSENCE | Khi reject đơn | Leave request | Không cập nhật attendance tự động | Nghỉ không phép phải đến từ attendance thực tế/manual |
| BR-LEAVE-05 | Không cho overlap TG nghỉ phép | Không cho phép tạo đơn nghỉ có khoảng thời gian overlap với đơn đã tồn tại (PENDING/APPROVED) | Khi tạo đơn xin nghỉ phép | Tg nghỉ phép | Không cho tạo đơn xin nghỉ phép |  |

# 3. Nhóm rule về sự tồn tại bản ghi điểm danh

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-05 | bảng ghi điểm danh chỉ tồn tại khi tiết học còn hiệu lực | Hệ thống chỉ tạo bản ghi điểm danh cho tiết học còn hiệu lực | Khi xử lý timetable | Tiết học trên TKB, HS | Có bảng ghi điểm danh / không có bảng ghi điểm danh | tiết học bị hủy thì bảng ghi điểm danh không còn tồn tại |
| BR-ATT-06 | Thêm tiết học trong quá khứ | Khi thêm tiết trong quá khứ, hệ thống tạo bản ghi điểm danh mới cho các học sinh liên quan | Thêm tiết quá khứ | Tiết học trên TKB, HS | bảng ghi điểm danh mới được tạo | Không có HS thì k tạo điểm danh |
| BR-ATT-07 | Hủy tiết học trong quá khứ | Khi hủy tiết trong quá khứ, bản ghi điểm danh tương ứng không còn tồn tại | Cancel past lesson | Tiết học trên TKB, HS | bảng ghi điểm danh bị remove | Xóa cứng |

# 4. Nhóm rule ưu tiên source

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-08 | Source priority theo 2 tầng | Tầng 1: LEAVE_REQUEST, MANUAL; Tầng 2: SYSTEM_AUTO | Khi nhiều source cùng tác động | Current source, new source | Effective source | Rule cốt lõi của module |
| BR-ATT-09 | SYSTEM_AUTO là thấp nhất | SYSTEM_AUTO chỉ là mặc định nền và không được ghi đè dữ liệu từ LEAVE_REQUEST hoặc MANUAL | Khi job auto chạy / recalculate | Current source, new source | Có ghi đè hay không | SYSTEM_AUTO không bao giờ thắng tầng 1 |
| BR-ATT-10 | LEAVE_REQUEST và MANUAL ngang quyền | LEAVE_REQUEST và  MANUAL có cùng độ ưu tiên | Khi leave/manual cùng tác động | Current source, new source | So sánh theo thời điểm | Không tạo ưu tiên cứng |
| BR-ATT-11 | Last valid update wins | Giữa LEAVE_REQUEST và  MANUAL, bản cập nhật hợp lệ đến sau là kết quả hiện hành | Khi có update tầng 1 mới | last_updated_at, version | Effective result | Áp dụng cho cả approve leave và manual edit |
| BR-ATT-12 | Xác định ‘đến sau’ | So sánh theo last_updated_at | Khi 2 event cùng cấp cạnh tranh | timestamp, version | Event thắng | Event nào sau thì event đó thắng |

# 5. Nhóm rule auto attendance

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-13 | Auto attendance chỉ áp dụng cho bảng ghi điểm danh đang tồn tại | Job hệ thống chỉ xử lý attendance với các bảng ghi điểm danh đang tồn tại | Auto job chạy | Existing bảng ghi điểm danh list | Attendance update | Không xử lý bảng ghi điểm danh không tồn tại |
| BR-ATT-14 | Không ghi đè source tầng 1 | Nếu bảng ghi điểm danh đã có LEAVE_REQUEST hoặc MANUAL thì auto job không ghi đè | Auto job chạy | Current source | Skip update | Tránh auto phá dữ liệu nghiệp vụ |
| BR-ATT-15 | Giá trị auto mặc định | Nếu bảng ghi điểm danh chưa có source tầng 1, hệ thống gán source SYSTEM_AUTO | Auto job chạy | bảng ghi điểm danh chưa có tier-1 source | Source SYSTEM_AUTO | Đây là mặc định nền |

# 6. Nhóm rule approve leave

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-16 | Approve leave chỉ áp dụng lên bảng ghi điểm danh đang tồn tại | Khi leave request được APPROVED, hệ thống chỉ cập nhật các bảng ghi điểm danh đang tồn tại trong phạm vi nghỉ | Approve leave | Leave request, bảng ghi điểm danh list | Attendance update | Không tạo attendance cho bảng ghi điểm danh không tồn tại |
| BR-ATT-17 | Approve leave là event tầng 1 | Approve leave cập nhật attendance thành EXCUSED_ABSENCE, source = LEAVE_REQUEST | Approve leave | requestId, affected bảng ghi điểm danhs | Updated attendance | Có lưu source_ref_id |
| BR-ATT-18 | Approve leave ghi đè SYSTEM_AUTO | Nếu attendance hiện tại là SYSTEM_AUTO, leave approved được ghi đè | Approve leave | Current source = SYSTEM_AUTO | EXCUSED_ABSENCE / LEAVE_REQUEST | Không cần so sánh ưu tiên |
| BR-ATT-19 | Approve leave ghi đè MANUAL nếu đến sau | Nếu attendance hiện tại là MANUAL, leave approved vẫn có thể là kết quả cuối nếu event approve mới hơn | Approve leave | Current source = MANUAL | Effective result cập nhật theo last write wins | Đây là rule mới đã chốt |
| BR-ATT-20 | Không tạo conflict mặc định | Hệ thống không bắt buộc tạo conflict giữa LEAVE_REQUEST và MANUAL; thay vào đó lưu audit log | Approve leave / manual edit | Tier-1 source change | Attendance result + audit | Conflict logic không dùng mặc định |

# 7. Nhóm rule manual edit

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-21 | Manual edit là event tầng 1 | Khi người dùng sửa attendance thủ công, source được cập nhật thành MANUAL | Manual edit | bảng ghi điểm danhId, newStatus | Attendance updated | Manual là source cùng cấp với leave |
| BR-ATT-22 | Manual edit ghi đè LEAVE_REQUEST nếu đến sau | Nếu bảng ghi điểm danh hiện tại là LEAVE_REQUEST, manual edit mới hơn sẽ là kết quả hiện hành | Manual edit | Current source = LEAVE_REQUEST | Effective result theo last write wins | Không khóa cứng theo leave |
| BR-ATT-23 | Manual edit ghi đè SYSTEM_AUTO | Nếu bảng ghi điểm danh hiện tại là SYSTEM_AUTO, manual edit ghi đè trực tiếp | Manual edit | Current source = SYSTEM_AUTO | Attendance updated | Không cần so sánh với SYSTEM_AUTO |

# 8. Nhóm rule thêm/hủy tiết học quá khứ

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-24 | Thêm tiết học   trong quá khứ phải tính source khởi tạo đúng | Khi tạo bảng ghi điểm danh mới do thêm tiết học quá khứ, nếu có leave approved thì khởi tạo bằng LEAVE_REQUEST, ngược lại khởi tạo bằng SYSTEM_AUTO | Add past lesson | lesson/session, leave data | Initial attendance | Không auto cứng SYSTEM_AUTO nếu đã có leave |
| BR-ATT-25 | Không auto cứng có mặt nếu có leave approved | bảng ghi điểm danh mới thêm trong quá khứ không được mặc định SYSTEM_AUTO nếu đã có leave approved áp dụng | Add past lesson | Approved leave in range | EXCUSED_ABSENCE / LEAVE_REQUEST | Rule bắt buộc để tránh sai lịch sử |
| BR-ATT-26 | Hủy tiết học   làm bảng ghi điểm danh không còn tồn tại | Khi tiết học bị hủy, bảng ghi điểm danh attendance tương ứng không còn tồn tại | Hủy tiết trong quá khứ | Tiết học trên TKB | bảng ghi điểm danh removed | Không dùng soft delete |
| BR-ATT-27 | bảng ghi điểm danh không tồn tại không dùng cho báo cáo | bản ghi điểm danh không còn tồn tại không được tính vào báo cáo/chỉ số attendance chính thức | Báo cáo / thống kê | bảng ghi điểm danh existence | Excluded from report | Áp dụng cho toàn hệ thống |

# 9. Nhóm rule audit log

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-28 | Bắt buộc có audit log | Mọi thay đổi attendance phải được ghi audit log | Mọi attendance action | Before/after data | Audit record | Bắt buộc cho tra soát |
| BR-ATT-29 | Nội dung audit tối thiểu | Audit phải ghi action, actor/source, before/after status, before/after source, source_ref_id, timestamp, reason/note | Khi ghi audit | Change event | Audit log đầy đủ | Cần cho last-write-wins |

# 10. Nhóm rule Mapping buổi → tiết

| Mã Rule | Tên Rule | Mô tả | Trigger | Input | Output | Exception / Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| BR-ATT-30 | Mapping buổi → tiết | Khi APPROVED LEAVE_REQUEST thì sẽ apply cho tất cả những tiết học thuộc buổi đã approve | Approve đơn xin nghỉ phép | Approved leave/ Tiết học/ buổi học | Attendance updated |  |

# Matrix dữ liệu

| STT | Trạng thái đơn nghỉ | Điểm danh hiện tại (source) | Điều kiện | Hành động | Kết quả điểm danh |
| --- | --- | --- | --- | --- | --- |
| 1 | PENDING | Bất kỳ | - | Không xử lý | Giữ nguyên |
| 2 | REJECTED | Bất kỳ | - | Không xử lý | Giữ nguyên |
| 3 | APPROVED | Chưa có | - | Tạo mới | Nghỉ có phép / LEAVE_REQUEST |
| 4 | APPROVED | SYSTEM_AUTO | - | Ghi đè | Nghỉ có phép / LEAVE_REQUEST |
| 5 | APPROVED | LEAVE_REQUEST | - | Đồng bộ lại (nếu cần) | Nghỉ có phép / LEAVE_REQUEST |
| 6 | APPROVED | MANUAL | Leave mới hơn | Ghi đè | Nghỉ có phép / LEAVE_REQUEST |
| 7 | APPROVED | MANUAL | Manual mới hơn | Không ghi đè | Giữ MANUAL |
| 8 | APPROVED | Không tồn tại slot | Do chưa có tiết học | Không tạo | Không có điểm danh |
| 9 | APPROVED | Bất kỳ | Slot bị hủy (lesson bị hủy) | Xóa slot | Không tồn tại |
| 10 | APPROVED | LEAVE_REQUEST | Có update leave mới hơn | Update lại | Nghỉ có phép / LEAVE_REQUEST |
| 11 | APPROVED | MANUAL | Có update manual mới hơn | Update lại | MANUAL mới nhất |
| 12 | APPROVED | SYSTEM_AUTO | Có auto job chạy | Không ghi đè | Giữ LEAVE_REQUEST hoặc MANUAL |

<p align="center"></p>

# Sequence Diagram

# 1. SD-01 – Duyệt đơn nghỉ → Cập nhật điểm danh

## 1.1. Thông tin chung

| Mục | Nội dung |
| --- | --- |
| Mã | SD-01 |
| Tên | Duyệt đơn nghỉ và cập nhật điểm danh |
| Mục tiêu | Khi người duyệt duyệt một đơn xin nghỉ hợp lệ, hệ thống cập nhật trạng thái đơn và cập nhật điểm danh của các bản ghi nằm trong phạm vi nghỉ |
| Tác nhân chính | Admin / Super Admin / GVCN |
| Thành phần tham gia | Màn hình quản lý đơn nghỉ phép, Module xin nghỉ phép, Module điểm danh, Thông báo, Cơ sở dữ liệu |
| Tiền điều kiện | Đơn xin nghỉ tồn tại và đang ở trạng thái Chờ duyệt |
| Hậu điều kiện | Đơn chuyển sang trạng thái Đã duyệt; các bản ghi điểm danh liên quan được tạo hoặc cập nhật theo nguồn Đơn nghỉ |
| Luật áp dụng | BR-NP-03, BR-NP-04, BR-ĐD-16, BR-ĐD-17, BR-ĐD-18, BR-ĐD-19, BR-ĐD-20 |
| Ngoại lệ | Nếu đơn không còn ở trạng thái Chờ duyệt thì hệ thống từ chối xử lý |

## 1.2. Luồng chính

| Bước | Thành phần | Mô tả xử lý |
| --- | --- | --- |
| 1 | Người duyệt | Chọn chức năng duyệt đơn nghỉ |
| 2 | Màn hình quản lý đơn nghỉ phép | Gửi yêu cầu duyệt đơn tới Module xin nghỉ phép |
| 3 | Module xin nghỉ phép | Kiểm tra trạng thái hiện tại của đơn trong cơ sở dữ liệu |
| 4 | Cơ sở dữ liệu | Trả về kết quả kiểm tra trạng thái đơn |
| 5 | Module xin nghỉ phép | Cập nhật trạng thái đơn thành Đã duyệt, lưu người duyệt và thời gian duyệt |
| 6 | Module xin nghỉ phép | Gửi yêu cầu sang Module điểm danh để áp dụng đơn nghỉ lên các bản ghi điểm danh liên quan |
| 7 | Module điểm danh | Tìm các bản ghi điểm danh đang tồn tại trong phạm vi nghỉ |
| 8 | Cơ sở dữ liệu | Trả về danh sách bản ghi điểm danh liên quan |
| 9 | Module điểm danh | Lần lượt xử lý từng bản ghi điểm danh |
| 10 | Module điểm danh | Nếu chưa có điểm danh thì tạo mới với trạng thái Nghỉ có phép, nguồn = Đơn nghỉ |
| 11 | Module điểm danh | Nếu nguồn hiện tại là Tự động hệ thống thì cập nhật thành Nghỉ có phép, nguồn = Đơn nghỉ |
| 12 | Module điểm danh | Nếu nguồn hiện tại là Thủ công thì so sánh thời điểm cập nhật; nếu đơn nghỉ mới hơn thì ghi đè theo nguyên tắc cập nhật đến sau |
| 13 | Module điểm danh | Nếu nguồn hiện tại là Đơn nghỉ thì đồng bộ lại dữ liệu/tham chiếu nếu cần |
| 14 | Module điểm danh | Ghi log cho từng thay đổi điểm danh vào cơ sở dữ liệu |
| 15 | Module xin nghỉ phép | Ghi log duyệt đơn vào cơ sở dữ liệu |
| 16 | Module xin nghỉ phép | Gửi thông báo kết quả cho phụ huynh/học sinh |
| 17 | Màn hình quản lý đơn nghỉ phép | Hiển thị kết quả duyệt thành công |

## 1.3. Luồng thay thế / ngoại lệ

| Mã | Điều kiện | Xử lý |
| --- | --- | --- |
| A1 | Đơn không tồn tại | Hệ thống trả lỗi, không xử lý tiếp |
| A2 | Đơn không ở trạng thái Chờ duyệt | Hệ thống trả lỗi, không cập nhật dữ liệu |
| A3 | Trong phạm vi nghỉ không có bản ghi điểm danh đang tồn tại | Hệ thống chỉ cập nhật trạng thái đơn và ghi log, không cập nhật điểm danh Ngoài ra, đối với case xin nghỉ trong tương lại, đến nagỳ hiện hành mới hiển thị thông tin điểm danh |

# 2. SD-02 – Cập nhật điểm danh thủ công

## 2.1. Thông tin chung

| Mục | Nội dung |
| --- | --- |
| Mã | SD-02 |
| Tên | Cập nhật điểm danh thủ công |
| Mục tiêu | Cho phép người dùng có quyền cập nhật điểm danh thủ công cho một bản ghi điểm danh đang tồn tại |
| Tác nhân chính | Admin / GVCN / GVBM theo phân quyền |
| Thành phần tham gia | Giao diện điểm danh, Module điểm danh, Cơ sở dữ liệu |
| Tiền điều kiện | Bản ghi điểm danh đang tồn tại |
| Hậu điều kiện | Bản ghi điểm danh được cập nhật với nguồn = Thủ công |
| Luật áp dụng | BR-ĐD-21, BR-ĐD-22, BR-ĐD-23 |
| Ngoại lệ | Nếu bản ghi điểm danh không còn tồn tại thì không cho phép cập nhật |

## 2.3. Luồng chính

| Bước | Thành phần | Mô tả xử lý |
| --- | --- | --- |
| 1 | Người dùng | Chọn sửa điểm danh |
| 2 | Giao diện điểm danh | Gửi yêu cầu cập nhật tới Module điểm danh |
| 3 | Module điểm danh | Lấy dữ liệu điểm danh hiện tại từ cơ sở dữ liệu |
| 4 | Cơ sở dữ liệu | Trả về bản ghi điểm danh hiện tại hoặc rỗng |
| 5 | Module điểm danh | Nếu chưa có điểm danh thì tạo mới với nguồn = Thủ công |
| 6 | Module điểm danh | Nếu nguồn hiện tại là Tự động hệ thống thì ghi đè trực tiếp bằng Thủ công |
| 7 | Module điểm danh | Nếu nguồn hiện tại là Đơn nghỉ thì so sánh thời điểm cập nhật; nếu thủ công mới hơn thì ghi đè |
| 8 | Module điểm danh | Nếu nguồn hiện tại là Thủ công thì cập nhật bằng dữ liệu mới nhất |
| 9 | Module điểm danh | Ghi log thay đổi vào cơ sở dữ liệu |
| 10 | Giao diện điểm danh | Hiển thị kết quả cập nhật thành công |

<p align="center"></p>

## 2.3. Luồng thay thế / ngoại lệ

| Mã | Điều kiện | Xử lý |
| --- | --- | --- |
| A1 | Bản ghi điểm danh không tồn tại | Hệ thống trả lỗi, không cập nhật |
| A2 | Người dùng không có quyền sửa điểm danh | Hiển thị trang 403 |

# 3. SD-03 – Thêm tiết trong quá khứ → Tạo điểm danh

## 3.1. Thông tin chung

| Mục | Nội dung |
| --- | --- |
| Mã | SD-03 |
| Tên | Thêm tiết trong quá khứ và tạo điểm danh |
| Mục tiêu | Khi thêm tiết trong quá khứ, hệ thống tạo các bản ghi điểm danh tương ứng cho học sinh liên quan và gán trạng thái khởi tạo đúng theo luật nghiệp vụ |
| Tác nhân chính | Admin |
| Thành phần tham gia | Màn hình thời khóa biểu, Module thời khóa biểu, Module điểm danh, Module xin nghỉ phép, Cơ sở dữ liệu |
| Tiền điều kiện | Tiết học được tạo thành công |
| Hậu điều kiện | Các bản ghi điểm danh được tạo mới; trạng thái khởi tạo được xác định theo đơn nghỉ đã duyệt hoặc theo mặc định hệ thống |
| Luật áp dụng | BR-ĐD-06, BR-ĐD-24, BR-ĐD-25 |
| Ngoại lệ | Không có học sinh bị ảnh hưởng |

## 3.2. Luồng chính

| Bước | Thành phần | Mô tả xử lý |
| --- | --- | --- |
| 1 | Admin | Chọn thêm tiết trong quá khứ |
| 2 | Màn hình thời khóa biểu | Gửi yêu cầu thêm tiết tới Module thời khóa biểu |
| 3 | Module thời khóa biểu | Tạo tiết học trong cơ sở dữ liệu |
| 4 | Module thời khóa biểu | Gửi yêu cầu tạo bản ghi điểm danh sang Module điểm danh |
| 5 | Module điểm danh | Duyệt qua danh sách học sinh bị ảnh hưởng |
| 6 | Module điểm danh | Kiểm tra với Module xin nghỉ phép xem có đơn nghỉ đã duyệt áp dụng cho thời điểm này hay không |
| 7 | Module xin nghỉ phép | Truy vấn cơ sở dữ liệu để tìm đơn nghỉ phù hợp |
| 8 | Cơ sở dữ liệu | Trả kết quả có hoặc không có đơn nghỉ đã duyệt |
| 9 | Module điểm danh | Nếu có đơn nghỉ đã duyệt thì tạo điểm danh = Nghỉ có phép, nguồn = Đơn nghỉ |
| 10 | Module điểm danh | Nếu không có đơn nghỉ đã duyệt thì tạo điểm danh = Có mặt, nguồn = Tự động hệ thống |
| 11 | Module điểm danh | Ghi log tạo điểm danh vào cơ sở dữ liệu |
| 12 | Module thời khóa biểu | Ghi log thêm tiết vào cơ sở dữ liệu |
| 13 | Màn hình thời khóa biểu | Hiển thị kết quả thêm tiết thành công |

## 3.3. Luồng thay thế / ngoại lệ

| Mã | Điều kiện | Xử lý |
| --- | --- | --- |
| A1 | Không có học sinh thuộc phạm vi áp dụng | Hệ thống tạo tiết nhưng không tạo điểm danh |
| A2 | Tạo tiết thất bại | Hệ thống dừng quy trình, không tạo điểm danh |

# 4. SD-04 – Hủy tiết trong quá khứ → Xóa bản ghi điểm danh

## 4.1. Thông tin chung

| Mục | Nội dung |
| --- | --- |
| Mã | SD-04 |
| Tên | Hủy tiết trong quá khứ và xóa bản ghi điểm danh |
| Mục tiêu | Khi hủy một tiết học trong quá khứ, các bản ghi điểm danh liên quan không còn tồn tại |
| Tác nhân chính | Admin |
| Thành phần tham gia | Màn hình thời khóa biểu, Module thời khóa biểu, Module điểm danh, Cơ sở dữ liệu |
| Tiền điều kiện | tiết học đang tồn tại |
| Hậu điều kiện | tiết học bị hủy; các bản ghi điểm danh liên quan bị xóa |
| Luật áp dụng | BR-ĐD-07, BR-ĐD-26, BR-ĐD-27 |
| Ngoại lệ | Không tìm thấy tiết học cần hủy |

## 4.2. Luồng chính

| Bước | Thành phần | Mô tả xử lý |
| --- | --- | --- |
| 1 | Admin | Chọn hủy tiết trong quá khứ |
| 2 | Màn hình thời khóa biểu | Gửi yêu cầu hủy tới Module thời khóa biểu |
| 3 | Module thời khóa biểu | Cập nhật trạng thái tiết học thành hủy trong cơ sở dữ liệu |
| 4 | Module thời khóa biểu | Gửi yêu cầu sang Module điểm danh để xóa các bản ghi liên quan |
| 5 | Module điểm danh | Tìm các bản ghi điểm danh theo tiết học |
| 6 | Cơ sở dữ liệu | Trả về danh sách bản ghi điểm danh liên quan |
| 7 | Module điểm danh | Xóa từng bản ghi điểm danh |
| 8 | Module điểm danh | Ghi log xóa vào cơ sở dữ liệu |
| 9 | Module thời khóa biểu | Ghi log hủy tiết vào cơ sở dữ liệu |
| 10 | Màn hình thời khóa biểu | Hiển thị kết quả hủy tiết thành công |

## 4.3. Luồng thay thế / ngoại lệ

| Mã | Điều kiện | Xử lý |
| --- | --- | --- |
| A1 | Không tìm thấy tiết học | Hệ thống trả lỗi |
| A2 | Không có bản ghi điểm danh liên quan | Hệ thống chỉ cập nhật trạng thái hủy của tiết học và ghi log |

# 5. SD-05 – Tác vụ tự động điểm danh

## 5.1. Thông tin chung

| Mục | Nội dung |
| --- | --- |
| Mã | SD-05 |
| Tên | Tác vụ tự động điểm danh |
| Mục tiêu | Hệ thống tự động gán hoặc cập nhật điểm danh mặc định cho các bản ghi đang tồn tại, nhưng không được ghi đè dữ liệu từ đơn nghỉ hoặc cập nhật thủ công |
| Tác nhân chính | Tác vụ hệ thống |
| Thành phần tham gia | Tác vụ tự động, Module điểm danh, Module xin nghỉ phép, Cơ sở dữ liệu |
| Tiền điều kiện | Có các bản ghi điểm danh đang tồn tại cần xử lý |
| Hậu điều kiện | Các bản ghi chưa có nguồn tầng 1 được cập nhật theo luật mặc định |
| Luật áp dụng | BR-ĐD-13, BR-ĐD-14, BR-ĐD-15 |
| Ngoại lệ | Dữ liệu tiết học hoặc danh sách bản ghi không hợp lệ |

## 5.2. Luồng chính

| Bước | Thành phần | Mô tả xử lý |
| --- | --- | --- |
| 1 | Tác vụ tự động | Gửi yêu cầu xử lý các bản ghi điểm danh hiện có |
| 2 | Module điểm danh | Lấy danh sách các bản ghi đang tồn tại từ cơ sở dữ liệu |
| 3 | Cơ sở dữ liệu | Trả về danh sách bản ghi |
| 4 | Module điểm danh | Duyệt từng bản ghi điểm danh |
| 5 | Module điểm danh | Lấy dữ liệu điểm danh hiện tại |
| 6 | Module điểm danh | Nếu nguồn hiện tại là Thủ công thì bỏ qua |
| 7 | Module điểm danh | Nếu nguồn hiện tại là Đơn nghỉ thì bỏ qua |
| 8 | Module điểm danh | Nếu chưa có nguồn tầng 1 thì kiểm tra có đơn nghỉ đã duyệt hay không |
| 9 | Module xin nghỉ phép | Truy vấn cơ sở dữ liệu để tìm đơn nghỉ phù hợp |
| 10 | Cơ sở dữ liệu | Trả về kết quả có hoặc không có đơn nghỉ đã duyệt |
| 11 | Module điểm danh | Nếu có đơn nghỉ đã duyệt thì cập nhật thành Nghỉ có phép, nguồn = Đơn nghỉ |
| 12 | Module điểm danh | Nếu không có đơn nghỉ đã duyệt thì cập nhật thành Có mặt, nguồn = Tự động hệ thống |
| 13 | Module điểm danh | Ghi log cập nhật vào cơ sở dữ liệu |

## 5.3. Luồng thay thế / ngoại lệ

| Mã | Điều kiện | Xử lý |
| --- | --- | --- |
| A1 | Không có bản ghi cần xử lý | Tác vụ kết thúc |
| A2 | Lỗi truy vấn đơn nghỉ | Ghi log lỗi và bỏ qua bản ghi hiện tại |
