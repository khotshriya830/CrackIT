from flask import Flask, request, redirect, url_for, session, render_template_string
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "crackit_secret_2026"

DATABASE = "crackit.db"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create/migrate the CrackIt database without deleting existing data."""
    conn = get_db()

    # -------------------- TABLES --------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            eligibility TEXT,
            qualification TEXT,
            age TEXT,
            pattern TEXT,
            selection TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam TEXT NOT NULL,
            exam_id INTEGER,
            type TEXT NOT NULL DEFAULT 'Study Material',
            description TEXT,
            link TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            exam TEXT NOT NULL,
            questions INTEGER NOT NULL,
            exam_id INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            explanation TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------- SAFE MIGRATION --------------------
    # CREATE TABLE IF NOT EXISTS does NOT add columns to an old database.
    # These checks fix the exact 'no such column: exams.age' and
    # 'no such column: materials.exam' problems without deleting the DB.
    def columns(table):
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    exam_cols = columns("exams")
    for col, definition in {
        "category": "TEXT",
        "description": "TEXT",
        "eligibility": "TEXT",
        "qualification": "TEXT",
        "age": "TEXT",
        "pattern": "TEXT",
        "selection": "TEXT"
    }.items():
        if col not in exam_cols:
            conn.execute(f"ALTER TABLE exams ADD COLUMN {col} {definition}")

    material_cols = columns("materials")
    for col, definition in {
        "exam": "TEXT",
        "exam_id": "INTEGER",
        "type": "TEXT NOT NULL DEFAULT 'Study Material'",
        "description": "TEXT",
        "link": "TEXT"
    }.items():
        if col not in material_cols:
            conn.execute(f"ALTER TABLE materials ADD COLUMN {col} {definition}")

    test_cols = columns("tests")
    for col, definition in {"exam": "TEXT", "questions": "INTEGER", "exam_id": "INTEGER"}.items():
        if col not in test_cols:
            conn.execute(f"ALTER TABLE tests ADD COLUMN {col} {definition}")

    # -------------------- EXAMS --------------------
    exam_rows = [
        ("UPSC Civil Services", "Civil Services", "India's premier examination for recruitment to IAS, IPS, IFS and other services.", "Indian citizen with required educational qualification.", "Bachelor's degree from a recognized university.", "21 - 32 years generally, subject to category relaxations.", "Prelims → Mains → Interview", "Prelims → Mains → Personality Test"),
        ("MPSC Rajyaseva", "State Government", "Maharashtra Public Service Commission State Services Examination.", "Candidate must satisfy MPSC eligibility requirements.", "Bachelor's degree from a recognized university.", "Generally 19 - 38 years, subject to applicable rules.", "Prelims → Mains → Interview", "Prelims → Mains → Interview"),
        ("SSC CGL", "Staff Selection", "Graduate-level examination for various central government posts.", "Candidate must meet SSC eligibility criteria.", "Bachelor's degree for most posts.", "Generally 18 - 32 years depending on post.", "Tier-based computer examinations", "Tier examinations → Document Verification"),
        ("Banking PO", "Banking", "Competitive examination for Probationary Officer positions.", "Candidate must satisfy the respective banking examination rules.", "Bachelor's degree.", "Usually 20 - 30 years depending on examination.", "Prelims → Mains → Interview", "Prelims → Mains → Interview"),
        ("NDA & NA", "Defence", "National Defence Academy examination for entry into Armed Forces training.", "Candidate must satisfy NDA eligibility conditions.", "12th standard qualification as applicable.", "Age criteria as specified in the official notification.", "Written Examination → SSB", "Written → SSB → Medical → Merit"),
        ("JEE Main", "Engineering Entrance", "National level entrance examination for engineering admissions.", "Candidates must satisfy current JEE eligibility rules.", "Class 12 with required subjects.", "As specified by current admission rules.", "Computer Based Test", "Exam → Rank → Counselling")
    ]

    for row in exam_rows:
        existing = conn.execute("SELECT id FROM exams WHERE name = ?", (row[0],)).fetchone()
        if existing:
            conn.execute("""
                UPDATE exams SET category=?, description=?, eligibility=?, qualification=?,
                age=?, pattern=?, selection=? WHERE id=?
            """, (*row[1:], existing[0]))
        else:
            conn.execute("""
                INSERT INTO exams
                (name, category, description, eligibility, qualification, age, pattern, selection)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

    # -------------------- FIX OLD MATERIAL ROWS --------------------
    exam_aliases = {
        "UPSC": "UPSC Civil Services",
        "MPSC": "MPSC Rajyaseva",
        "SSC": "SSC CGL",
        "Banking": "Banking PO",
        "NDA": "NDA & NA",
        "JEE": "JEE Main",
        "All Exams": None
    }
    for old_name, full_name in exam_aliases.items():
        if full_name:
            conn.execute("""
                UPDATE materials
                SET exam = ?
                WHERE exam = ?
            """, (full_name, old_name))

    conn.execute("""
        UPDATE materials
        SET exam_id = (
            SELECT e.id FROM exams e
            WHERE LOWER(TRIM(materials.exam)) = LOWER(TRIM(e.name))
            LIMIT 1
        )
        WHERE exam_id IS NULL
    """)

    result_cols = columns("results")
    for col, definition in {
        "user_id": "INTEGER",
        "exam_id": "INTEGER",
        "score": "INTEGER",
        "total_questions": "INTEGER",
        "percentage": "REAL",
        "created_at": "TIMESTAMP"
    }.items():
        if col not in result_cols:
            conn.execute(f"ALTER TABLE results ADD COLUMN {col} {definition}")

    # -------------------- TESTS --------------------
    test_rows = [
        ("UPSC General Studies Mock", "UPSC Civil Services"),
        ("MPSC General Knowledge Test", "MPSC Rajyaseva"),
        ("SSC CGL Practice Challenge", "SSC CGL"),
        ("Banking Aptitude Test", "Banking PO"),
        ("NDA Defence Awareness Test", "NDA & NA"),
        ("JEE Main Physics & Mathematics Test", "JEE Main")
    ]
    for title, exam_name in test_rows:
        exam = conn.execute("SELECT id FROM exams WHERE name = ?", (exam_name,)).fetchone()
        if not exam:
            continue
        # Use the exam name for compatibility with older databases that
        # do not yet have the optional tests.exam_id column.
        existing = conn.execute(
            "SELECT id FROM tests WHERE LOWER(TRIM(exam)) = LOWER(TRIM(?)) LIMIT 1",
            (exam_name,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE tests SET title=?, exam=?, questions=? WHERE id=?",
                (title, exam_name, 50, existing[0])
            )
        else:
            conn.execute(
                "INSERT INTO tests (title, exam, questions) VALUES (?, ?, ?)",
                (title, exam_name, 50)
            )

    # -------------------- QUESTION BANK MIGRATION --------------------
    # Older versions stored questions with a required test_id. The current
    # system stores questions against exam_id so one live question bank can
    # power every mock-test attempt.
    question_info = conn.execute("PRAGMA table_info(questions)").fetchall()
    if question_info:
        question_cols = {row[1] for row in question_info}
        if "test_id" in question_cols:
            old_questions = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("ALTER TABLE questions RENAME TO questions_legacy")
            conn.execute("""
                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id INTEGER,
                    question TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    explanation TEXT
                )
            """)

            def legacy_value(row, names, default=""):
                for name in names:
                    if name in row.keys():
                        return row[name]
                return default

            for old in old_questions:
                exam_id = legacy_value(old, ["exam_id"], None)

                if not exam_id:
                    old_test_id = legacy_value(old, ["test_id"], None)
                    if old_test_id:
                        test_row = conn.execute(
                            "SELECT exam_id, exam FROM tests WHERE id=?",
                            (old_test_id,)
                        ).fetchone()
                        if test_row:
                            exam_id = test_row["exam_id"]
                            if not exam_id and test_row["exam"]:
                                exam_row = conn.execute(
                                    "SELECT id FROM exams WHERE LOWER(TRIM(name)) LIKE LOWER(?) LIMIT 1",
                                    (f"%{test_row['exam']}%",)
                                ).fetchone()
                                if exam_row:
                                    exam_id = exam_row["id"]

                if not exam_id:
                    old_exam = legacy_value(old, ["exam"], "")
                    if old_exam:
                        exam_row = conn.execute(
                            "SELECT id FROM exams WHERE LOWER(TRIM(name)) LIKE LOWER(?) LIMIT 1",
                            (f"%{old_exam}%",)
                        ).fetchone()
                        if exam_row:
                            exam_id = exam_row["id"]

                q_text = legacy_value(old, ["question", "question_text"], "") or ""
                a = legacy_value(old, ["option_a", "a"], "") or ""
                b = legacy_value(old, ["option_b", "b"], "") or ""
                c = legacy_value(old, ["option_c", "c"], "") or ""
                d = legacy_value(old, ["option_d", "d"], "") or ""
                correct = (legacy_value(old, ["correct_answer", "answer", "correct"], "") or "").upper().strip()
                explanation = legacy_value(old, ["explanation"], "") or ""

                if exam_id and q_text and a and b and c and d and correct in {"A", "B", "C", "D"}:
                    conn.execute("""
                        INSERT INTO questions
                        (exam_id, question, option_a, option_b, option_c, option_d, correct_answer, explanation)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (exam_id, q_text, a, b, c, d, correct, explanation))

            conn.execute("DROP TABLE questions_legacy")
            conn.execute("PRAGMA foreign_keys = ON")

    # Ensure the current question table exists and has all required columns.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            explanation TEXT
        )
    """)

    question_cols = columns("questions")
    for col, definition in {
        "exam_id": "INTEGER",
        "question": "TEXT",
        "option_a": "TEXT",
        "option_b": "TEXT",
        "option_c": "TEXT",
        "option_d": "TEXT",
        "correct_answer": "TEXT",
        "explanation": "TEXT"
    }.items():
        if col not in question_cols:
            conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {definition}")

    # -------------------- MATERIALS --------------------
    material_rows = [
        ("Indian Polity Notes", "Polity", "UPSC Civil Services", "Constitution, Parliament, Fundamental Rights and governance basics."),
        ("Modern Indian History", "History", "UPSC Civil Services", "Important modern Indian history topics for revision."),
        ("Maharashtra GK", "General Knowledge", "MPSC Rajyaseva", "Maharashtra history, geography and general knowledge."),
        ("Quantitative Aptitude", "Quantitative Aptitude", "SSC CGL", "Arithmetic and numerical practice for competitive examinations."),
        ("Reasoning Practice Set", "Reasoning", "SSC CGL", "Practice material for common reasoning patterns."),
        ("Banking Awareness Notes", "Banking Awareness", "Banking PO", "Banking terminology and basic financial concepts."),
        ("Defence Awareness", "General Knowledge", "NDA & NA", "Defence awareness and general knowledge revision."),
        ("Physics & Mathematics Revision", "PCM", "JEE Main", "Quick revision material for selected JEE Main concepts."),
        ("Current Affairs - Monthly", "Current Affairs", "All Exams", "Monthly current-affairs revision for competitive-exam preparation.")
    ]
    for title, subject, exam_name, description in material_rows:
        exam = conn.execute("SELECT id FROM exams WHERE name = ?", (exam_name,)).fetchone()
        if exam:
            exists = conn.execute("SELECT id FROM materials WHERE title = ? AND exam_id = ?", (title, exam[0])).fetchone()
            if not exists:
                conn.execute("""
                    INSERT INTO materials (title, subject, exam, exam_id, type, description, link)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (title, subject, exam_name, exam[0], "Study Material", description, "#"))

    # -------------------- 50 QUESTIONS PER EXAM --------------------
    # Each tuple = question, A, B, C, D, correct option, explanation.
    question_sets = {
        "UPSC Civil Services": [
            ("Which part of the Indian Constitution contains Fundamental Rights?", "Part I", "Part II", "Part III", "Part IV", "C", "Fundamental Rights are contained in Part III."),
            ("The Directive Principles of State Policy are included in which part?", "Part II", "Part III", "Part IV", "Part V", "C", "Directive Principles are in Part IV."),
            ("Who is the constitutional head of the Union?", "Prime Minister", "President", "Chief Justice", "Speaker", "B", "The President is the constitutional head of the Union."),
            ("What is the normal term of the Lok Sabha?", "3 years", "4 years", "5 years", "6 years", "C", "The normal term is five years unless dissolved earlier."),
            ("Which body conducts the UPSC Civil Services Examination?", "UPSC", "SSC", "NTA", "IBPS", "A", "The Union Public Service Commission conducts it."),
            ("The Constitution of India was adopted on which date?", "15 August 1947", "26 November 1949", "26 January 1950", "2 October 1950", "B", "The Constitution was adopted on 26 November 1949."),
            ("Which is the highest court in India?", "High Court", "District Court", "Supreme Court", "Tribunal", "C", "The Supreme Court is the highest court in India."),
            ("Who appoints the Prime Minister of India?", "President", "Chief Justice", "Parliament", "Election Commission", "A", "The President appoints the Prime Minister."),
            ("Which house is also known as the Council of States?", "Lok Sabha", "Rajya Sabha", "Vidhan Sabha", "Vidhan Parishad", "B", "Rajya Sabha is the Council of States."),
            ("Which amendment added Fundamental Duties to the Constitution?", "42nd", "44th", "73rd", "86th", "A", "The 42nd Amendment added Fundamental Duties."),
            ("Who is the ex-officio Chairman of the Rajya Sabha?", "President", "Vice-President", "Prime Minister", "Speaker", "B", "The Vice-President is the ex-officio Chairman of Rajya Sabha."),
            ("Article 21 protects which right?", "Right to Property", "Right to Life and Personal Liberty", "Right to Vote", "Right to Education only", "B", "Article 21 protects life and personal liberty."),
            ("The President of India is elected by which body?", "Directly by citizens", "Electoral College", "Lok Sabha only", "Rajya Sabha only", "B", "The President is elected by an Electoral College."),
            ("Which constitutional body recommends the distribution of tax revenues between Centre and States?", "Election Commission", "Finance Commission", "UPSC", "CAG", "B", "The Finance Commission performs this role."),
            ("Who is the guardian of the Constitution?", "Parliament", "Supreme Court", "Election Commission", "President", "B", "The Supreme Court safeguards constitutional provisions through judicial review."),
            ("The minimum age for membership of Lok Sabha is?", "18", "21", "25", "30", "C", "A Lok Sabha member must be at least 25 years old."),
            ("The minimum age for membership of Rajya Sabha is?", "21", "25", "30", "35", "C", "A Rajya Sabha member must be at least 30 years old."),
            ("Which schedule contains the Union, State and Concurrent Lists?", "Fifth", "Seventh", "Ninth", "Tenth", "B", "The Seventh Schedule contains the three legislative lists."),
            ("Which amendment introduced Panchayati Raj constitutional status?", "42nd", "61st", "73rd", "74th", "C", "The 73rd Amendment deals with Panchayats."),
            ("Which amendment gave constitutional status to urban local bodies?", "73rd", "74th", "86th", "91st", "B", "The 74th Amendment deals with municipalities."),
            ("Who audits the accounts of the Union and States?", "CAG", "UPSC", "Finance Commission", "NITI Aayog", "A", "The Comptroller and Auditor General audits government accounts."),
            ("Which institution replaced the Planning Commission?", "Finance Commission", "NITI Aayog", "UPSC", "GST Council", "B", "NITI Aayog replaced the Planning Commission."),
            ("What is the upper house of Parliament called?", "Lok Sabha", "Rajya Sabha", "Vidhan Sabha", "Gram Sabha", "B", "Rajya Sabha is the upper house of Parliament."),
            ("Money Bills can be introduced only in which house?", "Rajya Sabha", "Lok Sabha", "Either House", "State Legislature", "B", "A Money Bill can be introduced only in Lok Sabha."),
            ("Who certifies a bill as a Money Bill in Parliament?", "President", "Prime Minister", "Lok Sabha Speaker", "Rajya Sabha Chairman", "C", "The Lok Sabha Speaker certifies a Money Bill."),
            ("Which Fundamental Right abolishes untouchability?", "Article 14", "Article 15", "Article 17", "Article 19", "C", "Article 17 abolishes untouchability."),
            ("Freedom of speech and expression is protected under which article?", "Article 14", "Article 19", "Article 21", "Article 32", "B", "Article 19 includes freedom of speech and expression."),
            ("Who can proclaim a National Emergency under the Constitution?", "Prime Minister", "President", "Chief Justice", "Speaker", "B", "The President proclaims an Emergency under the Constitution."),
            ("Which article deals with constitutional remedies?", "Article 19", "Article 21", "Article 32", "Article 44", "C", "Article 32 provides the right to constitutional remedies."),
            ("The Preamble declares India to be a?", "Monarchy", "Sovereign Socialist Secular Democratic Republic", "Federal Monarchy", "Unitary Kingdom", "B", "These words describe India's constitutional identity."),
            ("Who is the nominal executive at the Union level?", "Prime Minister", "President", "Cabinet Secretary", "Speaker", "B", "The President is the nominal constitutional executive."),
            ("The real executive at the Union level is headed by the?", "President", "Prime Minister", "Chief Justice", "Vice-President", "B", "The Prime Minister heads the Council of Ministers."),
            ("Which body conducts elections to Parliament and State Legislatures?", "UPSC", "Election Commission of India", "CAG", "Finance Commission", "B", "The Election Commission conducts these elections."),
            ("The Governor of a State is appointed by the?", "Chief Minister", "President", "State Legislature", "High Court", "B", "The President appoints the Governor."),
            ("The Council of Ministers is collectively responsible to which house in a state?", "Legislative Council", "Legislative Assembly", "High Court", "Governor only", "B", "The state Council of Ministers is collectively responsible to the Legislative Assembly."),
            ("Which writ is used to produce a person unlawfully detained before the court?", "Mandamus", "Habeas Corpus", "Certiorari", "Quo Warranto", "B", "Habeas Corpus protects against unlawful detention."),
            ("Which writ commands a public authority to perform a legal duty?", "Mandamus", "Habeas Corpus", "Prohibition", "Quo Warranto", "A", "Mandamus orders performance of a public duty."),
            ("Which institution is responsible for monetary policy in India?", "RBI", "SEBI", "NITI Aayog", "CAG", "A", "The Reserve Bank of India is the monetary authority."),
            ("What is GDP?", "Gross Domestic Product", "General Development Plan", "Gross Development Price", "Government Domestic Policy", "A", "GDP is Gross Domestic Product."),
            ("Inflation generally means?", "Fall in general prices", "Rise in general price level", "Rise in exports only", "Fall in money supply only", "B", "Inflation is a sustained rise in the general price level."),
            ("Which sector includes agriculture?", "Primary", "Secondary", "Tertiary", "Quaternary only", "A", "Agriculture belongs to the primary sector."),
            ("Which sector mainly includes manufacturing?", "Primary", "Secondary", "Tertiary", "Household", "B", "Manufacturing is part of the secondary sector."),
            ("Which sector includes banking and transport services?", "Primary", "Secondary", "Tertiary", "Agricultural", "C", "Banking and transport are service activities in the tertiary sector."),
            ("The Green Revolution in India is mainly associated with increased production of?", "Food grains", "Tea only", "Cotton only", "Jute only", "A", "The Green Revolution greatly increased food-grain production."),
            ("Which gas is most abundant in Earth's atmosphere?", "Oxygen", "Nitrogen", "Carbon dioxide", "Argon", "B", "Nitrogen forms the largest share of Earth's atmosphere."),
            ("Which layer protects Earth from much of the Sun's ultraviolet radiation?", "Troposphere", "Ozone layer", "Mesosphere", "Core", "B", "Stratospheric ozone absorbs much ultraviolet radiation."),
            ("Photosynthesis mainly takes place in which cell organelle?", "Mitochondria", "Chloroplast", "Nucleus", "Ribosome", "B", "Chloroplasts contain chlorophyll and carry out photosynthesis."),
            ("Which is a renewable source of energy?", "Coal", "Petroleum", "Solar energy", "Natural gas", "C", "Solar energy is renewable."),
            ("The Indian monsoon is strongly influenced by?", "Seasonal reversal of winds", "Only ocean tides", "Earthquakes", "Volcanic eruptions", "A", "Monsoon winds show a seasonal reversal of direction."),
            ("Which is the longest river in India by course within India commonly cited in exams?", "Ganga", "Narmada", "Tapi", "Mahanadi", "A", "The Ganga is commonly identified as India's longest river."),
            ("The Himalayas are an example of?", "Block mountains", "Fold mountains", "Volcanic mountains", "Residual hills", "B", "The Himalayas are young fold mountains."),
        ],
        "MPSC Rajyaseva": [
            ("What is the capital of Maharashtra?", "Pune", "Mumbai", "Nagpur", "Nashik", "B", "Mumbai is the capital of Maharashtra."),
            ("Which sea lies to the west of Maharashtra?", "Bay of Bengal", "Arabian Sea", "Indian Ocean", "Red Sea", "B", "Maharashtra has a western coastline along the Arabian Sea."),
            ("Which city is known as the cultural capital of Maharashtra?", "Pune", "Nashik", "Kolhapur", "Akola", "A", "Pune is widely known as the cultural capital of Maharashtra."),
            ("The Maharashtra Public Service Commission is abbreviated as?", "MPSC", "MPPSC", "UPSC", "SSC", "A", "MPSC stands for Maharashtra Public Service Commission."),
            ("Which fort is associated with Chhatrapati Shivaji Maharaj's coronation?", "Raigad", "Sinhagad", "Pratapgad", "Lohagad", "A", "The coronation took place at Raigad Fort."),
            ("Which river system is associated with Pune city?", "Mula-Mutha", "Yamuna", "Kaveri", "Teesta", "A", "The Mula and Mutha rivers meet at Pune."),
            ("Which language is primarily associated with Maharashtra?", "Gujarati", "Marathi", "Kannada", "Bengali", "B", "Marathi is the principal language of Maharashtra."),
            ("Which mountain range runs through western Maharashtra?", "Western Ghats", "Aravalli", "Himalaya", "Eastern Ghats", "A", "The Western Ghats run along western Maharashtra."),
            ("Which festival has a major public tradition in Maharashtra?", "Onam", "Ganesh Chaturthi", "Bihu", "Pongal", "B", "Ganesh Chaturthi has a major public tradition in Maharashtra."),
            ("Which Maharashtra city is famous for vineyards and wine production?", "Nashik", "Solapur", "Amravati", "Akola", "A", "Nashik is well known for vineyards and wine production."),
            ("Which is the largest city in Maharashtra by population?", "Nagpur", "Mumbai", "Nashik", "Kolhapur", "B", "Mumbai is the largest city by population among these options."),
            ("Nagpur is known as the winter capital of which state?", "Gujarat", "Maharashtra", "Goa", "Madhya Pradesh", "B", "Nagpur is the winter capital of Maharashtra."),
            ("Which city is associated with the Ajanta Caves region?", "Aurangabad", "Ratnagiri", "Satara", "Latur", "A", "The Ajanta Caves are in Maharashtra's Chhatrapati Sambhajinagar region."),
            ("Ellora Caves are located in which state?", "Maharashtra", "Rajasthan", "Odisha", "Kerala", "A", "Ellora Caves are in Maharashtra."),
            ("Which fort is famous for the Treaty of Purandar context?", "Purandar", "Raigad", "Torna", "Sindhudurg", "A", "The Treaty of Purandar is associated with Purandar Fort."),
            ("Sindhudurg Fort was built under which ruler?", "Shivaji Maharaj", "Akbar", "Ashoka", "Tipu Sultan", "A", "Sindhudurg was built under Chhatrapati Shivaji Maharaj."),
            ("Which river is one of Maharashtra's major east-flowing rivers?", "Godavari", "Narmada", "Tapi", "Sabarmati", "A", "The Godavari flows eastward through Maharashtra."),
            ("Which river flows westward into the Arabian Sea?", "Godavari", "Krishna", "Tapi", "Yamuna", "C", "The Tapi flows westward into the Arabian Sea."),
            ("Which district is famous for the Lonar crater lake?", "Buldhana", "Pune", "Raigad", "Satara", "A", "Lonar Lake is in Buldhana district."),
            ("Which city is associated with the Deekshabhoomi monument?", "Nagpur", "Mumbai", "Pune", "Nashik", "A", "Deekshabhoomi is a major Buddhist monument in Nagpur."),
            ("Who founded the Satyashodhak Samaj?", "Jyotirao Phule", "Lokmanya Tilak", "Gopal Krishna Gokhale", "Savarkar", "A", "Jyotirao Phule founded the Satyashodhak Samaj in 1873."),
            ("Who is associated with the social reform movement for women's education in Maharashtra?", "Savitribai Phule", "Rani Lakshmibai", "Sarojini Naidu", "Annie Besant", "A", "Savitribai Phule was a pioneer of women's education."),
            ("Who founded the newspaper Kesari?", "Bal Gangadhar Tilak", "Jyotirao Phule", "Gopal Ganesh Agarkar", "Dadabhai Naoroji", "A", "Kesari was founded by Bal Gangadhar Tilak."),
            ("Which reformer was associated with the newspaper Sudharak?", "Gopal Ganesh Agarkar", "Tilak", "Phule", "Shahu Maharaj", "A", "Agarkar was closely associated with Sudharak."),
            ("Chhatrapati Shahu Maharaj is especially remembered for?", "Social justice and education reforms", "Space research", "Banking reforms", "Railway construction", "A", "Shahu Maharaj promoted education and social justice."),
            ("Which is a major cash crop of Maharashtra?", "Sugarcane", "Tea", "Coffee", "Rubber", "A", "Sugarcane is an important cash crop in Maharashtra."),
            ("Which crop is strongly associated with Vidarbha?", "Cotton", "Tea", "Rubber", "Coconut", "A", "Cotton is a major crop of Vidarbha."),
            ("Which region of Maharashtra is known for Konkan's coastal geography?", "Western coastal belt", "Northern plateau only", "Eastern desert", "Himalayan belt", "A", "Konkan forms Maharashtra's western coastal belt."),
            ("Which is a major port of Maharashtra?", "Mumbai Port", "Paradip", "Kandla", "Tuticorin", "A", "Mumbai Port is a major port in Maharashtra."),
            ("Which national park is in Maharashtra?", "Tadoba-Andhari", "Kaziranga", "Gir", "Ranthambore", "A", "Tadoba-Andhari is in Maharashtra."),
            ("Tadoba-Andhari is especially known for?", "Tigers", "One-horned rhinoceros", "Asiatic lions", "Snow leopards", "A", "Tadoba-Andhari is a major tiger habitat."),
            ("Which sanctuary is famous for Indian wild ass?", "Radhanagari", "Little Rann of Kutch", "Bhimashankar", "Koyna", "B", "The Little Rann of Kutch is famous for the Indian wild ass."),
            ("Bhimashankar is famous for a temple dedicated to?", "Shiva", "Vishnu", "Brahma", "Surya", "A", "Bhimashankar is one of the Jyotirlinga shrines dedicated to Shiva."),
            ("Which river originates near Mahabaleshwar?", "Krishna", "Ganga", "Yamuna", "Brahmaputra", "A", "The Krishna River originates near Mahabaleshwar."),
            ("Which hill station is in the Sahyadri range?", "Mahabaleshwar", "Jaisalmer", "Shimla only", "Darjeeling only", "A", "Mahabaleshwar is in the Sahyadri/Western Ghats."),
            ("Which city is famous for the annual Pandharpur Wari?", "Pandharpur", "Nagpur", "Nashik", "Thane", "A", "Pandharpur is the destination of the Wari pilgrimage."),
            ("The Wari tradition is strongly associated with devotion to?", "Vithoba", "Jagannath", "Rama only", "Buddha", "A", "The Wari is devoted to Vithoba of Pandharpur."),
            ("Which sea fort is near Malvan?", "Sindhudurg", "Daulatabad", "Raigad", "Shivneri", "A", "Sindhudurg Fort is near Malvan on the Konkan coast."),
            ("Which fort is associated with Shivaji Maharaj's birthplace?", "Shivneri", "Raigad", "Pratapgad", "Purandar", "A", "Shivneri Fort is associated with his birthplace."),
            ("The Maharashtra Legislative Assembly is located in?", "Mumbai", "Nagpur only", "Pune", "Nashik", "A", "The main Legislative Assembly is in Mumbai."),
            ("Which city hosts the Maharashtra Legislature's winter session traditionally?", "Nagpur", "Nashik", "Kolhapur", "Aurangabad", "A", "Nagpur traditionally hosts the winter session."),
            ("Which district is associated with the Koyna Dam?", "Satara", "Pune", "Dhule", "Bhandara", "A", "Koyna Dam is in Satara district."),
            ("Koyna project is mainly associated with?", "Hydroelectric power", "Nuclear power", "Solar-only power", "Wind-only power", "A", "The Koyna project is a major hydroelectric project."),
            ("Which city is known as the Oxford of the East in common usage?", "Pune", "Mumbai", "Nagpur", "Nashik", "A", "Pune is popularly called the Oxford of the East."),
            ("Which industry is especially important in western Maharashtra?", "Sugar industry", "Jute only", "Tea only", "Rubber only", "A", "Sugar cooperatives and sugar industry are important in western Maharashtra."),
            ("Which district is known for the Bibi Ka Maqbara?", "Chhatrapati Sambhajinagar", "Pune", "Satara", "Solapur", "A", "Bibi Ka Maqbara is in Chhatrapati Sambhajinagar."),
            ("Which river is important to Nashik and originates near Trimbakeshwar?", "Godavari", "Krishna", "Narmada", "Tapi", "A", "The Godavari originates near Trimbakeshwar in Nashik district."),
            ("Which place is one of the major Kumbh Mela sites in Maharashtra?", "Nashik-Trimbakeshwar", "Kolhapur", "Ratnagiri", "Latur", "A", "Nashik-Trimbakeshwar hosts a Kumbh gathering."),
            ("Which commission conducts Maharashtra State Services Examination?", "MPSC", "UPSC", "SSC", "IBPS", "A", "MPSC conducts Maharashtra State Services examinations."),
        ],
        "SSC CGL": [
            ("If 20% of a number is 40, what is the number?", "100", "150", "200", "250", "C", "40 ÷ 0.20 = 200."),
            ("Find the next number: 2, 4, 8, 16, ?", "24", "32", "36", "40", "B", "Each number is multiplied by 2."),
            ("Which word is the opposite of 'Ancient'?", "Old", "Modern", "Historic", "Past", "B", "Modern is the opposite of ancient."),
            ("If A=1, B=2, then C=?", "2", "3", "4", "5", "B", "C is the third letter."),
            ("What is 15 × 6?", "80", "90", "100", "120", "B", "15 × 6 = 90."),
            ("A train covers 60 km in 1 hour. What is its speed?", "30 km/h", "45 km/h", "60 km/h", "90 km/h", "C", "Speed is 60 km/h."),
            ("Which is a prime number?", "21", "27", "29", "33", "C", "29 is prime."),
            ("The average of 10 and 20 is?", "10", "15", "20", "30", "B", "(10+20)/2 = 15."),
            ("Which one is a synonym of 'Rapid'?", "Slow", "Fast", "Weak", "Late", "B", "Rapid means fast."),
            ("If a book costs ₹200 and discount is ₹20, selling price is?", "₹160", "₹170", "₹180", "₹190", "C", "₹200 - ₹20 = ₹180."),
            ("What is 25% of 240?", "40", "50", "60", "80", "C", "240 × 25/100 = 60."),
            ("Simplify: 3/4 + 1/4", "1/2", "1", "3/2", "2", "B", "The sum is 1."),
            ("What is the HCF of 12 and 18?", "3", "6", "9", "12", "B", "The HCF is 6."),
            ("What is the LCM of 4 and 6?", "8", "10", "12", "24", "C", "The LCM is 12."),
            ("If a:b = 2:3 and b=15, a=?", "5", "10", "12", "15", "B", "2/3 × 15 = 10."),
            ("A shopkeeper buys an item for ₹500 and sells it for ₹600. Profit percent?", "10%", "15%", "20%", "25%", "C", "Profit is ₹100, so 100/500 × 100 = 20%."),
            ("Simple interest on ₹1000 at 10% per annum for 2 years is?", "₹100", "₹150", "₹200", "₹250", "C", "SI = PRT/100 = ₹200."),
            ("If a man walks 5 km in 1 hour, how far in 4 hours at same speed?", "10 km", "15 km", "20 km", "25 km", "C", "5 × 4 = 20 km."),
            ("A right angle measures?", "45°", "90°", "180°", "360°", "B", "A right angle is 90 degrees."),
            ("The perimeter of a square of side 5 cm is?", "10 cm", "15 cm", "20 cm", "25 cm", "C", "Perimeter = 4 × 5 = 20 cm."),
            ("Which number is divisible by 3?", "124", "125", "126", "127", "C", "1+2+6 = 9, divisible by 3."),
            ("What is 12²?", "124", "144", "154", "164", "B", "12 × 12 = 144."),
            ("What is √81?", "7", "8", "9", "10", "C", "9 × 9 = 81."),
            ("If 5 workers finish a job in 10 days, total worker-days are?", "15", "25", "50", "100", "C", "5 × 10 = 50 worker-days."),
            ("The next term of 5, 10, 15, 20 is?", "22", "24", "25", "30", "C", "The sequence increases by 5."),
            ("Choose the correctly spelled word.", "Accomodation", "Accommodation", "Acommodation", "Accommadation", "B", "Accommodation is the correct spelling."),
            ("One who cannot read or write is called?", "Literate", "Illiterate", "Scholar", "Editor", "B", "Illiterate means unable to read or write."),
            ("Opposite of 'Expand' is?", "Extend", "Contract", "Increase", "Enlarge", "B", "Contract means to become smaller."),
            ("Synonym of 'Brief' is?", "Short", "Long", "Heavy", "Late", "A", "Brief means short."),
            ("Which is a noun?", "Quickly", "Honesty", "Run", "Beautiful", "B", "Honesty is a noun."),
            ("If SOUTH is coded as T P V U I, the coding mainly shifts letters by?", "-1", "+1", "+2", "No shift", "B", "Each letter is shifted one position forward."),
            ("A clock shows 3:00. The angle between hands is?", "0°", "45°", "90°", "180°", "C", "At 3:00 the hands are at 90 degrees."),
            ("If today is Monday, what day will it be after 10 days?", "Wednesday", "Thursday", "Friday", "Saturday", "B", "10 mod 7 = 3; Monday + 3 = Thursday."),
            ("Find the odd one out: Apple, Mango, Potato, Banana", "Apple", "Mango", "Potato", "Banana", "C", "Potato is a vegetable; the others are fruits."),
            ("Complete: Book : Read :: Food : ?", "Cook", "Eat", "Buy", "Sell", "B", "Food is eaten."),
            ("If CAT = 24 using letter positions, DOG = ?", "24", "26", "26", "30", "B", "D+O+G = 4+15+7 = 26."),
            ("A person facing north turns right. Which direction now?", "West", "East", "South", "North", "B", "A right turn from north points east."),
            ("Which is the smallest prime number?", "0", "1", "2", "3", "C", "2 is the smallest prime number."),
            ("What is 7 × 8?", "54", "56", "58", "64", "B", "7 × 8 = 56."),
            ("If a:b = 4:5 and a=20, b=?", "15", "20", "25", "30", "C", "20 × 5/4 = 25."),
            ("A discount of 10% on ₹800 gives selling price?", "₹700", "₹720", "₹740", "₹760", "B", "10% of ₹800 is ₹80; SP = ₹720."),
            ("What is the median of 2, 4, 6, 8, 10?", "4", "5", "6", "8", "C", "The middle value is 6."),
            ("What is the mode of 2, 3, 3, 4, 5?", "2", "3", "4", "5", "B", "3 occurs most often."),
            ("Which gas is essential for human respiration?", "Nitrogen", "Oxygen", "Carbon dioxide", "Hydrogen", "B", "Humans require oxygen for aerobic respiration."),
            ("The SI unit of force is?", "Joule", "Newton", "Watt", "Pascal", "B", "Force is measured in newtons."),
            ("Who is known as the Father of the Indian Constitution?", "B. R. Ambedkar", "Mahatma Gandhi", "Rajendra Prasad", "Sardar Patel", "A", "B. R. Ambedkar chaired the Drafting Committee."),
            ("The Indian national animal is?", "Lion", "Tiger", "Elephant", "Leopard", "B", "The Bengal tiger is India's national animal."),
            ("Which planet is known as the Red Planet?", "Venus", "Mars", "Jupiter", "Mercury", "B", "Mars is known as the Red Planet."),
            ("Which organ filters blood in the human body?", "Heart", "Kidney", "Lung", "Stomach", "B", "Kidneys filter blood and form urine."),
        ],
        "Banking PO": [
            ("What does ATM stand for?", "Automatic Teller Machine", "Any Time Money", "Automated Transfer Mode", "Account Transfer Machine", "A", "ATM means Automatic Teller Machine."),
            ("What is the full form of RBI?", "Reserve Bank of India", "Rural Bank of India", "Regional Bank of India", "Reserve Banking Institute", "A", "RBI stands for Reserve Bank of India."),
            ("A savings account primarily helps customers to?", "Store and manage money", "Issue passports", "Conduct elections", "Register vehicles", "A", "Savings accounts are used to deposit and manage money."),
            ("What is a cheque?", "A written payment instruction", "A loan agreement", "A tax bill", "A share certificate", "A", "A cheque is a written payment instruction."),
            ("What does EMI commonly mean?", "Equated Monthly Instalment", "Estimated Money Index", "Electronic Monthly Income", "Equal Market Interest", "A", "EMI means Equated Monthly Instalment."),
            ("Which institution regulates banking in India?", "RBI", "NITI Aayog", "SEBI only", "NTA", "A", "RBI is India's central bank and banking regulator."),
            ("What is interest?", "Cost of borrowing or return on deposits", "A currency", "A bank branch", "A tax only", "A", "Interest can be the cost of borrowing or return earned on deposits."),
            ("Which system is used for instant digital payments in India?", "UPI", "GPS", "HTML", "SMTP", "A", "UPI is a digital payments system."),
            ("What does KYC stand for?", "Know Your Customer", "Keep Your Cash", "Know Your Credit", "Key Yield Calculation", "A", "KYC means Know Your Customer."),
            ("A fixed deposit generally has?", "A specified tenure", "No account holder", "Only cash withdrawals", "No interest", "A", "A fixed deposit is maintained for a specified tenure."),
            ("What is NEFT?", "National Electronic Funds Transfer", "National Equity Finance Tax", "New Electronic Fund Token", "Net Exchange Fund Transfer", "A", "NEFT is National Electronic Funds Transfer."),
            ("What is RTGS mainly used for?", "Real-time gross settlement of funds", "Tax filing", "Stock listing", "ATM maintenance", "A", "RTGS settles eligible transfers in real time on a gross basis."),
            ("What does IMPS stand for?", "Immediate Payment Service", "Indian Money Processing System", "Instant Market Payment Scheme", "Integrated Money Posting Service", "A", "IMPS means Immediate Payment Service."),
            ("What is a bank's CRR?", "Cash Reserve Ratio", "Credit Recovery Rate", "Current Return Ratio", "Cash Return Reserve", "A", "CRR means Cash Reserve Ratio."),
            ("What is SLR?", "Statutory Liquidity Ratio", "Savings Loan Rate", "Secure Lending Reserve", "Statutory Loan Return", "A", "SLR means Statutory Liquidity Ratio."),
            ("Repo rate is the rate at which RBI lends short-term funds to?", "Commercial banks", "Households directly", "Schools", "Municipalities only", "A", "Repo is a policy rate for lending to banks against eligible securities."),
            ("Reverse repo refers to?", "Rate at which RBI absorbs funds from banks", "Rate of tax refund", "Home-loan rate", "Insurance premium", "A", "Reverse repo historically refers to RBI borrowing/absorbing liquidity from banks."),
            ("What is a non-performing asset commonly called?", "NPA", "NPM", "NTA", "NPS", "A", "NPA stands for Non-Performing Asset."),
            ("Which body regulates the securities market in India?", "SEBI", "RBI only", "NTA", "UPSC", "A", "SEBI regulates the securities market."),
            ("Which institution insures bank deposits in India up to applicable limits?", "DICGC", "SEBI", "IRDAI", "NITI Aayog", "A", "DICGC provides deposit insurance subject to applicable limits."),
            ("What is a debit card mainly linked to?", "Bank account", "Passport", "PAN only", "Demat only", "A", "Debit card transactions generally draw from a linked bank account."),
            ("A credit card primarily allows?", "Borrowing up to an approved limit", "Unlimited free money", "Opening a savings account", "Issuing currency", "A", "A credit card provides a line of credit subject to terms."),
            ("What is a demand deposit?", "Deposit withdrawable on demand", "Long-term bond only", "Insurance policy", "Equity share", "A", "Demand deposits can generally be withdrawn on demand."),
            ("What is a term deposit?", "Deposit for a specified period", "A current account only", "A tax return", "A share market order", "A", "Term deposits are held for a specified tenure."),
            ("What does IFSC identify?", "A bank branch for electronic transfers", "A stock", "A tax slab", "A loan type", "A", "IFSC identifies bank branches for electronic fund transfers."),
            ("What does MICR use?", "Magnetic Ink Character Recognition", "Mobile Internet Cash Reserve", "Market Interest Credit Rate", "Money Identification Cash Rule", "A", "MICR means Magnetic Ink Character Recognition."),
            ("What is a demand draft?", "A prepaid bank instrument for payment", "A credit card", "A tax receipt", "A share certificate", "A", "A demand draft is a bank-issued prepaid payment instrument."),
            ("What is overdraft?", "Withdrawal beyond available balance up to a limit", "Fixed deposit", "Insurance claim", "Tax rebate", "A", "An overdraft allows eligible withdrawals beyond the account balance up to a limit."),
            ("What is a mortgage?", "Loan secured by property", "Unsecured gift", "Savings account", "Debit card", "A", "A mortgage is a loan secured against property."),
            ("What is financial inclusion?", "Access to useful and affordable financial services", "Only stock trading", "Only foreign exchange", "Closing bank accounts", "A", "Financial inclusion expands access to appropriate financial services."),
            ("What is inflation?", "General rise in prices", "General fall in prices", "Rise in exports only", "Fall in population", "A", "Inflation is a general rise in prices over time."),
            ("What is deflation?", "General decline in price levels", "Rise in price levels", "Increase in taxes only", "Increase in exports only", "A", "Deflation is a sustained decline in the general price level."),
            ("What is GDP?", "Gross Domestic Product", "General Deposit Plan", "Gross Debt Position", "Government Development Price", "A", "GDP measures the value of final goods and services produced within an economy."),
            ("What is fiscal policy mainly concerned with?", "Government revenue and expenditure", "Weather", "Bank passwords", "Stock symbols only", "A", "Fiscal policy uses government taxation and spending."),
            ("What is monetary policy mainly concerned with?", "Money supply and interest conditions", "Road construction", "School curriculum", "Population census", "A", "Monetary policy manages monetary and financial conditions."),
            ("What is a bank rate?", "A central bank policy lending rate", "A deposit account number", "A cheque number", "A tax code", "A", "Bank rate is a policy rate associated with central bank lending."),
            ("What is a balance sheet?", "Statement of assets and liabilities", "Only a sales bill", "A cheque", "A passbook entry only", "A", "A balance sheet reports assets, liabilities and equity."),
            ("What is a loan?", "Money borrowed and repayable under agreed terms", "A gift", "A deposit only", "A dividend", "A", "A loan is borrowed money that must be repaid under agreed terms."),
            ("What is collateral?", "Asset pledged to secure a loan", "Bank employee", "Interest payment", "Currency note", "A", "Collateral is an asset pledged to secure borrowing."),
            ("What is a dividend?", "Distribution of profit to shareholders", "Bank loan", "Tax penalty", "Deposit insurance", "A", "A dividend is a distribution made to shareholders."),
            ("What is a bond?", "Debt instrument", "Savings account", "Debit card", "ATM PIN", "A", "A bond is a debt instrument."),
            ("What is a share?", "Unit of ownership in a company", "Loan agreement", "Tax invoice", "Bank guarantee", "A", "A share represents a unit of ownership in a company."),
            ("What is a mutual fund?", "Pooled investment vehicle", "Bank branch", "Insurance card", "Tax receipt", "A", "Mutual funds pool money from investors and invest according to their mandate."),
            ("What does PAN stand for?", "Permanent Account Number", "Personal Account Note", "Public Access Number", "Payment Account Name", "A", "PAN means Permanent Account Number."),
            ("What does GST stand for?", "Goods and Services Tax", "General Sales Transfer", "Government Service Tariff", "Goods Supply Token", "A", "GST means Goods and Services Tax."),
            ("What is a current account generally used for?", "Frequent business transactions", "Only long-term deposits", "Only pension payments", "Only stock trading", "A", "Current accounts are commonly used for frequent transactions, especially by businesses."),
            ("What is a savings account generally designed for?", "Saving and routine personal banking", "Only government borrowing", "Only share trading", "Only international trade", "A", "Savings accounts support saving and routine banking."),
            ("What is digital banking?", "Banking services through electronic channels", "Only cash banking", "Only branch visits", "Only cheque writing", "A", "Digital banking provides banking services through electronic channels."),
            ("Which code is commonly used for UPI identification?", "UPI ID", "ISBN", "PIN code only", "IFSC alone", "A", "UPI transactions commonly use a UPI ID/VPA."),
        ],
        "NDA & NA": [
            ("What does SSB stand for in NDA selection?", "Services Selection Board", "Special Security Branch", "State Selection Bureau", "Service Study Board", "A", "SSB stands for Services Selection Board."),
            ("NDA is associated with training for the?", "Armed Forces", "Judiciary", "Banking sector", "Railways", "A", "NDA provides entry to Armed Forces training."),
            ("Which force is primarily responsible for land warfare?", "Indian Army", "Indian Navy", "Indian Air Force", "Coast Guard", "A", "The Army is primarily responsible for land warfare."),
            ("Which force is primarily responsible for maritime defence?", "Indian Army", "Indian Navy", "Indian Air Force", "Police", "B", "The Navy is responsible for maritime defence."),
            ("Which force operates military aircraft?", "Indian Air Force", "Indian Navy only", "Indian Army only", "BSF", "A", "The Air Force operates military aircraft as its core role."),
            ("What is the capital of India?", "Mumbai", "New Delhi", "Chennai", "Kolkata", "B", "New Delhi is India's capital."),
            ("How many hours are there in one day?", "12", "18", "24", "36", "C", "One day has 24 hours."),
            ("Which planet is known as the Red Planet?", "Earth", "Mars", "Venus", "Jupiter", "B", "Mars is commonly called the Red Planet."),
            ("What is the SI unit of force?", "Joule", "Newton", "Watt", "Pascal", "B", "The SI unit of force is the newton."),
            ("Which quality is important for an officer?", "Discipline", "Carelessness", "Dishonesty", "Indifference", "A", "Discipline is an important officer-like quality."),
            ("Which is the highest rank in the Indian Army?", "Field Marshal", "Major", "Captain", "Colonel", "A", "Field Marshal is the highest ceremonial rank in the Indian Army."),
            ("Which is the highest rank in the Indian Navy?", "Admiral", "Commander", "Captain", "Lieutenant", "A", "Admiral is the highest active rank in the Indian Navy."),
            ("Which is the highest active rank in the Indian Air Force?", "Air Chief Marshal", "Air Marshal", "Air Vice Marshal", "Wing Commander", "A", "Air Chief Marshal is the highest active rank."),
            ("The President of India is the Supreme Commander of the?", "Armed Forces", "Parliament", "Judiciary", "Election Commission", "A", "The President is Supreme Commander of the Armed Forces."),
            ("The Indian Army Day is observed on?", "15 January", "26 January", "15 August", "4 December", "A", "Army Day is observed on 15 January."),
            ("Navy Day in India is observed on?", "4 December", "8 October", "15 January", "26 July", "A", "Indian Navy Day is observed on 4 December."),
            ("Air Force Day in India is observed on?", "8 October", "4 December", "15 January", "26 January", "A", "Air Force Day is observed on 8 October."),
            ("Kargil Vijay Diwas is observed on?", "26 July", "15 August", "9 May", "4 December", "A", "Kargil Vijay Diwas is observed on 26 July."),
            ("The Indian Armed Forces consist of Army, Navy and?", "Air Force", "Police", "CRPF", "BSF", "A", "The three services are Army, Navy and Air Force."),
            ("What does NCC stand for?", "National Cadet Corps", "National Command Council", "Naval Cadet Command", "National Civil Corps", "A", "NCC means National Cadet Corps."),
            ("What does NDA stand for?", "National Defence Academy", "National Development Academy", "Naval Defence Association", "National Duty Academy", "A", "NDA means National Defence Academy."),
            ("What does NA in NDA & NA refer to?", "Naval Academy", "National Army", "Naval Authority", "National Aviation", "A", "NA refers to Naval Academy."),
            ("Which service guards India's coastline and maritime interests with a dedicated coast guard force?", "Indian Coast Guard", "Indian Army", "CAG", "NDRF", "A", "The Indian Coast Guard is responsible for designated maritime security roles."),
            ("What is the SSB primarily designed to assess?", "Officer-like qualities", "Typing speed only", "Accounting only", "Driving only", "A", "SSB assesses officer-like qualities through multiple activities."),
            ("Which test is commonly part of SSB Stage I?", "Officer Intelligence Rating and PPDT", "Final medical only", "Swimming only", "Driving test", "A", "Stage I commonly includes OIR and PPDT."),
            ("What does PPDT stand for?", "Picture Perception and Discussion Test", "Personal Physical Defence Test", "Public Personality Development Test", "Preliminary Pilot Driving Test", "A", "PPDT means Picture Perception and Discussion Test."),
            ("Which quality means ability to guide a team toward a goal?", "Leadership", "Negligence", "Indiscipline", "Apathy", "A", "Leadership is the ability to guide and influence a team toward objectives."),
            ("Which is a basic principle of military discipline?", "Obedience to lawful orders", "Ignoring orders", "Avoiding responsibility", "Breaking rules", "A", "Military discipline requires obedience to lawful orders and standards."),
            ("Which instrument is used to find direction?", "Compass", "Thermometer", "Barometer", "Ammeter", "A", "A compass is used to determine direction."),
            ("Which direction is opposite to north?", "East", "West", "South", "North-East", "C", "South is opposite to north."),
            ("What is the boiling point of water at standard pressure?", "50°C", "100°C", "150°C", "200°C", "B", "Water boils at about 100°C at standard atmospheric pressure."),
            ("What is the freezing point of water at standard pressure?", "0°C", "10°C", "32°C", "100°C", "A", "Water freezes at 0°C at standard pressure."),
            ("Which gas is most abundant in Earth's atmosphere?", "Oxygen", "Nitrogen", "Hydrogen", "Carbon dioxide", "B", "Nitrogen is the most abundant atmospheric gas."),
            ("Which organ pumps blood through the body?", "Lungs", "Heart", "Kidney", "Liver", "B", "The heart pumps blood through the circulatory system."),
            ("Which blood group is commonly called the universal red-cell donor?", "AB+", "O negative", "A+", "B+", "B", "O negative is commonly described as the universal red-cell donor."),
            ("Which vitamin is produced in skin with sunlight exposure?", "Vitamin A", "Vitamin B12", "Vitamin C", "Vitamin D", "D", "Sunlight exposure helps the body synthesize vitamin D."),
            ("What is the largest planet in the Solar System?", "Earth", "Mars", "Jupiter", "Venus", "C", "Jupiter is the largest planet."),
            ("What is the nearest star to Earth?", "Sirius", "Sun", "Polaris", "Alpha Centauri", "B", "The Sun is Earth's nearest star."),
            ("Which force attracts objects toward Earth?", "Friction", "Gravity", "Magnetism", "Buoyancy", "B", "Gravity attracts masses toward Earth."),
            ("Speed is defined as?", "Distance/time", "Time/distance", "Mass/volume", "Force/area", "A", "Speed equals distance divided by time."),
            ("What is the SI unit of power?", "Joule", "Watt", "Newton", "Pascal", "B", "Power is measured in watts."),
            ("Which metal is liquid at room temperature?", "Iron", "Mercury", "Copper", "Aluminium", "B", "Mercury is liquid at ordinary room temperature."),
            ("Which acid is present in lemon?", "Acetic acid", "Citric acid", "Hydrochloric acid", "Sulfuric acid", "B", "Lemons contain citric acid."),
            ("Which is the largest ocean?", "Atlantic", "Indian", "Pacific", "Arctic", "C", "The Pacific Ocean is the largest ocean."),
            ("Which continent is the largest by area?", "Africa", "Asia", "Europe", "Australia", "B", "Asia is the largest continent by area."),
            ("What is the national animal of India?", "Lion", "Tiger", "Elephant", "Peacock", "B", "The Bengal tiger is India's national animal."),
            ("What is the national bird of India?", "Sparrow", "Peacock", "Eagle", "Swan", "B", "The Indian peafowl is India's national bird."),
            ("Which quality is closely related to honesty?", "Integrity", "Negligence", "Fear", "Confusion", "A", "Integrity includes honesty and strong moral principles."),
            ("A good leader should generally?", "Take responsibility", "Avoid decisions", "Blame others", "Ignore the team", "A", "Responsible leadership includes accountability."),
            ("Which map direction is usually at the top?", "South", "North", "West", "East", "B", "Standard maps generally place north at the top."),
            ("What is the basic unit of life?", "Atom", "Cell", "Tissue", "Organ", "B", "The cell is the basic structural and functional unit of life."),
        ],
        "JEE Main": [
            ("What is the derivative of x²?", "x", "2x", "x²", "2", "B", "d(x²)/dx = 2x."),
            ("What is the SI unit of electric current?", "Volt", "Ampere", "Ohm", "Watt", "B", "The SI unit of electric current is ampere."),
            ("What is the atomic number of hydrogen?", "1", "2", "8", "10", "A", "Hydrogen has atomic number 1."),
            ("The acceleration due to gravity near Earth is approximately?", "9.8 m/s²", "98 m/s²", "0.98 m/s²", "19.6 m/s²", "A", "Near Earth's surface, g is approximately 9.8 m/s²."),
            ("What is the value of sin 90°?", "0", "1", "-1", "1/2", "B", "sin 90° = 1."),
            ("Which particle has a negative charge?", "Proton", "Neutron", "Electron", "Photon", "C", "The electron carries negative electric charge."),
            ("What is H2O commonly called?", "Hydrogen peroxide", "Water", "Oxygen", "Hydrogen", "B", "H2O is water."),
            ("If a body is at rest, its velocity is?", "1 m/s", "0", "9.8 m/s", "10 m/s", "B", "A body at rest has zero velocity."),
            ("What is 2³?", "4", "6", "8", "9", "C", "2³ = 8."),
            ("Which is a vector quantity?", "Mass", "Time", "Velocity", "Temperature", "C", "Velocity has magnitude and direction."),
            ("What is the value of cos 0°?", "0", "1", "-1", "1/2", "B", "cos 0° = 1."),
            ("What is the value of tan 45°?", "0", "1", "√3", "1/√3", "B", "tan 45° = 1."),
            ("The SI unit of work is?", "Newton", "Joule", "Watt", "Pascal", "B", "Work is measured in joules."),
            ("The SI unit of power is?", "Joule", "Newton", "Watt", "Volt", "C", "Power is measured in watts."),
            ("Ohm's law is?", "V=IR", "P=VI only", "F=ma", "Q=mcΔT", "A", "Ohm's law states V = IR for an ohmic conductor under suitable conditions."),
            ("The resistance of a conductor is measured in?", "Volt", "Ampere", "Ohm", "Coulomb", "C", "Resistance is measured in ohms."),
            ("Charge is measured in?", "Coulomb", "Joule", "Watt", "Tesla", "A", "Electric charge is measured in coulombs."),
            ("The speed of light in vacuum is approximately?", "3×10^8 m/s", "3×10^6 m/s", "3×10^5 m/s", "3×10^10 m/s", "A", "Light travels in vacuum at about 3×10^8 m/s."),
            ("Which law relates force, mass and acceleration?", "Newton's second law", "Newton's first law", "Ohm's law", "Boyle's law", "A", "Newton's second law gives F = ma."),
            ("Momentum is equal to?", "mv", "m/v", "v/m", "ma", "A", "Linear momentum p = mv."),
            ("The unit of frequency is?", "Hertz", "Tesla", "Watt", "Ohm", "A", "Frequency is measured in hertz."),
            ("Which particle has no electric charge?", "Proton", "Electron", "Neutron", "Ion", "C", "A neutron is electrically neutral."),
            ("The nucleus contains?", "Only electrons", "Protons and neutrons", "Only protons", "Only neutrons", "B", "The atomic nucleus contains protons and neutrons."),
            ("Atomic number equals number of?", "Neutrons", "Protons", "Nucleons only", "Electrons plus neutrons", "B", "Atomic number is the number of protons."),
            ("A solution with pH less than 7 is?", "Basic", "Neutral", "Acidic", "Salty", "C", "pH below 7 indicates acidity at standard conditions."),
            ("The chemical symbol for sodium is?", "So", "Na", "S", "Sd", "B", "Sodium is represented by Na."),
            ("The chemical symbol for potassium is?", "P", "K", "Pt", "Po", "B", "Potassium is represented by K."),
            ("Which gas is released in photosynthesis?", "Oxygen", "Nitrogen", "Hydrogen", "Methane", "A", "Plants release oxygen during photosynthesis."),
            ("The powerhouse of the cell is?", "Nucleus", "Mitochondrion", "Ribosome", "Golgi body", "B", "Mitochondria produce much of the cell's ATP."),
            ("DNA stands for?", "Deoxyribonucleic Acid", "Dinucleic Acid", "Deoxygenated Nucleic Acid", "Double Nitrogen Acid", "A", "DNA means Deoxyribonucleic Acid."),
            ("What is the value of log10 100?", "1", "2", "10", "100", "B", "10² = 100, so log10 100 = 2."),
            ("What is the value of 5! ?", "20", "60", "100", "120", "D", "5! = 5×4×3×2×1 = 120."),
            ("The roots of x² - 5x + 6 = 0 are?", "1 and 6", "2 and 3", "-2 and -3", "3 and 4", "B", "(x-2)(x-3)=0."),
            ("The slope of y = 3x + 2 is?", "2", "3", "5", "-3", "B", "The coefficient of x is the slope."),
            ("The integral of 1 dx is?", "1", "x + C", "x²", "0", "B", "The indefinite integral of 1 is x + C."),
            ("The determinant of [[1,0],[0,1]] is?", "0", "1", "2", "-1", "B", "The determinant of the identity matrix is 1."),
            ("If two vectors are perpendicular, their dot product is?", "1", "-1", "0", "Infinity", "C", "Perpendicular vectors have zero dot product."),
            ("The magnitude of unit vector is?", "0", "1", "2", "Depends on direction", "B", "A unit vector has magnitude 1."),
            ("The wavelength and frequency relation for a wave is?", "v = fλ", "v = f/λ", "λ = vf", "f = vλ", "A", "Wave speed v = fλ."),
            ("In a series circuit, current is?", "Same through each element", "Different through each element", "Always zero", "Infinite", "A", "The same current flows through series elements."),
            ("In a parallel circuit, voltage across branches is?", "Same", "Always zero", "Always different", "Infinite", "A", "Parallel branches share the same potential difference."),
            ("Which mirror can form a magnified upright virtual image?", "Concave mirror", "Plane mirror only", "Convex mirror only", "No mirror", "A", "A concave mirror can form a magnified upright virtual image when the object is within the focal length."),
            ("Which lens is converging?", "Concave", "Convex", "Cylindrical only", "Plane glass", "B", "A convex lens is converging."),
            ("The unit of magnetic field is?", "Tesla", "Weber only", "Ohm", "Ampere", "A", "Magnetic field is measured in tesla."),
            ("The unit of capacitance is?", "Farad", "Henry", "Tesla", "Weber", "A", "Capacitance is measured in farads."),
            ("Which thermodynamic law introduces the concept of thermal equilibrium?", "Zeroth law", "First law", "Second law", "Third law", "A", "The zeroth law establishes thermal equilibrium and temperature."),
            ("The first law of thermodynamics expresses conservation of?", "Mass only", "Energy", "Charge only", "Momentum only", "B", "The first law is conservation of energy."),
            ("Which quantum number describes the principal energy level?", "n", "l", "m", "s", "A", "The principal quantum number is n."),
            ("The maximum number of electrons in an s subshell is?", "1", "2", "6", "10", "B", "An s subshell contains one orbital and holds two electrons."),
            ("The maximum number of electrons in a p subshell is?", "2", "4", "6", "8", "C", "A p subshell has three orbitals and holds six electrons."),
            ("Avogadro's number is approximately?", "6.022×10^23", "6.022×10^10", "9.8×10^23", "3×10^8", "A", "One mole contains about 6.022×10^23 entities."),
        ]
    }

    # Insert only missing questions. This is important: if the user already
    # has 10 questions, the next run adds 40 more instead of duplicating them.
    for exam_name, questions in question_sets.items():
        exam = conn.execute("SELECT id FROM exams WHERE name = ?", (exam_name,)).fetchone()
        if not exam:
            continue

        exam_id = exam[0]
        existing_count = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE exam_id = ?", (exam_id,)
        ).fetchone()[0]

        if existing_count < 50:
            existing_questions = {
                row[0] for row in conn.execute(
                    "SELECT question FROM questions WHERE exam_id = ?", (exam_id,)
                ).fetchall()
            }

            for q in questions:
                if q[0] in existing_questions:
                    continue
                conn.execute("""
                    INSERT INTO questions
                    (exam_id, question, option_a, option_b, option_c, option_d,
                     correct_answer, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (exam_id, *q))
                existing_questions.add(q[0])

                current = conn.execute(
                    "SELECT COUNT(*) FROM questions WHERE exam_id = ?", (exam_id,)
                ).fetchone()[0]
                if current >= 50:
                    break

        # Guarantee at least 50 questions even if a question bank was edited
        # later and contains fewer than 50 entries.
        qcount = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE exam_id = ?", (exam_id,)
        ).fetchone()[0]

        if qcount < 50:
            fallback = (
                f"{exam_name}: Which approach is most useful for effective exam preparation?",
                "Regular study and practice",
                "Skipping revision",
                "Avoiding mock tests",
                "Studying without a plan",
                "A",
                "Regular study, revision and practice are important for competitive-exam preparation."
            )
            existing_questions = {
                row[0] for row in conn.execute(
                    "SELECT question FROM questions WHERE exam_id = ?", (exam_id,)
                ).fetchall()
            }
            if fallback[0] not in existing_questions:
                conn.execute("""
                    INSERT INTO questions
                    (exam_id, question, option_a, option_b, option_c, option_d, correct_answer, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (exam_id, *fallback))
            qcount = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE exam_id = ?", (exam_id,)
            ).fetchone()[0]

        # Always make the test card show the real question count.
        # Update the mock-test card without requiring tests.exam_id.
        # This works with both the old and new CrackIt database schema.
        conn.execute(
            "UPDATE tests SET questions = ?, exam = ? WHERE LOWER(TRIM(exam)) = LOWER(TRIM(?))",
            (qcount, exam_name, exam_name)
        )

    conn.commit()
    conn.close()



# ============================================================
# GLOBAL DESIGN
# ============================================================

BASE_CSS = """
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Inter', sans-serif;
    background: #f5f7fb;
    color: #172033;
}

a {
    text-decoration: none;
    color: inherit;
}

button,
input,
select {
    font-family: inherit;
}

.container {
    width: min(1200px, 92%);
    margin: auto;
}

/* ---------------- NAVBAR ---------------- */

.navbar {
    height: 76px;
    background: white;
    border-bottom: 1px solid #edf0f5;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 5%;
    position: sticky;
    top: 0;
    z-index: 50;
}

.logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 24px;
    font-weight: 800;
    color: #172033;
}

.logo-icon {
    width: 42px;
    height: 42px;
    border-radius: 13px;
    background: linear-gradient(135deg,#6c5ce7,#8e7dff);
    display: flex;
    justify-content: center;
    align-items: center;
    color: white;
    font-size: 20px;
    box-shadow: 0 8px 20px rgba(108,92,231,.25);
}

.nav-links {
    display: flex;
    gap: 30px;
    align-items: center;
    color: #657084;
    font-size: 14px;
    font-weight: 600;
}

.nav-links a:hover {
    color: #6c5ce7;
}

.nav-buttons {
    display: flex;
    gap: 10px;
}

/* ---------------- BUTTONS ---------------- */

.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
    padding: 12px 20px;
    border-radius: 12px;
    font-weight: 700;
    transition: .2s;
}

.btn:hover {
    transform: translateY(-2px);
}

.btn-primary {
    background: #6c5ce7;
    color: white;
    box-shadow: 0 8px 18px rgba(108,92,231,.22);
}

.btn-dark {
    background: #172033;
    color: white;
}

.btn-light {
    background: #f0efff;
    color: #6556db;
}

/* ---------------- LANDING ---------------- */

.hero {
    min-height: calc(100vh - 76px);
    background:
        radial-gradient(circle at 80% 20%, rgba(108,92,231,.15), transparent 25%),
        radial-gradient(circle at 10% 80%, rgba(34,197,94,.08), transparent 25%),
        #fafbff;
    display: flex;
    align-items: center;
}

.hero-grid {
    display: grid;
    grid-template-columns: 1.1fr .9fr;
    gap: 70px;
    align-items: center;
}

.badge {
    display: inline-block;
    background: #efedff;
    color: #6556db;
    padding: 8px 14px;
    border-radius: 30px;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 22px;
}

.hero h1 {
    font-size: clamp(42px,6vw,72px);
    line-height: 1.05;
    letter-spacing: -3px;
    margin-bottom: 22px;
}

.gradient-text {
    background: linear-gradient(90deg,#6c5ce7,#9b8cff);
    -webkit-background-clip: text;
    color: transparent;
}

.hero p {
    color: #687286;
    line-height: 1.8;
    max-width: 600px;
    font-size: 17px;
}

.hero-actions {
    margin-top: 32px;
    display: flex;
    gap: 12px;
}

.hero-card {
    position: relative;
    background: white;
    border: 1px solid #edf0f5;
    border-radius: 28px;
    padding: 25px;
    box-shadow: 0 25px 70px rgba(33,39,64,.12);
}

.dashboard-preview {
    background: #f6f5ff;
    border-radius: 20px;
    padding: 18px;
}

.preview-top {
    display: flex;
    justify-content: space-between;
    margin-bottom: 18px;
}

.preview-title {
    font-size: 20px;
    font-weight: 800;
}

.mini-cards {
    display: grid;
    grid-template-columns: repeat(2,1fr);
    gap: 12px;
}

.mini-card {
    background: white;
    padding: 18px;
    border-radius: 16px;
}

.mini-number {
    font-size: 25px;
    font-weight: 800;
}

.mini-label {
    color: #8891a3;
    font-size: 12px;
    margin-top: 5px;
}

/* ---------------- AUTH ---------------- */

.auth-page {
    min-height: 100vh;
    display: grid;
    grid-template-columns: 1fr 1fr;
    background: #f7f7fb;
}

.auth-left {
    background: linear-gradient(145deg,#17152d,#40349b);
    color: white;
    padding: 8%;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.auth-left h1 {
    font-size: 50px;
    line-height: 1.1;
    margin: 25px 0;
}

.auth-left p {
    color: #d9d6ef;
    line-height: 1.8;
}

.auth-right {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 40px;
}

.auth-box {
    background: white;
    width: min(460px,100%);
    padding: 42px;
    border-radius: 25px;
    box-shadow: 0 20px 60px rgba(0,0,0,.08);
}

.auth-box h2 {
    font-size: 30px;
    margin-bottom: 8px;
}

.auth-box > p {
    color: #8992a5;
    margin-bottom: 30px;
}

.form-group {
    margin-bottom: 18px;
}

.form-group label {
    display: block;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
}

.form-control {
    width: 100%;
    padding: 14px 15px;
    border: 1px solid #e2e5ed;
    border-radius: 12px;
    outline: none;
    background: #fafbfc;
}

.form-control:focus {
    border-color: #6c5ce7;
    background: white;
}

.full {
    width: 100%;
}

/* ---------------- APP LAYOUT ---------------- */

.app-layout {
    display: flex;
    min-height: 100vh;
}

.sidebar {
    width: 245px;
    background: #17152d;
    color: white;
    padding: 25px 15px;
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
}

.sidebar .logo {
    color: white;
    padding: 0 12px;
    margin-bottom: 40px;
}

.sidebar .logo-icon {
    background: #6c5ce7;
}

.menu-title {
    color: #7f7b9e;
    font-size: 10px;
    font-weight: 800;
    padding: 0 15px;
    margin: 20px 0 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.sidebar a {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #aaa6c2;
    padding: 13px 15px;
    border-radius: 12px;
    font-size: 13px;
    margin-bottom: 5px;
}

.sidebar a:hover,
.sidebar a.active {
    color: white;
    background: rgba(255,255,255,.1);
}

.main {
    margin-left: 245px;
    width: calc(100% - 245px);
}

.topbar {
    background: white;
    height: 76px;
    border-bottom: 1px solid #edf0f5;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 35px;
}

.search {
    background: #f5f6fa;
    border: none;
    padding: 12px 18px;
    border-radius: 12px;
    width: 280px;
    outline: none;
}

.user-mini {
    display: flex;
    align-items: center;
    gap: 12px;
}

.avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg,#6c5ce7,#a79cff);
    color: white;
    display: flex;
    justify-content: center;
    align-items: center;
    font-weight: 800;
}

.page {
    padding: 35px;
}

.page-title {
    font-size: 28px;
    font-weight: 800;
    margin-bottom: 8px;
}

.page-subtitle {
    color: #8891a3;
    margin-bottom: 28px;
}

/* ---------------- DASHBOARD ---------------- */

.greeting {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
}

.greeting h1 {
    font-size: 28px;
}

.greeting p {
    color: #8992a5;
    margin-top: 6px;
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(4,1fr);
    gap: 18px;
}

.stat-card {
    border-radius: 20px;
    padding: 22px;
    min-height: 135px;
}

.stat-card:nth-child(1) {
    background: #e9e6ff;
}

.stat-card:nth-child(2) {
    background: #dff8ee;
}

.stat-card:nth-child(3) {
    background: #fff0d8;
}

.stat-card:nth-child(4) {
    background: #ffe3eb;
}

.stat-icon {
    font-size: 22px;
    margin-bottom: 16px;
}

.stat-number {
    font-size: 28px;
    font-weight: 800;
}

.stat-label {
    color: #697286;
    font-size: 12px;
    margin-top: 4px;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: 1.4fr .8fr;
    gap: 20px;
    margin-top: 22px;
}

.card {
    background: white;
    border: 1px solid #edf0f5;
    border-radius: 20px;
    padding: 23px;
}

.card-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.card-title h3 {
    font-size: 17px;
}

.chart {
    height: 220px;
    display: flex;
    align-items: end;
    gap: 15px;
    padding-top: 20px;
}

.bar {
    flex: 1;
    border-radius: 8px 8px 3px 3px;
    background: linear-gradient(to top,#6c5ce7,#a99fff);
}

.progress-circle {
    width: 150px;
    height: 150px;
    border-radius: 50%;
    background: conic-gradient(#6c5ce7 0 72%,#eceafc 72% 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 10px auto 20px;
}

.progress-inner {
    width: 115px;
    height: 115px;
    border-radius: 50%;
    background: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 27px;
    font-weight: 800;
}

.test-list {
    display: grid;
    gap: 12px;
}

.test-item {
    border: 1px solid #edf0f5;
    padding: 15px;
    border-radius: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.test-item small {
    color: #8992a5;
}

/* ---------------- EXAMS ---------------- */

.search-large {
    display: flex;
    gap: 12px;
    margin-bottom: 25px;
}

.search-large input {
    flex: 1;
    padding: 16px;
    border: 1px solid #e2e5ed;
    border-radius: 13px;
    outline: none;
}

.exam-grid {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 20px;
}

.exam-card {
    background: white;
    border: 1px solid #edf0f5;
    padding: 24px;
    border-radius: 20px;
    transition: .2s;
}

.exam-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 15px 35px rgba(30,35,60,.08);
}

.exam-icon {
    width: 52px;
    height: 52px;
    border-radius: 15px;
    background: #efedff;
    color: #6c5ce7;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 23px;
    margin-bottom: 18px;
}

.exam-card h3 {
    margin-bottom: 8px;
}

.exam-category {
    color: #6c5ce7;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 12px;
}

.exam-card p {
    color: #7c8597;
    font-size: 13px;
    line-height: 1.6;
    margin-bottom: 20px;
}

/* ---------------- DETAILS ---------------- */

.detail-hero {
    background: linear-gradient(135deg,#211b52,#6c5ce7);
    color: white;
    padding: 40px;
    border-radius: 25px;
    margin-bottom: 22px;
}

.detail-hero .tag {
    display: inline-block;
    background: rgba(255,255,255,.15);
    padding: 7px 12px;
    border-radius: 20px;
    font-size: 11px;
    margin-bottom: 18px;
}

.detail-hero h1 {
    font-size: 36px;
    margin-bottom: 12px;
}

.detail-hero p {
    color: #ddd9fa;
    max-width: 750px;
    line-height: 1.7;
}

.detail-grid {
    display: grid;
    grid-template-columns: repeat(2,1fr);
    gap: 18px;
}

.info-card {
    background: white;
    padding: 23px;
    border-radius: 18px;
    border: 1px solid #edf0f5;
}

.info-card h3 {
    font-size: 15px;
    margin-bottom: 12px;
}

.info-card p {
    color: #737d91;
    font-size: 13px;
    line-height: 1.7;
}

/* ---------------- MATERIALS ---------------- */

.material-grid {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 18px;
}

.material-card {
    background: white;
    border: 1px solid #edf0f5;
    border-radius: 18px;
    padding: 22px;
}

.material-icon {
    font-size: 28px;
    margin-bottom: 15px;
}

.material-card h3 {
    font-size: 15px;
    margin-bottom: 7px;
}

.material-card p {
    color: #8992a5;
    font-size: 12px;
    margin-bottom: 15px;
}

/* ---------------- ROADMAP ---------------- */

.roadmap {
    max-width: 850px;
    margin: auto;
}

.road-step {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
}

.step-number {
    min-width: 50px;
    height: 50px;
    border-radius: 50%;
    background: #6c5ce7;
    color: white;
    display: flex;
    justify-content: center;
    align-items: center;
    font-weight: 800;
}

.step-content {
    background: white;
    border: 1px solid #edf0f5;
    padding: 20px;
    border-radius: 17px;
    flex: 1;
}

.step-content h3 {
    margin-bottom: 7px;
}

.step-content p {
    color: #7d8699;
    font-size: 13px;
    line-height: 1.6;
}

/* ---------------- TEST ---------------- */

.test-container {
    max-width: 850px;
    margin: auto;
}

.timer {
    background: #ffe7ec;
    color: #e0526d;
    padding: 12px 18px;
    border-radius: 12px;
    font-weight: 800;
}

.question-card {
    background: white;
    padding: 30px;
    border-radius: 22px;
    border: 1px solid #edf0f5;
    margin-top: 20px;
}

.question-card h2 {
    margin: 14px 0 22px;
    line-height: 1.35;
}

.option-list {
    display: grid;
    gap: 10px;
}

.option {
    border: 1px solid #e1e4eb;
    padding: 17px;
    border-radius: 13px;
    margin-top: 0;
    cursor: pointer;
    transition: .2s;
}

.option:hover {
    border-color: #6c5ce7;
    background: #f5f3ff;
}

.option input {
    margin-right: 10px;
}

.test-nav {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 14px;
    margin-top: 30px;
    padding-top: 2px;
}

/* ---------------- PROFILE ---------------- */

.profile-grid {
    display: grid;
    grid-template-columns: .8fr 1.2fr;
    gap: 20px;
}

.profile-card {
    background: white;
    padding: 30px;
    border-radius: 20px;
    border: 1px solid #edf0f5;
}

.profile-avatar {
    width: 90px;
    height: 90px;
    border-radius: 50%;
    background: linear-gradient(135deg,#6c5ce7,#a99fff);
    color: white;
    font-size: 32px;
    font-weight: 800;
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 15px;
}

.notification {
    display: flex;
    gap: 15px;
    padding: 17px 0;
    border-bottom: 1px solid #edf0f5;
}

.notification-icon {
    width: 38px;
    height: 38px;
    background: #efedff;
    color: #6c5ce7;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
}

/* ---------------- RESULT ---------------- */

.result-box {
    max-width: 700px;
    margin: auto;
    text-align: center;
    background: white;
    padding: 45px;
    border-radius: 25px;
    border: 1px solid #edf0f5;
}

.score {
    font-size: 65px;
    font-weight: 800;
    color: #6c5ce7;
    margin: 20px 0;
}

.result-stats {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 12px;
    margin: 25px 0;
}

.result-stat {
    background: #f7f7fb;
    padding: 18px;
    border-radius: 13px;
}

.result-stat strong {
    display: block;
    font-size: 20px;
}

.result-stat span {
    color: #8992a5;
    font-size: 11px;
}

/* ---------------- FOOTER ---------------- */

.footer {
    padding: 35px 5%;
    text-align: center;
    background: #17152d;
    color: #aaa6c2;
    font-size: 13px;
}

/* ---------------- RESPONSIVE ---------------- */

@media(max-width:1000px) {
    .hero-grid,
    .auth-page,
    .dashboard-grid,
    .profile-grid {
        grid-template-columns: 1fr;
    }

    .stat-grid {
        grid-template-columns: repeat(2,1fr);
    }

    .exam-grid,
    .material-grid {
        grid-template-columns: repeat(2,1fr);
    }

    .sidebar {
        width: 210px;
    }

    .main {
        margin-left: 210px;
        width: calc(100% - 210px);
    }
}

@media(max-width:700px) {
    .nav-links {
        display: none;
    }

    .sidebar {
        display: none;
    }

    .main {
        margin-left: 0;
        width: 100%;
    }

    .stat-grid,
    .exam-grid,
    .material-grid,
    .detail-grid,
    .result-stats {
        grid-template-columns: 1fr;
    }

    .page {
        padding: 20px;
    }

    .topbar {
        padding: 0 20px;
    }

    .search {
        width: 150px;
    }

    .hero-grid {
        gap: 30px;
    }
}

</style>
"""


# ============================================================
# NAVIGATION
# ============================================================

def sidebar(active="dashboard"):

    items = [
        ("dashboard", "📊", "Dashboard", "/dashboard"),
        ("exams", "🎯", "Examinations", "/exams"),
        ("tests", "📝", "Mock Tests", "/tests"),
        ("materials", "📚", "Study Materials", "/materials"),
        ("roadmap", "🗺️", "Roadmap", "/roadmap"),
        ("result", "📈", "Performance", "/result"),
        ("profile", "👤", "Profile", "/profile")
    ]

    html = """
    <aside class="sidebar">
        <a href="/" class="logo">
            <span class="logo-icon">C</span>
            CrackIt
        </a>

        <div class="menu-title">Main Menu</div>
    """

    for key, icon, name, link in items:
        cls = "active" if key == active else ""
        html += f"""
        <a class="{cls}" href="{link}">
            <span>{icon}</span>
            {name}
        </a>
        """

    html += """
        <div class="menu-title">Account</div>

        <a href="/profile">
            <span>🔔</span>
            Notifications
        </a>

        <a href="/logout">
            <span>↪</span>
            Logout
        </a>
    </aside>
    """

    return html


def topbar():

    name = session.get("user_name", "Student")

    return f"""
    <header class="topbar">
        <input class="search" placeholder="⌕  Search anything...">

        <div class="user-mini">
            <span style="font-size:20px;">🔔</span>
            <div class="avatar">
                {name[0].upper()}
            </div>
            <strong>{name}</strong>
        </div>
    </header>
    """


def app_page(content, active="dashboard"):

    return BASE_CSS + f"""
    <div class="app-layout">
        {sidebar(active)}

        <main class="main">
            {topbar()}

            <section class="page">
                {content}
            </section>

        </main>
    </div>
    """


# ============================================================
# LANDING PAGE
# ============================================================

@app.route("/")
def home():

    return BASE_CSS + """

    <nav class="navbar">

        <a class="logo" href="/">
            <span class="logo-icon">C</span>
            CrackIt
        </a>

        <div class="nav-links">
            <a href="#features">Features</a>
            <a href="/exams">Examinations</a>
            <a href="/tests">Mock Tests</a>
            <a href="/roadmap">Roadmap</a>
        </div>

        <div class="nav-buttons">
            <a href="/login" class="btn btn-light">Login</a>
            <a href="/register" class="btn btn-primary">Get Started</a>
        </div>

    </nav>

    <section class="hero">

        <div class="container hero-grid">

            <div>

                <span class="badge">
                    🚀 SMARTER PREPARATION • BETTER RESULTS
                </span>

                <h1>
                    From <span class="gradient-text">Preparation</span>
                    to Selection.
                </h1>

                <p>
                    CrackIt is your all-in-one competitive examination
                    preparation platform. Discover exams, learn with
                    quality resources, practice mock tests and track
                    your preparation journey in one place.
                </p>

                <div class="hero-actions">
                    <a href="/register" class="btn btn-primary">
                        Start Preparation →
                    </a>

                    <a href="/exams" class="btn btn-dark">
                        Explore Exams
                    </a>
                </div>

                <div style="display:flex;gap:35px;margin-top:40px;">
                    <div>
                        <strong style="font-size:25px;">15+</strong>
                        <div style="font-size:12px;color:#8992a5;">
                            Exam Categories
                        </div>
                    </div>

                    <div>
                        <strong style="font-size:25px;">100+</strong>
                        <div style="font-size:12px;color:#8992a5;">
                            Practice Questions
                        </div>
                    </div>

                    <div>
                        <strong style="font-size:25px;">3</strong>
                        <div style="font-size:12px;color:#8992a5;">
                            Languages
                        </div>
                    </div>
                </div>

            </div>

            <div class="hero-card">

                <div class="dashboard-preview">

                    <div class="preview-top">
                        <div>
                            <div style="font-size:11px;color:#8a91a2;">
                                STUDENT DASHBOARD
                            </div>
                            <div class="preview-title">
                                Welcome back! 👋
                            </div>
                        </div>

                        <div class="avatar">S</div>
                    </div>

                    <div class="mini-cards">

                        <div class="mini-card">
                            <div class="mini-number">72%</div>
                            <div class="mini-label">
                                Preparation
                            </div>
                        </div>

                        <div class="mini-card">
                            <div class="mini-number">18</div>
                            <div class="mini-label">
                                Tests Taken
                            </div>
                        </div>

                        <div class="mini-card">
                            <div class="mini-number">86%</div>
                            <div class="mini-label">
                                Accuracy
                            </div>
                        </div>

                        <div class="mini-card">
                            <div class="mini-number">24</div>
                            <div class="mini-label">
                                Study Hours
                            </div>
                        </div>

                    </div>

                    <div style="
                        background:white;
                        padding:20px;
                        border-radius:16px;
                        margin-top:12px;
                    ">

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            margin-bottom:12px;
                        ">
                            <strong>Weekly Progress</strong>
                            <span style="color:#6c5ce7;">+18%</span>
                        </div>

                        <div class="chart" style="height:130px;">

                            <div class="bar" style="height:45%;"></div>
                            <div class="bar" style="height:65%;"></div>
                            <div class="bar" style="height:50%;"></div>
                            <div class="bar" style="height:80%;"></div>
                            <div class="bar" style="height:70%;"></div>
                            <div class="bar" style="height:95%;"></div>
                            <div class="bar" style="height:85%;"></div>

                        </div>

                    </div>

                </div>

            </div>

        </div>

    </section>

    <section id="features"
             style="padding:80px 5%;background:white;">

        <div class="container">

            <div style="text-align:center;margin-bottom:40px;">
                <span class="badge">WHY CRACKIT?</span>

                <h2 style="font-size:38px;margin-bottom:12px;">
                    Everything you need to prepare.
                </h2>

                <p style="color:#8992a5;">
                    One platform. One preparation journey.
                </p>
            </div>

            <div class="exam-grid">

                <div class="card">
                    <div style="font-size:30px;margin-bottom:15px;">🎯</div>
                    <h3>Exam Discovery</h3>
                    <p style="color:#8992a5;margin-top:10px;">
                        Explore competitive examinations and understand
                        eligibility, qualification and selection process.
                    </p>
                </div>

                <div class="card">
                    <div style="font-size:30px;margin-bottom:15px;">📚</div>
                    <h3>Study Resources</h3>
                    <p style="color:#8992a5;margin-top:10px;">
                        Access organized study materials and previous-year
                        papers for effective preparation.
                    </p>
                </div>

                <div class="card">
                    <div style="font-size:30px;margin-bottom:15px;">📈</div>
                    <h3>Track Progress</h3>
                    <p style="color:#8992a5;margin-top:10px;">
                        Monitor your preparation, test performance and
                        overall progress.
                    </p>
                </div>

            </div>

        </div>

    </section>

    <footer class="footer">
        © 2026 CrackIt — From Preparation to Selection
    </footer>
    """


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    message = ""

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users
            WHERE email=? AND password=?
        """, (email, password)).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect("/dashboard")

        message = "Invalid email or password."

    return BASE_CSS + f"""

    <div class="auth-page">

        <div class="auth-left">

            <a href="/" class="logo" style="color:white;">
                <span class="logo-icon">C</span>
                CrackIt
            </a>

            <h1>
                Welcome<br>
                <span style="color:#a99fff;">
                    Back, Aspirant.
                </span>
            </h1>

            <p>
                Continue your preparation journey and move
                one step closer to your dream selection.
            </p>

        </div>

        <div class="auth-right">

            <div class="auth-box">

                <h2>Welcome Back 👋</h2>

                <p>Login to continue your CrackIt journey.</p>

                {"<div style='background:#ffe7eb;color:#c33;padding:12px;border-radius:10px;margin-bottom:15px;'>" + message + "</div>" if message else ""}

                <form method="POST">

                    <div class="form-group">
                        <label>Email Address</label>
                        <input
                            class="form-control"
                            type="email"
                            name="email"
                            placeholder="Enter your email"
                            required>
                    </div>

                    <div class="form-group">
                        <label>Password</label>
                        <input
                            class="form-control"
                            type="password"
                            name="password"
                            placeholder="Enter password"
                            required>
                    </div>

                    <button class="btn btn-primary full">
                        Login →
                    </button>

                </form>

                <p style="text-align:center;margin-top:22px;">
                    Don't have an account?
                    <a href="/register"
                       style="color:#6c5ce7;font-weight:700;">
                        Create Account
                    </a>
                </p>

            </div>

        </div>

    </div>
    """


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    message = ""

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO users(name,email,password)
                VALUES(?,?,?)
            """, (name, email, password))

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            conn.close()

            message = "Email already registered."

    return BASE_CSS + f"""

    <div class="auth-page">

        <div class="auth-left">

            <a href="/" class="logo" style="color:white;">
                <span class="logo-icon">C</span>
                CrackIt
            </a>

            <h1>
                Start Your<br>
                <span style="color:#a99fff;">
                    Preparation.
                </span>
            </h1>

            <p>
                Create your account and build a smarter
                preparation strategy for your target examination.
            </p>

            <div style="
                margin-top:35px;
                display:grid;
                gap:15px;
            ">

                <div>✓ Personalized preparation</div>
                <div>✓ Mock tests & performance</div>
                <div>✓ Study materials</div>
                <div>✓ Exam notifications</div>

            </div>

        </div>

        <div class="auth-right">

            <div class="auth-box">

                <h2>Create Account ✨</h2>

                <p>Join CrackIt and start preparing today.</p>

                {"<div style='background:#ffe7eb;color:#c33;padding:12px;border-radius:10px;margin-bottom:15px;'>" + message + "</div>" if message else ""}

                <form method="POST">

                    <div class="form-group">
                        <label>Full Name</label>
                        <input
                            class="form-control"
                            name="name"
                            placeholder="Enter your name"
                            required>
                    </div>

                    <div class="form-group">
                        <label>Email Address</label>
                        <input
                            class="form-control"
                            type="email"
                            name="email"
                            placeholder="Enter your email"
                            required>
                    </div>

                    <div class="form-group">
                        <label>Password</label>
                        <input
                            class="form-control"
                            type="password"
                            name="password"
                            placeholder="Create password"
                            required>
                    </div>

                    <button class="btn btn-primary full">
                        Create Account →
                    </button>

                </form>

                <p style="text-align:center;margin-top:22px;">
                    Already registered?
                    <a href="/login"
                       style="color:#6c5ce7;font-weight:700;">
                        Login
                    </a>
                </p>

            </div>

        </div>

    </div>
    """


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    name = session.get("user_name", "Student")

    content = f"""

    <div class="greeting">

        <div>
            <h1>Good Morning, {name}! 👋</h1>

            <p>
                Here's your preparation overview for today.
            </p>
        </div>

        <a href="/tests" class="btn btn-primary">
            Take a Mock Test →
        </a>

    </div>

    <div class="stat-grid">

        <div class="stat-card">
            <div class="stat-icon">🎯</div>
            <div class="stat-number">72%</div>
            <div class="stat-label">Preparation Progress</div>
        </div>

        <div class="stat-card">
            <div class="stat-icon">📝</div>
            <div class="stat-number">18</div>
            <div class="stat-label">Tests Completed</div>
        </div>

        <div class="stat-card">
            <div class="stat-icon">🔥</div>
            <div class="stat-number">7 Days</div>
            <div class="stat-label">Current Study Streak</div>
        </div>

        <div class="stat-card">
            <div class="stat-icon">🏆</div>
            <div class="stat-number">86%</div>
            <div class="stat-label">Average Accuracy</div>
        </div>

    </div>

    <div class="dashboard-grid">

        <div class="card">

            <div class="card-title">
                <h3>Study Activity</h3>
                <span style="color:#6c5ce7;font-size:12px;">
                    This Week
                </span>
            </div>

            <div class="chart">

                <div class="bar" style="height:45%;"></div>
                <div class="bar" style="height:65%;"></div>
                <div class="bar" style="height:50%;"></div>
                <div class="bar" style="height:80%;"></div>
                <div class="bar" style="height:70%;"></div>
                <div class="bar" style="height:95%;"></div>
                <div class="bar" style="height:85%;"></div>

            </div>

            <div style="
                display:flex;
                justify-content:space-around;
                color:#8992a5;
                font-size:11px;
            ">
                <span>Mon</span>
                <span>Tue</span>
                <span>Wed</span>
                <span>Thu</span>
                <span>Fri</span>
                <span>Sat</span>
                <span>Sun</span>
            </div>

        </div>

        <div class="card">

            <div class="card-title">
                <h3>Preparation</h3>
            </div>

            <div class="progress-circle">
                <div class="progress-inner">
                    72%
                </div>
            </div>

            <p style="
                text-align:center;
                color:#8992a5;
                font-size:12px;
            ">
                Keep going! You're making great progress.
            </p>

        </div>

    </div>

    <div class="card" style="margin-top:22px;">

        <div class="card-title">

            <h3>Upcoming Tests</h3>

            <a href="/tests"
               style="color:#6c5ce7;font-size:12px;font-weight:700;">
                View All
            </a>

        </div>

        <div class="test-list">

            <div class="test-item">
                <div>
                    <strong>UPSC General Studies Mock</strong>
                    <br>
                    <small>20 Questions • 30 Minutes</small>
                </div>

                <a href="/test/1" class="btn btn-light">
                    Start
                </a>
            </div>

            <div class="test-item">
                <div>
                    <strong>SSC Reasoning Challenge</strong>
                    <br>
                    <small>15 Questions • 20 Minutes</small>
                </div>

                <a href="/test/3" class="btn btn-light">
                    Start
                </a>
            </div>

        </div>

    </div>

    """

    return app_page(content, "dashboard")


# ============================================================
# EXAM LISTING
# ============================================================

@app.route("/exams")
def exams():

    search = request.args.get("search", "")

    conn = get_db()

    if search:

        exams = conn.execute("""
            SELECT * FROM exams
            WHERE name LIKE ?
            OR category LIKE ?
        """, (f"%{search}%", f"%{search}%")).fetchall()

    else:

        exams = conn.execute(
            "SELECT * FROM exams"
        ).fetchall()

    conn.close()

    cards = ""

    for exam in exams:

        cards += f"""

        <div class="exam-card">

            <div class="exam-icon">🎯</div>

            <div class="exam-category">
                {exam["category"]}
            </div>

            <h3>{exam["name"]}</h3>

            <p>
                {exam["description"]}
            </p>

            <a href="/exam/{exam["id"]}"
               class="btn btn-light">
                View Details →
            </a>

        </div>

        """

    content = f"""

    <div class="page-title">
        Explore Examinations
    </div>

    <div class="page-subtitle">
        Find your target examination and understand everything
        you need before starting preparation.
    </div>

    <form class="search-large" method="GET">

        <input
            name="search"
            value="{search}"
            placeholder="Search UPSC, MPSC, SSC, Banking, NDA...">

        <button class="btn btn-primary">
            Search
        </button>

    </form>

    <div class="exam-grid">
        {cards}
    </div>

    """

    return app_page(content, "exams")


# ============================================================
# EXAM DETAILS
# ============================================================

@app.route("/exam/<int:exam_id>")
def exam_details(exam_id):

    conn = get_db()
    exam = conn.execute(
        "SELECT * FROM exams WHERE id=?",
        (exam_id,)
    ).fetchone()

    if not exam:
        conn.close()
        return redirect("/exams")

    preview_questions = conn.execute(
        "SELECT * FROM questions WHERE exam_id=? ORDER BY id DESC LIMIT 5",
        (exam_id,)
    ).fetchall()
    question_count = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE exam_id=?",
        (exam_id,)
    ).fetchone()[0]
    conn.close()

    question_preview = ""
    for n, q in enumerate(preview_questions, 1):
        question_preview += f"""
        <div style="padding:15px 0;border-bottom:1px solid #edf0f5;">
            <div style="font-size:11px;color:#6c5ce7;font-weight:800;margin-bottom:6px;">QUESTION {n}</div>
            <div style="font-weight:700;line-height:1.5;">{q['question']}</div>
            <div style="font-size:12px;color:#8992a5;margin-top:7px;line-height:1.7;">
                A. {q['option_a']} &nbsp; B. {q['option_b']} &nbsp; C. {q['option_c']} &nbsp; D. {q['option_d']}
            </div>
        </div>
        """
    if not question_preview:
        question_preview = "<p style='color:#8992a5;'>No questions have been added yet. Click Manage Questions to add questions for this examination.</p>"

    content = f"""

    <div class="detail-hero">

        <span class="tag">
            {exam["category"]}
        </span>

        <h1>{exam["name"]}</h1>

        <p>
            {exam["description"]}
        </p>

        <div style="margin-top:25px;">

            <a href="/test/{exam_id}"
               class="btn"
               style="background:white;color:#5e50d4;">
                Practice Mock Test →
            </a>

            <a href="/question-bank/{exam_id}"
               class="btn"
               style="background:rgba(255,255,255,.14);color:white;margin-left:8px;">
                Manage Questions
            </a>

        </div>

    </div>

    <div class="detail-grid">

        <div class="info-card">
            <h3>🎓 Eligibility</h3>
            <p>{exam["eligibility"]}</p>
        </div>

        <div class="info-card">
            <h3>📚 Qualification</h3>
            <p>{exam["qualification"]}</p>
        </div>

        <div class="info-card">
            <h3>🎂 Age Limit</h3>
            <p>{exam["age"]}</p>
        </div>

        <div class="info-card">
            <h3>📝 Exam Pattern</h3>
            <p>{exam["pattern"]}</p>
        </div>

        <div class="info-card">
            <h3>🏆 Selection Process</h3>
            <p>{exam["selection"]}</p>
        </div>

        <div class="info-card">
            <h3>📖 Preparation</h3>
            <p>
                Use CrackIt study materials, roadmap and mock tests
                to build your preparation strategy.
            </p>
        </div>

    </div>

    <div class="card" style="margin-top:22px;">
        <div class="card-title">
            <h3>📝 Question Bank</h3>
            <span style="color:#8992a5;font-size:12px;">{question_count} questions available</span>
        </div>
        <p style="color:#8992a5;margin-bottom:5px;">
            The questions below are connected to this examination. Future mock tests automatically use the live question bank.
        </p>
        {question_preview}
        <div style="margin-top:18px;">
            <a href="/question-bank/{exam_id}" class="btn btn-primary">Manage Question Bank →</a>
        </div>
    </div>

    """

    return app_page(content, "exams")


# ============================================================
# QUESTION BANK MANAGEMENT
# ============================================================

@app.route("/question-bank/<int:exam_id>", methods=["GET", "POST"])
def question_bank(exam_id):
    conn = get_db()
    exam = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()

    if not exam:
        conn.close()
        return "Exam not found", 404

    action = request.form.get("action", "")

    if request.method == "POST":
        if action == "add":
            values = {k: request.form.get(k, "").strip() for k in ["question", "option_a", "option_b", "option_c", "option_d", "explanation"]}
            correct = request.form.get("correct_answer", "").upper().strip()
            if all(values[k] for k in ["question", "option_a", "option_b", "option_c", "option_d"]) and correct in {"A", "B", "C", "D"}:
                conn.execute("""
                    INSERT INTO questions (exam_id, question, option_a, option_b, option_c, option_d, correct_answer, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (exam_id, values["question"], values["option_a"], values["option_b"], values["option_c"], values["option_d"], correct, values["explanation"]))
                conn.commit()

        elif action == "update":
            qid = request.form.get("question_id", "").strip()
            values = {k: request.form.get(k, "").strip() for k in ["question", "option_a", "option_b", "option_c", "option_d", "explanation"]}
            correct = request.form.get("correct_answer", "").upper().strip()
            if qid.isdigit() and all(values[k] for k in ["question", "option_a", "option_b", "option_c", "option_d"]) and correct in {"A", "B", "C", "D"}:
                conn.execute("""
                    UPDATE questions SET question=?, option_a=?, option_b=?, option_c=?, option_d=?, correct_answer=?, explanation=?
                    WHERE id=? AND exam_id=?
                """, (values["question"], values["option_a"], values["option_b"], values["option_c"], values["option_d"], correct, values["explanation"], int(qid), exam_id))
                conn.commit()

        elif action == "delete":
            qid = request.form.get("question_id", "").strip()
            if qid.isdigit():
                conn.execute("DELETE FROM questions WHERE id=? AND exam_id=?", (int(qid), exam_id))
                conn.commit()

        return redirect(f"/question-bank/{exam_id}")

    questions = conn.execute("SELECT * FROM questions WHERE exam_id=? ORDER BY id DESC", (exam_id,)).fetchall()
    conn.close()

    rows = ""
    for i, q in enumerate(questions, 1):
        explanation = q["explanation"] or ""
        rows += f"""
        <div class="card" style="margin-bottom:14px;">
            <div style="font-size:12px;color:#6c5ce7;font-weight:800;margin-bottom:8px;">QUESTION {i}</div>
            <h3 style="margin-bottom:10px;">{q['question']}</h3>
            <div style="color:#737d91;font-size:13px;line-height:1.9;">
                A. {q['option_a']}<br>
                B. {q['option_b']}<br>
                C. {q['option_c']}<br>
                D. {q['option_d']}<br>
                <b>Correct Answer: {q['correct_answer']}</b>
            </div>
            <div style="color:#8992a5;font-size:12px;margin-top:8px;">{explanation}</div>
            <details style="margin-top:15px;">
                <summary style="cursor:pointer;color:#6c5ce7;font-weight:700;">Edit this question</summary>
                <form method="POST" style="margin-top:15px;">
                    <input type="hidden" name="action" value="update">
                    <input type="hidden" name="question_id" value="{q['id']}">
                    <div class="form-group"><label>Question</label><input class="form-control" name="question" value="{q['question']}" required></div>
                    <div class="detail-grid">
                        <div class="form-group"><label>Option A</label><input class="form-control" name="option_a" value="{q['option_a']}" required></div>
                        <div class="form-group"><label>Option B</label><input class="form-control" name="option_b" value="{q['option_b']}" required></div>
                        <div class="form-group"><label>Option C</label><input class="form-control" name="option_c" value="{q['option_c']}" required></div>
                        <div class="form-group"><label>Option D</label><input class="form-control" name="option_d" value="{q['option_d']}" required></div>
                    </div>
                    <div class="detail-grid">
                        <div class="form-group"><label>Correct Answer</label><select class="form-control" name="correct_answer">
                            <option value="A" {'selected' if q['correct_answer']=='A' else ''}>A</option>
                            <option value="B" {'selected' if q['correct_answer']=='B' else ''}>B</option>
                            <option value="C" {'selected' if q['correct_answer']=='C' else ''}>C</option>
                            <option value="D" {'selected' if q['correct_answer']=='D' else ''}>D</option>
                        </select></div>
                        <div class="form-group"><label>Explanation</label><input class="form-control" name="explanation" value="{explanation}"></div>
                    </div>
                    <button class="btn btn-primary" type="submit">Save Changes</button>
                </form>
                <form method="POST" style="margin-top:8px;" onsubmit="return confirm('Delete this question?')">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="question_id" value="{q['id']}">
                    <button class="btn" style="background:#ffe7eb;color:#c33;" type="submit">Delete Question</button>
                </form>
            </details>
        </div>
        """

    content = f"""
    <div class="page-title">Question Bank</div>
    <div class="page-subtitle">{exam['name']} • {len(questions)} questions</div>

    <div class="card" style="margin-bottom:22px;">
        <div class="card-title"><h3>➕ Add New Question</h3></div>
        <p style="color:#8992a5;margin-bottom:18px;">Add or change questions anytime. New questions automatically become available for future mock tests.</p>
        <form method="POST">
            <input type="hidden" name="action" value="add">
            <div class="form-group"><label>Question</label><input class="form-control" name="question" placeholder="Enter question" required></div>
            <div class="detail-grid">
                <div class="form-group"><label>Option A</label><input class="form-control" name="option_a" required></div>
                <div class="form-group"><label>Option B</label><input class="form-control" name="option_b" required></div>
                <div class="form-group"><label>Option C</label><input class="form-control" name="option_c" required></div>
                <div class="form-group"><label>Option D</label><input class="form-control" name="option_d" required></div>
            </div>
            <div class="detail-grid">
                <div class="form-group"><label>Correct Answer</label><select class="form-control" name="correct_answer" required>
                    <option value="">Select</option><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option>
                </select></div>
                <div class="form-group"><label>Explanation</label><input class="form-control" name="explanation" placeholder="Optional explanation"></div>
            </div>
            <button class="btn btn-primary" type="submit">Add Question ✓</button>
        </form>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>📚 Existing Questions</h3>
        <a href="/exam/{exam_id}" class="btn btn-light">← Back to Exam</a>
    </div>
    {rows if rows else '<div class="card"><p style="color:#8992a5;">No questions yet. Add your first question above.</p></div>'}
    """
    return app_page(content, "exams")


# ============================================================
# MOCK TEST LIST
# ============================================================

@app.route("/tests")
def tests():
    conn = get_db()

    # Do not depend on tests.exam_id. The project also works with an older
    # crackit.db where the tests table only has id/title/exam/questions.
    tests = conn.execute("SELECT * FROM tests ORDER BY id").fetchall()

    cards = ""
    for test in tests:
        exam_name = test["exam"]
        exam_row = conn.execute(
            "SELECT id, name, category FROM exams WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) LIMIT 1",
            (exam_name,)
        ).fetchone()

        if not exam_row:
            continue

        target_id = exam_row["id"]
        question_count = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE exam_id = ?",
            (target_id,)
        ).fetchone()[0]

        # Keep the database test count synchronized with the real question bank.
        if question_count > 0 and question_count != test["questions"]:
            conn.execute(
                "UPDATE tests SET questions = ? WHERE id = ?",
                (question_count, test["id"])
            )

        cards += f"""
        <div class="exam-card">
            <div class="exam-icon">📝</div>
            <div class="exam-category">{exam_row["category"]}</div>
            <h3>{test["title"]}</h3>
            <p>Practice exam-specific questions with automatic scoring and a timed test.</p>
            <div style="color:#8992a5;font-size:12px;margin-bottom:15px;">
                {question_count if question_count else test["questions"]} Questions • 20 Minute Test
            </div>
            <a href="/test/{target_id}" class="btn btn-primary">Start Test →</a>
        </div>
        """

    conn.commit()
    conn.close()

    content = f"""
    <div class="page-title">Mock Tests</div>
    <div class="page-subtitle">Practice. Analyze. Improve. Repeat.</div>
    <div class="exam-grid">{cards}</div>
    """
    return app_page(content, "tests")


# ============================================================
# MOCK TEST
# ============================================================

@app.route("/test/<int:exam_id>")
def test(exam_id):
    """Start a fresh randomized mock test for the selected examination."""
    conn = get_db()
    exam = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()

    if not exam:
        conn.close()
        return "Exam not found", 404

    bank_count = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE exam_id=?", (exam_id,)
    ).fetchone()[0]

    if bank_count == 0:
        conn.close()
        return app_page(
            "<div class='empty-state'><h2>No questions available</h2><p>Please use Manage Questions to add questions for this examination.</p></div>",
            "tests"
        )

    # 10 questions per attempt, randomly selected from the complete bank.
    # When the bank contains fewer than 10 questions, all are used.
    attempt_size = min(10, bank_count)
    questions = conn.execute("""
        SELECT * FROM questions
        WHERE exam_id=?
        ORDER BY RANDOM()
        LIMIT ?
    """, (exam_id, attempt_size)).fetchall()
    conn.close()

    # Store only the IDs shown in this attempt so the result is scored
    # against exactly the questions the student actually received.
    session[f"test_questions_{exam_id}"] = [q["id"] for q in questions]

    question_cards = ""
    for i, q in enumerate(questions, start=1):
        question_cards += f"""
        <div class="question-card" id="question-{i}" style="display:{'block' if i == 1 else 'none'};">
            <div class="question-number">Question {i} of {len(questions)}</div>
            <h2>{q['question']}</h2>
            <div class="option-list">
                <label class="option"><input type="radio" name="question_{q['id']}" value="A"> <span>A</span> {q['option_a']}</label>
                <label class="option"><input type="radio" name="question_{q['id']}" value="B"> <span>B</span> {q['option_b']}</label>
                <label class="option"><input type="radio" name="question_{q['id']}" value="C"> <span>C</span> {q['option_c']}</label>
                <label class="option"><input type="radio" name="question_{q['id']}" value="D"> <span>D</span> {q['option_d']}</label>
            </div>
            <div class="test-nav">
                <button type="button" class="btn btn-secondary" onclick="changeQuestion(-1)">← Previous</button>
                <button type="button" class="btn btn-primary" onclick="changeQuestion(1)">{'Next →' if i < len(questions) else 'Review →'}</button>
            </div>
        </div>
        """

    content = f"""
    <div class="test-shell">
        <div class="test-header">
            <div>
                <div class="eyebrow">CRACKIT MOCK TEST</div>
                <h1>{exam['name']}</h1>
                <p>Questions are selected automatically from the live question bank.</p>
            </div>
            <div class="timer-box" id="timer">20:00</div>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;gap:15px;margin:16px 0;color:#8992a5;font-size:13px;">
            <span>Question Bank: {bank_count}</span>
            <span>This Attempt: {len(questions)}</span>
        </div>

        <form method="POST" action="/submit-test/{exam_id}" id="testForm">
            {question_cards}
            <div class="submit-area" id="submitArea" style="display:none;">
                <div><strong>Ready to submit?</strong><p>Your score will be calculated automatically.</p></div>
                <button class="btn btn-primary" type="submit">Finish Test ✓</button>
            </div>
        </form>
    </div>

    <script>
    let currentQuestion = 1;
    const totalQuestions = {len(questions)};
    let seconds = 20 * 60;

    function showQuestion(n) {{
        document.querySelectorAll('.question-card').forEach(el => el.style.display = 'none');
        const current = document.getElementById('question-' + n);
        if (current) current.style.display = 'block';
        currentQuestion = n;
        document.getElementById('submitArea').style.display = n === totalQuestions ? 'flex' : 'none';
        window.scrollTo({{top: 0, behavior: 'smooth'}});
    }}

    function changeQuestion(step) {{
        const next = currentQuestion + step;
        if (next >= 1 && next <= totalQuestions) showQuestion(next);
    }}

    function updateTimer() {{
        const m = Math.floor(seconds / 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        document.getElementById('timer').textContent = m + ':' + s;
        if (seconds <= 0) {{
            document.getElementById('testForm').submit();
            return;
        }}
        seconds--;
    }}

    updateTimer();
    setInterval(updateTimer, 1000);
    </script>
    """
    return app_page(content, "tests")


# ============================================================
# SUBMIT MOCK TEST
# ============================================================

@app.route("/submit-test/<int:exam_id>", methods=["POST"])
def submit_test(exam_id):
    conn = get_db()
    exam = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()

    if not exam:
        conn.close()
        return "Exam not found", 404

    selected_ids = session.pop(f"test_questions_{exam_id}", None)
    if selected_ids:
        placeholders = ",".join("?" for _ in selected_ids)
        questions = conn.execute(
            f"SELECT * FROM questions WHERE exam_id=? AND id IN ({placeholders}) ORDER BY id",
            [exam_id, *selected_ids]
        ).fetchall()
    else:
        # Safe fallback if the browser/session was refreshed before submission.
        questions = conn.execute(
            "SELECT * FROM questions WHERE exam_id=? ORDER BY RANDOM() LIMIT 10",
            (exam_id,)
        ).fetchall()

    score = 0
    for question in questions:
        if request.form.get(f"question_{question['id']}") == question["correct_answer"]:
            score += 1

    total = len(questions)
    percentage = round((score / total) * 100, 2) if total else 0

    session["score"] = score
    session["total"] = total
    session["percentage"] = percentage
    session["result_exam"] = exam["name"]

    user_id = session.get("user_id")

    if user_id and total:
        conn.execute("""
            INSERT INTO results (user_id, exam_id, score, total_questions, percentage)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, exam_id, score, total, percentage))
        conn.commit()

    conn.close()

    # The score is stored in the session above.
    # Send the student to the dedicated Result / Performance page.
    return redirect("/result")



# ============================================================
# STUDY MATERIALS
# ============================================================


@app.route("/materials")
def materials():
    conn = get_db()
    rows = conn.execute("SELECT * FROM materials ORDER BY id DESC").fetchall()
    conn.close()

    cards = ""
    for m in rows:
        existing_link = (m["link"] or "").strip()

        # Old materials often have "#" as their link.
        # Use the built-in CrackIt viewer in that case.
        if existing_link and existing_link != "#":
            material_link = existing_link
            target = ' target="_blank" rel="noopener"'
        else:
            material_link = f"/material/{m['id']}"
            target = ""

        material_type = (
            m["type"]
            if "type" in m.keys() and m["type"]
            else "Study Material"
        )

        exam_name = (
            m["exam"]
            if "exam" in m.keys() and m["exam"]
            else "Competitive Examination"
        )

        cards += f"""
        <div class="material-card">
            <div class="material-icon">📚</div>
            <div class="exam-category">
                {m["subject"]} • {material_type}
            </div>

            <h3>{m["title"]}</h3>

            <p>
                {m["description"] or
                 "Study material for competitive-exam preparation."}
            </p>

            <div style="font-size:12px;color:#8992a5;margin-bottom:14px;">
                🎯 {exam_name}
            </div>

            <a href="{material_link}"
               class="btn btn-light"{target}>
                Open Material →
            </a>
        </div>
        """

    if not cards:
        cards = """
        <div class="card">
            <p>No study materials available yet.</p>
        </div>
        """

    content = f"""
    <div class="page-title">Study Materials</div>

    <div class="page-subtitle">
        Notes, practice sets and revision resources for your preparation.
    </div>

    <div class="material-grid">
        {cards}
    </div>
    """

    return app_page(content, "materials")


# ============================================================
# MATERIAL VIEWER
# ============================================================

def get_material_notes(title, subject):
    title_text = (title or "").lower()
    subject_text = (subject or "").lower()

    if "polity" in title_text or "constitution" in title_text:
        return """
INDIAN POLITY – QUICK STUDY NOTES

1. Indian Constitution
The Constitution is the supreme law of India. It defines the structure, powers and functions of the government.

2. Preamble
The Preamble describes the basic ideals and objectives of the Constitution, including justice, liberty, equality and fraternity.

3. Fundamental Rights
Fundamental Rights are contained in Part III of the Constitution.

4. Directive Principles
Directive Principles of State Policy are contained in Part IV.

5. Fundamental Duties
Fundamental Duties are listed in Article 51A.

6. Parliament
The Parliament consists of the President, Rajya Sabha and Lok Sabha.

QUICK REVISION
• Part III → Fundamental Rights
• Part IV → Directive Principles
• Article 51A → Fundamental Duties
"""

    if "history" in title_text or "history" in subject_text:
        return """
MODERN INDIAN HISTORY – QUICK STUDY NOTES

Important topics:

1. Revolt of 1857
2. Formation of Indian National Congress
3. Swadeshi Movement
4. Non-Cooperation Movement
5. Civil Disobedience Movement
6. Quit India Movement
7. Indian Independence

QUICK REVISION
1857 → Revolt
1885 → Indian National Congress
1920 → Non-Cooperation Movement
1930 → Civil Disobedience Movement
1942 → Quit India Movement
1947 → Independence
"""

    if "geography" in title_text or "geography" in subject_text:
        return """
INDIAN GEOGRAPHY – QUICK STUDY NOTES

Important topics:

1. Himalayas
2. Northern Plains
3. Peninsular Plateau
4. Indian Desert
5. Coastal Plains
6. Major Rivers
7. Indian Climate
8. Soil Types
9. Agriculture
10. Mineral Resources

Important rivers include the Ganga, Yamuna, Brahmaputra, Godavari, Krishna, Narmada and Tapi.
"""

    if "science" in title_text or "science" in subject_text:
        return """
GENERAL SCIENCE – QUICK STUDY NOTES

PHYSICS
• Motion
• Force
• Work and Energy
• Heat
• Light
• Electricity

CHEMISTRY
• Matter
• Atoms and Molecules
• Acids and Bases
• Metals and Non-metals
• Chemical Reactions

BIOLOGY
• Cell
• Human Body
• Nutrition
• Diseases
• Plants
• Reproduction
"""

    if "current affair" in title_text or "current affair" in subject_text:
        return """
CURRENT AFFAIRS – MONTHLY REVISION AREAS

Revise:

1. National events
2. International events
3. Government schemes
4. Important appointments
5. Awards and honours
6. Sports
7. Science and technology
8. Defence
9. Economy
10. Important reports and days

Update these notes regularly with verified current information.
"""

    if "quantitative" in title_text or "aptitude" in title_text:
        return """
QUANTITATIVE APTITUDE – QUICK REVISION

Important topics:

• Number System
• Percentage
• Profit and Loss
• Ratio and Proportion
• Average
• Simple and Compound Interest
• Time and Work
• Time, Speed and Distance
• Data Interpretation

Practice formulas and solve timed questions regularly.
"""

    if "reasoning" in title_text or "reasoning" in subject_text:
        return """
REASONING – QUICK REVISION

Important topics:

• Analogy
• Classification
• Series
• Coding-Decoding
• Blood Relations
• Direction Sense
• Syllogism
• Seating Arrangement
• Logical Puzzles

Practice regularly and review mistakes.
"""

    if "banking" in title_text or "banking" in subject_text:
        return """
BANKING AWARENESS – QUICK STUDY NOTES

Important areas:

• Basic banking terms
• Types of bank accounts
• RBI
• Monetary policy
• Interest rates
• Inflation
• Digital banking
• Financial inclusion
• Financial abbreviations
"""

    if "defence" in title_text or "defence" in subject_text:
        return """
DEFENCE AWARENESS – QUICK STUDY NOTES

Important areas:

• Indian Armed Forces
• Army
• Navy
• Air Force
• Defence commands
• Military exercises
• Missiles and aircraft
• Defence organisations
• Ranks and appointments
"""

    if "physics" in title_text or "mathematics" in title_text:
        return """
PHYSICS & MATHEMATICS – QUICK REVISION

PHYSICS
• Units and Dimensions
• Motion
• Laws of Motion
• Work, Energy and Power
• Gravitation
• Electricity

MATHEMATICS
• Algebra
• Trigonometry
• Coordinate Geometry
• Calculus
• Probability
• Statistics

Keep a formula sheet and practise numerical problems regularly.
"""

    return f"""
{title}

Subject: {subject}

This study material is available on CrackIt for examination preparation.

Read the topic carefully, make short revision notes, practise questions and revise regularly.
"""


@app.route("/material/<int:material_id>")
def material_view(material_id):
    conn = get_db()

    material = conn.execute(
        "SELECT * FROM materials WHERE id=?",
        (material_id,)
    ).fetchone()

    conn.close()

    if not material:
        return "Study material not found", 404

    title = material["title"]
    subject = material["subject"]

    exam_name = (
        material["exam"]
        if "exam" in material.keys() and material["exam"]
        else "Competitive Examination"
    )

    material_type = (
        material["type"]
        if "type" in material.keys() and material["type"]
        else "Study Material"
    )

    description = (
        material["description"]
        or "Study material for competitive-exam preparation."
    )

    existing_link = (material["link"] or "").strip()

    external_button = ""

    if existing_link and existing_link != "#":
        external_button = f"""
        <a href="{existing_link}"
           target="_blank"
           rel="noopener"
           class="btn btn-primary"
           style="margin-left:10px;">
            Open File / Link ↗
        </a>
        """

    notes = get_material_notes(title, subject)

    content = f"""
    <div style="max-width:950px;margin:auto;">

        <a href="/materials"
           class="btn btn-light"
           style="margin-bottom:20px;">
            ← Back to Study Materials
        </a>

        <div class="detail-hero" style="margin-bottom:22px;">

            <div class="tag">{material_type}</div>

            <h1>{title}</h1>

            <p>{description}</p>

            <div style="margin-top:18px;font-size:13px;opacity:.9;">
                📚 {subject}
                &nbsp; • &nbsp;
                🎯 {exam_name}
            </div>

        </div>

        <div class="card">

            <div class="card-title"
                 style="align-items:center;">

                <h3>📖 Study Material</h3>

                <div>
                    {external_button}
                </div>

            </div>

            <div style="
                white-space:pre-wrap;
                color:#4f596c;
                line-height:1.85;
                font-size:15px;
                background:#fafbff;
                border:1px solid #edf0f5;
                border-radius:16px;
                padding:25px;
            ">{notes}</div>

        </div>

    </div>
    """

    return app_page(content, "materials")


# ============================================================
# ROADMAP

# ============================================================

@app.route("/roadmap")
def roadmap():
    content = """
    <div class="page-title">Preparation Roadmap</div>
    <div class="page-subtitle">Follow a simple step-by-step plan from preparation to selection.</div>

    <div class="roadmap">
        <div class="road-step"><div class="step-number">1</div><div class="step-content"><h3>Choose Your Examination</h3><p>Select the examination that matches your goal and review its eligibility, qualification and pattern.</p></div></div>
        <div class="road-step"><div class="step-number">2</div><div class="step-content"><h3>Understand the Syllabus</h3><p>Break the syllabus into subjects and smaller topics so your preparation stays organized.</p></div></div>
        <div class="road-step"><div class="step-number">3</div><div class="step-content"><h3>Build Your Study Plan</h3><p>Set daily study targets, revision sessions and realistic weekly goals.</p></div></div>
        <div class="road-step"><div class="step-number">4</div><div class="step-content"><h3>Study & Revise</h3><p>Use CrackIt's study materials and revise important concepts regularly.</p></div></div>
        <div class="road-step"><div class="step-number">5</div><div class="step-content"><h3>Practice Mock Tests</h3><p>Attempt timed mock tests and use your results to identify topics that need more practice.</p></div></div>
        <div class="road-step"><div class="step-number">6</div><div class="step-content"><h3>Track Performance</h3><p>Review scores, accuracy and progress and continuously improve your preparation strategy.</p></div></div>
    </div>
    """
    return app_page(content, "roadmap")


# ============================================================
# PROFILE & NOTIFICATIONS
# ============================================================

@app.route("/profile")
def profile():
    conn = get_db()
    user_id = session.get("user_id")
    user = None
    if user_id:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()

    name = user["name"] if user else session.get("user_name", "Student")
    email = user["email"] if user else "Not logged in"
    initial = name[:1].upper() if name else "S"

    content = f"""
    <div class="page-title">Profile & Notifications</div>
    <div class="page-subtitle">Manage your student profile and stay updated.</div>

    <div class="profile-grid">
        <div class="profile-card">
            <div class="profile-avatar">{initial}</div>
            <h2>{name}</h2>
            <p style="color:#8992a5;margin-top:7px;">{email}</p>
            <div style="margin-top:22px;padding-top:18px;border-top:1px solid #edf0f5;">
                <strong>CrackIt Student</strong>
                <p style="color:#8992a5;font-size:13px;margin-top:7px;line-height:1.6;">Keep your preparation consistent and use mock tests to track improvement.</p>
            </div>
        </div>

        <div class="profile-card">
            <h3 style="margin-bottom:5px;">Notifications</h3>
            <div class="notification"><div class="notification-icon">📝</div><div><strong>Mock Tests Available</strong><p style="color:#8992a5;font-size:12px;margin-top:4px;">Practice exam-specific questions with automatic scoring.</p></div></div>
            <div class="notification"><div class="notification-icon">📚</div><div><strong>Study Materials</strong><p style="color:#8992a5;font-size:12px;margin-top:4px;">Use the latest notes and practice resources in your preparation.</p></div></div>
            <div class="notification"><div class="notification-icon">🎯</div><div><strong>Keep Practicing</strong><p style="color:#8992a5;font-size:12px;margin-top:4px;">Regular revision and timed practice can help you monitor progress.</p></div></div>
        </div>
    </div>
    """
    return app_page(content, "profile")


# ============================================================
# RESULT PAGE
# ============================================================

@app.route("/result")
def result():
    score = session.get("score")
    total = session.get("total")
    percentage = session.get("percentage")
    exam_name = session.get("result_exam", "Mock Test")

    if score is None or total is None:
        content = """
        <div class="result-box">
            <div class="page-title">Performance</div>
            <p style="color:#8992a5;margin:15px 0 25px;">Complete a mock test to see your result here.</p>
            <a href="/tests" class="btn btn-primary">Go to Mock Tests →</a>
        </div>
        """
        return app_page(content, "result")

    percentage = float(percentage if percentage is not None else (score / total * 100 if total else 0))
    performance = "Excellent" if percentage >= 80 else "Good" if percentage >= 60 else "Keep Practicing"

    content = f"""
    <div class="result-box">
        <div class="result-badge">✓ TEST COMPLETED</div>
        <h1 style="margin-top:15px;">{exam_name}</h1>
        <p style="color:#8992a5;margin-top:8px;">Your result has been calculated automatically.</p>
        <div class="score">{percentage:.0f}%</div>
        <h2>{performance}!</h2>
        <p style="color:#8992a5;margin-top:8px;">You scored <b>{score}</b> out of <b>{total}</b> questions.</p>
        <div class="result-stats">
            <div class="result-stat"><strong>{score}</strong><span>Correct Answers</span></div>
            <div class="result-stat"><strong>{max(total-score,0)}</strong><span>Incorrect / Unanswered</span></div>
            <div class="result-stat"><strong>{total}</strong><span>Total Questions</span></div>
        </div>
        <a href="/tests" class="btn btn-primary">Try Another Test →</a>
    </div>
    """
    return app_page(content, "result")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":
    init_db()
    print("")
    print("========================================")
    print("        CRACKIT SERVER STARTED")
    print("========================================")
    print("")
    print("Open: http://127.0.0.1:5000")
    print("")
    app.run(debug=True)
