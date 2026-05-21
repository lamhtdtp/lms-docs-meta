# OpenSync TTC — Query test sau sync (school_id=13)

Context đã chốt:
- `school_id = 13`
- `default_branch_id = 9741`
- `school_year_id = 9725`

## 1) Verify config map đúng branch/schoolYear

```sql
SELECT *
FROM ttc_opensync_config
WHERE school_id = 13
  AND default_branch_id = 9741
  AND enabled = 1
  AND deleted = 0;
```

## 2) Grade sync vào branch 9741

```sql
SELECT COUNT(*) AS grade_count
FROM grade
WHERE branch_id = 9741
  AND deleted = 0;
```

Spot-check vài grade:

```sql
SELECT id, code, name, level, status
FROM grade
WHERE branch_id = 9741 AND deleted = 0
ORDER BY level ASC, id DESC
LIMIT 50;
```

## 3) Classroom sync vào branch 9741 + school_year 9725

```sql
SELECT COUNT(*) AS classroom_count
FROM classroom
WHERE branch_id = 9741
  AND school_year_id = 9725
  AND deleted = 0;
```

Spot-check:

```sql
SELECT id, code, name, grade_id, status, priority
FROM classroom
WHERE branch_id = 9741
  AND school_year_id = 9725
  AND deleted = 0
ORDER BY id DESC
LIMIT 50;
```

## 4) Classroom thiếu grade (không nên có)

```sql
SELECT id, code, name
FROM classroom
WHERE branch_id = 9741
  AND school_year_id = 9725
  AND deleted = 0
  AND grade_id IS NULL;
```

## 5) User STUDENT/TEACHER có role ở branch 9741

```sql
SELECT r.code AS role_code, COUNT(*) AS cnt
FROM user_branch_role ubr
JOIN `user` u ON u.id = ubr.user_id AND u.deleted = 0
JOIN role r ON r.id = ubr.role_id
WHERE ubr.branch_id = 9741
  AND r.code IN ('STUDENT', 'TEACHER')
GROUP BY r.code;
```

## 6) Học sinh đã vào lớp (classroom_student ACTIVE) trong school_year 9725

```sql
SELECT COUNT(*) AS classroom_student_active
FROM classroom_student cs
JOIN classroom c ON c.id = cs.classroom_id AND c.deleted = 0
WHERE c.branch_id = 9741
  AND c.school_year_id = 9725
  AND cs.status = 'ACTIVE';
```

## 7) Học sinh có role STUDENT nhưng chưa có ClassroomStudent ACTIVE (trong year 9725)

```sql
SELECT u.id, u.username, u.citizen_identity_code, u.last_name, u.first_name
FROM `user` u
JOIN user_branch_role ubr ON ubr.user_id = u.id AND ubr.branch_id = 9741
JOIN role r ON r.id = ubr.role_id AND r.code = 'STUDENT'
LEFT JOIN classroom_student cs ON cs.student_id = u.id AND cs.status = 'ACTIVE'
LEFT JOIN classroom c ON c.id = cs.classroom_id
  AND c.deleted = 0
  AND c.school_year_id = 9725
  AND c.branch_id = 9741
WHERE u.deleted = 0
  AND c.id IS NULL
LIMIT 200;
```

## 8) ClassroomStudent trỏ tới classroom khác branch/year (để bắt sai mapping)

```sql
SELECT cs.id, cs.student_id, cs.classroom_id, cs.status, c.branch_id, c.school_year_id
FROM classroom_student cs
JOIN classroom c ON c.id = cs.classroom_id
WHERE cs.status = 'ACTIVE'
  AND (c.branch_id <> 9741 OR c.school_year_id <> 9725)
LIMIT 200;
```

## 9) Duplicate CIC trong school 13 (nếu sync tạo duplicate sẽ thấy)

```sql
SELECT u.citizen_identity_code, COUNT(*) AS cnt
FROM `user` u
WHERE u.school_id = 13
  AND u.deleted = 0
  AND u.citizen_identity_code IS NOT NULL
  AND u.citizen_identity_code <> ''
GROUP BY u.citizen_identity_code
HAVING COUNT(*) > 1;
```

## 10) Tổng user school 13 và số user có CIC (để so với số HS/GV từ OpenSync)

```sql
SELECT
  COUNT(*) AS total_users,
  SUM(CASE WHEN citizen_identity_code IS NOT NULL AND citizen_identity_code <> '' THEN 1 ELSE 0 END) AS has_cic
FROM `user`
WHERE school_id = 13 AND deleted = 0;
```

