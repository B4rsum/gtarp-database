import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path="chat_history.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_tables()

    def init_tables(self):
        # Таблица истории чата
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')
        # Таблица для выученного сленга (кэш)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_synonyms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE,
                translation TEXT,
                confidence REAL
            )
        ''')
        self.conn.commit()

    def get_chat_history(self, limit_pairs=5):
        if limit_pairs == 0: return []
        limit = limit_pairs * 2
        self.cursor.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        rows = self.cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    def save_message(self, role, content):
        self.cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        self.conn.commit()

    def clear_history(self):
        self.cursor.execute("DELETE FROM messages")
        self.conn.commit()

    # --- НОВЫЕ МЕТОДЫ ДЛЯ КЭША СЛЕНГА ---
    def get_learned_synonyms(self):
        """Возвращает словарь выученных синонимов: {слово: перевод}"""
        self.cursor.execute("SELECT word, translation FROM learned_synonyms")
        rows = self.cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    def add_learned_synonym(self, word, translation, confidence=1.0):
        """Сохраняет новый синоним в локальную базу"""
        try:
            clean_word = word.lower().strip()
            self.cursor.execute(
                "INSERT OR REPLACE INTO learned_synonyms (word, translation, confidence) VALUES (?, ?, ?)",
                (clean_word, translation, confidence)
            )
            self.conn.commit()
        except Exception as e:
            print(f"Ошибка сохранения выученного синонима: {e}")

    def clear_learned_synonyms(self):
        """Полностью очищает базу выученных слов"""
        self.cursor.execute("DELETE FROM learned_synonyms")
        self.conn.commit()

    def close(self):
        self.conn.close()