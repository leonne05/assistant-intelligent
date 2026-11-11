import json
import os
import sqlite3
from datetime import datetime


class StudyMemory:
    def __init__(self, database_path):
        self.database_path = database_path
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        self.create_tables()


    def create_tables(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS courses ("
            "course_id TEXT PRIMARY KEY, "
            "data TEXT NOT NULL, "
            "updated_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "role TEXT NOT NULL, "
            "content TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS quizzes ("
            "quiz_id TEXT PRIMARY KEY, "
            "course_id TEXT NOT NULL, "
            "data TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS attempts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "quiz_id TEXT NOT NULL, "
            "course_id TEXT NOT NULL, "
            "topic TEXT NOT NULL, "
            "correct INTEGER NOT NULL, "
            "answered_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS subjects ("
            "name TEXT PRIMARY KEY, "
            "created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS plans ("
            "plan_id TEXT PRIMARY KEY, "
            "subject TEXT NOT NULL, "
            "data TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        connection.commit()
        connection.close()


    def save_course(self, course_id, course):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT OR REPLACE INTO courses (course_id, data, updated_at) VALUES (?, ?, ?)",
            (course_id, json.dumps(course, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
        connection.close()


    def load_all_courses(self):
        connection = sqlite3.connect(self.database_path)
        rows = connection.execute("SELECT course_id, data FROM courses").fetchall()
        connection.close()

        return {course_id: json.loads(data) for course_id, data in rows}


    def delete_course(self, course_id):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
        connection.commit()
        connection.close()


    def add_message(self, role, content):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
        connection.close()


    def get_recent_messages(self, limit):
        connection = sqlite3.connect(self.database_path)
        rows = connection.execute(
            "SELECT role, content, created_at FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        connection.close()

        return [{"role": role, "content": content, "created_at": created_at} for role, content, created_at in reversed(rows)]


    def clear_messages(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM messages")
        connection.commit()
        connection.close()


    def save_quiz(self, quiz_id, course_id, quiz):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT OR REPLACE INTO quizzes (quiz_id, course_id, data, created_at) VALUES (?, ?, ?, ?)",
            (quiz_id, course_id, json.dumps(quiz, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
        connection.close()


    def load_quiz(self, quiz_id):
        connection = sqlite3.connect(self.database_path)
        row = connection.execute("SELECT data FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
        connection.close()

        if row is None:
            return None

        return json.loads(row[0])


    def delete_quizzes(self, course_id):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM quizzes WHERE course_id = ?", (course_id,))
        connection.commit()
        connection.close()


    def save_attempts(self, quiz_id, course_id, results):
        answered_at = datetime.now().isoformat(timespec="seconds")
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO attempts (quiz_id, course_id, topic, correct, answered_at) VALUES (?, ?, ?, ?, ?)",
            [(quiz_id, course_id, topic, 1 if correct else 0, answered_at) for topic, correct in results],
        )
        connection.commit()
        connection.close()


    def get_attempts(self, course_id=None):
        connection = sqlite3.connect(self.database_path)

        if not course_id:
            rows = connection.execute(
                "SELECT course_id, topic, correct, answered_at FROM attempts ORDER BY id"
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT course_id, topic, correct, answered_at FROM attempts WHERE course_id = ? ORDER BY id",
                (course_id,),
            ).fetchall()

        connection.close()

        return rows


    def delete_attempts(self, course_id):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM attempts WHERE course_id = ?", (course_id,))
        connection.commit()
        connection.close()


    def clear_attempts(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM attempts")
        connection.commit()
        connection.close()


    def add_subject(self, name):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT OR IGNORE INTO subjects (name, created_at) VALUES (?, ?)",
            (name, datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
        connection.close()


    def list_subjects(self):
        connection = sqlite3.connect(self.database_path)
        rows = connection.execute("SELECT name FROM subjects ORDER BY name COLLATE NOCASE").fetchall()
        connection.close()

        return [name for (name,) in rows]


    def delete_subject(self, name):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM subjects WHERE name = ?", (name,))
        connection.commit()
        connection.close()


    def save_plan(self, plan_id, subject, plan):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT OR REPLACE INTO plans (plan_id, subject, data, created_at) VALUES (?, ?, ?, ?)",
            (plan_id, subject, json.dumps(plan, ensure_ascii=False), plan["created_at"]),
        )
        connection.commit()
        connection.close()


    def load_plan(self, plan_id):
        connection = sqlite3.connect(self.database_path)
        row = connection.execute("SELECT data FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
        connection.close()

        if row is None:
            return None

        return json.loads(row[0])


    def list_plans(self, subject=None):
        connection = sqlite3.connect(self.database_path)

        if subject:
            rows = connection.execute(
                "SELECT data FROM plans WHERE subject = ? ORDER BY created_at DESC",
                (subject,),
            ).fetchall()
        else:
            rows = connection.execute("SELECT data FROM plans ORDER BY created_at DESC").fetchall()

        connection.close()

        return [json.loads(data) for (data,) in rows]


    def delete_plan(self, plan_id):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))
        connection.commit()
        deleted = cursor.rowcount > 0
        connection.close()

        return deleted


    def delete_plans(self, subject):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM plans WHERE subject = ?", (subject,))
        connection.commit()
        connection.close()


    def list_quizzes(self):
        connection = sqlite3.connect(self.database_path)
        rows = connection.execute(
            "SELECT quiz_id, course_id, data, created_at FROM quizzes ORDER BY created_at DESC"
        ).fetchall()
        connection.close()

        return [
            {"quiz_id": quiz_id, "course_id": course_id, "created_at": created_at, "quiz": json.loads(data)}
            for quiz_id, course_id, data, created_at in rows
        ]


    def delete_quiz(self, quiz_id):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.execute("DELETE FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        connection.commit()
        deleted = cursor.rowcount > 0
        connection.close()

        return deleted