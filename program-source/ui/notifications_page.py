import time
from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt6.QtGui import QFont

class ToastNotification(QWidget):
    """Всплывающая плашка в правом нижнем углу"""
    def __init__(self, parent, message, notif_type="info"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Segoe UI", 10))
        self.label.setStyleSheet(self.get_style(notif_type))
        layout.addWidget(self.label)
        
        self.adjustSize()
        
        # Позиционирование в правом нижнем углу главного окна
        if parent:
            p_rect = parent.geometry()
            x = p_rect.x() + p_rect.width() - self.width() - 20
            y = p_rect.y() + p_rect.height() - self.height() - 20
            self.move(x, y)
            
        self.show()
        
        # Анимация исчезновения через 3.5 секунды
        QTimer.singleShot(3500, self.fade_out)

    def get_style(self, notif_type):
        colors = {
            "success": "#10b981", # Зеленый
            "error": "#ef4444",   # Красный
            "info": "#a855f7"     # Фиолетовый (в стиле твоего приложения)
        }
        bg = colors.get(notif_type, "#a855f7")
        return f"""
            QLabel {{
                background-color: {bg};
                color: white;
                border-radius: 8px;
                padding: 12px 20px;
                font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
        """

    def fade_out(self):
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(500)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.close)
        self.anim.start()


class NotificationsPage(QWidget):
    """Страница с журналом событий"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = deque(maxlen=20) # Хранит только 20 последних событий
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("🔔 Журнал уведомлений")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #a855f7; margin-bottom: 10px;")
        layout.addWidget(title)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #151521;
                border: 2px solid #2b2b3d;
                border-radius: 10px;
                padding: 10px;
                color: white;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #2b2b3d;
            }
            QListWidget::item:selected {
                background-color: #4a2c6d;
                color: white;
            }
        """)
        layout.addWidget(self.list_widget)

    def add_notification(self, message, notif_type="info"):
        timestamp = time.strftime("%H:%M:%S")
        
        # Иконки для разных типов
        icons = {"success": "✅", "error": "❌", "info": "ℹ️"}
        icon = icons.get(notif_type, "ℹ️")
        
        log_text = f"[{timestamp}] {icon} {message}"
        self.history.append(log_text)
        
        # Обновляем список (новые сверху)
        self.list_widget.clear()
        for item_text in reversed(self.history):
            self.list_widget.addItem(QListWidgetItem(item_text))
            
        # Показываем всплывающий Toast
        main_window = self.window()
        if main_window:
            ToastNotification(main_window, message, notif_type)