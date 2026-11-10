import json
import os

class SettingsManager:
    def __init__(self, config_path="user_config.json"):
        self.config_path = config_path
        self.defaults = {
            "current_server": "Сервер Blaine",
            "github_token": "",
            "history_limit": 5,
            "ai_threads": 4,
            "ai_use_gpu": False,
            "ai_n_ctx": 2048,
            "current_model_id": "qwen_3b"
        }
        self.config = self.load_settings()

    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Объединяем дефолтные настройки с сохраненными
                    return {**self.defaults, **saved}
            except Exception:
                pass
        return self.defaults.copy()

    def save_settings(self, new_settings: dict):
        self.config.update(new_settings)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_settings(self.config)