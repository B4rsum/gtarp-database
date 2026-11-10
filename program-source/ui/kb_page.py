import os
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QSplitter, QTreeWidget, 
                             QTreeWidgetItem, QTextEdit, QLabel)
from PyQt6.QtCore import Qt

class KBPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("📚 База знаний (Просмотр правил)")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #a855f7; margin-bottom: 10px;")
        layout.addWidget(title)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.kb_tree = QTreeWidget()
        self.kb_tree.setHeaderHidden(True)
        self.kb_tree.itemClicked.connect(self.load_kb_file)
        splitter.addWidget(self.kb_tree)
        
        self.kb_viewer = QTextEdit()
        self.kb_viewer.setReadOnly(True)
        splitter.addWidget(self.kb_viewer)
        
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

    def load_kb_tree(self):
        self.kb_tree.clear()
        db_path = "data"
        if not os.path.exists(db_path): return
        self.add_kb_nodes(self.kb_tree, db_path)

    def add_kb_nodes(self, parent_item, path):
        for item_name in os.listdir(path):
            item_path = os.path.join(path, item_name)
            if os.path.isdir(item_path):
                folder_item = QTreeWidgetItem(parent_item)
                folder_item.setText(0, f"📁 {item_name}")
                self.add_kb_nodes(folder_item, item_path)
                folder_item.setExpanded(True)
            elif item_name.endswith('.html') or item_name.endswith('.txt'):
                file_item = QTreeWidgetItem(parent_item)
                file_item.setText(0, f"📄 {item_name.replace('.html', '').replace('.txt', '')}")
                file_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

    def load_kb_file(self, item, column):
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f: 
                    content = f.read()
                
                if "<" in content and ">" in content:
                    soup = BeautifulSoup(content, 'html.parser')
                    for img in soup.find_all('img'):
                        for attr in ['width', 'height', 'style', 'class']:
                            if img.has_attr(attr): del img[attr]
                        parent = img.parent
                        if parent and parent.name in ['a', 'div', 'span']:
                            for attr in ['style', 'class', 'width', 'height']:
                                if parent.has_attr(attr): del parent[attr]
                            parent['style'] = 'display: block; clear: both; text-align: center;'
                        img['style'] = 'display: block; clear: both; margin: 15px auto; max-width: 100%; height: auto; border: 2px solid #4e4e68; border-radius: 8px;'
                    self.kb_viewer.setHtml(str(soup))
                else:
                    self.kb_viewer.setPlainText(content)
            except Exception as e:
                self.kb_viewer.setPlainText(f"Ошибка при чтении файла:\n{e}")