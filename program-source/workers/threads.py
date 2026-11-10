import os
import time
import requests
import json
from PyQt6.QtCore import QThread, pyqtSignal
from ai_engine import AIEngine

# --- ПОТОК ЗАГРУЗКИ ИИ ---
class InitWorker(QThread):
    finished_signal = pyqtSignal(bool, str)
    def __init__(self, main_window, model_filename):
        super().__init__()
        self.mw = main_window
        self.model_filename = model_filename
        
    def run(self):
        try:
            self.mw.ai_engine = AIEngine(
                model_path=f"models/{self.model_filename}",
                n_threads=self.mw.ai_threads,
                use_gpu=self.mw.ai_use_gpu,
                n_ctx=self.mw.ai_n_ctx,
                db_manager=self.mw.db_mgr
            )
            print(f"Загрузка нейросети {self.model_filename}...")
            if self.mw.ai_engine.load_model():
                print("Нейросеть загружена. Чтение правил...")
                self.mw.ai_engine.load_rules(self.mw.current_server)
                print("Проверка векторов...")
                if self.mw.ai_engine.load_vectors(): print("Векторы загружены.")
                else: print("Векторы не найдены. Создайте их в настройках.")
                self.finished_signal.emit(True, "")
            else:
                self.finished_signal.emit(False, f"Файл модели {self.model_filename} поврежден или не читается.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

# --- ПОТОК ДЛЯ ЧАТА ---
class ChatWorker(QThread):
    finished_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    
    def __init__(self, ai_engine, query, history):
        super().__init__()
        self.ai_engine = ai_engine
        self.query = query
        self.history = history
        self._is_running = True

    def stop(self):
        self._is_running = False
        self.log_signal.emit("🛑 Отправлен сигнал на остановку нейросети...")

    def run(self):
        self.log_signal.emit("⏳ Анализ запроса...")
        try:
            answer = self.ai_engine.generate_answer(
                self.query, 
                self.history, 
                log_func=self.log_signal.emit,
                is_running_func=lambda: self._is_running 
            )
            if self._is_running:
                self.finished_signal.emit(answer)
        except Exception as e:
            if self._is_running:
                self.finished_signal.emit(f"Ошибка ИИ: {e}")

# --- ПОТОК ДЛЯ ВЕКТОРИЗАЦИИ ---
class IndexWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)
    def __init__(self, ai_engine, server_name):
        super().__init__()
        self.ai_engine = ai_engine
        self.server_name = server_name
    def run(self):
        try:
            success = self.ai_engine.build_embeddings(
                progress_callback=lambda p: self.progress_signal.emit(p, f"Векторизация базы: {p}%"),
                server_name=self.server_name
            )
            self.finished_signal.emit(success, "")
        except Exception as e:
            print(f"Ошибка векторизации: {e}")
            self.finished_signal.emit(False, str(e))

# --- ПОТОКИ ЗАГРУЗКИ БАЗЫ ---
class CheckWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, int)
    def __init__(self, db_path, current_server, token):
        super().__init__()
        self.db_path = db_path
        self.current_server = current_server
        self.token = token
        self.manifest_url = "https://raw.githubusercontent.com/B4rsum/gtarp-database/main/manifest.json"
    def run(self):
        self.log_signal.emit("🔍 Сверка версий с GitHub...")
        try:
            headers = {"Authorization": f"token {self.token}"} if self.token else {}
            response = requests.get(self.manifest_url, headers=headers, timeout=15)
            if response.status_code != 200:
                self.log_signal.emit(f"⚠️ Ошибка загрузки манифеста: {response.status_code}")
                self.finished_signal.emit(False, 0)
                return
            manifest = response.json().get('files', [])
            server_has_files = any(item['path'].startswith(self.current_server) for item in manifest)
            if not server_has_files:
                self.finished_signal.emit(True, -1)
                return
            target_folders = ["Правила проекта", self.current_server]
            remote_files = {}
            for item in manifest:
                path = item['path']
                if any(path.startswith(folder) for folder in target_folders):
                    remote_files[os.path.join(self.db_path, path.replace("/", os.sep))] = item['hash']
            local_state = {}
            if os.path.exists("db_state.json"):
                with open("db_state.json", "r", encoding="utf-8") as f:
                    local_state = json.load(f)
            updates_count = sum(1 for path, file_hash in remote_files.items() if not os.path.exists(path) or local_state.get(path) != file_hash)
            self.finished_signal.emit(True, updates_count)
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка сети: {e}")
            self.finished_signal.emit(False, 0)

class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, bool, int)
    def __init__(self, db_path, current_server, token):
        super().__init__()
        self.db_path = db_path
        self.current_server = current_server
        self.token = token
        self.manifest_url = "https://raw.githubusercontent.com/B4rsum/gtarp-database/main/manifest.json"
        self.files_to_download = []
        
    def run(self):
        self.log_signal.emit("🔍 Загрузка списка файлов (manifest.json)...")
        try:
            headers = {"Authorization": f"token {self.token}"} if self.token else {}
            response = requests.get(self.manifest_url, headers=headers, timeout=15)
            if response.status_code != 200:
                self.finished_signal.emit(False, False, 0)
                return
            manifest = response.json().get('files', [])
            server_has_files = any(item['path'].startswith(self.current_server) for item in manifest)
            if not server_has_files:
                self.finished_signal.emit(False, False, -1)
                return
            
            target_folders = ["Правила проекта", self.current_server]
            expected_local_paths = set()
            
            # 1. Формируем список того, что ДОЛЖНО быть на диске
            for item in manifest:
                path = item['path']
                if any(path.startswith(folder) for folder in target_folders):
                    local_path = os.path.normpath(os.path.join(self.db_path, path.replace("/", os.sep)))
                    expected_local_paths.add(local_path)
                    
                    if path.endswith('.html') or path.endswith('.txt'):
                        raw_url = f"https://raw.githubusercontent.com/B4rsum/gtarp-database/main/{requests.utils.quote(path)}"
                        self.files_to_download.append({'path': local_path, 'url': raw_url, 'hash': item['hash']})
                        
        except Exception:
            self.finished_signal.emit(False, False, 0)
            return
            
        if not self.files_to_download:
            self.finished_signal.emit(False, False, 0)
            return

        # 2. ЗАЧИСТКА СИРОТ (Удаляем локальные файлы, которых нет на GitHub)
        self.log_signal.emit("🧹 Проверка устаревших файлов...")
        deleted_count = 0
        for folder in target_folders:
            local_folder = os.path.join(self.db_path, folder)
            if os.path.exists(local_folder):
                for root, _, files in os.walk(local_folder):
                    for file in files:
                        if file.endswith('.html') or file.endswith('.txt'):
                            file_path = os.path.normpath(os.path.join(root, file))
                            if file_path not in expected_local_paths:
                                try:
                                    os.remove(file_path)
                                    deleted_count += 1
                                    self.log_signal.emit(f"🗑️ Удален устаревший файл: {file}")
                                except Exception as e:
                                    self.log_signal.emit(f"⚠️ Не удалось удалить {file}: {e}")
        
        if deleted_count > 0:
            self.log_signal.emit(f"✅ Удалено {deleted_count} устаревших файлов.")

        # 3. СКАЧИВАНИЕ ОБНОВЛЕНИЙ
        local_state = {}
        state_file = "db_state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    local_state = json.load(f)
            except: pass
            
        # Очищаем local_state от удаленных файлов
        local_state = {k: v for k, v in local_state.items() if os.path.normpath(k) in expected_local_paths}

        files_to_update = [info for info in self.files_to_download if not os.path.exists(info['path']) or local_state.get(info['path']) != info['hash']]
        
        if not files_to_update:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(local_state, f, ensure_ascii=False, indent=4)
            self.finished_signal.emit(True, True, 0)
            return
            
        total_files = len(files_to_update)
        start_time = time.time()
        downloaded_bytes = 0
        
        for i, file_info in enumerate(files_to_update):
            try:
                res = requests.get(file_info['url'], timeout=15)
                if res.status_code == 200:
                    os.makedirs(os.path.dirname(file_info['path']), exist_ok=True)
                    with open(file_info['path'], 'wb') as f:
                        f.write(res.content)
                    downloaded_bytes += len(res.content)
                    local_state[file_info['path']] = file_info['hash']
            except Exception: pass
            percent = int(((i + 1) / total_files) * 100)
            elapsed = time.time() - start_time
            speed_text = "0 KB/s"
            if elapsed > 0:
                speed_kb = (downloaded_bytes / 1024) / elapsed
                speed_text = f"{speed_kb/1024:.1f} MB/s" if speed_kb > 1024 else f"{speed_kb:.0f} KB/s"
            self.progress_signal.emit(percent, f"Обновление: {percent}% | {speed_text}")
            
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(local_state, f, ensure_ascii=False, indent=4)
            
        self.finished_signal.emit(True, True, 0)

class ModelDownloadWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.stop_flag = False 

    def run(self):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            response = requests.get(self.url, headers=headers, stream=True, timeout=30)
            
            if response.status_code != 200:
                self.finished_signal.emit(False, f"Ошибка сервера: {response.status_code}")
                return
                
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024 * 1024 
            downloaded = 0
            
            with open(self.save_path, 'wb') as file:
                for data in response.iter_content(block_size):
                    if self.stop_flag:
                        file.close()
                        if os.path.exists(self.save_path):
                            os.remove(self.save_path)
                        self.finished_signal.emit(False, "Остановлено пользователем")
                        return
                        
                    file.write(data)
                    downloaded += len(data)
                    
                    if total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        downloaded_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        self.progress_signal.emit(percent, f"Скачано {percent}% | {downloaded_mb:.1f} из {total_mb:.1f} МБ")
                        
            self.finished_signal.emit(True, "Успешно")
        except Exception as e:
            if os.path.exists(self.save_path):
                os.remove(self.save_path)
            self.finished_signal.emit(False, str(e))