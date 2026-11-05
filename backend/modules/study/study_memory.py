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