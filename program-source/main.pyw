import sys
import os
import json
import shutil
import gc
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QLabel, QTextEdit, QStackedWidget)
from PyQt6.QtCore import Qt

# Наши новые модули
from core.db_manager import DatabaseManager
from core.settings_manager import SettingsManager
from workers.threads import InitWorker, CheckWorker, DownloadWorker, ModelDownloadWorker, IndexWorker
from ui.widgets import SplashScreen, EmittingStream, CustomMessageBox, ServerSelectDialog, ConfirmVectorsDialog, DeleteFilesDialog, ClearDBDialog
from ui.chat_page import ChatPage
from ui.kb_page import KBPage
from ui.settings_page import SettingsPage
from ui.notifications_page import NotificationsPage 
from ai_engine import AIEngine

# --- ЗАГРУЗКА МЕТАДАННЫХ ---
APP_VERSION = "1.0.0"
DEVELOPER = "B4rsum"
SUPPORT_URL = ""
try:
    if os.path.exists("version.json"):
        with open("version.json", "r", encoding="utf-8") as f:
            v_data = json.load(f)
            APP_VERSION = v_data.get("version", APP_VERSION)
            DEVELOPER = v_data.get("developer", DEVELOPER)
            SUPPORT_URL = v_data.get("support_url", SUPPORT_URL)
except Exception: pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GTARPHelper - Помощник по правилам")
        self.resize(1100, 750)
        
        # Инициализация менеджеров
        self.settings_mgr = SettingsManager()
        self.db_mgr = DatabaseManager()
        
        # Загрузка настроек
        self.current_server = self.settings_mgr.get("current_server", "Сервер Blaine")
        self.github_token = self.settings_mgr.get("github_token", "")
        self.history_limit = self.settings_mgr.get("history_limit", 5)
        self.ai_threads = self.settings_mgr.get("ai_threads", 4)
        self.ai_use_gpu = self.settings_mgr.get("ai_use_gpu", False)
        self.ai_n_ctx = self.settings_mgr.get("ai_n_ctx", 4096)
        self.current_model_id = self.settings_mgr.get("current_model_id", "qwen_7b")
        
        self.available_models = self.load_models_config()
        
        self.ai_status = "Загрузка..."
        self.ai_engine = None

        self.setup_ui()
        self.start_loading()

    def load_models_config(self):
        if os.path.exists("models.json"):
            try:
                with open("models.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("models", [])
            except Exception as e:
                print(f"Ошибка чтения models.json: {e}")
        return [{"id": "qwen_7b", "display_name": "Qwen 2.5 7B", "url": "", "filename": "qwen2.5-7b-instruct-q4_k_m.gguf"}]

    def get_current_model_info(self):
        for m in self.available_models:
            if m["id"] == self.current_model_id:
                return m
        return self.available_models[0]

    def setup_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QWidget { color: #ffffff; }
            QPushButton { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 8px; padding: 12px; font-size: 16px; font-weight: bold; text-align: left; padding-left: 20px; }
            QPushButton:hover { background-color: #4a2c6d; border: 2px solid #a855f7; }
            QTextEdit { background-color: #151521; border: 2px solid #2b2b3d; border-radius: 10px; padding: 10px; font-size: 15px; }
            QLineEdit { background-color: #2b2b3d; border: 2px solid #4e4e68; border-radius: 10px; padding: 10px; font-size: 15px; }
            QLineEdit:focus { border: 2px solid #a855f7; }
            QProgressBar { border: 2px solid #2b2b3d; border-radius: 5px; text-align: center; background-color: #151521; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: #a855f7; border-radius: 3px; }
            QTreeWidget { background-color: #151521; border: 2px solid #2b2b3d; border-radius: 10px; padding: 5px; font-size: 14px; }
            QTreeWidget::item { padding: 5px; }
            QTreeWidget::item:selected { background-color: #4a2c6d; color: white; }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        left_widget = QWidget()
        left_widget.setFixedWidth(230)
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)
        
        self.btn_server = QPushButton(f"🟢 {self.current_server.replace('Сервер ', 'Сервер: ')}")
        self.btn_server.setStyleSheet("QPushButton { background-color: #2e3b2e; border: 2px solid #4ade80; border-radius: 8px; padding: 12px; font-size: 16px; font-weight: bold; text-align: left; padding-left: 15px; margin-bottom: 20px; } QPushButton:hover { background-color: #3f5a3f; border: 2px solid #86efac; }")
        self.btn_server.clicked.connect(self.open_server_select)
        left_panel.addWidget(self.btn_server)
        
        self.btn_chat = QPushButton("💬 Чат")
        self.btn_db = QPushButton("📚 База знаний")
        self.btn_settings = QPushButton("⚙️ Настройки")
        self.btn_notifications = QPushButton("🔔 Уведомления")
        
        left_panel.addWidget(self.btn_chat)
        left_panel.addWidget(self.btn_db)
        left_panel.addWidget(self.btn_settings)
        left_panel.addWidget(self.btn_notifications)
        
        self.ai_log_area = QTextEdit()
        self.ai_log_area.setReadOnly(True)
        self.ai_log_area.setMinimumHeight(120)
        self.ai_log_area.setStyleSheet("background-color: #151521; border: 2px solid #2b2b3d; border-radius: 8px; font-size: 12px; padding: 5px; color: #a855f7;")
        self.ai_log_area.setText("> Ожидание...")
        left_panel.addWidget(self.ai_log_area)
        left_panel.addStretch() 
        
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setStyleSheet("font-size: 12px; color: #a0a0a0; margin-left: 5px; margin-bottom: 5px;")
        left_panel.addWidget(self.version_label)
        
        self.stacked_widget = QStackedWidget()
        
        self.page_chat = ChatPage(self.db_mgr)
        self.page_chat.log_signal.connect(self.update_ai_log)
        self.stacked_widget.addWidget(self.page_chat)
        
        self.page_db = KBPage()
        self.stacked_widget.addWidget(self.page_db)
        
        self.page_settings = SettingsPage(
            self.settings_mgr, self.available_models, self.current_server, 
            APP_VERSION, DEVELOPER, SUPPORT_URL
        )
        self.connect_settings_signals()
        self.stacked_widget.addWidget(self.page_settings)
        
        self.page_notifications = NotificationsPage()
        self.stacked_widget.addWidget(self.page_notifications)
        
        self.page_chat.notification_signal.connect(self.page_notifications.add_notification)
        
        main_layout.addWidget(left_widget)  
        main_layout.addWidget(self.stacked_widget, 1)
        
        self.btn_chat.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_db.clicked.connect(self.open_kb_page)
        self.btn_settings.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        self.btn_notifications.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))

    def connect_settings_signals(self):
        self.page_settings.request_check_updates.connect(self.check_updates)
        self.page_settings.request_download_db.connect(self.download_database)
        self.page_settings.request_clear_db.connect(lambda: ClearDBDialog(self).exec())
        self.page_settings.github_token_updated.connect(self.save_token)
        
        self.page_settings.request_apply_ai_settings.connect(self.apply_ai_settings)
        self.page_settings.request_model_change.connect(self.apply_model_change)
        self.page_settings.request_download_model.connect(self.download_model)
        self.page_settings.request_stop_model_download.connect(self.stop_model_download)
        self.page_settings.request_delete_model.connect(self.delete_ai_model)
        self.page_settings.request_start_vectorization.connect(self.start_vectorization)
        self.page_settings.request_clear_vectors.connect(self.clear_vectors)
        self.page_settings.request_clear_slang_cache.connect(self.clear_slang_cache)
        
        self.page_settings.history_limit_updated.connect(self.update_history_limit)
        self.page_settings.request_clear_history.connect(self.clear_chat_history)

    def start_loading(self):
        model_info = self.get_current_model_info()
        model_path = os.path.join("models", model_info["filename"])

        if os.path.exists(model_path) and os.path.getsize(model_path) < 100 * 1024 * 1024:
            print(f"Файл {model_path} поврежден (слишком мал). Удаляю...")
            try:
                os.remove(model_path)
            except:
                pass

        if not os.path.exists(model_path):
            found_alternative = False
            for m in self.available_models:
                alt_path = os.path.join("models", m["filename"])
                if os.path.exists(alt_path) and os.path.getsize(alt_path) > 100 * 1024 * 1024:
                    self.current_model_id = m["id"]
                    self.settings_mgr.set("current_model_id", m["id"])
                    self.page_settings.current_model_id = m["id"]
                    idx = self.page_settings.combo_model.findData(m["id"])
                    if idx >= 0: self.page_settings.combo_model.setCurrentIndex(idx)
                    self.page_settings.update_model_button_text()
                    model_info = m
                    model_path = alt_path
                    found_alternative = True
                    break
            
            if not found_alternative:
                self.ai_status = "Модель не найдена"
                self.page_chat.update_status(f"Модель повреждена или не скачана. Скачайте модель {model_info['display_name']} в настройках.")
                self.show()
                return

        if self.ai_engine and self.ai_engine.llm:
            print("Выгрузка старой модели из памяти...")
            try:
                self.ai_engine.llm.close()
            except Exception:
                pass
            self.ai_engine.llm = None
            gc.collect()

        self.hide()
        self.splash = SplashScreen()
        self.splash.show()
        self.stream = EmittingStream()
        self.stream.text_written.connect(self.splash.append_log)
        sys.stdout = self.stream
        
        self.init_worker = InitWorker(self, model_info["filename"])
        self.init_worker.finished_signal.connect(self.on_loading_finished)
        self.init_worker.start()

    def on_loading_finished(self, success, error_msg):
        sys.stdout = sys.__stdout__
        self.splash.close()
        if success:
            self.ai_status = "Модель загружена"
            self.history_limit = self.settings_mgr.get("history_limit", 5)
            self.page_chat.set_ai_engine(self.ai_engine, self.history_limit, self.ai_status)
        else:
            self.ai_status = f"Ошибка: {error_msg}"
            self.page_chat.update_status(f"Ошибка загрузки ИИ:\n{error_msg}\nПопробуйте уменьшить контекст (ОЗУ) или скачать модель заново.")
            CustomMessageBox(self, "Ошибка загрузки", f"Не удалось загрузить ИИ:\n{error_msg}\n\nСовет: Если у вас мало ОЗУ, уменьшите контекст в настройках.", is_error=True).exec()
        self.show()

    def closeEvent(self, event):
        if hasattr(self, 'init_worker') and self.init_worker.isRunning(): 
            self.init_worker.terminate()
        if self.ai_engine and self.ai_engine.llm:
            try:
                self.ai_engine.llm.close()
            except Exception:
                pass
        self.db_mgr.close()
        event.accept()

    def update_ai_log(self, text):
        self.ai_log_area.append(text)
        scrollbar = self.ai_log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # --- ОБРАБОТЧИКИ СИГНАЛОВ ---
    def save_token(self, text):
        self.github_token = text.strip()
        self.settings_mgr.set("github_token", self.github_token)

    def update_history_limit(self, value):
        self.history_limit = value
        self.settings_mgr.set("history_limit", value)
        if self.ai_engine:
            self.page_chat.history_limit = value

    def clear_chat_history(self):
        self.page_chat.clear_history()
        CustomMessageBox(self, "Успех", "История чата полностью очищена!").exec()

    def clear_slang_cache(self):
        self.db_mgr.clear_learned_synonyms()
        CustomMessageBox(self, "Успех", "Память сленга очищена.").exec()

    def open_kb_page(self):
        self.stacked_widget.setCurrentIndex(1)
        self.page_db.load_kb_tree()

    # --- БАЗА ДАННЫХ ---
    def check_updates(self):
        self.page_settings.btn_check_updates.setEnabled(False)
        self.page_settings.btn_check_updates.setText("⏳ Проверка...")
        self.page_settings.db_log.clear()
        
        self.check_worker = CheckWorker("data", self.current_server, self.github_token)
        self.check_worker.log_signal.connect(self.page_settings.update_db_log)
        self.check_worker.finished_signal.connect(self.check_finished)
        self.check_worker.start()

    def check_finished(self, success, count):
        self.page_settings.btn_check_updates.setEnabled(True)
        self.page_settings.btn_check_updates.setText("🔍 Проверить актуальность")
        if success:
            if count == -1:
                self.page_settings.update_db_log(f"❌ База данных для сервера '{self.current_server}' отсутствует на GitHub.")
                CustomMessageBox(self, "Ошибка", f"База данных для сервера '{self.current_server}' пока не готова.", is_error=True).exec()
            elif count > 0:
                self.page_settings.update_db_log(f"🔔 Доступно обновлений: {count}")
                CustomMessageBox(self, "Есть обновления", f"Доступно новых или измененных файлов: {count}.\nНажмите 'Обновить базу данных'.").exec()
            else:
                self.page_settings.update_db_log("✅ База данных актуальна.")
                CustomMessageBox(self, "Актуально", "Ваша база данных уже содержит самую свежую информацию!").exec()
        else:
            self.page_settings.update_db_log("❌ Ошибка при проверке обновлений.")

    def download_database(self):
        self.page_settings.btn_update_db.setEnabled(False)
        self.page_settings.btn_update_db.setText("⏳ Скачивание...")
        self.page_settings.db_log.clear()
        self.page_settings.db_progress.setValue(0)
        self.page_settings.db_progress.setVisible(True)
        
        self.download_worker = DownloadWorker("data", self.current_server, self.github_token)
        self.download_worker.log_signal.connect(self.page_settings.update_db_log)
        self.download_worker.progress_signal.connect(self.page_settings.set_db_progress)
        self.download_worker.finished_signal.connect(self.download_finished)
        self.download_worker.start()

    def download_finished(self, success, has_updates, error_code=0):
        self.page_settings.btn_update_db.setEnabled(True)
        self.page_settings.btn_update_db.setText("🔄 Обновить базу данных")
        self.page_settings.hide_db_progress()
        
        if error_code == -1:
            CustomMessageBox(self, "Ошибка", f"База данных для сервера '{self.current_server}' пока не готова.", is_error=True).exec()
            return
            
        if success:
            if has_updates:
                self.page_settings.update_db_log("✅ База данных успешно обновлена!")
                self.ai_engine.load_rules(self.current_server)
                self.page_settings.stack.setCurrentIndex(2) 
                
                self.start_vectorization(skip_confirmation=True)
                CustomMessageBox(self, "Успех", f"База данных обновлена! Идет подготовка ИИ.").exec()
            else:
                self.page_settings.update_db_log("✅ База данных актуальна.")
                CustomMessageBox(self, "Актуально", "Ваша база данных уже содержит самую свежую информацию!").exec()
        else:
            self.page_settings.update_db_log("❌ Ошибка: не удалось получить файлы.")
            CustomMessageBox(self, "Ошибка", "Не удалось скачать базу. Проверьте интернет.", is_error=True).exec()

    # --- НЕЙРОСЕТЬ ---
    def apply_model_change(self, new_model_id):
        if new_model_id != self.current_model_id:
            self.current_model_id = new_model_id
            self.settings_mgr.set("current_model_id", new_model_id)
            self.page_settings.current_model_id = new_model_id
            self.page_settings.update_model_button_text()
            self.start_loading()
        else:
            self.start_loading()

    def apply_ai_settings(self, threads, use_gpu, n_ctx):
        self.ai_threads = threads
        self.ai_use_gpu = use_gpu
        self.ai_n_ctx = n_ctx
        
        self.settings_mgr.save_settings({
            "ai_threads": self.ai_threads,
            "ai_use_gpu": self.ai_use_gpu,
            "ai_n_ctx": self.ai_n_ctx
        })
        CustomMessageBox(self, "Обновление", "Настройки сохранены! Перезагрузка нейросети...").exec()
        self.start_loading()

    def start_vectorization(self, skip_confirmation=False):
        if not skip_confirmation and self.ai_engine and os.path.exists(self.ai_engine.dense_vectors_file):
            dialog = ConfirmVectorsDialog(self)
            dialog.exec()
            if dialog.result_action == "close": return

        self.page_settings.btn_build_vectors.setEnabled(False)
        self.page_settings.btn_build_vectors.setText("⏳ Векторизация...")
        self.page_settings.vector_progress.setValue(0)
        self.page_settings.vector_progress.setVisible(True)
        
        self.index_worker = IndexWorker(self.ai_engine, self.current_server)
        self.index_worker.progress_signal.connect(self.page_settings.set_vector_progress)
        self.index_worker.finished_signal.connect(self.index_finished)
        self.index_worker.start()

    def index_finished(self, success, error_msg=""):
        self.page_settings.vector_progress.setVisible(False)
        self.page_settings.btn_build_vectors.setEnabled(True)
        self.page_settings.btn_build_vectors.setText("⚙️ Создать векторы (Поиск по смыслу)")
        if success:
            CustomMessageBox(self, "Успех", "Векторы созданы! Теперь поиск работает по смыслу.").exec()
        else:
            CustomMessageBox(self, "Ошибка", f"Ошибка при создании векторов:\n{error_msg}", is_error=True).exec()

    def clear_vectors(self):
        self.ai_engine.clear_vectors()
        CustomMessageBox(self, "Успех", "Созданные векторы удалены.").exec()

    def delete_ai_model(self):
        if not os.path.exists("models"): return
        files = [f for f in os.listdir("models") if f.endswith(".gguf") and not any(x in f for x in ["e5", "embed", "MiniLM", "giga"])]
        if not files:
            CustomMessageBox(self, "Информация", "ИИ-модели не найдены.").exec()
            return
        
        if self.ai_engine and self.ai_engine.llm:
            print("Выгрузка модели из памяти...")
            try:
                self.ai_engine.llm.close()
            except:
                pass
            self.ai_engine.llm = None
            gc.collect()

        dialog = DeleteFilesDialog(self, "Удаление ИИ-Модели", files)
        if dialog.exec():
            self.ai_engine.clear_vectors()

    def download_model(self):
        current_model = self.get_current_model_info()
        save_path = os.path.join("models", current_model["filename"])
        
        if os.path.exists(save_path):
            if os.path.getsize(save_path) < 100 * 1024 * 1024:
                os.remove(save_path)
                CustomMessageBox(self, "Ошибка файла", "Скачанная модель была повреждена. Начинаю скачивание заново...", is_error=True).exec()
            else:
                CustomMessageBox(self, "Модель найдена", f"Модель уже скачана.").exec()
                return
            
        self.page_settings.btn_download_model.setVisible(False)
        self.page_settings.btn_stop_download.setVisible(True)
        self.page_settings.btn_stop_download.setText("🛑 Остановить скачивание")
        
        self.page_settings.model_progress.setValue(0)
        self.page_settings.model_progress.setVisible(True)
        
        os.makedirs("models", exist_ok=True)
        self.model_worker = ModelDownloadWorker(current_model["url"], save_path)
        self.model_worker.progress_signal.connect(self.page_settings.set_model_progress)
        self.model_worker.finished_signal.connect(self.model_download_finished)
        self.model_worker.start()

    def stop_model_download(self):
        if hasattr(self, 'model_worker') and self.model_worker.isRunning():
            self.model_worker.stop_flag = True
            self.page_settings.btn_stop_download.setEnabled(False)
            self.page_settings.btn_stop_download.setText("Останавливаю...")

    def model_download_finished(self, success, error_message):
        current_model = self.get_current_model_info()
        
        self.page_settings.btn_download_model.setVisible(True)
        self.page_settings.btn_download_model.setEnabled(True)
        self.page_settings.btn_download_model.setText(f"🧠 Скачать {current_model['display_name']}")
        
        self.page_settings.btn_stop_download.setVisible(False)
        self.page_settings.btn_stop_download.setEnabled(True)
        
        self.page_settings.model_progress.setVisible(False)
        
        if success:
            CustomMessageBox(self, "Успех", f"Модель успешно скачана! Нажмите 'Применить модель'.").exec()
        else:
            if error_message == "Остановлено пользователем":
                CustomMessageBox(self, "Отмена", "Скачивание остановлено. Недокачанный файл удален.").exec()
            else:
                CustomMessageBox(self, "Ошибка", f"Не удалось скачать нейросеть:\n{error_message}", is_error=True).exec()

    # --- СМЕНА СЕРВЕРА ---
    def open_server_select(self):
        servers = []
        try:
            headers = {"Authorization": f"token {self.github_token}"} if self.github_token else {}
            res_servers = requests.get("https://raw.githubusercontent.com/B4rsum/gtarp-database/main/servers.json", headers=headers, timeout=10)
            if res_servers.status_code == 200:
                servers_data = res_servers.json()
                servers = [srv["name"] for srv in servers_data if srv["name"] != "Правила проекта"]
            else:
                servers = ["Сервер Blaine", "Сервер Hawick", "Сервер Sandy"]
        except Exception:
            servers = ["Сервер Blaine", "Сервер Hawick", "Сервер Sandy"]

        if not servers:
            CustomMessageBox(self, "Ошибка", "Список серверов пуст.", is_error=True).exec()
            return

        dialog = ServerSelectDialog(servers, self.current_server, self)
        if dialog.exec():
            selected = dialog.selected_server
            
            self.current_server = selected
            self.btn_server.setText(f"🟢 {self.current_server.replace('Сервер ', 'Сервер: ')}")
            self.page_settings.set_current_server(self.current_server)
            self.settings_mgr.set("current_server", selected)
            
            # 1. Загружаем тексты правил для нового сервера (это переопределит пути к файлам)
            self.ai_engine.load_rules(self.current_server)
            
            # 2. Проверяем, есть ли готовые векторы для ЭТОГО сервера
            if os.path.exists(self.ai_engine.dense_vectors_file):
                self.ai_engine.load_vectors()
                self.page_chat.update_status(f"Модель загружена. Активен: {self.current_server}")
            else:
                # Если векторов нет — очищаем память и просим создать
                self.ai_engine.clear_vectors()
                self.page_chat.update_status(f"База для {self.current_server} не проиндексирована. Создайте векторы.")
                CustomMessageBox(self, "Требуется индексация", 
                                 f"Вы переключились на {self.current_server}.\nНажмите 'Создать векторы' в настройках (Нейросеть), чтобы бот мог искать по правилам этого сервера.").exec()
            
            self.stacked_widget.setCurrentIndex(2) 
            self.page_settings.stack.setCurrentIndex(1) 
            self.check_updates()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    sys.exit(app.exec())