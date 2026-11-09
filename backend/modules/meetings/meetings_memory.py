import json
import os
import sqlite3
from datetime import datetime


class MeetingsMemory:
    def __init__(self, database_path):
        self.database_path = database_path
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        self.create_tables()


    def create_tables(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS meetings ("
            "meeting_id TEXT PRIMARY KEY, "
            "data TEXT NOT NULL, "
            "updated_at TEXT NOT NULL)"
        )
        connection.commit()
        connection.close()


    def save_meeting(self, meeting_id, meeting):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT OR REPLACE INTO meetings (meeting_id, data, updated_at) VALUES (?, ?, ?)",
            (meeting_id, json.dumps(meeting, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
        connection.close()


    def load_all_meetings(self):
        connection = sqlite3.connect(self.database_path)
        rows = connection.execute("SELECT meeting_id, data FROM meetings ORDER BY updated_at").fetchall()
        connection.close()

        return {meeting_id: json.loads(data) for meeting_id, data in rows}


    def delete_meeting(self, meeting_id):
        connection = sqlite3.connect(self.database_path)
        connection.execute("DELETE FROM meetings WHERE meeting_id = ?", (meeting_id,))
        connection.commit()
        connection.close()