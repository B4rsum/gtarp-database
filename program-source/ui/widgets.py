import os
import shutil
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QCheckBox, QScrollArea, 
                             QWidget, QListWidget, QListWidgetItem, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

# --- ПЕРЕХВАТЧИК ВЫВОДА В КОНСОЛЬ ---
class EmittingStream(QObject):
    text_written = pyqtSignal(str)
    def write(self, text): self.text_written.emit(str(text))
    def flush(self): pass

# --- КРАСИВОЕ ОКНО ЗАГРУЗКИ ---
class SplashScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(500, 300)
        self.setStyleSheet("QDialog { background-color: #1e1e2e; border: 2px solid #a855f7; border-radius: 10px; } QLabel { color: #a855f7; font-size: 22px; font-weight: bold; } QTextEdit { background-color: #151521; border: none; color: #86efac; font-family: Consolas, monospace; font-size: 12px; }")
        layout = QVBoxLayout(self)
        title = QLabel("GTARPHelper")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.width() // 2, screen.center().y() - self.height() // 2)
    
    def append_log(self, text):
        self.log_area.moveCursor(self.log_area.textCursor().MoveOperation.End)
        self.log_area.insertPlainText(text)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

# --- КРАСИВОЕ ВСПЛЫВАЮЩЕЕ ОКНО ---
class CustomMessageBox(QDialog):
    def __init__(self, parent, title, text, is_error=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(350, 180)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("QDialog { background-color: #1e1e2e; border: 2px solid #4e4e68; border-radius: 8px; } QLabel { color: white; font-size: 14px; } QPushButton { background-color: #a855f7; color: white; border-radius: 5px; padding: 6px 20px; font-weight: bold; min-width: 80px; } QPushButton:hover { background-color: #c084fc; }")
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        color = "#ef4444" if is_error else "#a855f7"
        title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
        layout.addWidget(title_label)
        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        layout.addStretch()
        btn_ok = QPushButton("ОК")
        btn_ok.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

# --- ДИАЛОГ ПРЕДУПРЕЖДЕНИЯ О ВЕКТОРАХ ---
class ConfirmVectorsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Векторы уже созданы")
        self.setFixedSize(420, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("QDialog { background-color: #1e1e2e; border: 2px solid #4e4e68; border-radius: 8px; } QLabel { color: white; font-size: 14px; } QPushButton { border-radius: 5px; padding: 8px 15px; font-weight: bold; font-size: 14px; }")
        self.result_action = "close"
        layout = QVBoxLayout(self)
        title_label = QLabel("Векторы уже созданы")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #eab308;")
        layout.addWidget(title_label)
        msg_label = QLabel("Векторы для текущей базы знаний уже созданы и актуальны.\nВы уверены, что хотите пересоздать их? Это может занять время.")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_close = QPushButton("Закрыть")
        btn_close.setStyleSheet("QPushButton { background-color: #4e4e68; color: white; } QPushButton:hover { background-color: #64748b; }")
        btn_close.clicked.connect(self.accept)
        btn_recreate = QPushButton("Все равно пересоздать")
        btn_recreate.setStyleSheet("QPushButton { background-color: #eab308; color: white; } QPushButton:hover { background-color: #fde047; }")
        btn_recreate.clicked.connect(self.force_recreate)
        btn_layout.addWidget(btn_close)
        btn_layout.addWidget(btn_recreate)
        layout.addLayout(btn_layout)
    def force_recreate(self):
        self.result_action = "recreate"
        self.accept()

# --- ДИАЛОГ УДАЛЕНИЯ ФАЙЛОВ ---
class DeleteFilesDialog(QDialog):
    def __init__(self, parent, title, files):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(400, 300)
        self.setStyleSheet("QDialog { background-color: #1e1e2e; color: white; } QCheckBox { font-size: 14px; padding: 5px; background-color: transparent; color: white; } QPushButton { background-color: #ef4444; color: white; border-radius: 5px; padding: 10px; font-weight: bold; font-size: 14px;} QPushButton:hover { background-color: #f87171; } QScrollArea { border: 2px solid #2b2b3d; border-radius: 5px; background-color: #151521; } QScrollArea > QWidget > QWidget { background-color: transparent; }")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите файлы для удаления:"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        self.check_layout = QVBoxLayout(container)
        self.checkboxes = []
        for file_name in files:
            cb = QCheckBox(file_name)
            cb.setChecked(True)
            cb.setStyleSheet("color: white; font-size: 14px;")
            self.checkboxes.append(cb)
            self.check_layout.addWidget(cb)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.btn_delete = QPushButton("🗑 Удалить выбранное")
        self.btn_delete.clicked.connect(self.delete_selected)
        layout.addWidget(self.btn_delete)
    def delete_selected(self):
        deleted = []
        errors = []
        for cb in self.checkboxes:
            if cb.isChecked():
                file_path = os.path.join("models", cb.text())
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted.append(cb.text())
                    else:
                        errors.append(f"{cb.text()}: Файл не найден")
                except Exception as e:
                    errors.append(f"{cb.text()}: {e}")
        msg = f"Удалено файлов: {len(deleted)}"
        if errors: msg += "\n\nОшибки:\n" + "\n".join(errors)
        CustomMessageBox(self, "Результат", msg, is_error=(len(errors) > 0)).exec()
        self.accept()

# --- ОКНО ВЫБОРА СЕРВЕРА ---
class ServerSelectDialog(QDialog):
    def __init__(self, servers, current_server, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор сервера")
        self.resize(400, 550)
        self.selected_server = current_server
        self.setStyleSheet("QDialog { background-color: #1e1e2e; color: white; } QListWidget { background-color: transparent; border: none; font-size: 16px; outline: none; } QListWidget::item { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 8px; margin-bottom: 8px; padding: 12px; color: white; } QListWidget::item:hover { background-color: #3b3b4d; border: 2px solid #a855f7; } QListWidget::item:selected { background-color: #4a2c6d; border: 2px solid #a855f7; color: white; } QPushButton { background-color: #a855f7; color: white; border-radius: 5px; padding: 10px; font-weight: bold; font-size: 16px; margin-top: 10px; } QPushButton:hover { background-color: #c084fc; }")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите сервер, на котором вы играете:"))
        self.list_widget = QListWidget()
        for srv in servers:
            display_name = srv.replace("Сервер ", "")
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, srv)
            self.list_widget.addItem(item)
            if srv == current_server: self.list_widget.setCurrentItem(item)
        layout.addWidget(self.list_widget)
        self.btn_select = QPushButton("Выбрать сервер")
        self.btn_select.clicked.connect(self.confirm_selection)
        layout.addWidget(self.btn_select)
    def confirm_selection(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_server = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

# --- ОКНО ОЧИСТКИ БАЗЫ ---
class ClearDBDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Очистка базы данных")
        self.resize(400, 300)
        self.setStyleSheet("QDialog { background-color: #1e1e2e; color: white; } QCheckBox { font-size: 14px; padding: 5px; } QPushButton { background-color: #ef4444; color: white; border-radius: 5px; padding: 10px; font-weight: bold; font-size: 14px;} QPushButton:hover { background-color: #f87171; } QScrollArea { border: none; background-color: transparent; } QWidget { background-color: transparent; }")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите папки для удаления:"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.check_layout = QVBoxLayout(container)
        self.checkboxes = []
        db_path = "data"
        if os.path.exists(db_path):
            for item in os.listdir(db_path):
                if os.path.isdir(os.path.join(db_path, item)):
                    cb = QCheckBox(item)
                    self.checkboxes.append(cb)
                    self.check_layout.addWidget(cb)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.btn_delete = QPushButton("🗑 Удалить выбранное")
        self.btn_delete.clicked.connect(self.delete_selected)
        layout.addWidget(self.btn_delete)
    def delete_selected(self):
        db_path = "data"
        deleted_count = 0
        for cb in self.checkboxes:
            if cb.isChecked():
                try:
                    shutil.rmtree(os.path.join(db_path, cb.text()))
                    deleted_count += 1
                except Exception: pass
        if os.path.exists("db_state.json"): os.remove("db_state.json")
        CustomMessageBox(self, "Успех", f"Удалено папок: {deleted_count}").exec()
        self.accept()