import sqlite3

conn = sqlite3.connect("crackit.db")
cursor = conn.cursor()

# Fix materials table
cursor.execute("PRAGMA table_info(materials)")
material_columns = [row[1] for row in cursor.fetchall()]

if "exam_id" not in material_columns:

    cursor.execute("""
        ALTER TABLE materials
        ADD COLUMN exam_id INTEGER
    """)

    print("exam_id added to materials table.")

else:

    print("materials.exam_id already exists.")


# Fix questions table
cursor.execute("PRAGMA table_info(questions)")
question_columns = [row[1] for row in cursor.fetchall()]

if "exam_id" not in question_columns:

    cursor.execute("""
        ALTER TABLE questions
        ADD COLUMN exam_id INTEGER
    """)

    print("exam_id added to questions table.")

else:

    print("questions.exam_id already exists.")


conn.commit()
conn.close()

print("Database fixed successfully.")