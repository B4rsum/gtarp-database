import os
import re
import json
import math
import numpy as np
import pickle
from bs4 import BeautifulSoup
from llama_cpp import Llama
from fastembed import TextEmbedding, SparseTextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

class AIEngine:
    def __init__(self, model_path="models/qwen2.5-3b-instruct-q4_k_m.gguf", n_threads=4, use_gpu=False, n_ctx=4096, db_manager=None):
        self.model_path = os.path.join(BASE_DIR, model_path)
        self.n_threads = n_threads
        self.use_gpu = use_gpu
        self.n_ctx = n_ctx
        self.db_mgr = db_manager
        
        self.llm = None
        self.dense_model = None
        self.sparse_model = None
        self.reranker = None
        
        self.embed_error = ""
        self.context_chunks = []
        self.dense_embeddings = None
        self.sparse_embeddings = None 
        self.hierarchy = []
        self.faction_keywords = set() 
        
        self.current_server = "Сервер Blaine"
        self.dense_vectors_file = ""
        self.sparse_vectors_file = ""
        self.chunks_file = ""

    def load_model(self):
        if os.path.exists(self.model_path):
            n_gpu_layers = -1 if self.use_gpu else 0
            print(f"Загрузка LLM (Потоки: {self.n_threads}, GPU: {self.use_gpu}, Контекст: {self.n_ctx})...")
            self.llm = Llama(
                model_path=self.model_path, 
                n_ctx=self.n_ctx, 
                n_threads=self.n_threads, 
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )
        else:
            return False
                
        hierarchy_file = os.path.join(BASE_DIR, "hierarchy.json")
        if os.path.exists(hierarchy_file):
            with open(hierarchy_file, "r", encoding="utf-8") as f:
                self.hierarchy = json.load(f).get("hierarchy", [])
                
        self.load_embedders()
        return True

    def load_embedders(self):
        if self.dense_model is None:
            try:
                print("Инициализация моделей поиска...")
                self.dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
                self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25") 
                self.reranker = TextCrossEncoder(model_name="jinaai/jina-reranker-v2-base-multilingual")
                self.embed_error = ""
            except Exception as e:
                self.dense_model = None
                self.sparse_model = None
                self.reranker = None
                self.embed_error = str(e)
                print(f"Ошибка загрузки моделей поиска: {e}")

    def load_vectors(self):
        if os.path.exists(self.dense_vectors_file) and os.path.exists(self.sparse_vectors_file) and os.path.exists(self.chunks_file):
            try:
                self.dense_embeddings = np.load(self.dense_vectors_file)
                with open(self.sparse_vectors_file, "rb") as f:
                    self.sparse_embeddings = pickle.load(f)
                with open(self.chunks_file, "r", encoding="utf-8") as f:
                    self.context_chunks = json.load(f)
                return True
            except Exception as e:
                print(f"Ошибка загрузки векторов: {e}")
        return False

    def save_vectors(self):
        if self.dense_embeddings is not None and self.sparse_embeddings is not None and self.context_chunks:
            os.makedirs(MODELS_DIR, exist_ok=True)
            np.save(self.dense_vectors_file, self.dense_embeddings)
            with open(self.sparse_vectors_file, "wb") as f:
                pickle.dump(self.sparse_embeddings, f)
            with open(self.chunks_file, "w", encoding="utf-8") as f:
                json.dump(self.context_chunks, f, ensure_ascii=False)

    def clear_vectors(self):
        self.dense_embeddings = None
        self.sparse_embeddings = None
        self.context_chunks = []
        for file in [self.dense_vectors_file, self.sparse_vectors_file, self.chunks_file]:
            if file and os.path.exists(file): 
                os.remove(file)

    def get_priority(self, filename):
        filename_lower = filename.lower()
        for level in self.hierarchy:
            for name in level.get("names", []):
                if name.lower() in filename_lower:
                    return level.get("priority", 99)
        return 99

    def load_rules(self, server_name):
        self.current_server = server_name
        self.dense_vectors_file = os.path.join(MODELS_DIR, f"vectors_dense_{server_name}.npy")
        self.sparse_vectors_file = os.path.join(MODELS_DIR, f"vectors_sparse_{server_name}.pkl")
        self.chunks_file = os.path.join(MODELS_DIR, f"chunks_hybrid_{server_name}.json")
        
        self.context_chunks = []
        self.faction_keywords = set()
        
        folders = [
            os.path.join(DATA_DIR, "Правила проекта"),
            os.path.join(DATA_DIR, server_name)
        ]
        
        print(f"\n--- Поиск правил для {server_name} ---")
        for folder in folders:
            if not os.path.exists(folder): 
                continue
            
            print(f"📂 Читаю папку: {folder}")
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.endswith('.html') or file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        filename = os.path.basename(file_path).replace('.html', '').replace('.txt', '')[:30]
                        
                        # ОПРЕДЕЛЯЕМ ТИП ДОКУМЕНТА
                        if "Правила проекта" in root or "Законодательная база" in root or "Кодекс" in file:
                            tag = "[ТИП: ОБЩИЕ]"
                        else:
                            tag = "[ТИП: ФРАКЦИЯ]"
                            # Вытаскиваем название фракции для триггера
                            rel_path = os.path.relpath(root, os.path.join(DATA_DIR, server_name))
                            if rel_path != ".":
                                parts = rel_path.split(os.sep)
                                generic_folders = ["Дополнительные правила сервера", "РП ситуации", "Государственные фракции", "Преступные синдикаты", "Уличные группировки", "Неофициальные организации"]
                                for part in parts:
                                    if part not in generic_folders:
                                        self.faction_keywords.add(part.lower())
                                        break

                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if file.endswith('.html'):
                                soup = BeautifulSoup(content, 'html.parser')
                                text = soup.get_text(separator='\n')
                            else:
                                text = content
                                
                            text = re.sub(r'\n\s*\n', '\n', text)
                            text = re.sub(r'[ \t]+', ' ', text)
                            parts = re.split(r'(?=\n\s*(?:Статья\s+\d+|\d+\.\d+))', text, flags=re.IGNORECASE)
                            
                            for part in parts:
                                part = part.strip()
                                if len(part) > 15:
                                    if len(part) > 800:
                                        for i in range(0, len(part), 600):
                                            self.context_chunks.append(f"{tag} [Файл: {filename}] {part[i:i+800]}")
                                    else:
                                        self.context_chunks.append(f"{tag} [Файл: {filename}] {part}")
        print(f"✅ Загружено кусков: {len(self.context_chunks)}")
        print(f"🎯 Найдено ключевых слов фракций: {len(self.faction_keywords)}")

    def build_embeddings(self, progress_callback=None, server_name="Сервер Blaine"):
        self.load_rules(server_name)
        self.load_embedders()
        
        if not self.dense_model or not self.sparse_model:
            raise Exception(f"Модели не загружены! Ошибка: {self.embed_error}")
        if not self.context_chunks:
            raise Exception("База данных пуста! Проверьте, лежат ли файлы в папке data.")
            
        total = len(self.context_chunks)
        print(f"Начинаю векторизацию {total} кусков для {server_name}...")

        print("-> Создание Dense (смысловых) векторов...")
        dense_generator = self.dense_model.embed(self.context_chunks)
        self.dense_embeddings = []
        for i, emb in enumerate(dense_generator):
            self.dense_embeddings.append(emb)
            if progress_callback and (i % 10 == 0 or i == total - 1):
                progress_callback(int((i / total) * 50)) 
        
        self.dense_embeddings = np.array(self.dense_embeddings, dtype=np.float32)
        norms = np.linalg.norm(self.dense_embeddings, axis=1, keepdims=True)
        self.dense_embeddings = self.dense_embeddings / np.maximum(norms, 1e-8)
        
        print("-> Создание Sparse (лексических) векторов...")
        sparse_generator = self.sparse_model.embed(self.context_chunks)
        self.sparse_embeddings = list(sparse_generator)
        
        if progress_callback:
            progress_callback(100)
            
        self.save_vectors()
        return True

    def sparse_dot_product(self, v1, v2):
        score = 0.0
        i, j = 0, 0
        while i < len(v1.indices) and j < len(v2.indices):
            if v1.indices[i] == v2.indices[j]:
                score += v1.values[i] * v2.values[j]
                i += 1
                j += 1
            elif v1.indices[i] < v2.indices[j]: i += 1
            else: j += 1
        return score

    def apply_all_synonyms(self, query, log_func):
        search_query = query
        synonyms_file = os.path.join(BASE_DIR, "synonyms.json")
        if os.path.exists(synonyms_file):
            try:
                with open(synonyms_file, "r", encoding="utf-8") as f:
                    synonyms = json.load(f)
                for word, expansion in synonyms.items():
                    if re.search(r'\b' + re.escape(word) + r'\b', query.lower()):
                        search_query += f" {expansion}"
            except Exception: pass
            
        if self.db_mgr:
            learned = self.db_mgr.get_learned_synonyms()
            for word, translation in learned.items():
                if re.search(r'\b' + re.escape(word) + r'\b', query.lower()):
                    search_query += f" {translation}"
                    log_func(f"🧠 Из кэша: '{word}' -> '{translation}'")
                    
        return search_query

    def rewrite_query_history(self, query, history, log_func):
        if not history: return query
        if len(query.split()) > 5: return query

        last_user_query = ""
        for msg in reversed(history):
            if msg["role"] == "user":
                last_user_query = msg["content"]
                break
                
        if not last_user_query: return query

        prompt = (
            "<|im_start|>system\n"
            "Ты — ИИ-помощник. Твоя задача — понять, является ли текущий вопрос продолжением предыдущего.\n"
            "Если текущий вопрос содержит местоимения (это, за него, там, а если) или спрашивает уточнение (какая статья, а срок), ты должен объединить его с прошлым вопросом.\n"
            "ЕСЛИ ТЕКУЩИЙ ВОПРОС НА СОВЕРШЕННО ДРУГУЮ ТЕМУ, выведи ТОЛЬКО ТЕКУЩИЙ ВОПРОС без изменений.\n"
            "Выведи ТОЛЬКО итоговый вопрос без кавычек и лишних слов.<|im_end|>\n"
            f"<|im_start|>user\nПредыдущий вопрос: {last_user_query}\nТекущий вопрос: {query}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        
        try:
            res = self.llm(prompt, max_tokens=60, temperature=0.1, stop=["<|im_end|>"], echo=False)
            rewritten = res['choices'][0]['text'].strip()
            rewritten = rewritten.replace("Вопрос:", "").replace("Ответ:", "").strip()
            if len(rewritten) > 3 and rewritten != last_user_query:
                log_func(f"🔄 CQR: Переписано -> '{rewritten}'")
                return rewritten
        except: pass
        return query

    def expand_query_llm(self, query, log_func):
        if re.match(r'^\d+(\.\d+)?$', query.strip()): return query
        
        prompt = "<|im_start|>system\nТы — составитель законов для ролевого сервера GTA5RP. Твоя задача — сформулировать текст закона (Уголовного или Административного кодекса), который отвечает на вопрос игрока.\n"
        prompt += "ВНИМАНИЕ: Игроки спрашивают про наказания по законам штата. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать про внутренние уставы фракций (FIB, LSPD, мафий). \n"
        prompt += "Если игрок пишет 'Я задержал', 'Я сотрудник', 'В меня стреляли', значит игрок — гос. служащий. В этом случае ОБЯЗАТЕЛЬНО добавь в гипотезу статью про 'Посягательство на жизнь сотрудника правоохранительного органа' и 'Незаконный оборот оружия/наркотиков'.\n"
        prompt += "Если игрок пишет 'на меня напали', 'меня ударили', сформулируй статью за 'Умышленное причинение вреда здоровью'.\n"
        prompt += "Используй официальные термины: 'незаконный оборот', 'хранение', 'ношение', 'лишение свободы', 'штраф', 'посягательство'.\n"
        prompt += "Выведи ТОЛЬКО текст статьи, без вступлений и кавычек.<|im_end|>\n"
        prompt += f"<|im_start|>user\nВопрос игрока: {query}<|im_end|>\n<|im_start|>assistant\n"
        
        try:
            res = self.llm(prompt, max_tokens=80, temperature=0.3, stop=["<|im_end|>"], echo=False)
            hyde_text = res['choices'][0]['text'].strip().replace('"', '')
            if len(hyde_text) > 5:
                log_func(f"🧠 LLM Гипотеза: '{query}' -> '{hyde_text}'")
                return hyde_text
        except Exception: pass
        return query

    def _perform_search(self, queries, rerank_query, search_all=True):
        candidates = set()
        for q in queries:
            q_dense_vec = list(self.dense_model.embed([q]))[0]
            q_dense_vec = q_dense_vec / np.maximum(np.linalg.norm(q_dense_vec), 1e-8)
            dense_ranks = np.argsort(np.dot(self.dense_embeddings, q_dense_vec))[::-1][:40]
            
            q_sparse_vec = list(self.sparse_model.embed([q]))[0]
            sparse_scores = [self.sparse_dot_product(q_sparse_vec, doc) for doc in self.sparse_embeddings]
            sparse_ranks = np.argsort(sparse_scores)[::-1][:40]

            k = 60; rrf_scores = {}
            for rank, idx in enumerate(dense_ranks): rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank + 1)
            for rank, idx in enumerate(sparse_ranks): rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank + 1)
            sorted_idx = sorted(rrf_scores.keys(), key=lambda idx: rrf_scores[idx], reverse=True)
            
            candidates.update(sorted_idx[:50]) 
        
        candidate_indices = list(candidates)
        if not search_all:
            candidate_indices = [i for i in candidate_indices if "[ТИП: ОБЩИЕ]" in self.context_chunks[i]]
            
        if not candidate_indices:
            return []

        candidate_chunks = [self.context_chunks[i] for i in candidate_indices]
        
        raw_scores = list(self.reranker.rerank(rerank_query, candidate_chunks))
        rerank_scores = [sigmoid(s) for s in raw_scores] 
        
        reranked_results = sorted(zip(rerank_scores, candidate_chunks), key=lambda x: x[0], reverse=True)
        return reranked_results

    def generate_answer(self, query, history=None, log_func=print, is_running_func=lambda: True):
        if not self.llm:
            return "Ошибка: Нейросеть не загружена."

        if history is None: history = []
        
        query_fixed = query
        
        # УМНОЕ РЕГУЛЯРНОЕ ВЫРАЖЕНИЕ
        article_match = re.search(
            r'(?:статья|ст\.?|пункт|п\.?)\s*(\d+(?:\.\d+)?)'
            r'|\b(\d+\.\d+)\b'
            r'|\b(\d+)\s*(?:ук|дк|ак|гк)\b'
            r'|(?:ук|дк|ак|гк)\s*(\d+)\b',
            query_fixed, re.IGNORECASE
        )
        
        if article_match:
            article_num = next((g for g in article_match.groups() if g is not None), None)
            
            target_codex = ""
            q_lower = query_fixed.lower()
            if "ук" in q_lower or "уголов" in q_lower: target_codex = "уголов"
            elif "дк" in q_lower or "дорож" in q_lower: target_codex = "дорож"
            elif "ак" in q_lower or "админ" in q_lower: target_codex = "админ"
            elif "гк" in q_lower or "граждан" in q_lower: target_codex = "граждан"
            
            for chunk in self.context_chunks:
                chunk_lower = chunk.lower()
                if target_codex and target_codex not in chunk_lower: continue
                
                if re.search(rf"^\[тип: [^\]]+\] \[файл: [^\]]+\]\s*статья\s*{re.escape(article_num)}(?:\s|\.|$|:)", chunk_lower):
                    log_func(f"✅ Статья {article_num} найдена напрямую!")
                    clean_chunk = re.sub(r'\[ТИП: [^\]]+\] ', '', chunk).replace('[Файл: ', '').replace(']', ':')
                    return f"Согласно правилам:\n{clean_chunk}"

        if not self.dense_model or not self.sparse_model or not self.reranker:
            return f"Ошибка: Библиотеки поиска не загрузились."
            
        if self.dense_embeddings is None or not self.context_chunks:
            return "Ошибка: Векторы не созданы. Перейдите в Настройки -> Нейросеть и нажмите 'Создать векторы'."

        log_func("🧠 Этап 1: Гибридный поиск...")
        
        search_queries = [query_fixed]
        
        query_with_synonyms = self.apply_all_synonyms(query_fixed, log_func)
        if query_with_synonyms != query_fixed:
            search_queries.append(query_with_synonyms)
            
        rewritten = self.rewrite_query_history(query_fixed, history, log_func)
        if rewritten != query_fixed and rewritten not in search_queries:
            search_queries.append(rewritten)

        # ОПРЕДЕЛЯЕМ, НУЖЕН ЛИ ПОИСК ПО ФРАКЦИЯМ
        needs_faction = any(kw in query.lower() for kw in self.faction_keywords) or any(w in query.lower() for w in ["устав", "фракция", "сотрудник", "лидер", "банда", "мафия", "lspd", "fib", "lssd", "ems", "армия", "нг", "задержал", "арестовал", "обыскал", "патрулировал"])
        
        # ШАГ 1: Ищем ТОЛЬКО в общих правилах
        reranked_results = self._perform_search(search_queries, query_fixed, search_all=False)
        top_score = reranked_results[0][0] if reranked_results else 0.0
        
        log_func(f"📊 Уверенность (Общие правила): {top_score:.2f}")

        # ШАГ 2: Если не уверены или нужна фракция - ищем везде
        if top_score < 0.6 or needs_faction:
            if needs_faction:
                log_func("🎯 Вопрос касается фракции. Подключаю уставы...")
            else:
                log_func("⚠️ Уверенность низкая. Расширяю поиск на уставы фракций...")
                
            reranked_results = self._perform_search(search_queries, query_fixed, search_all=True)
            top_score = reranked_results[0][0] if reranked_results else 0.0
            log_func(f"📊 Уверенность (Все правила): {top_score:.2f}")

        # ШАГ 3: HyDE (если всё еще плохо)
        if top_score < 0.65:
            log_func("⚠️ Поиск не уверен. Генерирую гипотезу через нейросеть (HyDE)...")
            query_to_expand = rewritten if rewritten != query_fixed else query_fixed
            expanded = self.expand_query_llm(query_to_expand, log_func)
            
            if expanded != query_to_expand:
                new_queries = search_queries + [expanded]
                new_reranked = self._perform_search(new_queries, expanded, search_all=True)
                new_top_score = new_reranked[0][0] if new_reranked else 0.0
                
                log_func(f"📊 Новая уверенность: {new_top_score:.2f}")
                
                if new_top_score > top_score and new_top_score > 0.5:
                    reranked_results = new_reranked
                    top_score = new_top_score
                    
                    if self.db_mgr:
                        log_func("💾 Сохраняю гипотезу в локальный кэш...")
                        self.db_mgr.add_learned_synonym(query_to_expand, expanded, confidence=top_score)
                else:
                    if new_top_score > top_score:
                        reranked_results = new_reranked
                        top_score = new_top_score

        if top_score < 0.35:
            log_func(f"🛑 Уверенность слишком низкая ({top_score:.2f}). Отменяю генерацию.")
            return "В правилах нет точной информации по этому вопросу. Попробуйте переформулировать запрос или уточнить детали."

        top_chunks = [chunk for score, chunk in reranked_results[:4]]
        top_chunks.sort(key=lambda x: self.get_priority(x))
        
        formatted_chunks = []
        for chunk in top_chunks:
            priority = self.get_priority(chunk)
            if priority == 1:
                formatted_chunks.append(f"--- ПРАВИЛА СЕРВЕРА/ФРАКЦИИ (Высший приоритет) ---\n{chunk}")
            elif priority == 2:
                formatted_chunks.append(f"--- ОБЩИЕ ПРАВИЛА ПРОЕКТА (Базовый приоритет) ---\n{chunk}")
            else:
                formatted_chunks.append(f"--- СПРАВОЧНАЯ ИНФОРМАЦИЯ ---\n{chunk}")
                
        context_text = "\n\n".join(formatted_chunks)
        log_func(f"✅ Отобрано {len(top_chunks)} лучших фрагментов.")
        
        if top_chunks:
            log_func(f"🔍 Топ-1 фрагмент: {top_chunks[0][:100]}...")

        log_func("✍️ Генерация ответа...")
        
        has_subpoints = False
        if top_chunks:
            if re.search(r'[а-я]\)', top_chunks[0]) or re.search(r'\d\)', top_chunks[0]):
                has_subpoints = True

        prompt = f"<|im_start|>system\n"
        prompt += f"Ты — опытный юрист сервера {self.current_server} GTA5RP. Твоя задача — проанализировать предоставленные фрагменты текста и СОБРАТЬ из них единый, структурированный ответ на вопрос игрока.\n"
        prompt += "ПРАВИЛА СИНТЕЗА:\n"
        prompt += f"1. Ты ОТВЕЧАЕШЬ ТОЛЬКО по правилам сервера {self.current_server}. Если в тексте есть правила других серверов, ИГНОРИРУЙ их.\n"
        prompt += "2. ИЕРАРХИЯ: 'ПРАВИЛА СЕРВЕРА/ФРАКЦИИ' имеют ВЫСШИЙ приоритет. 'ОБЩИЕ ПРАВИЛА ПРОЕКТА' — базовые. Если они противоречат, опирайся на правило сервера.\n"
        
        # УНИВЕРСАЛЬНЫЙ АНАЛИЗ РОЛЕЙ
        prompt += "3. АНАЛИЗ РОЛЕЙ: Внимательно прочитай вопрос. Определи, КТО нарушитель.\n"
        prompt += "   - Если нарушает сам игрок ('я ударил', 'я ограбил') -> пиши 'Ваши действия нарушают...'\n"
        prompt += "   - Если нарушает кто-то другой (один человек, несколько человек, группа лиц), а игрок жертва, свидетель или коп ('на меня напали', 'я задержал', 'я увидел') -> пиши 'Действия нарушителя(ей) нарушают...' и выдавай наказание для НИХ.\n"
        prompt += "   - НИКОГДА не пиши 'Ваше действие', если игрок выступает свидетелем, жертвой или сотрудником.\n"
        
        prompt += "4. ВАЖНО: Если в тексте есть тег '[ТИП: ФРАКЦИЯ]', это внутренний устав. Используй его ТОЛЬКО если игрок спрашивает про действия фракции. Если игрок спрашивает про общие законы (УК, АК), игнорируй уставы фракций.\n"
        prompt += "5. ОТСЕИВАЙ МУСОР. Если правило просто содержит похожие слова, но описывает другую ситуацию, НЕ ВКЛЮЧАЙ его в ответ.\n"
        prompt += "6. Если в тексте сказано 'не разрешено' или 'нет прямого разрешения' — сделай вывод, что действие ЗАПРЕЩЕНО.\n"
        prompt += "7. Всегда указывай пункт/статью и наказание. Пиши четко, по пунктам.\n"
        prompt += "8. НЕ пиши в ответе '[Файл: ...]' и '[ТИП: ...]'.\n"
        
        if has_subpoints:
            prompt += "9. В найденном тексте есть подпункты. Выдай их все с разными штрафами и попроси уточнить детали.\n"
            
        prompt += "<|im_end|>\n"
        
        safe_history = history[-4:] if len(history) > 4 else history
        for msg in safe_history:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<|im_start|>{role}\n{msg['content']}<|im_end|>\n"
            
        prompt += f"<|im_start|>user\nВопрос игрока: {query_fixed}\n\nТекст правил:\n{context_text}\n\nТвой ответ:<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"

        try:
            stream = self.llm(
                prompt, 
                max_tokens=800, # УВЕЛИЧЕНО ДО 800
                temperature=0.1, 
                repeat_penalty=1.1, 
                stop=["<|im_end|>"], 
                stream=True
            )
            
            answer = ""
            for chunk in stream:
                if not is_running_func():
                    log_func("🛑 Генерация прервана на уровне нейросети.")
                    break
                text_piece = chunk['choices'][0]['text']
                answer += text_piece
                
        except Exception as e:
            return f"Ошибка ИИ: {e}"
        
        answer = answer.strip()
        answer = re.sub(r'^(Вопрос:|Ответ:)', '', answer).strip()
        answer = re.sub(r'\[Файл: [^\]]+\]', '', answer).strip()
        answer = re.sub(r'\[ТИП: [^\]]+\]', '', answer).strip()
        
        if not is_running_func() and not answer:
            return "Генерация прервана."
            
        if "В правилах этого нет" in answer and len(answer) < 30: 
            return "В правилах этого нет."
            
        return answer