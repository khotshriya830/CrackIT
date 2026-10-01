import sqlite3

conn = sqlite3.connect("crackit.db")
cursor = conn.cursor()

print("\nQUESTIONS TABLE:")
cursor.execute("PRAGMA table_info(questions)")

for column in cursor.fetchall():
    print(column)

print("\nMATERIALS TABLE:")
cursor.execute("PRAGMA table_info(materials)")

for column in cursor.fetchall():
    print(column)

print("\nEXAMS TABLE:")
cursor.execute("PRAGMA table_info(exams)")

for column in cursor.fetchall():
    print(column)

conn.close()