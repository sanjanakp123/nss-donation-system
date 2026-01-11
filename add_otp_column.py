import sqlite3
import os

print("Current folder:", os.getcwd())

db = sqlite3.connect("database.db")
cursor = db.cursor()

try:
    cursor.execute("""
        ALTER TABLE donations
        ADD COLUMN otp_verified INTEGER DEFAULT 0
    """)
    print("✅ otp_verified column added")
except Exception as e:
    print("⚠️", e)

db.commit()
db.close()
