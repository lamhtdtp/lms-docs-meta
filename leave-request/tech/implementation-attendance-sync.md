---
title: Implementation — Đồng bộ điểm danh sau khi APPROVED đơn nghỉ (Leave → Attendance)
scope: leave-request
status: ready-to-build
phase: 1A (sync) + 1B (reconcile SD-03/SD-05)
repos:
  - BE: ~/dev/dtp/lms-api
sources:
  - leave-request/SKILL.md (BR-LEAVE-03, BR-ATT-16..20, NG-03..07, SD-01..05)
  - leave-request/tech/teacher.md
  - leave-request/tech/admin.md
  - leave-request/tech/implementation-teacher-admin.md (phase trước — defer)
  - leave-request/testing/test-cases.md §6 TC-ATT-01..09
---

## 0. Quyết định kiến trúc đã chốt

| # | Câu hỏi | Quyết định | Lý do |
|---|---------|------------|-------|
| 1 | **Sync hay async** với review? | **Sync** (in-transaction) | UX rõ — user thấy điểm danh cập nhật ngay; rollback dễ; nếu p95 > 3s ở phase 2 sẽ chuyển async qua `@TransactionalEventListener(AFTER_COMMIT)`. |
| 2 | **APPROVED ngày tương lai** xử lý thế nào? | **Defer cho job auto + SD-03** | Đúng theo SKILL §SD-01: "nghỉ tương lai có thể chỉ hiện điểm danh khi đến ngày hiện hành". Service sẽ skip slot có `date > today`, counter `deferredFuture` cho audit. |
| 3 | **Audit table** dùng cái nào? | **Tạo bảng riêng `attendance_audit`** | Schema clean, chuyên cho điểm danh; index theo `source_ref_id` để query log theo `leave_request.id`; tách khỏi log đơn nghỉ (đã có hoặc sẽ có) để không trộn 2 domain. |
| 4 | **Batch size tối đa** cho 1 lần review? | **50 đơn / request** | Đủ cho UI bulk-select; chạy sync ~50 × ~5 slot = ~250 row update vẫn < 1s; > 50 → BE trả 400 `BATCH_TOO_LARGE`, UI chia chunk. |

> Phase 2 (optional, sau pilot): chuyển sang event `LeaveApprovedEvent` + worker async + metric/alert. Đã đặt sẵn extension point ở §6.

---

## 1. Tổng quan service

```
LeaveRequestService.review(req, ctx)               [TX boundary]
        │
        ├── update LeaveRequest.status = APPROVED/REJECTED
        ├── if APPROVED:
        │       outcome = LeaveAttendanceSyncService.applyApprovedLeaves(leaves)
        │       ↑ trả về số liệu: applied / idempotent / noSlot / deferredFuture / skippedNewerManual
        │
        └── NotificationService.notifyReviewBatch(leaves, outcome)
```

**Trigger thứ 2** (Phase 1B): khi TKB tạo tiết quá khứ → gọi `reconcileOnNewSlot(slotId)` → tra leave APPROVED phủ slot → áp dụng tương tự (SD-03).

---

## 2. Schema thay đổi

### 2.1 Bảng `attendance_audit` (mới)

```sql
CREATE TABLE attendance_audit (
  id              BIGSERIAL PRIMARY KEY,
  rollcall_id     BIGINT,                              -- NULL khi NO_SLOT
  student_id      BIGINT NOT NULL,
  slot_id         BIGINT,                              -- NULL khi NO_SLOT
  classroom_id    BIGINT NOT NULL,
  date            DATE   NOT NULL,
  session         VARCHAR(16) NOT NULL,                -- MORNING / AFTERNOON
  action          VARCHAR(32) NOT NULL,                -- APPLIED / NO_CHANGE / SKIPPED_NEWER_MANUAL / NO_SLOT / DEFERRED_FUTURE
  before_status   VARCHAR(32),
  after_status    VARCHAR(32),
  before_source   VARCHAR(32),
  after_source    VARCHAR(32),
  before_ref_id   BIGINT,
  after_ref_id    BIGINT,                              -- leave_request.id khi after_source=LEAVE_REQUEST
  actor_user_id   BIGINT,
  actor_role      VARCHAR(32),                         -- TEACHER / ADMIN / SUPER_ADMIN / SYSTEM
  reason          TEXT,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX att_audit_idx_ref_leave
  ON attendance_audit (after_ref_id) WHERE after_source = 'LEAVE_REQUEST';
CREATE INDEX att_audit_idx_student_date ON attendance_audit (student_id, date);
CREATE INDEX att_audit_idx_rollcall    ON attendance_audit (rollcall_id) WHERE rollcall_id IS NOT NULL;
```

Liquibase changeset:

```xml
<changeSet id="2026-05-13-01" author="lms-team">
  <createTable tableName="attendance_audit">
    <column name="id" type="bigserial"><constraints primaryKey="true" nullable="false"/></column>
    <column name="rollcall_id"    type="bigint"/>
    <column name="student_id"     type="bigint"><constraints nullable="false"/></column>
    <column name="slot_id"        type="bigint"/>
    <column name="classroom_id"   type="bigint"><constraints nullable="false"/></column>
    <column name="date"           type="date"><constraints nullable="false"/></column>
    <column name="session"        type="varchar(16)"><constraints nullable="false"/></column>
    <column name="action"         type="varchar(32)"><constraints nullable="false"/></column>
    <column name="before_status"  type="varchar(32)"/>
    <column name="after_status"   type="varchar(32)"/>
    <column name="before_source"  type="varchar(32)"/>
    <column name="after_source"   type="varchar(32)"/>
    <column name="before_ref_id"  type="bigint"/>
    <column name="after_ref_id"   type="bigint"/>
    <column name="actor_user_id"  type="bigint"/>
    <column name="actor_role"     type="varchar(32)"/>
    <column name="reason"         type="text"/>
    <column name="created_at" type="timestamp" defaultValueComputed="NOW()">
      <constraints nullable="false"/>
    </column>
  </createTable>
  <sql>CREATE INDEX att_audit_idx_ref_leave ON attendance_audit (after_ref_id) WHERE after_source = 'LEAVE_REQUEST';</sql>
  <sql>CREATE INDEX att_audit_idx_student_date ON attendance_audit (student_id, date);</sql>
  <sql>CREATE INDEX att_audit_idx_rollcall    ON attendance_audit (rollcall_id) WHERE rollcall_id IS NOT NULL;</sql>
</changeSet>
```

### 2.2 `rollcall` — cột phải có (verify trước khi build)

Bảng `rollcall` hiện tại (theo `RollCallService` + `EAttendanceStatus`) cần có **các cột** sau:

| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | bigserial | |
| `student_id` | bigint | |
| `slot_id` | bigint | hoặc `timetable_slot_id` — theo tên repo |
| `status` | varchar | `PRESENT` / `EXCUSED_ABSENCE` / `UNEXCUSED_ABSENCE` |
| `source` | varchar | `SYSTEM_AUTO` / `LEAVE_REQUEST` / `MANUAL` |
| `source_ref_id` | bigint | NULL hoặc `leave_request.id` |
| `updated_at` | timestamp | dùng cho last-write-wins NG-05 |
| `updated_by` | bigint | |

→ Nếu thiếu cột nào (vd `source_ref_id`, `source`) → bổ sung migration song song:

```xml
<changeSet id="2026-05-13-02" author="lms-team">
  <addColumn tableName="rollcall">
    <column name="source"        type="varchar(32)"/>
    <column name="source_ref_id" type="bigint"/>
  </addColumn>
  <sql>CREATE INDEX rollcall_idx_source_ref ON rollcall (source_ref_id) WHERE source_ref_id IS NOT NULL;</sql>
</changeSet>
```

> ⚠️ Spike trước khi viết: check `RollCall` entity hiện có, nếu đã có 2 cột này thì bỏ changeset 02.

### 2.3 `leave_request` — thêm `reviewed_at` nếu chưa có

Theo `tech/teacher.md` đã đề xuất `reviewed_by`, `reviewed_at`, `reviewed_by_role_code`. Bắt buộc có `reviewed_at` (đóng vai trò event timestamp cho NG-05).

---

## 3. Code skeleton

### 3.1 Domain `LeaveAttendanceOutcome.java`

```java
package vn.dtpsoft.modules.leaverequest.attendance;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Value;

@Value @Builder @AllArgsConstructor
public class LeaveAttendanceOutcome {
    int applied;             // số rollcall đã update / tạo theo leave
    int idempotent;          // đã apply trước, không thay đổi
    int noSlot;              // buổi không có tiết tồn tại
    int deferredFuture;      // slot.date > today — chờ job auto
    int skippedNewerManual;  // MANUAL mới hơn approval → giữ
    int totalLeavesProcessed;

    public static LeaveAttendanceOutcome empty() {
        return LeaveAttendanceOutcome.builder().build();
    }
}
```

### 3.2 `LeaveAttendanceSyncService.java`

```java
package vn.dtpsoft.modules.leaverequest.attendance;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.dtpsoft.constant.EAttendanceStatus;
import vn.dtpsoft.constant.EAttendanceSource;
import vn.dtpsoft.modules.leaverequest.domain.LeaveRequest;
import vn.dtpsoft.modules.leaverequest.domain.LeaveSession;
import vn.dtpsoft.modules.rollcall.domain.RollCall;
import vn.dtpsoft.modules.rollcall.domain.RollCallRepository;
import vn.dtpsoft.modules.timetable.TimetableQuery;
import vn.dtpsoft.modules.timetable.TimetableSlot;
import vn.dtpsoft.security.AuthContext;

import java.time.Clock;
import java.time.LocalDate;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class LeaveAttendanceSyncService {

    private final TimetableQuery            timetable;
    private final RollCallRepository        rollCallRepo;
    private final AttendanceAuditRepository auditRepo;
    private final Clock                     clock;

    /** Phase 1A — gọi từ LeaveRequestService.review khi status=APPROVED. */
    @Transactional
    public LeaveAttendanceOutcome applyApprovedLeaves(List<LeaveRequest> leaves, AuthContext ctx) {
        if (leaves == null || leaves.isEmpty()) return LeaveAttendanceOutcome.empty();
        Accumulator acc = new Accumulator();
        for (LeaveRequest l : leaves) applyOne(l, ctx, acc);
        acc.totalLeavesProcessed = leaves.size();
        log.info("Leave→Attendance sync: leaves={} applied={} idempotent={} noSlot={} deferred={} skipped={}",
            leaves.size(), acc.applied, acc.idempotent, acc.noSlot, acc.deferredFuture, acc.skippedNewerManual);
        return acc.build();
    }

    /** Phase 1B — gọi từ Timetable khi tạo tiết quá khứ (SD-03). */
    @Transactional
    public LeaveAttendanceOutcome reconcileOnNewSlot(TimetableSlot slot, AuthContext ctx) {
        // ... reuse logic; lookup leaves WHERE status=APPROVED
        // AND classroom_id=slot.classroomId AND <slot.date,slot.session> nằm trong session list
        // For each (student, leave): applyToSlot(slot, leave, rc, ctx, acc)
        return LeaveAttendanceOutcome.empty(); // implement tương tự applyOne
    }

    private void applyOne(LeaveRequest leave, AuthContext ctx, Accumulator acc) {
        LocalDate today = LocalDate.now(clock);
        for (LeaveSession s : leave.getSessions()) {
            if (s.date().isAfter(today)) {
                acc.deferredFuture++;
                continue;
            }
            List<TimetableSlot> slots = timetable.findSlotsByClassroomDateSession(
                leave.getClassroomId(), s.date(), s.session());

            if (slots.isEmpty()) {
                acc.noSlot++;
                auditRepo.save(AttendanceAudit.builder()
                    .studentId(leave.getStudentId())
                    .classroomId(leave.getClassroomId())
                    .date(s.date()).session(s.session().name())
                    .action(AttendanceAction.NO_SLOT)
                    .afterRefId(leave.getId())
                    .actorUserId(ctx.userId()).actorRole(ctx.role().name())
                    .reason("Leave APPROVED but no timetable slot")
                    .build());
                continue;
            }
            for (TimetableSlot slot : slots) applyToSlot(slot, leave, ctx, acc);
        }
    }

    private void applyToSlot(TimetableSlot slot, LeaveRequest leave, AuthContext ctx, Accumulator acc) {
        Optional<RollCall> existing = rollCallRepo
            .findByStudentIdAndSlotId(leave.getStudentId(), slot.id());

        DecideOutcome decision = decide(existing.orElse(null), leave);
        switch (decision) {
            case APPLY              -> doApply(slot, leave, existing.orElse(null), ctx, acc);
            case NO_CHANGE          -> { acc.idempotent++; }
            case SKIP_NEWER_MANUAL  -> {
                acc.skippedNewerManual++;
                auditRepo.save(snapshot(existing.get(), leave, AttendanceAction.SKIPPED_NEWER_MANUAL, ctx, null));
            }
        }
    }

    private DecideOutcome decide(RollCall rc, LeaveRequest leave) {
        if (rc == null) return DecideOutcome.APPLY;
        EAttendanceSource src = rc.getSource();
        if (src == null || src == EAttendanceSource.SYSTEM_AUTO) return DecideOutcome.APPLY;
        if (src == EAttendanceSource.LEAVE_REQUEST) {
            return Objects.equals(rc.getSourceRefId(), leave.getId())
                ? DecideOutcome.NO_CHANGE
                : DecideOutcome.APPLY;
        }
        if (src == EAttendanceSource.MANUAL) {
            return leave.getReviewedAt().isAfter(rc.getUpdatedAt())
                ? DecideOutcome.APPLY
                : DecideOutcome.SKIP_NEWER_MANUAL;
        }
        return DecideOutcome.APPLY;
    }

    private void doApply(TimetableSlot slot, LeaveRequest leave, RollCall existing, AuthContext ctx, Accumulator acc) {
        RollCall rc = existing != null ? existing : RollCall.builder()
            .studentId(leave.getStudentId())
            .slotId(slot.id())
            .build();

        AttendanceAudit audit = snapshot(rc, leave, AttendanceAction.APPLIED, ctx,
            existing == null ? "Created from leave APPROVED" : null);

        rc.setStatus(EAttendanceStatus.EXCUSED_ABSENCE);
        rc.setSource(EAttendanceSource.LEAVE_REQUEST);
        rc.setSourceRefId(leave.getId());
        rc.setUpdatedAt(leave.getReviewedAt());
        rc.setUpdatedBy(leave.getReviewedBy());
        rollCallRepo.save(rc);

        audit.setRollcallId(rc.getId());
        auditRepo.save(audit);

        acc.applied++;
    }

    private AttendanceAudit snapshot(RollCall rc, LeaveRequest leave, AttendanceAction action,
                                     AuthContext ctx, String reason) {
        return AttendanceAudit.builder()
            .rollcallId(rc != null ? rc.getId() : null)
            .studentId(leave.getStudentId())
            .slotId(rc != null ? rc.getSlotId() : null)
            .classroomId(leave.getClassroomId())
            .date(/* derive từ slot */ null)
            .session(/* derive */ null)
            .action(action)
            .beforeStatus(rc == null ? null : rc.getStatus() == null ? null : rc.getStatus().name())
            .afterStatus(action == AttendanceAction.APPLIED ? EAttendanceStatus.EXCUSED_ABSENCE.name() : null)
            .beforeSource(rc == null || rc.getSource() == null ? null : rc.getSource().name())
            .afterSource(action == AttendanceAction.APPLIED ? EAttendanceSource.LEAVE_REQUEST.name() : null)
            .beforeRefId(rc == null ? null : rc.getSourceRefId())
            .afterRefId(action == AttendanceAction.APPLIED ? leave.getId() : null)
            .actorUserId(ctx.userId()).actorRole(ctx.role().name())
            .reason(reason)
            .build();
    }

    private enum DecideOutcome { APPLY, NO_CHANGE, SKIP_NEWER_MANUAL }

    private static class Accumulator {
        int applied, idempotent, noSlot, deferredFuture, skippedNewerManual, totalLeavesProcessed;
        LeaveAttendanceOutcome build() {
            return LeaveAttendanceOutcome.builder()
                .applied(applied).idempotent(idempotent).noSlot(noSlot)
                .deferredFuture(deferredFuture).skippedNewerManual(skippedNewerManual)
                .totalLeavesProcessed(totalLeavesProcessed).build();
        }
    }
}
```

### 3.3 `LeaveRequestService.review` — sửa

```java
@Transactional
public ReviewResult review(ReviewRequest req, AuthContext ctx) {
    if (req.ids().size() > 50) {                                    // §0 #4
        throw new ApiException(ErrorCode.LEAVE_REVIEW_BATCH_TOO_LARGE);
    }

    List<LeaveRequest> leaves = leaveRepo.findAllPendingByIdsAndScope(req.ids(), ctx);
    if (leaves.isEmpty()) throw new ApiException(ErrorCode.LEAVE_NOT_PENDING);

    validateSingleBranch(leaves);                                   // BR đã có
    leaves.forEach(l -> {
        l.setStatus(req.status());
        l.setReviewedBy(ctx.userId());
        l.setReviewedByRoleCode(ctx.role().name());
        l.setReviewedAt(Instant.now());
        l.setRejectReason(req.status() == REJECTED ? req.rejectReason() : null);
    });
    leaveRepo.saveAll(leaves);

    LeaveAttendanceOutcome attendance = (req.status() == APPROVED)
        ? leaveAttendanceSyncService.applyApprovedLeaves(leaves, ctx)
        : LeaveAttendanceOutcome.empty();

    notificationService.notifyReviewBatch(leaves, attendance);
    return new ReviewResult(leaves, attendance);
}
```

### 3.4 Domain `AttendanceAudit` + repository

```java
@Entity
@Table(name = "attendance_audit")
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class AttendanceAudit {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "rollcall_id")    private Long rollcallId;
    @Column(name = "student_id")     private Long studentId;
    @Column(name = "slot_id")        private Long slotId;
    @Column(name = "classroom_id")   private Long classroomId;
    @Column(name = "date")           private LocalDate date;
    @Column(name = "session")        private String session;

    @Enumerated(EnumType.STRING) @Column(name = "action")
    private AttendanceAction action;

    @Column(name = "before_status") private String beforeStatus;
    @Column(name = "after_status")  private String afterStatus;
    @Column(name = "before_source") private String beforeSource;
    @Column(name = "after_source")  private String afterSource;
    @Column(name = "before_ref_id") private Long   beforeRefId;
    @Column(name = "after_ref_id")  private Long   afterRefId;
    @Column(name = "actor_user_id") private Long   actorUserId;
    @Column(name = "actor_role")    private String actorRole;
    @Column(name = "reason")        private String reason;

    @Column(name = "created_at", updatable = false, insertable = false)
    private Instant createdAt;
}

public enum AttendanceAction {
    APPLIED, NO_CHANGE, SKIPPED_NEWER_MANUAL, NO_SLOT, DEFERRED_FUTURE
}

public interface AttendanceAuditRepository extends JpaRepository<AttendanceAudit, Long> {
    List<AttendanceAudit> findByAfterRefIdOrderByCreatedAtDesc(Long leaveId);
    List<AttendanceAudit> findByStudentIdAndDateBetweenOrderByCreatedAtDesc(
        Long studentId, LocalDate from, LocalDate to);
}
```

### 3.5 Error codes mới

```java
public enum ErrorCode {
    // ...
    LEAVE_REVIEW_BATCH_TOO_LARGE("LEAVE_REVIEW_BATCH_TOO_LARGE", 400),
    LEAVE_NOT_PENDING            ("LEAVE_NOT_PENDING",            409),
}
```

---

## 4. API response — bổ sung `attendance` payload

Endpoint `PUT /leave-requests/review` trả thêm field để FE hiển thị toast:

```json
{
  "leaves": [
    { "id": 101, "status": "APPROVED", "reviewedAt": "2026-05-13T14:00:00Z" }
  ],
  "attendance": {
    "applied": 12,
    "idempotent": 0,
    "noSlot": 1,
    "deferredFuture": 4,
    "skippedNewerManual": 0,
    "totalLeavesProcessed": 3
  }
}
```

→ FE `lms-school` hiển thị:

> "Đã duyệt 3 đơn. Cập nhật **12 tiết điểm danh** (1 buổi không có tiết, 4 ngày tương lai sẽ tự động khi đến ngày)."

---

## 5. Test plan (đối chiếu `testing/test-cases.md` §6)

### 5.1 Unit `LeaveAttendanceSyncServiceTest`

| TC | Map test-cases.md | Precondition | Expected |
|----|-------------------|--------------|----------|
| applied_when_no_existing_record | TC-ATT-02 | Slot tồn tại, RollCall chưa có | tạo mới `EXCUSED + LEAVE_REQUEST`; audit `APPLIED` |
| applied_overwrite_system_auto | TC-ATT-03 | RC `PRESENT/SYSTEM_AUTO` | overwrite → `EXCUSED + LEAVE_REQUEST`; audit có before/after |
| no_change_when_same_leave | (idempotency) | Đã apply leave id=X | counter `idempotent++`, **không** ghi audit thừa |
| skipped_when_newer_manual | TC-ATT-05 | MANUAL updatedAt > leave.reviewedAt | giữ MANUAL; audit `SKIPPED_NEWER_MANUAL` |
| applied_when_leave_newer_than_manual | TC-ATT-05 (mirror) | MANUAL updatedAt < leave.reviewedAt | overwrite |
| deferred_when_future_date | (mới — phase 1A choice 2) | slotDate > today | counter `deferredFuture++`, **không** tạo audit |
| no_slot_when_timetable_empty | TC-ATT-04 | buổi không có tiết | audit `NO_SLOT`, counter `noSlot++` |
| multiple_slots_per_session | TC-ATT-02 (BR-ATT-30) | 1 buổi có N tiết | N record được update |
| rejected_no_sync | TC-LR-REVIEW-REJECT, NG-07 | status=REJECTED | service KHÔNG được gọi; không record nào đổi |
| batch_too_large_rejected | (mới — phase 1A choice 4) | 51 ids | 400 `LEAVE_REVIEW_BATCH_TOO_LARGE`; leaves unchanged |

### 5.2 Integration `LeaveRequestReviewIT`

| TC | Flow |
|----|------|
| review_approved_triggers_sync | seed leave PENDING + slot + auto attendance → PUT review APPROVED → DB thấy RC.source=LEAVE_REQUEST |
| review_rejected_no_attendance_change | PUT review REJECTED → audit table không có record cho leave này |
| batch_3_leaves_under_1s | seed 3 leaves × 5 slots/đơn → đo latency p95 |
| reconcile_new_slot_picks_approved_leave | seed leave APPROVED tương lai → tạo slot ngày đó → RC tạo với LEAVE_REQUEST |

### 5.3 Update test-cases.md

File `leave-request/testing/test-cases.md` §6 đã có TC-ATT-01..09 — không cần tạo mới, chỉ cập nhật trạng thái từ "phase sau" → "trong scope phase 1A".

---

## 6. Lộ trình triển khai

### Phase 1A — APPROVED → attendance (3–5 md)

| Bước | File | Validate |
|------|------|----------|
| 1 | Liquibase changeset `attendance_audit` + verify `rollcall` columns | `liquibase update` OK |
| 2 | `EAttendanceSource` enum (nếu chưa có) | compile pass |
| 3 | `AttendanceAudit` entity + repository | smoke save 1 record |
| 4 | `LeaveAttendanceSyncService.applyApprovedLeaves` | unit test 8 case |
| 5 | `LeaveRequestService.review` integrate | integration test 3 case |
| 6 | Response DTO + FE toast | manual UI test |
| 7 | Notification: truyền `attendance` outcome xuống template (xem `tech/notification.md`) | xem notify content có số liệu |

### Phase 1B — SD-03 reconcile khi thêm tiết quá khứ (2–3 md)

| Bước | File | Validate |
|------|------|----------|
| 8 | `LeaveAttendanceSyncService.reconcileOnNewSlot` | unit |
| 9 | Hook trong `TimetableService.createSlot` (hoặc event listener) | integration |
| 10 | Job auto attendance — verify skip tầng 1 (đã có hoặc cần thêm guard) | regression existing tests |

### Phase 2 (sau pilot, optional) — Async + metric

- Publish `LeaveApprovedEvent(leaveIds, ctx)` sau `saveAll(leaves)`.
- `@TransactionalEventListener(AFTER_COMMIT)` → worker bean → `applyApprovedLeaves`.
- Metric Micrometer: `leave_attendance_sync.{applied,deferred,skipped}` counter; `leave_attendance_sync.latency` histogram.
- Alert: `applied=0` cho leave APPROVED có slot tồn tại > 10 lần/giờ.

---

## 7. Risk & Gotcha

| Risk | Hành động |
|------|-----------|
| `rollcall.source` chưa có cột | Migration 02 ở §2.2; spike trước |
| Batch 50 đơn × 5 slot × N HS → row update lớn | Đo trên dev với data thực; nếu chậm → chia chunk 25 hoặc chuyển async sớm |
| `LeaveRequest.reviewedAt` được set bằng `Instant.now()` — không bằng wall-clock client → vẫn OK cho NG-05 nhưng phải nhất quán trong cùng tx | Set 1 lần ở đầu `review()`, dùng chung cho cả leave và audit |
| `MANUAL` đang được edit cùng lúc với review (race condition) | DB row lock optimistic (`@Version`) trên `RollCall`; hoặc chấp nhận last-write-wins ở DB level |
| TKB chỉnh sửa giữa lúc review (slot bị huỷ) | Service đọc slot trong cùng tx; nếu slot bị huỷ sau → hard-delete cascades sẽ xoá RC luôn (đã có theo BR-ATT-02) — audit table giữ lịch sử |
| FE hiển thị toast với số "deferred=4" nhưng PH/HS không hiểu | UX message: "4 ngày tương lai sẽ tự cập nhật khi đến ngày" — ghi rõ trong i18n |

---

## 8. Liên kết doc

- `leave-request/tech/implementation-teacher-admin.md` §2.4 → ghi rõ "đã làm xong, xem file này".
- `leave-request/tech/teacher.md` §"Khi duyệt Đồng ý" → link tới service `LeaveAttendanceSyncService`.
- `leave-request/tech/admin.md` §"Dùng chung entity, duyệt & điểm danh" → tương tự.
- `leave-request/tech/notification.md` → truyền `attendance.applied` vào nội dung notify.
- `leave-request/est2.md` → BE-C cập nhật: phase 1A ~3–5 md + 1B ~2–3 md = **5–8 md** (giảm so với ước lượng ban đầu 10–22 vì chốt rõ scope, defer async).

---

*Cập nhật khi: rollcall schema khác giả định; hoặc sau spike batch performance; hoặc chuyển sang async.*
