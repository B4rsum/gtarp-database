from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QLineEdit, QPushButton, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QTextCursor, QFont, QTextDocument
from workers.threads import ChatWorker
import re

class ChatPage(QWidget):
    log_signal = pyqtSignal(str)
    notification_signal = pyqtSignal(str, str) 

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.ai_engine = None
        self.history_limit = 5
        self.ai_status = "Ожидание..."
        self.is_generating = False
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True) 
        self.chat_history.setStyleSheet("background-color: #151521; border: 2px solid #2b2b3d; border-radius: 10px; padding: 10px; font-size: 15px; color: #e2e2e2;")
        
        font = QFont("Segoe UI", 11)
        self.chat_history.setFont(font)
        
        self.append_system_message(f"Здравствуйте! Я готов отвечать на вопросы по правилам.\nСтатус ИИ: {self.ai_status}")
        layout.addWidget(self.chat_history)
        
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите ваш вопрос...")
        self.message_input.setStyleSheet("background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 10px; padding: 10px; font-size: 15px; color: white;")
        self.message_input.returnPressed.connect(self.handle_send_or_stop)
        
        self.btn_clear = QPushButton("🗑️")
        self.btn_clear.setFixedWidth(40)
        self.btn_clear.setStyleSheet("""
            QPushButton { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 10px; padding: 10px; font-size: 16px; color: white; } 
            QPushButton:hover { background-color: #ef4444; border: 2px solid #f87171; }
        """)
        self.btn_clear.clicked.connect(self.confirm_clear_history)
        
        self.btn_action = QPushButton("➤")
        self.btn_action.setFixedWidth(60)
        self.btn_action.clicked.connect(self.handle_send_or_stop)
        
        self.set_button_to_send_state()
        
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.btn_clear)
        input_layout.addWidget(self.btn_action)
        layout.addLayout(input_layout)

    def set_button_to_send_state(self):
        self.btn_action.setText("➤")
        self.btn_action.setStyleSheet("""
            QPushButton { background-color: #a855f7; border: none; border-radius: 10px; padding: 10px 20px; font-size: 18px; text-align: center; padding-left: 0px; color: white; font-weight: bold; } 
            QPushButton:hover { background-color: #c084fc; }
        """)

    def set_button_to_stop_state(self):
        self.btn_action.setText("🛑")
        self.btn_action.setStyleSheet("""
            QPushButton { background-color: #ef4444; border: none; border-radius: 10px; padding: 10px 20px; font-size: 18px; text-align: center; padding-left: 0px; color: white; font-weight: bold; } 
            QPushButton:hover { background-color: #f87171; }
        """)

    def append_bubble(self, text, is_user=False):
        """Добавляет сообщение в виде прямоугольного пузыря"""
        if not is_user:
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Segoe UI", 11)) 
            doc.setMarkdown(text)
            html_text = doc.toHtml()
        else:
            html_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        align = "right" if is_user else "left"

        bubble_html = f"""
        <table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 10px; margin-bottom: 10px;">
            <tr>
                <td align="{align}">
                    <table cellspacing="0" cellpadding="12" style="background-color: #2b2b3d; border: 2px solid #4e4e68; max-width: 80%;">
                        <tr>
                            <td style="color: #ffffff; font-size: 15px; font-family: 'Segoe UI';">
                                {html_text}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(bubble_html)
        cursor.insertBlock()
        self.chat_history.setTextCursor(cursor)
        self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())

    def append_system_message(self, text):
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        cursor.insertHtml(f"<div align='center' style='color: #81858c; font-size: 12px; margin: 10px;'>{text}</div>")
        self.chat_history.setTextCursor(cursor)
        self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())

    def set_ai_engine(self, ai_engine, history_limit, status="Модель загружена"):
        self.ai_engine = ai_engine
        self.history_limit = history_limit
        self.ai_status = status
        self.chat_history.clear()
        self.append_system_message(f"Здравствуйте! Я готов отвечать на вопросы по правилам.\nСтатус ИИ: {self.ai_status}")

    def update_status(self, status):
        self.ai_status = status
        self.chat_history.clear()
        self.append_system_message(f"Статус ИИ: {self.ai_status}")

    def handle_send_or_stop(self):
        if self.is_generating:
            self.stop_generation()
        else:
            self.send_message()

    def send_message(self):
        query = self.message_input.text().strip()
        if not query: return
        
        if not self.ai_engine or not self.ai_engine.llm:
            self.append_system_message("<b>Ошибка:</b> Нейросеть не загружена. Скачайте модель в настройках.")
            return

        self.message_input.clear()
        self.db_manager.save_message("user", query)
        
        self.append_bubble(query, is_user=True)
        
        self.is_generating = True
        self.set_button_to_stop_state()
        self.message_input.setEnabled(False)
        
        self.thinking_cursor = self.chat_history.textCursor()
        self.thinking_cursor.movePosition(QTextCursor.MoveOperation.End)
        self.thinking_cursor.insertBlock()
        self.thinking_cursor.insertHtml("<div align='left' style='color: #81858c; margin: 5px;'><i>Бот: 🤖 Думает...</i></div>")
        self.chat_history.setTextCursor(self.thinking_cursor)
        self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())
        
        history = self.db_manager.get_chat_history(self.history_limit)[:-1]
        
        self.chat_worker = ChatWorker(self.ai_engine, query, history)
        self.chat_worker.finished_signal.connect(self.display_answer)
        self.chat_worker.log_signal.connect(self.log_signal.emit)
        self.chat_worker.start()

    def stop_generation(self):
        self.log_signal.emit("🛑 Генерация ответа остановлена пользователем.")
        
        if hasattr(self, 'thinking_cursor'):
            self.thinking_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            self.thinking_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            self.thinking_cursor.removeSelectedText()
            self.thinking_cursor.deletePreviousChar()
            
        self.append_system_message("Генерация ответа остановлена.")
            
        self.is_generating = False
        self.set_button_to_send_state()
        self.message_input.setEnabled(True)
        self.message_input.setFocus()
        self.notification_signal.emit("Генерация ответа остановлена", "info")

    def display_answer(self, answer):
        if not answer: answer = "В правилах этого нет."
        
        if not self.is_generating:
            return

        self.db_manager.save_message("assistant", answer)
        
        if hasattr(self, 'thinking_cursor'):
            self.thinking_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            self.thinking_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            self.thinking_cursor.removeSelectedText()
            self.thinking_cursor.deletePreviousChar()

        if answer.startswith("Ошибка ИИ:") or "out of memory" in answer.lower():
            error_msg = (
                "**Произошла ошибка при генерации ответа.**\n\n"
                "Скорее всего, вашему компьютеру не хватает оперативной памяти для обработки такого запроса.\n\n"
                "**Что можно сделать:**\n"
                "1. Зайдите в Настройки и уменьшите лимит контекста.\n"
                "2. Переформулируйте вопрос (сделайте его короче).\n"
                "3. Попробуйте задать вопрос еще раз."
            )
            self.append_bubble(error_msg, is_user=False)
            self.notification_signal.emit("Ошибка генерации (нехватка памяти)", "error")
        else:
            self.append_bubble(answer, is_user=False)
            self.notification_signal.emit("Ответ успешно сгенерирован", "success")
        
        self.is_generating = False
        self.set_button_to_send_state()
        self.message_input.setEnabled(True)
        self.message_input.setFocus()

    def confirm_clear_history(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Подтверждение очистки')
        msg_box.setText('Вы уверены, что хотите полностью очистить историю чата?\nЭто действие нельзя отменить.')
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        msg_box.setStyleSheet("""
            QMessageBox { background-color: #1e1e2e; }
            QMessageBox QLabel { color: #ffffff; font-size: 14px; }
            QPushButton { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 8px; padding: 8px 16px; font-size: 14px; color: white; font-weight: bold; min-width: 80px; } 
            QPushButton:hover { background-color: #4a2c6d; border: 2px solid #a855f7; }
        """)
        
        btn_yes = msg_box.addButton("Да, очистить", QMessageBox.ButtonRole.YesRole)
        btn_no = msg_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_yes:
            self.clear_history()

    def clear_history(self):
        self.db_manager.clear_history()
        self.chat_history.clear()
        self.append_system_message(f"История очищена. Статус ИИ: {self.ai_status}")
        self.notification_signal.emit("История чата очищена", "info")