import os
import webbrowser
import multiprocessing
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QLineEdit, QStackedWidget, 
                             QProgressBar, QSpinBox, QComboBox, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.widgets import CustomMessageBox, ConfirmVectorsDialog, ClearDBDialog

# --- КАСТОМНЫЕ ЭЛЕМЕНТЫ (БЕЗ КОЛЕСИКА) ---
class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event): event.ignore()

class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event): event.ignore()

class SettingsPage(QWidget):
    # Сигналы для главного окна
    request_check_updates = pyqtSignal()
    request_download_db = pyqtSignal()
    request_clear_db = pyqtSignal()
    github_token_updated = pyqtSignal(str)
    
    request_apply_ai_settings = pyqtSignal(int, bool, int) # threads, gpu, ctx
    request_model_change = pyqtSignal(str) # model_id
    request_download_model = pyqtSignal()
    request_stop_model_download = pyqtSignal()
    request_delete_model = pyqtSignal()
    request_start_vectorization = pyqtSignal()
    request_clear_vectors = pyqtSignal()
    request_clear_slang_cache = pyqtSignal()
    
    history_limit_updated = pyqtSignal(int)
    request_clear_history = pyqtSignal()

    def __init__(self, settings_mgr, available_models, current_server, version, developer, support_url, parent=None):
        super().__init__(parent)
        self.settings_mgr = settings_mgr
        self.available_models = available_models
        self.version = version
        self.developer = developer
        self.support_url = support_url
        
        self.current_server = current_server
        self.history_limit = self.settings_mgr.get("history_limit", 5)
        self.ai_threads = self.settings_mgr.get("ai_threads", 4)
        self.ai_use_gpu = self.settings_mgr.get("ai_use_gpu", False)
        self.ai_n_ctx = self.settings_mgr.get("ai_n_ctx", 2048)
        self.current_model_id = self.settings_mgr.get("current_model_id", "qwen_3b")
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # 1. Главное меню
        self.menu_page = QWidget()
        menu_layout = QVBoxLayout(self.menu_page)
        menu_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title = QLabel("⚙️ Настройки")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #a855f7; margin-bottom: 20px;")
        menu_layout.addWidget(title)
        
        btn_style = "QPushButton { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 8px; padding: 20px; font-size: 16px; font-weight: bold; text-align: left; padding-left: 20px; margin-bottom: 10px;} QPushButton:hover { background-color: #4a2c6d; border: 2px solid #a855f7; }"
        
        btn_menu_db = QPushButton("📁 База данных (Обновление, очистка)")
        btn_menu_db.setStyleSheet(btn_style)
        btn_menu_db.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        btn_menu_ai = QPushButton("🧠 Нейросеть (Модели, векторы)")
        btn_menu_ai.setStyleSheet(btn_style)
        btn_menu_ai.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        
        btn_menu_chat = QPushButton("💬 Чат (История, память)")
        btn_menu_chat.setStyleSheet(btn_style)
        btn_menu_chat.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        
        btn_menu_about = QPushButton("ℹ️ О программе")
        btn_menu_about.setStyleSheet(btn_style)
        btn_menu_about.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        
        menu_layout.addWidget(btn_menu_db)
        menu_layout.addWidget(btn_menu_ai)
        menu_layout.addWidget(btn_menu_chat)
        menu_layout.addWidget(btn_menu_about)
        self.stack.addWidget(self.menu_page)
        
        # 2. Подстраницы
        self.page_db = QWidget()
        self.setup_db_page()
        self.stack.addWidget(self.page_db)
        
        self.page_ai = QWidget()
        self.setup_ai_page()
        self.stack.addWidget(self.page_ai)
        
        self.page_chat = QWidget()
        self.setup_chat_page()
        self.stack.addWidget(self.page_chat)
        
        self.page_about = QWidget()
        self.setup_about_page()
        self.stack.addWidget(self.page_about)

    def create_back_btn(self, layout):
        btn_back = QPushButton("← Назад")
        btn_back.setStyleSheet("QPushButton { background-color: #4e4e68; color: white; padding: 8px; font-size: 14px; max-width: 100px; margin-bottom: 15px;} QPushButton:hover { background-color: #64748b; }")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        layout.addWidget(btn_back)

    # --- СТРАНИЦА БАЗЫ ДАННЫХ ---
    def setup_db_page(self):
        main_layout = QVBoxLayout(self.page_db)
        self.create_back_btn(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; } QScrollArea > QWidget > QWidget { background-color: transparent; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        
        self.server_label = QLabel(f"Обновление базы для: {self.current_server} (+ Общие правила)")
        self.server_label.setStyleSheet("font-size: 16px; margin-bottom: 10px;")
        layout.addWidget(self.server_label)
        
        btn_layout = QHBoxLayout()
        self.btn_check_updates = QPushButton("🔍 Проверить актуальность")
        self.btn_check_updates.setStyleSheet("QPushButton { background-color: #3b82f6; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #60a5fa; }")
        self.btn_check_updates.clicked.connect(self.request_check_updates.emit)
        
        self.btn_update_db = QPushButton("🔄 Обновить базу данных")
        self.btn_update_db.setStyleSheet("QPushButton { background-color: #22c55e; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #4ade80; }")
        self.btn_update_db.clicked.connect(self.request_download_db.emit)
        
        btn_layout.addWidget(self.btn_check_updates)
        btn_layout.addWidget(self.btn_update_db)
        layout.addLayout(btn_layout)

        self.db_progress = QProgressBar()
        self.db_progress.setVisible(False)
        self.db_progress.setMinimumHeight(25)
        layout.addWidget(self.db_progress)

        self.db_log = QTextEdit()
        self.db_log.setReadOnly(True)
        self.db_log.setText("> Ожидание действий...\n")
        self.db_log.setMaximumHeight(100)
        layout.addWidget(self.db_log)

        layout.addWidget(QLabel("Токен GitHub (опционально):"))
        self.input_token = QLineEdit()
        self.input_token.setPlaceholderText("github_pat_...")
        self.input_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_token.setText(self.settings_mgr.get("github_token", ""))
        self.input_token.textChanged.connect(self.github_token_updated.emit)
        layout.addWidget(self.input_token)

        self.btn_clear_db = QPushButton("🗑 Очистить базу данных")
        self.btn_clear_db.setStyleSheet("QPushButton { background-color: #ef4444; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #f87171; }")
        self.btn_clear_db.clicked.connect(lambda: self.request_clear_db.emit())
        layout.addWidget(self.btn_clear_db)
        layout.addStretch()
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # --- СТРАНИЦА НЕЙРОСЕТИ ---
    def setup_ai_page(self):
        main_layout = QVBoxLayout(self.page_ai)
        self.create_back_btn(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; } QScrollArea > QWidget > QWidget { background-color: transparent; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        
        layout.addWidget(QLabel("Выбор активной модели:"))
        self.combo_model = NoWheelComboBox()
        for m in self.available_models:
            self.combo_model.addItem(m["display_name"], m["id"])
        idx = self.combo_model.findData(self.current_model_id)
        if idx >= 0: self.combo_model.setCurrentIndex(idx)
        self.combo_model.setStyleSheet("background-color: #2b2b3d; border: 2px solid #4e4e68; padding: 5px; border-radius: 5px; color: white;")
        # ПОДКЛЮЧАЕМ СИГНАЛ ИЗМЕНЕНИЯ МОДЕЛИ
        self.combo_model.currentIndexChanged.connect(self.on_model_combo_changed) 
        layout.addWidget(self.combo_model)
        
        btn_save_model = QPushButton("💾 Применить модель и перезагрузить ИИ")
        btn_save_model.setStyleSheet("QPushButton { background-color: #a855f7; color: white; text-align: center; padding: 10px; margin-top: 5px; margin-bottom: 15px; font-weight: bold;} QPushButton:hover { background-color: #c084fc; }")
        btn_save_model.clicked.connect(lambda: self.request_model_change.emit(self.combo_model.currentData()))
        layout.addWidget(btn_save_model)

        layout.addWidget(QLabel("Параметры работы ИИ (для слабых ПК)"))
        layout.addWidget(QLabel("Количество ядер процессора (CPU Threads):"))
        self.spin_threads = NoWheelSpinBox()
        self.spin_threads.setRange(1, multiprocessing.cpu_count())
        self.spin_threads.setValue(self.ai_threads)
        self.spin_threads.setStyleSheet("background-color: #2b2b3d; border: 2px solid #4e4e68; padding: 5px; border-radius: 5px; color: white;")
        layout.addWidget(self.spin_threads)
        
        self.btn_toggle_gpu = QPushButton()
        self.btn_toggle_gpu.setCheckable(True)
        self.btn_toggle_gpu.setChecked(self.ai_use_gpu)
        self.btn_toggle_gpu.setStyleSheet("""
            QPushButton { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 8px; padding: 10px; font-size: 14px; font-weight: bold; color: #a0a0a0; text-align: left; padding-left: 15px; }
            QPushButton:checked { background-color: #2b2b3d; border: 2px solid #a855f7; color: white; }
        """)
        self.btn_toggle_gpu.toggled.connect(self.update_gpu_btn_text)
        self.update_gpu_btn_text(self.ai_use_gpu)
        layout.addWidget(self.btn_toggle_gpu)
        
        layout.addWidget(QLabel("Размер контекста (потребление ОЗУ):"))
        self.combo_ctx = NoWheelComboBox()
        self.combo_ctx.addItems(["1024 (Минимум ОЗУ)", "2048 (Стандарт)", "4096 (Максимум)"])
        self.combo_ctx.setCurrentIndex(1 if self.ai_n_ctx == 2048 else (0 if self.ai_n_ctx == 1024 else 2))
        self.combo_ctx.setStyleSheet("background-color: #2b2b3d; border: 2px solid #4e4e68; padding: 5px; border-radius: 5px; color: white;")
        layout.addWidget(self.combo_ctx)
        
        btn_save_ai_settings = QPushButton("💾 Сохранить настройки ресурсов")
        btn_save_ai_settings.setStyleSheet("QPushButton { background-color: #3b82f6; color: white; text-align: center; padding: 10px; margin-top: 10px; font-weight: bold;} QPushButton:hover { background-color: #60a5fa; }")
        btn_save_ai_settings.clicked.connect(self.emit_ai_settings)
        layout.addWidget(btn_save_ai_settings)
        
        layout.addSpacing(20)
        layout.addWidget(QLabel("Управление файлами моделей"))
        
        self.btn_download_model = QPushButton(f"🧠 Скачать {self.get_current_model_info()['display_name']}")
        self.btn_download_model.setStyleSheet("QPushButton { background-color: #3b82f6; color: white; text-align: center; padding: 15px; font-size: 16px;} QPushButton:hover { background-color: #60a5fa; }")
        self.btn_download_model.clicked.connect(self.request_download_model.emit)
        layout.addWidget(self.btn_download_model)
        
        self.btn_stop_download = QPushButton("🛑 Остановить скачивание")
        self.btn_stop_download.setStyleSheet("QPushButton { background-color: #ef4444; color: white; text-align: center; padding: 15px; font-size: 16px;} QPushButton:hover { background-color: #f87171; }")
        self.btn_stop_download.clicked.connect(self.request_stop_model_download.emit)
        self.btn_stop_download.setVisible(False)
        layout.addWidget(self.btn_stop_download)
        
        self.model_progress = QProgressBar()
        self.model_progress.setVisible(False)
        self.model_progress.setMinimumHeight(25)
        layout.addWidget(self.model_progress)
        
        self.btn_delete_model = QPushButton("🗑 Удалить ИИ-Модели")
        self.btn_delete_model.setStyleSheet("QPushButton { background-color: #ef4444; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #f87171; }")
        self.btn_delete_model.clicked.connect(self.request_delete_model.emit)
        layout.addWidget(self.btn_delete_model)
        
        layout.addSpacing(20)
        layout.addWidget(QLabel("Управление базой знаний (Векторы)"))
        self.btn_build_vectors = QPushButton("⚙️ Создать векторы (Поиск по смыслу)")
        self.btn_build_vectors.setStyleSheet("QPushButton { background-color: #eab308; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #fde047; }")
        self.btn_build_vectors.clicked.connect(self.request_start_vectorization.emit)
        layout.addWidget(self.btn_build_vectors)
        
        self.vector_progress = QProgressBar()
        self.vector_progress.setVisible(False)
        self.vector_progress.setMinimumHeight(25)
        layout.addWidget(self.vector_progress)
        
        self.btn_clear_vectors = QPushButton("🗑 Стереть созданные векторы")
        self.btn_clear_vectors.setStyleSheet("QPushButton { background-color: #ef4444; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #f87171; }")
        self.btn_clear_vectors.clicked.connect(self.request_clear_vectors.emit)
        layout.addWidget(self.btn_clear_vectors)

        self.btn_clear_slang = QPushButton("🧹 Очистить память сленга (сброс обучения)")
        self.btn_clear_slang.setStyleSheet("QPushButton { background-color: #f97316; color: white; text-align: center; padding: 12px; font-size: 14px; margin-top: 10px;} QPushButton:hover { background-color: #fb923c; }")
        self.btn_clear_slang.clicked.connect(self.request_clear_slang_cache.emit)
        layout.addWidget(self.btn_clear_slang)

        layout.addStretch()
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # НОВЫЙ МЕТОД ДЛЯ ОБНОВЛЕНИЯ КНОПКИ ПРИ ВЫБОРЕ В СПИСКЕ
    def on_model_combo_changed(self):
        selected_id = self.combo_model.currentData()
        for m in self.available_models:
            if m["id"] == selected_id:
                self.btn_download_model.setText(f"🧠 Скачать {m['display_name']}")
                return

    def update_gpu_btn_text(self, checked):
        self.btn_toggle_gpu.setText("☑ Использовать видеокарту (GPU)" if checked else "☐ Использовать видеокарту (GPU)")

    def emit_ai_settings(self):
        idx = self.combo_ctx.currentIndex()
        ctx = 1024 if idx == 0 else (2048 if idx == 1 else 4096)
        self.request_apply_ai_settings.emit(self.spin_threads.value(), self.btn_toggle_gpu.isChecked(), ctx)

    def get_current_model_info(self):
        for m in self.available_models:
            if m["id"] == self.current_model_id:
                return m
        return self.available_models[0]

    def update_model_button_text(self):
        self.btn_download_model.setText(f"🧠 Скачать {self.get_current_model_info()['display_name']}")

    # --- СТРАНИЦА ЧАТА ---
    def setup_chat_page(self):
        main_layout = QVBoxLayout(self.page_chat)
        self.create_back_btn(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; } QScrollArea > QWidget > QWidget { background-color: transparent; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("Настройки памяти чата"))
        layout.addWidget(QLabel("Глубина памяти (количество последних вопросов):"))
        
        self.spin_history = NoWheelSpinBox()
        self.spin_history.setRange(0, 20) 
        self.spin_history.setValue(self.history_limit)
        self.spin_history.setStyleSheet("background-color: #2b2b3d; border: 2px solid #4e4e68; padding: 5px; border-radius: 5px; color: white;")
        self.spin_history.valueChanged.connect(self.history_limit_updated.emit)
        layout.addWidget(self.spin_history)
        
        layout.addSpacing(20)
        btn_clear_chat = QPushButton("🗑 Очистить историю чата")
        btn_clear_chat.setStyleSheet("QPushButton { background-color: #ef4444; color: white; text-align: center; padding: 12px; font-size: 14px;} QPushButton:hover { background-color: #f87171; }")
        btn_clear_chat.clicked.connect(self.request_clear_history.emit)
        layout.addWidget(btn_clear_chat)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # --- СТРАНИЦА О ПРОГРАММЕ ---
    def setup_about_page(self):
        main_layout = QVBoxLayout(self.page_about)
        self.create_back_btn(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; } QScrollArea > QWidget > QWidget { background-color: transparent; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addStretch()
        
        title = QLabel("GTARPHelper")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #a855f7; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        version = QLabel(f"Версия: {self.version}")
        version.setStyleSheet("font-size: 16px; color: #cbd5e1;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        
        dev = QLabel(f"Разработчик: {self.developer}")
        dev.setStyleSheet("font-size: 16px; color: #cbd5e1; margin-bottom: 30px;")
        dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dev)
        
        support_btn = QPushButton("💖 Поддержать автора")
        support_btn.setMinimumWidth(250)
        if self.support_url:
            support_btn.setEnabled(True)
            support_btn.setStyleSheet("QPushButton { background-color: #22c55e; color: white; border-radius: 5px; padding: 15px; font-weight: bold; font-size: 16px;} QPushButton:hover { background-color: #4ade80; }")
            support_btn.clicked.connect(lambda: webbrowser.open(self.support_url))
        else:
            support_btn.setEnabled(False)
            support_btn.setText("💖 Поддержать автора (скоро)")
            support_btn.setStyleSheet("QPushButton { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 5px; padding: 15px; color: #a0a0a0; font-weight: bold; font-size: 16px;}")
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(support_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ MAIN.PYW ---
    def set_current_server(self, name):
        self.current_server = name
        self.server_label.setText(f"Обновление базы для: {self.current_server} (+ Общие правила)")

    def update_db_log(self, text):
        self.db_log.append(text)

    def set_db_progress(self, percent, text):
        self.db_progress.setVisible(True)
        self.db_progress.setValue(percent)
        self.db_progress.setFormat(text)

    def hide_db_progress(self):
        self.db_progress.setVisible(False)

    def set_vector_progress(self, percent, text):
        self.vector_progress.setValue(percent)
        self.vector_progress.setFormat(text)

    def set_model_progress(self, percent, text):
        self.model_progress.setValue(percent)
        self.model_progress.setFormat(text)