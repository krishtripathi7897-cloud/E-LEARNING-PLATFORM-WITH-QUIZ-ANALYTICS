"""
Run this once after the app has started (so database.db exists) to fill
the app with demo data — 2 courses, quizzes, questions, an enrolled
student, some quiz attempts, and notifications.

Usage:
    python seed_data.py
"""
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------- Users ----------
    def get_or_create_user(name, email, password, role):
        row = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return row["id"]
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role),
        )
        return cur.lastrowid

    instructor_id = get_or_create_user("Jyoti Jadhav", "instructor@demo.com", "demo123", "instructor")
    student_id = get_or_create_user("Krish Tripathi", "student@demo.com", "demo123", "student")

    # ---------- Courses ----------
    def get_or_create_course(title, description):
        row = cur.execute("SELECT id FROM courses WHERE title = ?", (title,)).fetchone()
        if row:
            return row["id"]
        cur.execute(
            "INSERT INTO courses (title, description, instructor_id, created_at) VALUES (?, ?, ?, ?)",
            (title, description, instructor_id, datetime.now().strftime("%d %b %Y")),
        )
        return cur.lastrowid

    course1 = get_or_create_course(
        "Python Programming Basics",
        "Learn Python from scratch — variables, loops, functions, and basic OOP concepts."
    )
    course2 = get_or_create_course(
        "Web Development Fundamentals",
        "HTML, CSS and JavaScript basics to build your first website."
    )

    # ---------- Enroll student in both ----------
    for cid in (course1, course2):
        exists = cur.execute(
            "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, cid)
        ).fetchone()
        if not exists:
            cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)", (student_id, cid))

    # ---------- Quizzes + Questions ----------
    def get_or_create_quiz(course_id, title, time_limit=10):
        row = cur.execute("SELECT id FROM quizzes WHERE title = ? AND course_id = ?", (title, course_id)).fetchone()
        if row:
            return row["id"]
        cur.execute(
            "INSERT INTO quizzes (course_id, title, time_limit) VALUES (?, ?, ?)",
            (course_id, title, time_limit),
        )
        return cur.lastrowid

    def add_question_if_missing(quiz_id, qtext, qtype, a, b, c, d, correct):
        row = cur.execute("SELECT id FROM questions WHERE qtext = ? AND quiz_id = ?", (qtext, quiz_id)).fetchone()
        if row:
            return row["id"]
        cur.execute("""
            INSERT INTO questions (quiz_id, qtext, qtype, option_a, option_b, option_c, option_d, correct_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (quiz_id, qtext, qtype, a, b, c, d, correct))
        return cur.lastrowid

    quiz1 = get_or_create_quiz(course1, "Python Basics Quiz")
    add_question_if_missing(quiz1, "Which keyword defines a function in Python?", "mcq", "func", "def", "function", "define", "def")
    add_question_if_missing(quiz1, "Python is a compiled language.", "truefalse", "", "", "", "", "False")
    add_question_if_missing(quiz1, "What does len() return for a list?", "short", "", "", "", "", "length")

    quiz2 = get_or_create_quiz(course2, "HTML & CSS Quiz")
    add_question_if_missing(quiz2, "Which tag is used for the largest heading?", "mcq", "<h6>", "<h1>", "<head>", "<heading>", "<h1>")
    add_question_if_missing(quiz2, "CSS stands for Cascading Style Sheets.", "truefalse", "", "", "", "", "True")

    conn.commit()

    # ---------- Sample quiz attempts (for analytics charts) ----------
    def add_attempt(quiz_id, score, total, days_ago):
        when = (datetime.now() - timedelta(days=days_ago)).strftime("%d %b %Y, %I:%M %p")
        exists = cur.execute(
            "SELECT id FROM attempts WHERE quiz_id = ? AND student_id = ? AND attempted_at = ?",
            (quiz_id, student_id, when)
        ).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO attempts (quiz_id, student_id, score, total, attempted_at) VALUES (?, ?, ?, ?, ?)",
                (quiz_id, student_id, score, total, when),
            )

    add_attempt(quiz1, 2, 3, days_ago=5)
    add_attempt(quiz1, 3, 3, days_ago=2)
    add_attempt(quiz2, 1, 2, days_ago=1)

    conn.commit()

    # ---------- Notifications ----------
    def add_notification(user_id, message, days_ago=0):
        when = (datetime.now() - timedelta(days=days_ago)).strftime("%d %b %Y, %I:%M %p")
        cur.execute(
            "INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
            (user_id, message, when),
        )

    add_notification(student_id, "New content 'Intro to Variables' added to Python Programming Basics", days_ago=4)
    add_notification(student_id, "New quiz 'Python Basics Quiz' is now available!", days_ago=3)
    add_notification(student_id, "New quiz 'HTML & CSS Quiz' is now available!", days_ago=1)

    conn.commit()
    conn.close()

    print("Demo data added successfully!")
    print("Instructor login -> email: instructor@demo.com | password: demo123")
    print("Student login    -> email: student@demo.com    | password: demo123")


if __name__ == "__main__":
    run()
