"""
🎬 视频播放器 — VLC 内核嵌入 PySide6

功能：播放/暂停/停止/静音 | 进度条拖拽 | 音量调节 | 全屏 | 播放列表
依赖：python-vlc (需 VLC 已安装)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QFrame, QSplitter,
)

_VLC_ERROR_MSG: str = ""
try:
    import vlc
    _ = vlc.Instance("--no-xlib")  # 验证 VLC 运行时 DLL 可加载
    HAS_VLC = True
except (ImportError, OSError, FileNotFoundError, NameError):
    vlc = None  # type: ignore
    HAS_VLC = False
    _VLC_ERROR_MSG = (
        "VLC 媒体播放器未安装，视频播放功能不可用。\n\n"
        "请前往 https://www.videolan.org/vlc/ 下载并安装 VLC。\n"
        "安装时请勾选「将 VLC 添加到系统 PATH」。\n\n"
        "安装完成后重启 OpenClass 即可使用视频播放器。"
    )


class VLCVideoWidget(QWidget):
    """VLC 视频播放器主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("vlcVideoPlayer")
        self.setMinimumSize(750, 520)
        self._instance = vlc.Instance("--no-xlib") if HAS_VLC else None
        self._player = None
        self._playlist: list[str] = []
        self._current_idx: int = -1
        self._seek_timer = QTimer(self)
        self._seek_timer.setInterval(500)
        self._seek_timer.timeout.connect(self._update_seek)

        self._build_ui()
        self._init_vlc()

    def _init_vlc(self) -> None:
        if not HAS_VLC:
            self._status_label.setText(_VLC_ERROR_MSG)
            self._status_label.setStyleSheet(
                "color: #f59e0b; font-size: 15px; border: none; padding: 20px;"
            )
            return
        try:
            self._player = self._instance.media_player_new()
            if self._player:
                self._player.set_hwnd(int(self._video_frame.winId()))
        except Exception as e:
            self._status_label.setText(f"VLC 初始化失败: {e}")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题行
        title = QLabel("🎬 视频播放器")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        layout.addWidget(title)

        # 主区域：视频 + 播放列表
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 视频区域
        video_panel = QWidget()
        vp = QVBoxLayout(video_panel)
        vp.setContentsMargins(0, 0, 0, 0)

        self._video_frame = QFrame()
        self._video_frame.setStyleSheet("background: #0f0f23; border: 1px solid #1e293b; border-radius: 12px;")
        self._video_frame.setMinimumSize(400, 300)
        self._video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)  # VLC 需要原生窗口句柄
        vp.addWidget(self._video_frame, stretch=1)

        # 进度条行
        seek_row = QHBoxLayout()
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("font-size: 13px; color: #94a3b8; border: none; min-width: 100px;")
        seek_row.addWidget(self._time_label)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setMinimumHeight(32)
        self._seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 8px; background: #e2e8f0; border-radius: 4px; }
            QSlider::handle:horizontal { width: 18px; height: 18px; margin: -5px 0;
                background: #6366f1; border-radius: 9px; }
            QSlider::sub-page:horizontal { background: #6366f1; border-radius: 4px; }
        """)
        self._seek_slider.sliderMoved.connect(self._on_seek)
        seek_row.addWidget(self._seek_slider, stretch=1)
        vp.addLayout(seek_row)

        splitter.addWidget(video_panel)

        # 播放列表
        list_panel = QWidget()
        list_panel.setFixedWidth(240)
        lp = QVBoxLayout(list_panel)
        lp.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel("📋 播放列表")
        list_label.setStyleSheet("font-size: 14px; font-weight: bold; border: none;")
        lp.addWidget(list_label)

        self._list_widget = QListWidget()
        self._list_widget.itemDoubleClicked.connect(self._on_list_double_click)
        self._list_widget.setStyleSheet("""
            QListWidget { font-size: 13px; border: 1px solid #e2e8f0; border-radius: 8px; }
        """)
        lp.addWidget(self._list_widget, stretch=1)

        add_btn = QPushButton("➕ 添加视频")
        add_btn.setMinimumHeight(44)
        add_btn.clicked.connect(self._add_files)
        add_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: #6366f1; color: #fff;
                border: none; border-radius: 8px; }
            QPushButton:hover { background: #4f46e5; }
        """)
        lp.addWidget(add_btn)

        clear_btn = QPushButton("清空列表")
        clear_btn.setMinimumHeight(40)
        clear_btn.clicked.connect(self._list_widget.clear)
        clear_btn.setStyleSheet("""
            QPushButton { font-size: 13px; background: rgba(128,128,128,0.06); color: #888; border: none; border-radius: 8px; }
            QPushButton:hover { background: rgba(128,128,128,0.15); }
        """)
        lp.addWidget(clear_btn)
        splitter.addWidget(list_panel)
        layout.addWidget(splitter, stretch=1)

        # 控制栏
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        btn_style = """
            QPushButton { font-size: 22px; min-width: 56px; min-height: 56px;
                background: rgba(128,128,128,0.06); border: none; border-radius: 12px; }
            QPushButton:hover { background: rgba(99,102,241,0.12); }
        """
        small_style = """
            QPushButton { font-size: 18px; min-width: 48px; min-height: 48px;
                background: rgba(128,128,128,0.06); border: none; border-radius: 10px; }
            QPushButton:hover { background: rgba(99,102,241,0.12); }
        """

        self._play_btn = QPushButton("▶")
        self._play_btn.setStyleSheet(btn_style)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setStyleSheet(small_style)
        self._stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self._stop_btn)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setStyleSheet(small_style)
        self._prev_btn.clicked.connect(self._prev)
        ctrl.addWidget(self._prev_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setStyleSheet(small_style)
        self._next_btn.clicked.connect(self._next)
        ctrl.addWidget(self._next_btn)

        ctrl.addSpacing(20)

        vol_label = QLabel("🔊")
        vol_label.setStyleSheet("font-size: 20px; border: none;")
        ctrl.addWidget(vol_label)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setMinimumHeight(28)
        self._vol_slider.setMaximumWidth(140)
        self._vol_slider.setStyleSheet(self._seek_slider.styleSheet())
        self._vol_slider.valueChanged.connect(self._on_volume)
        ctrl.addWidget(self._vol_slider)

        self._mute_btn = QPushButton("🔇")
        self._mute_btn.setStyleSheet(small_style)
        self._mute_btn.clicked.connect(self._toggle_mute)
        ctrl.addWidget(self._mute_btn)

        ctrl.addStretch()

        self._full_btn = QPushButton("📺 全屏")
        self._full_btn.setMinimumHeight(48)
        self._full_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: rgba(99,102,241,0.10);
                color: #6366f1; border: 1px solid rgba(99,102,241,0.20); border-radius: 10px; padding: 8px 20px; }
            QPushButton:hover { background: rgba(99,102,241,0.18); }
        """)
        self._full_btn.clicked.connect(self._toggle_fullscreen)
        ctrl.addWidget(self._full_btn)
        layout.addLayout(ctrl)

        self._status_label = QLabel("就绪 — 请添加视频文件")
        self._status_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")
        layout.addWidget(self._status_label)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm);;所有文件 (*.*)"
        )
        for f in files:
            self._playlist.append(f)
            self._list_widget.addItem(Path(f).name)
        if not self._is_playing() and self._playlist:
            self._current_idx = 0
            self._play(self._playlist[0])

    def _play(self, path: str) -> None:
        if not self._player:
            return
        media = self._instance.media_new(path)
        self._player.set_media(media)
        # 重新绑定窗口句柄
        self._player.set_hwnd(int(self._video_frame.winId()))
        self._player.play()
        self._seek_timer.start()
        self._play_btn.setText("⏸")
        self._status_label.setText(Path(path).name)

    def _toggle_play(self) -> None:
        if not self._player:
            return
        if self._player.is_playing():
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            self._player.play()
            self._play_btn.setText("⏸")

    def _stop(self) -> None:
        if self._player:
            self._player.stop()
            self._seek_timer.stop()
            self._seek_slider.setValue(0)
            self._time_label.setText("00:00 / 00:00")
            self._play_btn.setText("▶")

    def _prev(self) -> None:
        if self._playlist and self._current_idx > 0:
            self._current_idx -= 1
            self._play(self._playlist[self._current_idx])

    def _next(self) -> None:
        if self._playlist and self._current_idx < len(self._playlist) - 1:
            self._current_idx += 1
            self._play(self._playlist[self._current_idx])

    def _on_volume(self, value: int) -> None:
        if self._player:
            self._player.audio_set_volume(value)

    def _toggle_mute(self) -> None:
        if self._player:
            self._player.audio_toggle_mute()
            self._mute_btn.setText("🔈" if self._player.audio_get_mute() else "🔇")

    def _toggle_fullscreen(self) -> None:
        if self._player:
            self._player.toggle_fullscreen()

    def _on_seek(self, pos: int) -> None:
        if self._player:
            self._player.set_position(pos / 1000.0)

    def _update_seek(self) -> None:
        if not self._player or not self._player.is_playing():
            return
        length = self._player.get_length()
        current = self._player.get_time()
        if length > 0:
            self._seek_slider.setRange(0, 1000)
            self._seek_slider.setValue(int(current / length * 1000))
            self._time_label.setText(
                f"{self._fmt_time(current)} / {self._fmt_time(length)}"
            )

    @staticmethod
    def _fmt_time(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"

    def _is_playing(self) -> bool:
        return self._player and self._player.is_playing()

    def _on_list_double_click(self, item: QListWidgetItem) -> None:
        idx = self._list_widget.row(item)
        if 0 <= idx < len(self._playlist):
            self._current_idx = idx
            self._play(self._playlist[idx])

    def closeEvent(self, event) -> None:
        if self._player:
            self._player.stop()
            self._player.release()
        self._seek_timer.stop()
        super().closeEvent(event)


class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = VLCVideoWidget()
        layout.addWidget(self._inner)
