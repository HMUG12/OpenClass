"""
📦 解压工具 — 多格式压缩包解压（7z / ZIP / RAR）

功能：多线程解压 + 实时进度条 + 拖拽文件 + 密码支持
依赖：py7zr（.7z）, zipfile（内置）, rarfile（.rar）
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QLineEdit, QFileDialog, QMessageBox,
    QFrame, QTextEdit, QGroupBox,
)

# ── 可选依赖 ──
try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False

try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False


class _ExtractThread(QThread):
    """解压工作线程"""
    progress = Signal(int)
    finished = Signal(bool, str)  # success, message
    file_progress = Signal(str)   # 当前正在解压的文件名

    def __init__(self, archive_path: str, dest_path: str, password: str = ""):
        super().__init__()
        self.archive_path = archive_path
        self.dest_path = dest_path
        self.password = password

    def run(self) -> None:
        try:
            ext = Path(self.archive_path).suffix.lower()
            if ext == ".zip":
                self._extract_zip()
            elif ext == ".7z":
                self._extract_7z()
            elif ext == ".rar":
                self._extract_rar()
            else:
                self.finished.emit(False, f"不支持的格式: {ext}")
                return
            self.finished.emit(True, "解压完成！")
        except Exception as e:
            self.finished.emit(False, f"解压失败: {e}")

    def _extract_zip(self) -> None:
        with zipfile.ZipFile(self.archive_path, "r") as zf:
            if self.password:
                zf.setpassword(self.password.encode("utf-8"))
            total = len(zf.namelist())
            for i, name in enumerate(zf.namelist()):
                self.file_progress.emit(name)
                zf.extract(name, self.dest_path)
                self.progress.emit(int((i + 1) / total * 100))

    def _extract_7z(self) -> None:
        if not HAS_PY7ZR:
            raise ImportError("请安装 py7zr: pip install py7zr")
        with py7zr.SevenZipFile(self.archive_path, "r", password=self.password or None) as sz:
            files = sz.getnames()
            total = len(files) if files else 1
            sz.extractall(self.dest_path)
            self.progress.emit(100)

    def _extract_rar(self) -> None:
        if not HAS_RARFILE:
            raise ImportError("请安装 rarfile: pip install rarfile")
        with rarfile.RarFile(self.archive_path, "r") as rf:
            if self.password:
                rf.setpassword(self.password)
            files = rf.namelist()
            total = len(files)
            for i, name in enumerate(files):
                self.file_progress.emit(name)
                rf.extract(name, self.dest_path)
                self.progress.emit(int((i + 1) / total * 100))


class ArchiveExtractorWidget(QWidget):
    """解压工具主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("archiveExtractor")
        self.setMinimumSize(650, 520)
        self.setAcceptDrops(True)
        self._thread: _ExtractThread | None = None
        self._archive_path: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("📦 压缩包解压工具")
        title.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        layout.addWidget(title)

        # ── 选择文件 ──
        file_group = QGroupBox("压缩包文件")
        file_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #e2e8f0;
                border-radius: 10px; padding: 16px 12px 12px 12px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; }
        """)
        fg = QVBoxLayout(file_group)
        fg.setSpacing(10)

        drop_hint = QLabel("拖拽压缩包到此区域，或点击下方按钮选择")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_hint.setMinimumHeight(80)
        drop_hint.setStyleSheet("""
            border: 2px dashed #cbd5e1; border-radius: 12px;
            font-size: 15px; color: #94a3b8; padding: 24px;
        """)
        fg.addWidget(drop_hint)

        file_row = QHBoxLayout()
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("选择 .7z / .zip / .rar 文件")
        self._file_input.setMinimumHeight(48)
        self._file_input.setReadOnly(True)
        self._file_input.setStyleSheet("""
            QLineEdit { font-size: 15px; padding: 8px 14px;
                border: 1px solid #e2e8f0; border-radius: 10px; }
        """)
        file_row.addWidget(self._file_input, stretch=1)

        browse_btn = QPushButton("📂 浏览")
        browse_btn.setMinimumHeight(48)
        browse_btn.setMinimumWidth(100)
        browse_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 10px; padding: 8px 20px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        fg.addLayout(file_row)
        layout.addWidget(file_group)

        # ── 解压路径 ──
        path_group = QGroupBox("解压到")
        path_group.setStyleSheet(file_group.styleSheet())
        pg = QVBoxLayout(path_group)
        pg.setSpacing(10)

        path_row = QHBoxLayout()
        self._dest_input = QLineEdit()
        self._dest_input.setPlaceholderText("选择目标文件夹（默认同目录）")
        self._dest_input.setMinimumHeight(48)
        self._dest_input.setStyleSheet(self._file_input.styleSheet())
        path_row.addWidget(self._dest_input, stretch=1)

        dest_btn = QPushButton("📁 选择")
        dest_btn.setMinimumHeight(48)
        dest_btn.setMinimumWidth(100)
        dest_btn.setStyleSheet(browse_btn.styleSheet())
        dest_btn.clicked.connect(self._browse_dest)
        path_row.addWidget(dest_btn)
        pg.addLayout(path_row)
        layout.addWidget(path_group)

        # ── 密码 ──
        pwd_row = QHBoxLayout()
        pwd_label = QLabel("🔒 密码:")
        pwd_label.setStyleSheet("font-size: 15px; border: none;")
        pwd_row.addWidget(pwd_label)
        self._pwd_input = QLineEdit()
        self._pwd_input.setPlaceholderText("无密码则留空")
        self._pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_input.setMinimumHeight(44)
        self._pwd_input.setStyleSheet(self._file_input.styleSheet())
        pwd_row.addWidget(self._pwd_input, stretch=1)
        layout.addLayout(pwd_row)

        # ── 操作按钮 + 进度 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._extract_btn = QPushButton("⚡ 开始解压")
        self._extract_btn.setMinimumHeight(60)
        self._extract_btn.setStyleSheet("""
            QPushButton { font-size: 17px; font-weight: bold; background: #22c55e; color: #fff;
                border: none; border-radius: 12px; padding: 12px 36px; }
            QPushButton:hover { background: #16a34a; }
            QPushButton:disabled { background: #94a3b8; }
        """)
        self._extract_btn.clicked.connect(self._start_extract)
        btn_row.addWidget(self._extract_btn, stretch=1)

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(60)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.setStyleSheet("""
            QPushButton { font-size: 16px; background: rgba(128,128,128,0.08); color: #888;
                border: none; border-radius: 12px; padding: 12px 24px; }
            QPushButton:hover { background: rgba(128,128,128,0.18); }
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimumHeight(36)
        self._progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #e2e8f0; border-radius: 10px;
                text-align: center; font-size: 15px; }
            QProgressBar::chunk { background: #22c55e; border-radius: 8px; }
        """)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择压缩包", "",
            "压缩包 (*.7z *.zip *.rar);;所有文件 (*.*)"
        )
        if path:
            self._archive_path = path
            self._file_input.setText(path)
            if not self._dest_input.text():
                from pathlib import Path
                self._dest_input.setText(str(Path(path).parent / Path(path).stem))

    def _browse_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择解压目标文件夹")
        if path:
            self._dest_input.setText(path)

    def _start_extract(self) -> None:
        archive = self._file_input.text().strip()
        if not archive:
            QMessageBox.warning(self, "提示", "请先选择一个压缩包文件")
            return

        dest = self._dest_input.text().strip()
        if not dest:
            dest = str(Path(archive).parent / Path(archive).stem)
            self._dest_input.setText(dest)

        os.makedirs(dest, exist_ok=True)

        password = self._pwd_input.text().strip()

        self._extract_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("正在解压...")

        self._thread = _ExtractThread(archive, dest, password)
        self._thread.progress.connect(self._progress_bar.setValue)
        self._thread.file_progress.connect(lambda n: self._status_label.setText(f"解压中: {n}"))
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, success: bool, message: str) -> None:
        self._extract_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText(message)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "解压失败", message)

    def _cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(1000)
        self._extract_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText("已取消")

    # ── 拖拽支持 ──

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith((".7z", ".zip", ".rar")):
                self._archive_path = path
                self._file_input.setText(path)
                if not self._dest_input.text():
                    self._dest_input.setText(str(Path(path).parent / Path(path).stem))


class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = ArchiveExtractorWidget()
        layout.addWidget(self._inner)
