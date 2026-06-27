"""
🔄 音频格式转换器 — 基于 pydub + FFmpeg

功能：选择源文件 → 选择输出格式 → 调参数 → 批量转换 + 进度
依赖：pydub（需系统安装 FFmpeg）
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QComboBox, QSpinBox, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QGroupBox,
)

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

# 支持的输出格式
OUTPUT_FORMATS = {
    "MP3": "mp3",
    "WAV": "wav",
    "FLAC": "flac",
    "AAC": "aac",
    "OGG": "ogg",
}

BITRATE_OPTIONS = {
    "mp3": ["64k", "128k", "192k", "256k", "320k"],
    "aac": ["64k", "128k", "192k", "256k"],
    "ogg": ["64k", "128k", "192k", "256k"],
}


class _ConvertThread(QThread):
    """转换工作线程"""
    progress = Signal(int)         # 百分比 0-100
    file_progress = Signal(str)    # 当前文件名
    finished = Signal(bool, str)   # success, message

    def __init__(self, files: list[str], output_dir: str, fmt: str,
                 bitrate: str = "", sample_rate: int = 44100):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.fmt = fmt
        self.bitrate = bitrate
        self.sample_rate = sample_rate

    def run(self) -> None:
        total = len(self.files)
        for i, path in enumerate(self.files):
            name = Path(path).stem
            self.file_progress.emit(f"转换中: {name}")
            try:
                audio = AudioSegment.from_file(path)
                if self.sample_rate and self.sample_rate != audio.frame_rate:
                    audio = audio.set_frame_rate(self.sample_rate)

                out_path = os.path.join(self.output_dir, f"{name}.{self.fmt}")
                kwargs = {}
                if self.bitrate and self.fmt in ("mp3", "aac", "ogg"):
                    kwargs["bitrate"] = self.bitrate
                audio.export(out_path, format=self.fmt, **kwargs)
            except Exception as e:
                self.finished.emit(False, f"转换 [{name}] 失败: {e}")
                return
            self.progress.emit(int((i + 1) / total * 100))
        self.finished.emit(True, f"完成！共转换 {total} 个文件")


class AudioConverterWidget(QWidget):
    """音频格式转换器主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("audioConverter")
        self.setMinimumSize(650, 520)
        self._files: list[str] = []
        self._thread: _ConvertThread | None = None

        self._build_ui()

        if not HAS_PYDUB:
            self._status_label.setText("请安装 pydub: pip install pydub\n并确保系统已安装 FFmpeg")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        title = QLabel("🔄 音频格式转换器")
        title.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        layout.addWidget(title)

        # ── 源文件列表 ──
        src_group = QGroupBox("源音频文件")
        src_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #e2e8f0;
                border-radius: 10px; padding: 16px 12px 12px 12px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; }
        """)
        sg = QVBoxLayout(src_group)
        sg.setSpacing(8)

        self._file_list = QListWidget()
        self._file_list.setMinimumHeight(140)
        self._file_list.setStyleSheet("""
            QListWidget { font-size: 13px; border: 1px solid #f1f5f9; border-radius: 8px; }
        """)
        sg.addWidget(self._file_list)

        add_btn = QPushButton("➕ 添加音频文件")
        add_btn.setMinimumHeight(44)
        add_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 10px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        add_btn.clicked.connect(self._add_files)
        sg.addWidget(add_btn)
        layout.addWidget(src_group)

        # ── 输出设置 ──
        out_group = QGroupBox("输出设置")
        out_group.setStyleSheet(src_group.styleSheet())
        og = QVBoxLayout(out_group)
        og.setSpacing(12)

        # 格式选择
        fmt_row = QHBoxLayout()
        fmt_label = QLabel("输出格式:")
        fmt_label.setStyleSheet("font-size: 15px; border: none;")
        fmt_row.addWidget(fmt_label)
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(OUTPUT_FORMATS.keys())
        self._fmt_combo.setCurrentText("MP3")
        self._fmt_combo.setMinimumHeight(44)
        self._fmt_combo.setStyleSheet("QComboBox { font-size: 15px; padding: 6px 12px; border-radius: 8px; }")
        self._fmt_combo.currentTextChanged.connect(self._on_fmt_changed)
        fmt_row.addWidget(self._fmt_combo, stretch=1)

        bit_label = QLabel("比特率:")
        bit_label.setStyleSheet("font-size: 15px; border: none;")
        fmt_row.addWidget(bit_label)
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItems(BITRATE_OPTIONS.get("mp3", []))
        self._bitrate_combo.setCurrentText("192k")
        self._bitrate_combo.setMinimumHeight(44)
        self._bitrate_combo.setStyleSheet(self._fmt_combo.styleSheet())
        fmt_row.addWidget(self._bitrate_combo)
        og.addLayout(fmt_row)

        sr_row = QHBoxLayout()
        sr_label = QLabel("采样率 (Hz):")
        sr_label.setStyleSheet("font-size: 15px; border: none;")
        sr_row.addWidget(sr_label)
        self._sr_spin = QSpinBox()
        self._sr_spin.setRange(8000, 192000)
        self._sr_spin.setValue(44100)
        self._sr_spin.setSingleStep(1000)
        self._sr_spin.setMinimumHeight(44)
        self._sr_spin.setStyleSheet("QSpinBox { font-size: 15px; padding: 6px 12px; border-radius: 8px; min-width: 120px; }")
        sr_row.addWidget(self._sr_spin)
        sr_row.addStretch()
        og.addLayout(sr_row)
        layout.addWidget(out_group)

        # ── 输出目录 ──
        dir_row = QHBoxLayout()
        self._dir_label = QLabel("输出到: (默认源文件目录)")
        self._dir_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")
        dir_row.addWidget(self._dir_label, stretch=1)

        dir_btn = QPushButton("📁 选择目录")
        dir_btn.setMinimumHeight(44)
        dir_btn.setStyleSheet("""
            QPushButton { font-size: 14px; background: rgba(128,128,128,0.06); color: #6366f1;
                border: 1px solid rgba(128,128,128,0.12); border-radius: 10px; padding: 8px 18px; }
            QPushButton:hover { background: rgba(99,102,241,0.10); }
        """)
        dir_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(dir_btn)
        layout.addLayout(dir_row)
        self._output_dir: str = ""

        # ── 转换按钮 + 进度 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._convert_btn = QPushButton("⚡ 开始转换")
        self._convert_btn.setMinimumHeight(60)
        self._convert_btn.setStyleSheet("""
            QPushButton { font-size: 17px; font-weight: bold; background: #22c55e; color: #fff;
                border: none; border-radius: 12px; padding: 12px 36px; }
            QPushButton:hover { background: #16a34a; }
            QPushButton:disabled { background: #94a3b8; }
        """)
        self._convert_btn.clicked.connect(self._start_convert)
        btn_row.addWidget(self._convert_btn, stretch=1)

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

    def _on_fmt_changed(self, fmt_name: str) -> None:
        fmt = OUTPUT_FORMATS.get(fmt_name, "mp3")
        options = BITRATE_OPTIONS.get(fmt, [])
        self._bitrate_combo.clear()
        if options:
            self._bitrate_combo.addItems(options)
            self._bitrate_combo.setCurrentText(options[min(2, len(options) - 1)])
        else:
            self._bitrate_combo.addItem("N/A")

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频文件", "",
            "音频文件 (*.mp3 *.wav *.flac *.aac *.ogg *.wma *.m4a *.opus);;所有文件 (*.*)"
        )
        for f in files:
            self._files.append(f)
            self._file_list.addItem(f"{Path(f).name}  ({Path(f).parent})")

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self._output_dir = path
            self._dir_label.setText(f"输出到: {path}")

    def _start_convert(self) -> None:
        if not HAS_PYDUB:
            QMessageBox.critical(self, "缺少依赖", "请安装 pydub:\npip install pydub\n\n并确保系统已安装 FFmpeg")
            return
        if not self._files:
            QMessageBox.warning(self, "提示", "请先添加音频文件")
            return

        fmt = OUTPUT_FORMATS.get(self._fmt_combo.currentText(), "mp3")
        out_dir = self._output_dir or str(Path(self._files[0]).parent)
        os.makedirs(out_dir, exist_ok=True)

        bitrate = self._bitrate_combo.currentText()
        if bitrate == "N/A":
            bitrate = ""
        sr = self._sr_spin.value()

        self._convert_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("正在转换...")

        self._thread = _ConvertThread(
            self._files, out_dir, fmt, bitrate, sr
        )
        self._thread.progress.connect(self._progress_bar.setValue)
        self._thread.file_progress.connect(self._status_label.setText)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, success: bool, message: str) -> None:
        self._convert_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText(message)
        if success:
            QMessageBox.information(self, "完成", message)
            # 清空列表以便下一批
            self._files.clear()
            self._file_list.clear()
        else:
            QMessageBox.critical(self, "转换失败", message)

    def _cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait(1000)
        self._convert_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText("已取消")


class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = AudioConverterWidget()
        layout.addWidget(self._inner)
