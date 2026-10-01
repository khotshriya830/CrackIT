import sqlite3

DB_NAME = "crackit.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# First check your exam IDs
cursor.execute("SELECT id, name FROM exams")

exams = cursor.fetchall()

print("\nAvailable Exams:")
for exam in exams:
    print(exam)

# Example: change this according to your database
exam_id = 1

questions = [

    (
        exam_id,
        "Who is known as the Father of the Indian Constitution?",
        "Mahatma Gandhi",
        "Dr. B. R. Ambedkar",
        "Jawaharlal Nehru",
        "Sardar Patel",
        "B",
        "Dr. B. R. Ambedkar played a major role in drafting the Indian Constitution."
    ),

    (
        exam_id,
        "What is the capital of India?",
        "Mumbai",
        "New Delhi",
        "Kolkata",
        "Chennai",
        "B",
        "New Delhi is the capital of India."
    ),

    (
        exam_id,
        "Which is the largest planet in our Solar System?",
        "Earth",
        "Mars",
        "Jupiter",
        "Saturn",
        "C",
        "Jupiter is the largest planet in the Solar System."
    ),

    (
        exam_id,
        "Which article deals with the Right to Life and Personal Liberty?",
        "Article 14",
        "Article 19",
        "Article 21",
        "Article 32",
        "C",
        "Article 21 protects the Right to Life and Personal Liberty."
    ),

    (
        exam_id,
        "Which organization conducts the UPSC Civil Services Examination?",
        "SSC",
        "UPSC",
        "IBPS",
        "NTA",
        "B",
        "The Union Public Service Commission conducts the Civil Services Examination."
    )

]

cursor.executemany("""
    INSERT INTO questions
    (
        exam_id,
        question,
        option_a,
        option_b,
        option_c,
        option_d,
        correct_answer,
        explanation
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", questions)

conn.commit()
conn.close()

print("\nQuestions inserted successfully!")