"""
🎵 音频播放器 — 基于 QMediaPlayer

功能：播放/暂停/上下曲 | 进度拖拽 | 播放列表双击切换
依赖：PySide6.QtMultimedia（内置）
"""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QListWidget, QListWidgetItem, QFileDialog,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

# 支持格式
AUDIO_EXTS = (".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus")


class AudioPlayerWidget(QWidget):
    """音频播放器主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("audioPlayer")
        self.setMinimumSize(650, 480)

        # 播放器
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.7)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        # 状态
        self._playlist: list[str] = []
        self._current_idx: int = -1
        self._is_seeking: bool = False

        # 进度计时器
        self._pos_timer = QTimer(self)
        self._pos_timer.setInterval(200)
        self._pos_timer.timeout.connect(self._update_position)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # 标题
        title = QLabel("🎵 音频播放器")
        title.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        layout.addWidget(title)

        # ── 当前播放信息 ──
        self._current_label = QLabel("未选择曲目")
        self._current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.DemiBold))
        self._current_label.setStyleSheet("color: #6366f1; border: none; min-height: 60px;")
        layout.addWidget(self._current_label)

        # ── 进度条 ──
        seek_row = QHBoxLayout()
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("font-size: 13px; color: #94a3b8; border: none; min-width: 100px;")
        seek_row.addWidget(self._time_label)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setMinimumHeight(36)
        self._seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 10px; background: #e2e8f0; border-radius: 5px; }
            QSlider::handle:horizontal { width: 22px; height: 22px; margin: -6px 0;
                background: #6366f1; border-radius: 11px; }
            QSlider::sub-page:horizontal { background: #6366f1; border-radius: 5px; }
        """)
        self._seek_slider.sliderPressed.connect(lambda: setattr(self, '_is_seeking', True))
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._seek_slider.sliderMoved.connect(self._on_seek_moved)
        seek_row.addWidget(self._seek_slider, stretch=1)
        layout.addLayout(seek_row)

        # ── 控制按钮 ──
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_style = """
            QPushButton { font-size: 22px; min-width: 64px; min-height: 64px;
                background: rgba(128,128,128,0.06); border: none; border-radius: 14px; }
            QPushButton:hover { background: rgba(99,102,241,0.12); }
        """

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setStyleSheet(btn_style)
        self._prev_btn.setToolTip("上一首")
        self._prev_btn.clicked.connect(self._prev)
        ctrl.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶")
        self._play_btn.setStyleSheet(btn_style)
        self._play_btn.setToolTip("播放/暂停")
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setStyleSheet(btn_style)
        self._stop_btn.setToolTip("停止")
        self._stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self._stop_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setStyleSheet(btn_style)
        self._next_btn.setToolTip("下一首")
        self._next_btn.clicked.connect(self._next)
        ctrl.addWidget(self._next_btn)

        ctrl.addSpacing(30)

        # 音量
        vol_label = QLabel("🔊")
        vol_label.setStyleSheet("font-size: 22px; border: none;")
        ctrl.addWidget(vol_label)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setMinimumHeight(32)
        self._vol_slider.setMaximumWidth(140)
        self._vol_slider.setStyleSheet(self._seek_slider.styleSheet())
        self._vol_slider.valueChanged.connect(lambda v: self._audio_output.setVolume(v / 100.0))
        ctrl.addWidget(self._vol_slider)

        layout.addLayout(ctrl)

        # ── 播放列表 ──
        list_label = QLabel("📋 播放列表 (双击切换)")
        list_label.setStyleSheet("font-size: 14px; font-weight: bold; border: none;")
        layout.addWidget(list_label)

        list_row = QHBoxLayout()
        self._list_widget = QListWidget()
        self._list_widget.itemDoubleClicked.connect(self._on_list_double_click)
        self._list_widget.setMinimumHeight(150)
        self._list_widget.setStyleSheet("""
            QListWidget { font-size: 14px; border: 1px solid #e2e8f0; border-radius: 10px; padding: 6px; }
            QListWidget::item { padding: 8px; border-radius: 6px; }
            QListWidget::item:selected { background: rgba(99,102,241,0.10); color: #6366f1; }
        """)
        list_row.addWidget(self._list_widget, stretch=1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        add_btn = QPushButton("➕ 添加")
        add_btn.setMinimumHeight(48)
        add_btn.setMinimumWidth(90)
        add_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 10px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        add_btn.clicked.connect(self._add_files)
        btn_col.addWidget(add_btn)

        clear_btn = QPushButton("清空")
        clear_btn.setMinimumHeight(44)
        clear_btn.setMinimumWidth(90)
        clear_btn.setStyleSheet("""
            QPushButton { font-size: 13px; background: rgba(128,128,128,0.06); color: #888;
                border: none; border-radius: 10px; }
            QPushButton:hover { background: rgba(128,128,128,0.15); }
        """)
        clear_btn.clicked.connect(self._clear_list)
        btn_col.addWidget(clear_btn)

        remove_btn = QPushButton("移除")
        remove_btn.setMinimumHeight(44)
        remove_btn.setMinimumWidth(90)
        remove_btn.setStyleSheet(clear_btn.styleSheet())
        remove_btn.clicked.connect(self._remove_current)
        btn_col.addWidget(remove_btn)

        list_row.addLayout(btn_col)
        layout.addLayout(list_row)

    def _connect_signals(self) -> None:
        self._player.mediaStatusChanged.connect(self._on_media_status)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频文件", "",
            "音频文件 (*.mp3 *.wav *.flac *.aac *.ogg *.wma *.m4a *.opus);;所有文件 (*.*)"
        )
        for f in files:
            self._playlist.append(f)
            self._list_widget.addItem(Path(f).name)
        if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState and self._playlist:
            self._current_idx = len(self._playlist) - len(files)
            self._play_current()

    def _play_current(self) -> None:
        if not self._playlist or self._current_idx < 0:
            return
        path = self._playlist[self._current_idx]
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        self._pos_timer.start()
        self._play_btn.setText("⏸")
        self._current_label.setText(Path(path).name)
        # 高亮列表
        self._list_widget.setCurrentRow(self._current_idx)

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            if self._player.source().isEmpty() and self._playlist:
                self._current_idx = 0
                self._play_current()
            else:
                self._player.play()
                self._play_btn.setText("⏸")

    def _stop(self) -> None:
        self._player.stop()
        self._pos_timer.stop()
        self._seek_slider.setValue(0)
        self._time_label.setText("00:00 / 00:00")
        self._play_btn.setText("▶")

    def _prev(self) -> None:
        if self._playlist and self._current_idx > 0:
            self._current_idx -= 1
            self._play_current()

    def _next(self) -> None:
        if self._playlist and self._current_idx < len(self._playlist) - 1:
            self._current_idx += 1
            self._play_current()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # 自动播放下一首
            if self._current_idx < len(self._playlist) - 1:
                self._current_idx += 1
                self._play_current()
            else:
                self._stop()

    def _update_position(self) -> None:
        if self._is_seeking:
            return
        duration = self._player.duration()
        position = self._player.position()
        if duration > 0:
            self._seek_slider.setRange(0, duration)
            self._seek_slider.setValue(position)
            self._time_label.setText(
                f"{self._fmt_time(position)} / {self._fmt_time(duration)}"
            )

    def _on_seek_moved(self, pos: int) -> None:
        self._time_label.setText(f"{self._fmt_time(pos)} / {self._fmt_time(self._player.duration())}")

    def _on_seek_released(self) -> None:
        pos = self._seek_slider.value()
        self._player.setPosition(pos)
        self._is_seeking = False

    def _on_list_double_click(self, item: QListWidgetItem) -> None:
        idx = self._list_widget.row(item)
        if 0 <= idx < len(self._playlist):
            self._current_idx = idx
            self._play_current()

    def _clear_list(self) -> None:
        self._player.stop()
        self._pos_timer.stop()
        self._playlist.clear()
        self._list_widget.clear()
        self._current_idx = -1
        self._current_label.setText("未选择曲目")
        self._play_btn.setText("▶")
        self._seek_slider.setValue(0)
        self._time_label.setText("00:00 / 00:00")

    def _remove_current(self) -> None:
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._playlist):
            return
        was_playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and row == self._current_idx
        self._player.stop()
        self._playlist.pop(row)
        self._list_widget.takeItem(row)
        if row < self._current_idx:
            self._current_idx -= 1
        elif self._current_idx >= len(self._playlist):
            self._current_idx = len(self._playlist) - 1
        if was_playing and self._playlist:
            self._play_current()
        elif not self._playlist:
            self._clear_list()

    @staticmethod
    def _fmt_time(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"


class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = AudioPlayerWidget()
        layout.addWidget(self._inner)
