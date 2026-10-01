import sqlite3
import sys

DB_NAME = "crackit.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    return sqlite3.connect(DB_NAME)


# ============================================================
# SHOW AVAILABLE EXAMS
# ============================================================

def show_exams(cursor):
    cursor.execute("SELECT id, name FROM exams ORDER BY id")
    exams = cursor.fetchall()

    if not exams:
        print("\nNo examinations found in the database.")
        print("Please run app.py once first.")
        return []

    print("\n" + "=" * 60)
    print("AVAILABLE EXAMINATIONS")
    print("=" * 60)

    for exam_id, exam_name in exams:
        print(f"{exam_id}. {exam_name}")

    print("=" * 60)

    return exams


# ============================================================
# SELECT EXAM
# ============================================================

def select_exam(exams):
    while True:
        value = input("\nEnter Exam ID: ").strip()

        if not value.isdigit():
            print("Please enter a valid numeric Exam ID.")
            continue

        exam_id = int(value)

        for current_id, exam_name in exams:
            if current_id == exam_id:
                print(f"\nSelected Exam: {exam_name}")
                return exam_id, exam_name

        print("Invalid Exam ID. Please select an ID from the list.")


# ============================================================
# STUDY MATERIALS
# ============================================================
#
# Each item contains:
#
# (
#     subject,
#     title,
#     description,
#     material_type,
#     external_link
# )
#
# These are external official/reference resources.
# ============================================================

def get_materials():
    return [

        (
            "Indian Polity",
            "Indian Constitution – Complete Notes",
            "Official Constitution of India resources from the Legislative Department, Ministry of Law and Justice.",
            "Official Reference",
            "https://www.legislative.gov.in/documents"
        ),

        (
            "Indian History",
            "Modern Indian History Notes",
            "NCERT textbook resources that can be used for history study and revision.",
            "NCERT Reference",
            "https://ncert.nic.in/textbook.php"
        ),

        (
            "Geography",
            "Indian Geography Study Material",
            "NCERT textbook resources covering geography concepts for school and competitive-exam preparation.",
            "NCERT Reference",
            "https://ncert.nic.in/textbook.php"
        ),

        (
            "General Science",
            "General Science Basics",
            "NCERT science textbooks covering basic Physics, Chemistry and Biology concepts.",
            "NCERT Reference",
            "https://ncert.nic.in/textbook.php"
        ),

        (
            "Current Affairs",
            "Monthly Current Affairs",
            "Official Press Information Bureau releases for current national and government-related updates.",
            "Official Reference",
            "https://www.pib.gov.in/AllRelease.aspx?lang=1&reg=1"
        )

    ]


# ============================================================
# INSERT MATERIAL
# ============================================================

def add_material(cursor, exam_id, exam_name, material):
    subject, title, description, material_type, link = material

    # Check duplicate by exam + title
    cursor.execute(
        """
        SELECT id
        FROM materials
        WHERE exam_id = ?
          AND title = ?
        LIMIT 1
        """,
        (exam_id, title)
    )

    existing = cursor.fetchone()

    if existing:
        # Update an existing record so its link is corrected.
        cursor.execute(
            """
            UPDATE materials
            SET subject = ?,
                exam = ?,
                type = ?,
                description = ?,
                link = ?
            WHERE id = ?
            """,
            (
                subject,
                exam_name,
                material_type,
                description,
                link,
                existing[0]
            )
        )

        print(f"UPDATED : {title}")
        return "updated"

    cursor.execute(
        """
        INSERT INTO materials
        (
            title,
            subject,
            exam,
            exam_id,
            type,
            description,
            link
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            subject,
            exam_name,
            exam_id,
            material_type,
            description,
            link
        )
    )

    print(f"ADDED   : {title}")
    return "added"


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "=" * 60)
    print("CRACKIT - STUDY MATERIALS")
    print("=" * 60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

    except sqlite3.Error as error:
        print("\nCould not connect to crackit.db")
        print("Error:", error)
        sys.exit(1)

    try:

        # ----------------------------------------------------
        # CHECK EXAMS
        # ----------------------------------------------------
        exams = show_exams(cursor)

        if not exams:
            conn.close()
            return

        # ----------------------------------------------------
        # CHOOSE EXAM
        # ----------------------------------------------------
        exam_id, exam_name = select_exam(exams)

        # ----------------------------------------------------
        # GET MATERIALS
        # ----------------------------------------------------
        materials = get_materials()

        print("\n" + "-" * 60)
        print(f"ADDING MATERIALS FOR: {exam_name}")
        print("-" * 60)

        added = 0
        updated = 0

        # ----------------------------------------------------
        # INSERT / UPDATE
        # ----------------------------------------------------
        for material in materials:

            result = add_material(
                cursor,
                exam_id,
                exam_name,
                material
            )

            if result == "added":
                added += 1
            elif result == "updated":
                updated += 1

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------
        conn.commit()

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------
        print("\n" + "=" * 60)
        print("COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print("Exam      :", exam_name)
        print("Added     :", added)
        print("Updated   :", updated)
        print("Total     :", len(materials))

        print("=" * 60)

        print("\nThe material links have been saved in crackit.db.")

        print("\nNow start your Flask application:")
        print("py app.py")

        print("\nThen open:")
        print("http://127.0.0.1:5000/materials")

        print("\nClick 'Open Material →' on any card.")

    except sqlite3.Error as error:

        conn.rollback()

        print("\nDatabase error:")
        print(error)

    except KeyboardInterrupt:

        conn.rollback()

        print("\n\nOperation cancelled.")

    finally:

        conn.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
