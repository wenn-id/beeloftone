BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS workforce_employees (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS workforce_employee_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    employee_id TEXT NOT NULL REFERENCES workforce_employees(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    department TEXT NOT NULL CHECK(department=trim(department) AND length(department) BETWEEN 1 AND 160),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(employee_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS workforce_employee_events_current
    ON workforce_employee_events(employee_id,sequence DESC);

CREATE TABLE IF NOT EXISTS workforce_attendance_records (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES workforce_employees(id),
    work_date TEXT NOT NULL CHECK(date(work_date) IS NOT NULL AND work_date=date(work_date)),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(employee_id,work_date)
) STRICT;

CREATE TABLE IF NOT EXISTS workforce_attendance_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    attendance_id TEXT NOT NULL REFERENCES workforce_attendance_records(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    status TEXT NOT NULL CHECK(status IN ('present','leave','absent')),
    clock_in TEXT,
    clock_out TEXT,
    overtime_minutes INTEGER NOT NULL CHECK(overtime_minutes BETWEEN 0 AND 720),
    notes TEXT NOT NULL CHECK(notes=trim(notes) AND length(notes)<=1000),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(attendance_id,revision),
    CHECK((status='present' AND time(clock_in) IS NOT NULL AND time(clock_out) IS NOT NULL
           AND clock_in<clock_out)
       OR (status IN ('leave','absent') AND clock_in IS NULL AND clock_out IS NULL
           AND overtime_minutes=0))
) STRICT;
CREATE INDEX IF NOT EXISTS workforce_attendance_events_current
    ON workforce_attendance_events(attendance_id,sequence DESC);

CREATE TRIGGER IF NOT EXISTS workforce_employees_no_update
BEFORE UPDATE ON workforce_employees
BEGIN SELECT RAISE(ABORT,'Workforce employees are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_employees_no_delete
BEFORE DELETE ON workforce_employees
BEGIN SELECT RAISE(ABORT,'Workforce employees are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_employee_events_no_update
BEFORE UPDATE ON workforce_employee_events
BEGIN SELECT RAISE(ABORT,'Workforce employee history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_employee_events_no_delete
BEFORE DELETE ON workforce_employee_events
BEGIN SELECT RAISE(ABORT,'Workforce employee history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_attendance_records_no_update
BEFORE UPDATE ON workforce_attendance_records
BEGIN SELECT RAISE(ABORT,'Workforce attendance records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_attendance_records_no_delete
BEFORE DELETE ON workforce_attendance_records
BEGIN SELECT RAISE(ABORT,'Workforce attendance records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_attendance_events_no_update
BEFORE UPDATE ON workforce_attendance_events
BEGIN SELECT RAISE(ABORT,'Workforce attendance history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_attendance_events_no_delete
BEFORE DELETE ON workforce_attendance_events
BEGIN SELECT RAISE(ABORT,'Workforce attendance history is immutable'); END;

PRAGMA user_version=50;
COMMIT;
