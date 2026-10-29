# E-Learning Platform with Quiz Analytics

Simple stack: Python Flask + SQLite + Chart.js (no complex setup needed).

## How to run

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the app:
   ```
   python app.py
   ```

3. Open in browser:
   ```
   http://127.0.0.1:5000
   ```

The database file (`database.db`) will be created automatically on first run.

## Modules included (as per synopsis)

1. User Registration & Role Management (student / instructor)
2. Course & Content Management (upload videos/PDFs/notes)
3. Quiz Builder (MCQ, True/False, Short Answer)
4. Auto-Evaluation Engine (instant scoring)
5. Analytics Dashboard (Chart.js — score trends, topic-wise accuracy, class averages)
6. Notifications (new content / new quiz alerts, bell icon with unread count)

## How to use

1. Register as **Instructor** → create a course → add content → create a quiz → add questions → click "Finish & Publish Quiz"
2. Register as a second account as **Student** → browse courses → enroll → open course → attempt quiz → see result → check Analytics page
3. Login as Instructor again → go to a course's Analytics to see class performance
