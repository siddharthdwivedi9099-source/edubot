"""
Seed a realistic demo school ERP database (SQLite) so EduBot has live data
to query out-of-the-box. In production, point ERP_DB_URL at the school's
real MySQL/PostgreSQL/MSSQL instance instead.

Run:
    python scripts/seed_db.py
Outputs:
    backend/app/data/demo_school.db   (SQLite)

Schema covers: students, parents, teachers, classes, subjects, attendance,
fees, exam results, transport, library, and timetable.
"""
import asyncio
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import aiosqlite

random.seed(7)
DB_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "demo_school.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    grade INTEGER NOT NULL,
    section TEXT NOT NULL,
    class_teacher_id INTEGER,
    UNIQUE(grade, section)
);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY,
    employee_code TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    department TEXT,
    joined_on DATE
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    admission_no TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob DATE,
    gender TEXT,
    class_id INTEGER NOT NULL,
    house TEXT,
    blood_group TEXT,
    enrolled_on DATE,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE IF NOT EXISTS parents (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    relation TEXT,
    name TEXT,
    email TEXT,
    phone TEXT,
    occupation TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status TEXT CHECK(status IN ('present','absent','leave','late')),
    UNIQUE(student_id, date),
    FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS fees (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    quarter TEXT,
    amount_due REAL,
    amount_paid REAL DEFAULT 0,
    due_date DATE,
    paid_on DATE,
    status TEXT CHECK(status IN ('paid','due','overdue','partial')),
    FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS exam_results (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    exam TEXT,
    max_marks INTEGER,
    obtained_marks REAL,
    grade TEXT,
    term TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);

CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL,
    day_of_week INTEGER, -- 0=Mon
    period INTEGER,
    subject_id INTEGER,
    teacher_id INTEGER,
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id),
    FOREIGN KEY(teacher_id) REFERENCES teachers(id)
);

CREATE TABLE IF NOT EXISTS transport_routes (
    id INTEGER PRIMARY KEY,
    route_code TEXT UNIQUE,
    description TEXT,
    fee_slab TEXT
);

CREATE TABLE IF NOT EXISTS student_transport (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    route_id INTEGER,
    pickup_stop TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(route_id) REFERENCES transport_routes(id)
);

CREATE TABLE IF NOT EXISTS library_loans (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    book_title TEXT,
    issued_on DATE,
    due_on DATE,
    returned_on DATE,
    status TEXT CHECK(status IN ('issued','returned','overdue')),
    FOREIGN KEY(student_id) REFERENCES students(id)
);
"""

FIRST_NAMES_M = ["Aarav", "Vihaan", "Aditya", "Krish", "Ishaan", "Arjun", "Reyansh",
                 "Kabir", "Anish", "Vivaan", "Rohan", "Aryan", "Ayaan", "Dhruv"]
FIRST_NAMES_F = ["Saanvi", "Aanya", "Aadhya", "Diya", "Pari", "Ananya", "Myra",
                 "Anika", "Riya", "Avni", "Kiara", "Siya", "Ishita", "Navya"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Iyer", "Reddy", "Patel", "Kumar",
              "Singh", "Joshi", "Nair", "Mehta", "Rao", "Mukherjee", "Bose",
              "Shah", "Khan", "D'Souza", "Pillai"]
HOUSES = ["Tagore", "Gandhi", "Nehru", "Vivekananda"]
SECTIONS = ["A", "B", "C"]
SUBJECTS = [
    ("ENG", "English"), ("MAT", "Mathematics"), ("SCI", "Science"),
    ("SST", "Social Studies"), ("HIN", "Hindi"), ("CS", "Computer Science"),
    ("PHY", "Physics"), ("CHE", "Chemistry"), ("BIO", "Biology"),
    ("ECO", "Economics"), ("ACC", "Accountancy"), ("BST", "Business Studies"),
    ("HIS", "History"), ("GEO", "Geography"), ("PE", "Physical Education"),
]
DEPTS = ["Languages", "Mathematics", "Sciences", "Humanities", "Computer Science",
         "Physical Education", "Arts"]


def random_phone() -> str:
    return f"+91-{random.choice(['98','99','97','96','70','80'])}{random.randint(10000000, 99999999)}"


def random_dob(grade: int) -> date:
    base = date.today().year - (5 + grade)
    return date(base, random.randint(1, 12), random.randint(1, 28))


async def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    async with aiosqlite.connect(DB_PATH) as db:
        # Enable FK support
        await db.execute("PRAGMA foreign_keys = ON")

        # Schema
        for stmt in SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                await db.execute(stmt)
        await db.commit()

        # ── Teachers ──
        teachers = []
        for i in range(40):
            gender = random.choice(["M", "F"])
            fn = random.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
            ln = random.choice(LAST_NAMES)
            t = (
                f"T{1000+i}", fn, ln,
                f"{fn.lower()}.{ln.lower()}@school.edu",
                random_phone(),
                random.choice(DEPTS),
                date.today() - timedelta(days=random.randint(200, 4000)),
            )
            teachers.append(t)
        await db.executemany(
            "INSERT INTO teachers(employee_code,first_name,last_name,email,phone,"
            "department,joined_on) VALUES (?,?,?,?,?,?,?)",
            teachers,
        )

        # ── Classes (grades 1–12, three sections each) ──
        class_rows = []
        for g in range(1, 13):
            for sec in SECTIONS:
                class_rows.append((g, sec, random.randint(1, 40)))
        await db.executemany(
            "INSERT INTO classes(grade,section,class_teacher_id) VALUES (?,?,?)", class_rows
        )

        # ── Subjects ──
        await db.executemany(
            "INSERT INTO subjects(code,name) VALUES (?,?)", SUBJECTS
        )
        await db.commit()

        # Get subject IDs
        cur = await db.execute("SELECT id, code FROM subjects")
        subject_ids = {code: sid for sid, code in await cur.fetchall()}
        cur = await db.execute("SELECT id, grade, section FROM classes")
        class_rows = await cur.fetchall()  # [(id, grade, section), ...]

        # ── Students (about 30 per class → ~1080 total) ──
        students = []
        student_class_map = []
        for cid, grade, section in class_rows:
            for i in range(random.randint(28, 32)):
                gender = random.choice(["M", "F"])
                fn = random.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
                ln = random.choice(LAST_NAMES)
                adm_no = f"S{grade:02d}{section}{i:03d}{random.randint(1,99):02d}"
                students.append((
                    adm_no, fn, ln, random_dob(grade), gender, cid,
                    random.choice(HOUSES),
                    random.choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
                    date.today() - timedelta(days=random.randint(60, 2400)),
                ))
                student_class_map.append((adm_no, cid, grade))
        await db.executemany(
            "INSERT INTO students(admission_no,first_name,last_name,dob,gender,"
            "class_id,house,blood_group,enrolled_on) VALUES (?,?,?,?,?,?,?,?,?)",
            students,
        )
        await db.commit()

        cur = await db.execute("SELECT id, admission_no FROM students")
        student_id_by_admission = {a: sid for sid, a in await cur.fetchall()}
        all_student_ids = list(student_id_by_admission.values())

        # ── Parents ──
        parent_rows = []
        for adm_no, sid in student_id_by_admission.items():
            father_name = f"{random.choice(FIRST_NAMES_M)} {random.choice(LAST_NAMES)}"
            mother_name = f"{random.choice(FIRST_NAMES_F)} {random.choice(LAST_NAMES)}"
            parent_rows.append((sid, "Father", father_name,
                                f"father.{adm_no.lower()}@example.com",
                                random_phone(),
                                random.choice(["Engineer", "Doctor", "Business", "Teacher", "Govt Officer"])))
            parent_rows.append((sid, "Mother", mother_name,
                                f"mother.{adm_no.lower()}@example.com",
                                random_phone(),
                                random.choice(["Homemaker", "Doctor", "Engineer", "Lawyer", "Designer"])))
        await db.executemany(
            "INSERT INTO parents(student_id,relation,name,email,phone,occupation) "
            "VALUES (?,?,?,?,?,?)", parent_rows
        )

        # ── Attendance: last 60 working days ──
        att_rows = []
        today = date.today()
        for d in range(60):
            day = today - timedelta(days=d)
            if day.weekday() >= 5:  # skip weekends
                continue
            for sid in all_student_ids:
                # 92% present, 4% absent, 2% leave, 2% late
                r = random.random()
                if r < 0.92: status = "present"
                elif r < 0.96: status = "absent"
                elif r < 0.98: status = "leave"
                else: status = "late"
                att_rows.append((sid, day.isoformat(), status))
        # Insert in chunks
        for i in range(0, len(att_rows), 5000):
            await db.executemany(
                "INSERT OR IGNORE INTO attendance(student_id,date,status) VALUES (?,?,?)",
                att_rows[i:i+5000]
            )
        await db.commit()

        # ── Fees ──
        fee_rows = []
        for sid in all_student_ids:
            for q_idx, q in enumerate(["Q1", "Q2", "Q3", "Q4"]):
                amt = random.choice([12000, 15500, 19500, 23000, 27000])
                due_date = date(today.year, [4, 7, 10, 1][q_idx], 10)
                # Past quarters often paid; future quarters mostly due
                if due_date < today:
                    paid = amt if random.random() > 0.08 else 0
                    status = "paid" if paid else "overdue"
                    paid_on = (due_date + timedelta(days=random.randint(0, 5))) if paid else None
                else:
                    paid = 0
                    status = "due"
                    paid_on = None
                fee_rows.append((sid, q, amt, paid, due_date.isoformat(),
                                 paid_on.isoformat() if paid_on else None, status))
        await db.executemany(
            "INSERT INTO fees(student_id,quarter,amount_due,amount_paid,"
            "due_date,paid_on,status) VALUES (?,?,?,?,?,?,?)",
            fee_rows,
        )

        # ── Exam results ──
        result_rows = []
        # Pick 5 subjects per student (depending on grade)
        for adm_no, sid in student_id_by_admission.items():
            grade = next((g for an, _cid, g in student_class_map if an == adm_no), 6)
            if grade <= 5:
                subjects_for_student = ["ENG", "MAT", "SCI", "SST", "HIN"]
            elif grade <= 10:
                subjects_for_student = ["ENG", "MAT", "SCI", "SST", "HIN", "CS"]
            else:
                subjects_for_student = random.sample(
                    ["ENG", "PHY", "CHE", "MAT", "BIO", "CS", "ECO", "ACC", "BST", "HIS", "GEO"],
                    5,
                )
            for sub_code in subjects_for_student:
                for exam_name, term in [("Periodic Test 1", "T1"),
                                        ("Half-Yearly", "T1"),
                                        ("Periodic Test 2", "T2")]:
                    max_m = 80 if "Half" in exam_name else 40
                    obtained = round(random.gauss(max_m * 0.72, max_m * 0.12), 1)
                    obtained = max(0, min(max_m, obtained))
                    pct = obtained / max_m * 100
                    if pct >= 90: g_letter = "A1"
                    elif pct >= 80: g_letter = "A2"
                    elif pct >= 70: g_letter = "B1"
                    elif pct >= 60: g_letter = "B2"
                    elif pct >= 50: g_letter = "C1"
                    elif pct >= 40: g_letter = "C2"
                    else: g_letter = "D"
                    result_rows.append((sid, subject_ids[sub_code], exam_name,
                                        max_m, obtained, g_letter, term))
        for i in range(0, len(result_rows), 5000):
            await db.executemany(
                "INSERT INTO exam_results(student_id,subject_id,exam,max_marks,"
                "obtained_marks,grade,term) VALUES (?,?,?,?,?,?,?)",
                result_rows[i:i+5000],
            )

        # ── Timetable ──
        tt_rows = []
        teacher_count = 40
        for cid, grade, _section in class_rows:
            if grade <= 5:
                subs = ["ENG", "MAT", "SCI", "SST", "HIN", "PE"]
            elif grade <= 10:
                subs = ["ENG", "MAT", "SCI", "SST", "HIN", "CS", "PE"]
            else:
                subs = ["ENG", "PHY", "CHE", "MAT", "BIO", "CS", "PE"]
            for dow in range(5):  # Mon–Fri
                random.shuffle(subs)
                for period in range(7):
                    sub_code = subs[period % len(subs)]
                    tt_rows.append((cid, dow, period + 1,
                                    subject_ids[sub_code],
                                    random.randint(1, teacher_count)))
        await db.executemany(
            "INSERT INTO timetable(class_id,day_of_week,period,subject_id,teacher_id) "
            "VALUES (?,?,?,?,?)", tt_rows,
        )

        # ── Transport ──
        routes = [
            ("R-A1", "Sector 14 → Sector 56 → School", "Slab A"),
            ("R-A2", "Old Town → Civil Lines → School", "Slab A"),
            ("R-B1", "Greenfield → Lake Road → School", "Slab B"),
            ("R-B2", "DLF Phase 3 → Tower Road → School", "Slab B"),
            ("R-C1", "Highway Junction → Outer Ring → School", "Slab C"),
            ("R-C2", "Industrial Area → North Avenue → School", "Slab C"),
        ]
        await db.executemany(
            "INSERT INTO transport_routes(route_code,description,fee_slab) VALUES (?,?,?)", routes
        )
        cur = await db.execute("SELECT id FROM transport_routes")
        route_ids = [r[0] for r in await cur.fetchall()]
        # ~60% of students use transport
        st_rows = []
        for sid in all_student_ids:
            if random.random() < 0.6:
                st_rows.append((sid, random.choice(route_ids),
                                f"Stop {random.randint(1, 12)}"))
        await db.executemany(
            "INSERT INTO student_transport(student_id,route_id,pickup_stop) VALUES (?,?,?)",
            st_rows,
        )

        # ── Library loans ──
        BOOKS = ["The Hobbit", "Wings of Fire", "A Brief History of Time",
                 "Charlie and the Chocolate Factory", "Sapiens", "Diary of a Young Girl",
                 "Things Fall Apart", "Pride and Prejudice", "Train to Pakistan",
                 "Discovery of India", "Wings of Fire", "The Alchemist",
                 "1984", "To Kill a Mockingbird", "Little Women",
                 "Five Point Someone", "Malgudi Days", "Panchatantra"]
        loan_rows = []
        for sid in random.sample(all_student_ids, k=int(len(all_student_ids) * 0.4)):
            for _ in range(random.randint(1, 4)):
                issued = today - timedelta(days=random.randint(0, 90))
                due = issued + timedelta(days=14)
                returned = (issued + timedelta(days=random.randint(2, 18))) if random.random() > 0.2 else None
                if returned:
                    status = "returned"
                elif due < today:
                    status = "overdue"
                else:
                    status = "issued"
                loan_rows.append((sid, random.choice(BOOKS),
                                  issued.isoformat(), due.isoformat(),
                                  returned.isoformat() if returned else None, status))
        await db.executemany(
            "INSERT INTO library_loans(student_id,book_title,issued_on,due_on,"
            "returned_on,status) VALUES (?,?,?,?,?,?)",
            loan_rows,
        )

        await db.commit()

        # Print summary
        for tbl in ["students", "teachers", "parents", "attendance", "fees",
                    "exam_results", "timetable", "transport_routes", "library_loans"]:
            cur = await db.execute(f"SELECT COUNT(*) FROM {tbl}")
            n = (await cur.fetchone())[0]
            print(f"  {tbl:<20} {n:>8} rows")

    print(f"\n✅ Demo ERP DB written to {DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
