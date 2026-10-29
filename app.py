from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key-later"

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"pdf", "mp4", "mov", "txt", "doc", "docx", "png", "jpg", "jpeg"}


# ---------------- DATABASE HELPERS ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','instructor'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            instructor_id INTEGER NOT NULL,
            created_at TEXT,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            ctype TEXT NOT NULL,
            filename TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            time_limit INTEGER DEFAULT 10,
            FOREIGN KEY (course_id) REFERENCES courses(id)
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            qtext TEXT NOT NULL,
            qtype TEXT NOT NULL CHECK(qtype IN ('mcq','truefalse','short')),
            option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT,
            correct_answer TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            attempted_at TEXT,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def add_notification(user_id, message):
    conn = get_db()
    conn.execute(
        "INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
        (user_id, message, datetime.now().strftime("%d %b %Y, %I:%M %p")),
    )
    conn.commit()
    conn.close()


def current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user


def login_required(role=None):
    if "user_id" not in session:
        return False
    if role and session.get("role") != role:
        return False
    return True


@app.context_processor
def inject_notifications():
    """Har page pe unread notification count available rahe navbar ke liye."""
    if "user_id" in session:
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND is_read = 0",
            (session["user_id"],),
        ).fetchone()["c"]
        conn.close()
        return {"unread_count": count}
    return {"unread_count": 0}


# ---------------- HOME / AUTH ----------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        if not name or not email or not password or role not in ("student", "instructor"):
            flash("Please fill all fields correctly.", "error")
            return redirect(url_for("register"))

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("This email is already registered. Please login.", "error")
            conn.close()
            return redirect(url_for("register"))

        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role),
        )
        conn.commit()
        conn.close()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("instructor_dashboard" if user["role"] == "instructor" else "student_dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


# ---------------- DASHBOARDS ----------------

@app.route("/dashboard/student")
def student_dashboard():
    if not login_required("student"):
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    enrolled = conn.execute("""
        SELECT c.* FROM courses c
        JOIN enrollments e ON e.course_id = c.id
        WHERE e.student_id = ?
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("dashboard_student.html", courses=enrolled)


@app.route("/dashboard/instructor")
def instructor_dashboard():
    if not login_required("instructor"):
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    courses = conn.execute("SELECT * FROM courses WHERE instructor_id = ?", (session["user_id"],)).fetchall()
    conn.close()
    return render_template("dashboard_instructor.html", courses=courses)


# ---------------- COURSE & CONTENT MANAGEMENT ----------------

@app.route("/courses")
def browse_courses():
    if not login_required():
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    courses = conn.execute("""
        SELECT c.*, u.name as instructor_name FROM courses c
        JOIN users u ON u.id = c.instructor_id
    """).fetchall()

    enrolled_ids = set()
    if session.get("role") == "student":
        rows = conn.execute("SELECT course_id FROM enrollments WHERE student_id = ?", (session["user_id"],)).fetchall()
        enrolled_ids = {r["course_id"] for r in rows}
    conn.close()
    return render_template("browse_courses.html", courses=courses, enrolled_ids=enrolled_ids)


@app.route("/course/create", methods=["GET", "POST"])
def create_course():
    if not login_required("instructor"):
        flash("Only instructors can create courses.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title:
            flash("Course title is required.", "error")
            return redirect(url_for("create_course"))

        conn = get_db()
        conn.execute(
            "INSERT INTO courses (title, description, instructor_id, created_at) VALUES (?, ?, ?, ?)",
            (title, description, session["user_id"], datetime.now().strftime("%d %b %Y")),
        )
        conn.commit()
        conn.close()
        flash("Course created successfully!", "success")
        return redirect(url_for("instructor_dashboard"))

    return render_template("create_course.html")


@app.route("/course/<int:course_id>")
def view_course(course_id):
    if not login_required():
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        flash("Course not found.", "error")
        conn.close()
        return redirect(url_for("browse_courses"))

    contents = conn.execute("SELECT * FROM contents WHERE course_id = ?", (course_id,)).fetchall()
    quizzes = conn.execute("SELECT * FROM quizzes WHERE course_id = ?", (course_id,)).fetchall()

    is_enrolled = False
    if session.get("role") == "student":
        row = conn.execute(
            "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?",
            (session["user_id"], course_id),
        ).fetchone()
        is_enrolled = row is not None

    is_owner = session.get("role") == "instructor" and course["instructor_id"] == session.get("user_id")
    conn.close()

    return render_template(
        "view_course.html", course=course, contents=contents, quizzes=quizzes,
        is_enrolled=is_enrolled, is_owner=is_owner
    )


@app.route("/course/<int:course_id>/enroll")
def enroll_course(course_id):
    if not login_required("student"):
        flash("Only students can enroll.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?",
        (session["user_id"], course_id),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
            (session["user_id"], course_id),
        )
        conn.commit()
        flash("Enrolled successfully!", "success")
    else:
        flash("You are already enrolled.", "error")
    conn.close()
    return redirect(url_for("view_course", course_id=course_id))


@app.route("/course/<int:course_id>/add_content", methods=["GET", "POST"])
def add_content(course_id):
    if not login_required("instructor"):
        flash("Only instructors can add content.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ? AND instructor_id = ?",
                           (course_id, session["user_id"])).fetchone()
    if not course:
        flash("Course not found or not yours.", "error")
        conn.close()
        return redirect(url_for("instructor_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        ctype = request.form.get("ctype", "")
        file = request.files.get("file")

        if not title or not file or file.filename == "" or not allowed_file(file.filename):
            flash("Please provide a title and a valid file (pdf, mp4, doc, txt, image).", "error")
            conn.close()
            return redirect(url_for("add_content", course_id=course_id))

        filename = secure_filename(f"{course_id}_{datetime.now().timestamp()}_{file.filename}")
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn.execute(
            "INSERT INTO contents (course_id, title, ctype, filename) VALUES (?, ?, ?, ?)",
            (course_id, title, ctype, filename),
        )
        conn.commit()

        # notify all enrolled students
        students = conn.execute("SELECT student_id FROM enrollments WHERE course_id = ?", (course_id,)).fetchall()
        for s in students:
            add_notification(s["student_id"], f"New content '{title}' added to {course['title']}")

        conn.close()
        flash("Content added!", "success")
        return redirect(url_for("view_course", course_id=course_id))

    conn.close()
    return render_template("add_content.html", course=course)


# ---------------- DELETE (COURSE / CONTENT / QUIZ) ----------------

def _remove_upload(filename):
    """Uploaded file disk se bhi delete karo (agar exist kare)."""
    try:
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _delete_quiz_rows(conn, quiz_id):
    conn.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
    conn.execute("DELETE FROM attempts WHERE quiz_id = ?", (quiz_id,))
    conn.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))


@app.route("/course/<int:course_id>/delete", methods=["POST"])
def delete_course(course_id):
    if not login_required("instructor"):
        flash("Only instructors can delete courses.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    course = conn.execute(
        "SELECT * FROM courses WHERE id = ? AND instructor_id = ?",
        (course_id, session["user_id"]),
    ).fetchone()
    if not course:
        conn.close()
        flash("Course not found or not yours.", "error")
        return redirect(url_for("instructor_dashboard"))

    # pehle saare child records hatao (foreign keys ON hain)
    files = conn.execute("SELECT filename FROM contents WHERE course_id = ?", (course_id,)).fetchall()
    quizzes = conn.execute("SELECT id FROM quizzes WHERE course_id = ?", (course_id,)).fetchall()
    for q in quizzes:
        _delete_quiz_rows(conn, q["id"])
    conn.execute("DELETE FROM contents WHERE course_id = ?", (course_id,))

    students = conn.execute("SELECT student_id FROM enrollments WHERE course_id = ?", (course_id,)).fetchall()
    conn.execute("DELETE FROM enrollments WHERE course_id = ?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()

    for f in files:
        _remove_upload(f["filename"])
    for s in students:
        add_notification(s["student_id"], f"Course '{course['title']}' has been removed by the instructor.")

    flash(f"Course '{course['title']}' deleted.", "success")
    return redirect(url_for("instructor_dashboard"))


@app.route("/content/<int:content_id>/delete", methods=["POST"])
def delete_content(content_id):
    if not login_required("instructor"):
        return redirect(url_for("login"))

    conn = get_db()
    row = conn.execute("""
        SELECT ct.*, c.instructor_id FROM contents ct
        JOIN courses c ON c.id = ct.course_id
        WHERE ct.id = ?
    """, (content_id,)).fetchone()
    if not row or row["instructor_id"] != session["user_id"]:
        conn.close()
        flash("Content not found or not yours.", "error")
        return redirect(url_for("instructor_dashboard"))

    course_id = row["course_id"]
    conn.execute("DELETE FROM contents WHERE id = ?", (content_id,))
    conn.commit()
    conn.close()
    _remove_upload(row["filename"])
    flash("Content deleted.", "success")
    return redirect(url_for("view_course", course_id=course_id))


@app.route("/quiz/<int:quiz_id>/delete", methods=["POST"])
def delete_quiz(quiz_id):
    if not login_required("instructor"):
        return redirect(url_for("login"))

    conn = get_db()
    quiz = conn.execute("""
        SELECT q.*, c.instructor_id FROM quizzes q
        JOIN courses c ON c.id = q.course_id
        WHERE q.id = ?
    """, (quiz_id,)).fetchone()
    if not quiz or quiz["instructor_id"] != session["user_id"]:
        conn.close()
        flash("Quiz not found or not yours.", "error")
        return redirect(url_for("instructor_dashboard"))

    course_id = quiz["course_id"]
    _delete_quiz_rows(conn, quiz_id)
    conn.commit()
    conn.close()
    flash("Quiz deleted.", "success")
    return redirect(url_for("view_course", course_id=course_id))


@app.route("/question/<int:question_id>/delete", methods=["POST"])
def delete_question(question_id):
    if not login_required("instructor"):
        return redirect(url_for("login"))

    conn = get_db()
    row = conn.execute("""
        SELECT qs.quiz_id, c.instructor_id FROM questions qs
        JOIN quizzes q ON q.id = qs.quiz_id
        JOIN courses c ON c.id = q.course_id
        WHERE qs.id = ?
    """, (question_id,)).fetchone()
    if not row or row["instructor_id"] != session["user_id"]:
        conn.close()
        flash("Question not found or not yours.", "error")
        return redirect(url_for("instructor_dashboard"))

    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    flash("Question deleted.", "success")
    return redirect(url_for("add_question", quiz_id=row["quiz_id"]))


# ---------------- QUIZ BUILDER ----------------

@app.route("/course/<int:course_id>/quiz/create", methods=["GET", "POST"])
def create_quiz(course_id):
    if not login_required("instructor"):
        flash("Only instructors can create quizzes.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ? AND instructor_id = ?",
                           (course_id, session["user_id"])).fetchone()
    if not course:
        flash("Course not found or not yours.", "error")
        conn.close()
        return redirect(url_for("instructor_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        time_limit = request.form.get("time_limit", "10")
        if not title:
            flash("Quiz title is required.", "error")
            conn.close()
            return redirect(url_for("create_quiz", course_id=course_id))

        cur = conn.execute(
            "INSERT INTO quizzes (course_id, title, time_limit) VALUES (?, ?, ?)",
            (course_id, title, int(time_limit)),
        )
        conn.commit()
        quiz_id = cur.lastrowid
        conn.close()
        flash("Quiz created! Now add some questions.", "success")
        return redirect(url_for("add_question", quiz_id=quiz_id))

    conn.close()
    return render_template("create_quiz.html", course=course)


@app.route("/quiz/<int:quiz_id>/add_question", methods=["GET", "POST"])
def add_question(quiz_id):
    if not login_required("instructor"):
        flash("Only instructors can add questions.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    quiz = conn.execute("""
        SELECT q.*, c.title as course_title, c.instructor_id FROM quizzes q
        JOIN courses c ON c.id = q.course_id
        WHERE q.id = ?
    """, (quiz_id,)).fetchone()

    if not quiz or quiz["instructor_id"] != session["user_id"]:
        flash("Quiz not found or not yours.", "error")
        conn.close()
        return redirect(url_for("instructor_dashboard"))

    if request.method == "POST":
        qtext = request.form.get("qtext", "").strip()
        qtype = request.form.get("qtype", "")
        option_a = request.form.get("option_a", "")
        option_b = request.form.get("option_b", "")
        option_c = request.form.get("option_c", "")
        option_d = request.form.get("option_d", "")
        correct_answer = request.form.get("correct_answer", "").strip()

        if not qtext or not qtype or not correct_answer:
            flash("Please fill question, type and correct answer.", "error")
            conn.close()
            return redirect(url_for("add_question", quiz_id=quiz_id))

        conn.execute("""
            INSERT INTO questions (quiz_id, qtext, qtype, option_a, option_b, option_c, option_d, correct_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (quiz_id, qtext, qtype, option_a, option_b, option_c, option_d, correct_answer))
        conn.commit()
        flash("Question added! Add more or click Finish & Publish.", "success")
        conn.close()
        return redirect(url_for("add_question", quiz_id=quiz_id))

    questions = conn.execute("SELECT * FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchall()
    conn.close()
    return render_template("add_question.html", quiz=quiz, questions=questions)


@app.route("/quiz/<int:quiz_id>/finish")
def finish_quiz_setup(quiz_id):
    if not login_required("instructor"):
        return redirect(url_for("login"))
    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    course_id = quiz["course_id"]

    students = conn.execute("SELECT student_id FROM enrollments WHERE course_id = ?", (course_id,)).fetchall()
    for s in students:
        add_notification(s["student_id"], f"New quiz '{quiz['title']}' is now available!")

    conn.close()
    flash("Quiz is live for enrolled students!", "success")
    return redirect(url_for("view_course", course_id=course_id))


# ---------------- AUTO-EVALUATION ENGINE (QUIZ ATTEMPT) ----------------

@app.route("/quiz/<int:quiz_id>/attempt", methods=["GET", "POST"])
def attempt_quiz(quiz_id):
    if not login_required("student"):
        flash("Only students can attempt quizzes.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if not quiz:
        flash("Quiz not found.", "error")
        conn.close()
        return redirect(url_for("student_dashboard"))

    questions = conn.execute("SELECT * FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchall()

    if request.method == "POST":
        score = 0
        total = len(questions)

        for q in questions:
            given = request.form.get(f"question_{q['id']}", "").strip()
            correct = q["correct_answer"].strip()
            # auto-evaluation: MCQ/true-false exact match, short answer case-insensitive match
            if q["qtype"] == "short":
                is_correct = given.lower() == correct.lower()
            else:
                is_correct = given == correct
            if is_correct:
                score += 1

        conn.execute(
            "INSERT INTO attempts (quiz_id, student_id, score, total, attempted_at) VALUES (?, ?, ?, ?, ?)",
            (quiz_id, session["user_id"], score, total, datetime.now().strftime("%d %b %Y, %I:%M %p")),
        )
        conn.commit()
        attempt_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        conn.close()
        return redirect(url_for("quiz_result", attempt_id=attempt_id))

    conn.close()
    return render_template("attempt_quiz.html", quiz=quiz, questions=questions)


@app.route("/result/<int:attempt_id>")
def quiz_result(attempt_id):
    if not login_required("student"):
        return redirect(url_for("login"))

    conn = get_db()
    attempt = conn.execute("""
        SELECT a.*, q.title as quiz_title FROM attempts a
        JOIN quizzes q ON q.id = a.quiz_id
        WHERE a.id = ? AND a.student_id = ?
    """, (attempt_id, session["user_id"])).fetchone()
    conn.close()

    if not attempt:
        flash("Result not found.", "error")
        return redirect(url_for("student_dashboard"))

    percentage = round((attempt["score"] / attempt["total"]) * 100, 1) if attempt["total"] else 0
    return render_template("quiz_result.html", attempt=attempt, percentage=percentage)


# ---------------- ANALYTICS DASHBOARD ----------------

@app.route("/analytics")
def student_analytics():
    if not login_required("student"):
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    attempts = conn.execute("""
        SELECT a.*, q.title as quiz_title, c.title as course_title FROM attempts a
        JOIN quizzes q ON q.id = a.quiz_id
        JOIN courses c ON c.id = q.course_id
        WHERE a.student_id = ?
        ORDER BY a.id ASC
    """, (session["user_id"],)).fetchall()
    conn.close()

    labels = [a["quiz_title"] for a in attempts]
    scores = [round((a["score"] / a["total"]) * 100, 1) if a["total"] else 0 for a in attempts]

    # topic-wise (course-wise) average accuracy
    topic_totals = {}
    for a in attempts:
        topic_totals.setdefault(a["course_title"], []).append((a["score"] / a["total"]) * 100 if a["total"] else 0)
    topic_labels = list(topic_totals.keys())
    topic_scores = [round(sum(v) / len(v), 1) for v in topic_totals.values()]

    return render_template(
        "analytics_student.html", attempts=attempts,
        labels=labels, scores=scores, topic_labels=topic_labels, topic_scores=topic_scores
    )


@app.route("/analytics/course/<int:course_id>")
def instructor_analytics(course_id):
    if not login_required("instructor"):
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ? AND instructor_id = ?",
                           (course_id, session["user_id"])).fetchone()
    if not course:
        flash("Course not found or not yours.", "error")
        conn.close()
        return redirect(url_for("instructor_dashboard"))

    quizzes = conn.execute("SELECT * FROM quizzes WHERE course_id = ?", (course_id,)).fetchall()

    quiz_labels = []
    class_averages = []
    attempt_counts = []
    for q in quizzes:
        attempts = conn.execute("SELECT * FROM attempts WHERE quiz_id = ?", (q["id"],)).fetchall()
        if attempts:
            avg = sum((a["score"] / a["total"]) * 100 for a in attempts) / len(attempts)
        else:
            avg = 0
        quiz_labels.append(q["title"])
        class_averages.append(round(avg, 1))
        attempt_counts.append(len(attempts))

    conn.close()
    return render_template(
        "analytics_instructor.html", course=course, quiz_labels=quiz_labels,
        class_averages=class_averages, attempt_counts=attempt_counts
    )


# ---------------- NOTIFICATIONS ----------------

@app.route("/notifications")
def notifications():
    if not login_required():
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC", (session["user_id"],)
    ).fetchall()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    return render_template("notifications.html", notifs=notifs)


# ---------------- FILE SERVING ----------------

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
