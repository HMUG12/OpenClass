"""
🧩 插件中心 — 导入插件 + 网格卡片展示 + 日志查看

布局：
  ┌─────────────────────────────────────────┐
  │  🧩 插件中心          [导入插件] (80px)  │
  │  发现已安装的第三方功能插件               │
  ├─────────────────────────────────────────┤
  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
  │  │ 卡片 │ │ 卡片 │ │ 卡片 │ │ 卡片 │   │
  │  └──────┘ └──────┘ └──────┘ └──────┘   │
  │  ...                                    │
  │                          [查看日志]     │
  └─────────────────────────────────────────┘
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QScrollArea, QFileDialog, QMessageBox,
    QDialog, QTextEdit, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.utils.plugin_manager import PluggableManager, PluginMeta
from app.views.plugin_center.plugin_card import PluginCard


class _LogViewerDialog(QDialog):
    """插件日志查看弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 插件操作日志")
        self.setMinimumSize(750, 520)
        self.resize(850, 600)
        self.setStyleSheet("QDialog { background: #1e1e2e; border-radius: 12px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("插件操作日志 (最近 100 条)")
        title.setFont(QFont("Consolas, Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0; border: none;")
        layout.addWidget(title)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet("""
            QTextEdit {
                font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: 13px; line-height: 1.6;
                background: rgba(0,0,0,0.20); color: #d0d0d0;
                border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;
                padding: 12px;
            }
        """)
        layout.addWidget(self._text, stretch=1)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setMinimumHeight(44)
        refresh_btn.setStyleSheet("""
            QPushButton { font-size: 14px; background: rgba(139,92,246,0.10); color: #8b5cf6;
                border: 1px solid rgba(139,92,246,0.20); border-radius: 8px; padding: 8px 20px; }
            QPushButton:hover { background: rgba(139,92,246,0.18); }
        """)
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(44)
        close_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold; background: #8b5cf6; color: #fff;
                border: none; border-radius: 8px; padding: 8px 24px; }
            QPushButton:hover { background: #7c3aed; }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    def _refresh(self) -> None:
        logs = PluggableManager.get_recent_logs(100)
        self._text.setPlainText(logs)
        # 滚动到底部
        scrollbar = self._text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class PluginCenterView(QWidget):
    """插件中心主界面"""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pluginCenter")
        self._pm = PluggableManager()
        self._pm.plugins_changed.connect(self._on_plugins_changed)
        self._active_widget: QWidget | None = None
        self._cards: dict[str, PluginCard] = {}

        self._build_ui()
        self._refresh_cards()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 20, 36, 20)
        root.setSpacing(16)

        # ── 顶部栏 ──
        top = QHBoxLayout()
        top.setSpacing(16)

        header_block = QVBoxLayout()
        header_block.setSpacing(4)
        title = QLabel("🧩  插件中心")
        title.setFont(QFont("Microsoft YaHei", 26, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        header_block.addWidget(title)

        subtitle = QLabel("发现已安装的第三方功能插件，点击卡片加载")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 15px; border: none;")
        header_block.addWidget(subtitle)
        top.addLayout(header_block, stretch=1)

        # 导入按钮（80px 高，蓝色）
        import_btn = QPushButton("📥  导入插件")
        import_btn.setMinimumHeight(64)
        import_btn.setMinimumWidth(170)
        import_btn.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold;
                background: #3b82f6; color: #ffffff;
                border: none; border-radius: 12px; padding: 12px 28px;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:pressed { background: #1d4ed8; }
        """)
        import_btn.clicked.connect(self._on_import_clicked)
        top.addWidget(import_btn)
        root.addLayout(top)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(128,128,128,0.12); max-height: 1px;")
        root.addWidget(sep)

        # ── 网格卡片区 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        grid_container = QWidget()
        self._grid = QGridLayout(grid_container)
        self._grid.setSpacing(15)
        self._grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(grid_container)
        root.addWidget(scroll, stretch=1)

        # ── 底部栏 ──
        bottom = QHBoxLayout()
        bottom.addStretch()

        self._back_btn = QPushButton("←  返回插件列表")
        self._back_btn.setMinimumHeight(48)
        self._back_btn.setStyleSheet("""
            QPushButton { font-size: 14px; font-weight: bold;
                background: rgba(128,128,128,0.06); color: #6366f1;
                border: 1px solid rgba(128,128,128,0.12); border-radius: 10px; padding: 8px 24px; }
            QPushButton:hover { background: rgba(99,102,241,0.10); }
        """)
        self._back_btn.clicked.connect(self._on_back_clicked)
        self._back_btn.hide()
        bottom.addWidget(self._back_btn)
        bottom.addStretch()

        log_btn = QPushButton("📋  查看插件日志")
        log_btn.setMinimumHeight(48)
        log_btn.setStyleSheet("""
            QPushButton { font-size: 14px;
                background: rgba(128,128,128,0.06); color: #6366f1;
                border: 1px solid rgba(128,128,128,0.12); border-radius: 10px; padding: 8px 24px; }
            QPushButton:hover { background: rgba(99,102,241,0.10); }
        """)
        log_btn.clicked.connect(self._show_logs)
        bottom.addWidget(log_btn)
        root.addLayout(bottom)

    # ── 卡片刷新 ──

    def _refresh_cards(self) -> None:
        """清空网格，重新渲染所有插件卡片"""
        # 清除旧卡片
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()

        plugins = self._pm.plugin_list
        if not plugins:
            empty = QLabel("暂无已安装的插件\n点击上方「导入插件」按钮添加")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #94a3b8; font-size: 18px; padding: 60px; border: none;")
            self._grid.addWidget(empty, 0, 0, 1, 4)
            return

        cols = 4
        for idx, plugin in enumerate(plugins):
            card = PluginCard(
                plugin.id, plugin.icon, plugin.name, plugin.version, plugin.enabled
            )
            card.clicked.connect(self._on_card_clicked)
            card.toggled.connect(self._on_card_toggled)
            self._cards[plugin.id] = card
            row, col = divmod(idx, cols)
            self._grid.addWidget(card, row, col)

    # ── 事件处理 ──

    def _on_import_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择插件文件夹（包含 plugin.json）")
        if not folder:
            return

        # 检查是否已存在同名插件
        import json
        from pathlib import Path
        manifest_path = Path(folder) / "plugin.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin_id = manifest.get("id", "")
        except Exception:
            QMessageBox.critical(self, "导入失败", "无法读取 plugin.json")
            return

        if self._pm.get(plugin_id):
            reply = QMessageBox.question(
                self, "插件已存在",
                f"插件 '{plugin_id}' 已经存在。\n是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        success, msg = self._pm.import_plugin(folder)
        if success:
            QMessageBox.information(self, "导入成功", msg)
        else:
            QMessageBox.critical(self, "导入失败", msg)

    def _on_card_clicked(self, plugin_id: str) -> None:
        widget, error = self._pm.load_plugin_widget(plugin_id)
        if error:
            QMessageBox.critical(self, "加载失败", error)
            return

        # 切换为插件内容视图
        self._active_widget = widget

        # 隐藏网格区域的上层（用 stacked 或替换布局）
        # 简单方案：隐藏 scroll，显示 widget
        scroll = self.layout().itemAt(2)
        if scroll:
            scroll_widget = scroll.widget()
            if scroll_widget:
                scroll_widget.hide()

        # 隐藏导入按钮和副标题
        top_layout = self.layout().itemAt(0)
        if top_layout:
            top_w = top_layout.layout()
            if top_w:
                # 隐藏 subtitle
                header_block = top_w.itemAt(0)
                if header_block:
                    hb = header_block.layout()
                    if hb and hb.count() > 1:
                        sub = hb.itemAt(1)
                        if sub and sub.widget():
                            sub.widget().hide()
                import_btn = top_w.itemAt(1)
                if import_btn and import_btn.widget():
                    import_btn.widget().hide()

        self._back_btn.show()

        # 把 widget 贴到 layout 中
        self.layout().addWidget(widget)

    def _on_back_clicked(self) -> None:
        # 移除动态加载的 widget
        if self._active_widget:
            self.layout().removeWidget(self._active_widget)
            self._active_widget.deleteLater()
            self._active_widget = None

        self._back_btn.hide()

        # 恢复显示
        scroll = self.layout().itemAt(2)
        if scroll:
            scroll_widget = scroll.widget()
            if scroll_widget:
                scroll_widget.show()

        top_layout = self.layout().itemAt(0)
        if top_layout:
            top_w = top_layout.layout()
            if top_w:
                header_block = top_w.itemAt(0)
                if header_block:
                    hb = header_block.layout()
                    if hb and hb.count() > 1:
                        sub = hb.itemAt(1)
                        if sub and sub.widget():
                            sub.widget().show()
                import_btn = top_w.itemAt(1)
                if import_btn and import_btn.widget():
                    import_btn.widget().show()

    def _on_card_toggled(self, plugin_id: str, enabled: bool) -> None:
        meta = self._pm.get(plugin_id)
        if meta:
            meta.enabled = enabled

    def _on_plugins_changed(self) -> None:
        self._refresh_cards()

    def _show_logs(self) -> None:
        dlg = _LogViewerDialog(self)
        dlg.exec()
