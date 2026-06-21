"""
⚙️ 设置页面 — 优先 qfluentwidgets SettingCardGroup，降级纯 PySide6
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QSlider, QFormLayout,
    QGroupBox, QScrollArea, QMessageBox, QTextEdit, QListWidget,
    QListWidgetItem, QMenu,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices

from app.database.db_manager import db
from app.database.crypto import encrypt, decrypt
from app.views.settings.log_page import LogManagePage
from app.utils.signal_bus import signal_bus

# 尝试导入 qfluentwidgets
try:
    from qfluentwidgets import (
        SettingCardGroup, LineEditSettingCard, ComboBoxSettingCard,
        PushSettingCard, HyperlinkCard, PrimaryPushSettingCard,
        SwitchSettingCard, FluentIcon, setTheme, Theme, setThemeColor,
        InfoBar, InfoBarPosition, SmoothScrollArea, BodyLabel
    )
    from qfluentwidgets.common.config import QConfig, ConfigItem, OptionsConfigItem, qconfig
    _HAS_FLUENT = True
except ImportError:
    _HAS_FLUENT = False
    # 降级：QConfig 用纯 Python 实现
    import json, os
    from pathlib import Path
    from app.utils.resource import resource_path

    class _FakeConfigItem:
        def __init__(self, group, key, default, *args, **kwargs):
            self.group = group
            self.key = key
            self._default = default

    class OptionsConfigItem(_FakeConfigItem):
        def __init__(self, group, key, default, options=None):
            super().__init__(group, key, default)
            self.options = options or []

    ConfigItem = OptionsConfigItem

    class FakeQConfig:
        _file = Path(resource_path("data/app_config.json"))

        def __init__(self):
            self._data = {}
            if self._file.exists():
                try:
                    with open(self._file, "r") as f:
                        self._data = json.load(f)
                except Exception:
                    self._data = {}

        def get(self, item):
            section = self._data.get(item.group, {})
            return section.get(item.key, item._default)

        def set(self, item, value):
            self._data.setdefault(item.group, {})[item.key] = value
            self._file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self._file, "w") as f:
                    json.dump(self._data, f, indent=2)
            except Exception:
                pass

    qconfig = FakeQConfig()

    class FakeIcon:
        PASSWORD = "🔑"
        LINK = "🔗"
        DEVELOPER_TOOLS = "🛠"
        ACCEPT = "✅"
        SAVE = "💾"
        BRUSH = "🎨"
        ZOOM = "🔍"
        MENU = "📐"
        GITHUB = "🐙"
        CERTIFICATE = "📜"

    FluentIcon = FakeIcon()


class OpenClassConfig:
    """App 配置持久化"""
    themeMode = OptionsConfigItem("Appearance", "ThemeMode", "light", options=["light", "dark", "green"])
    navCollapsed = ConfigItem("Navigation", "Collapsed", False)
    navIconSize = OptionsConfigItem("Navigation", "IconSize", "medium", options=["small", "medium", "large"])

cfg = OpenClassConfig()


# ═══════════════════════════════════════════════════════════════
# API 密钥配置
# ═══════════════════════════════════════════════════════════════

class APIKeysView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("apiKeysView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        title = QLabel("🔑  API 密钥设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("配置 AI 供应商的 API 密钥，支持 OpenAI 兼容格式。密钥使用 AES-GCM 加密存储。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 16px;")
        layout.addWidget(desc)
        layout.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(16)

        providers = [
            ("OpenAI",   "sk-...", "https://api.openai.com/v1",        "gpt-4"),
            ("Anthropic","sk-ant-...", "https://api.anthropic.com/v1", "claude-3-opus-20240229"),
            ("DeepSeek", "", "https://api.deepseek.com/v1",            "deepseek-chat"),
            ("Ollama",   "", "http://localhost:11434/v1",              "llama3"),
        ]

        self._entries: list[dict] = []

        for prov, placeholder, url, model in providers:
            group = QGroupBox(prov)
            group.setStyleSheet("""
                QGroupBox {
                    font-size: 16px; font-weight: bold;
                    border: 1px solid #e2e8f0; border-radius: 10px;
                    margin-top: 8px; padding: 20px 16px 12px 16px;
                }
                QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            """)
            form = QFormLayout(group)
            form.setSpacing(8)

            saved = db.fetch_one(
                "SELECT api_key_encrypted, base_url, default_model, is_active "
                "FROM api_configs WHERE provider_name=?", (prov,)
            )
            saved_key = ""
            saved_url = url
            saved_model = model
            is_active = prov == "OpenAI"
            if saved:
                try:
                    saved_key = decrypt(saved["api_key_encrypted"]) if saved["api_key_encrypted"] else ""
                except Exception:
                    saved_key = ""
                saved_url = saved["base_url"] or url
                saved_model = saved["default_model"] or model
                is_active = bool(saved["is_active"])

            key_input = QLineEdit()
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            key_input.setPlaceholderText(placeholder)
            if saved_key:
                key_input.setText(saved_key)
            form.addRow("API Key:", key_input)

            url_input = QLineEdit()
            url_input.setText(saved_url)
            form.addRow("Base URL:", url_input)

            model_input = QLineEdit()
            model_input.setText(saved_model)
            form.addRow("默认模型:", model_input)

            active_check = QCheckBox("启用此供应商")
            active_check.setChecked(is_active)
            form.addRow("状态:", active_check)

            scroll_layout.addWidget(group)
            self._entries.append({
                "provider": prov,
                "key_input": key_input,
                "url_input": url_input,
                "model_input": model_input,
                "active_check": active_check,
            })

        # 保存按钮
        save_btn = QPushButton("💾 保存所有密钥")
        save_btn.setMinimumHeight(44)
        save_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold;
                background: #6366f1; color: white;
                border: none; border-radius: 10px; padding: 10px 24px;
            }
            QPushButton:hover { background: #4f46e5; }
        """)
        save_btn.clicked.connect(self._save_all)
        scroll_layout.addWidget(save_btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def _save_all(self) -> None:
        for entry in self._entries:
            prov = entry["provider"]
            key = entry["key_input"].text().strip()
            url = entry["url_input"].text().strip()
            model = entry["model_input"].text().strip()
            active = 1 if entry["active_check"].isChecked() else 0
            enc_key = encrypt(key) if key else ""

            existing = db.fetch_one("SELECT id FROM api_configs WHERE provider_name=?", (prov,))
            if existing:
                db.execute(
                    "UPDATE api_configs SET api_key_encrypted=?, base_url=?, "
                    "default_model=?, is_active=? WHERE provider_name=?",
                    (enc_key, url, model, active, prov)
                )
            else:
                db.execute(
                    "INSERT INTO api_configs (provider_name, api_key_encrypted, "
                    "base_url, default_model, is_active) VALUES (?,?,?,?,?)",
                    (prov, enc_key, url, model, active)
                )
        QMessageBox.information(self, "保存成功", "所有 API 密钥已加密存入数据库。")
        # 通知全局：API 配置已更新
        from app.utils.signal_bus import signal_bus
        signal_bus.config_updated.emit()
        signal_bus.signal_api_updated.emit()


# ═══════════════════════════════════════════════════════════════
# 主题设置
# ═══════════════════════════════════════════════════════════════

class ThemeView(QWidget):
    theme_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        title = QLabel("🎨  主题颜色")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("外观设置")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 16px; font-weight: bold;
                border: 1px solid #e2e8f0; border-radius: 10px;
                margin-top: 8px; padding: 20px 16px 12px 16px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; }
        """)
        form = QFormLayout(group)
        form.setSpacing(12)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["☀ 浅色", "🌙 深色", "🌿 护眼绿"])
        saved = qconfig.get(cfg.themeMode) if hasattr(cfg, 'themeMode') else "light"
        idx = 0 if saved == "light" else (1 if saved == "dark" else 2)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        form.addRow("全局主题:", self.theme_combo)

        self.icon_size_combo = QComboBox()
        self.icon_size_combo.addItems(["小", "中", "大"])
        self.icon_size_combo.setCurrentIndex(1)
        form.addRow("图标大小:", self.icon_size_combo)

        self.collapse_check = QCheckBox("仅显示图标")
        form.addRow("导航栏:", self.collapse_check)

        layout.addWidget(group)
        layout.addStretch()

    def _on_theme_changed(self, text: str) -> None:
        self.theme_changed.emit(text)
        theme_map = {"☀ 浅色": "light", "🌙 深色": "dark", "🌿 护眼绿": "green"}
        t = theme_map.get(text, "light")
        if hasattr(cfg, 'themeMode'):
            qconfig.set(cfg.themeMode, t)
        try:
            from app.utils.theme_manager import ThemeManager
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                ThemeManager.apply_theme(app, t)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# 关于
# ═══════════════════════════════════════════════════════════════

# ── MIT License 完整文本 ──
MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 未知之致 ,deepseek V4 pro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


DISCLAIMER_TEXT = (
    "⚠️ 免责声明：本软件仅供教育及课堂辅助学习用途。"
    "使用者需自行承担使用风险，开发者不对因使用本软件导致的任何数据丢失、"
    "系统故障、或教学事故负责。"
)


class AboutView(QWidget):
    """关于页面 — 基本信息 + 联系方式 + MIT 开源协议 + 免责声明。"""

    GITHUB_URL = "https://github.com/HMUG12/OpenClass"
    QQ_NUMBER = "3699672176"
    DEVELOPER = "未知之致 ,deepseek V4 pro"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aboutView")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 滚动区域 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(24)

        # ── 顶部标题 ──
        title = QLabel("OpenClass 测试版")
        title.setStyleSheet("font-size: 24pt; font-weight: 900; border: none;")
        layout.addWidget(title)

        # ── 分组一：基本信息 ──
        layout.addWidget(self._build_info_group())

        # ── 分组二：法律声明 ──
        layout.addWidget(self._build_legal_group())

        layout.addStretch()
        scroll.setWidget(content)

    # ═══════════════════════════════════════════════════════════
    # 分组：基本信息
    # ═══════════════════════════════════════════════════════════

    def _build_info_group(self) -> QWidget:
        if _HAS_FLUENT:
            group = SettingCardGroup("基本信息", self)
        else:
            group = QGroupBox("基本信息")
            group.setStyleSheet("""
                QGroupBox {
                    font-size: 15pt; font-weight: 600; border: 1px solid rgba(128,128,128,0.15);
                    border-radius: 12px; margin-top: 14px; padding: 24px 20px 20px 20px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin; left: 16px; padding: 0 8px;
                }
            """)

        # 为 SettingCardGroup 添加自定义子控件
        if _HAS_FLUENT:
            group_layout = group.vBoxLayout
            group_layout.setSpacing(0)
        else:
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(10)

        group_layout.addWidget(self._info_row("软件名称", "OpenClass"))
        group_layout.addWidget(self._info_row("版本", "测试版"))
        group_layout.addWidget(self._info_row("开发者", self.DEVELOPER))
        group_layout.addWidget(self._build_qq_row())
        group_layout.addWidget(self._build_github_row())

        return group

    # ═══════════════════════════════════════════════════════════
    # 分组：法律声明（MIT License + 免责声明）
    # ═══════════════════════════════════════════════════════════

    def _build_legal_group(self) -> QWidget:
        if _HAS_FLUENT:
            group = SettingCardGroup("法律声明", self)
        else:
            group = QGroupBox("法律声明")
            group.setStyleSheet("""
                QGroupBox {
                    font-size: 15pt; font-weight: 600; border: 1px solid rgba(128,128,128,0.15);
                    border-radius: 12px; margin-top: 14px; padding: 24px 20px 20px 20px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin; left: 16px; padding: 0 8px;
                }
            """)

        if _HAS_FLUENT:
            group_layout = group.vBoxLayout
            group_layout.setSpacing(12)
        else:
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(12)

        # ── MIT License 可滚动文本框 ──
        license_frame = QFrame()
        license_frame.setStyleSheet("""
            QFrame {
                background: rgba(128,128,128,0.04);
                border: 1px solid rgba(128,128,128,0.10);
                border-radius: 10px;
            }
        """)
        lic_layout = QVBoxLayout(license_frame)
        lic_layout.setContentsMargins(4, 4, 4, 4)

        self._license_text = QTextEdit()
        self._license_text.setReadOnly(True)
        self._license_text.setPlainText(MIT_LICENSE_TEXT)
        self._license_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12pt;
                color: #334155;
                background: transparent;
                border: none;
                padding: 14px;
            }
            QTextEdit {
                line-height: 1.5;
            }
        """)
        self._license_text.setMinimumHeight(220)
        lic_layout.addWidget(self._license_text)

        group_layout.addWidget(license_frame)

        # ── 免责声明（浅色背景框） ──
        disclaimer_frame = QFrame()
        disclaimer_frame.setStyleSheet("""
            QFrame {
                background: rgba(255,193,7,0.08);
                border: 1px solid rgba(255,193,7,0.22);
                border-radius: 10px;
                padding: 14px 16px;
            }
        """)
        disc_layout = QVBoxLayout(disclaimer_frame)
        disc_layout.setContentsMargins(2, 2, 2, 2)

        disc_label = QLabel(DISCLAIMER_TEXT)
        disc_label.setWordWrap(True)
        disc_label.setStyleSheet("""
            font-size: 13pt; color: #92400e; border: none;
            background: transparent; line-height: 1.5;
        """)
        disc_layout.addWidget(disc_label)

        group_layout.addWidget(disclaimer_frame)

        return group

    # ═══════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════

    def _info_row(self, label: str, value: str) -> QWidget:
        """单行信息：标签 | 值。"""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(16)

        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        lbl.setStyleSheet("font-size: 14px; color: #64748b; border: none; font-weight: 500;")
        h.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet("font-size: 14px; font-weight: 600; border: none;")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(val)
        h.addStretch()
        return row

    def _build_qq_row(self) -> QWidget:
        """QQ 行 — 可复制文本 + 复制按钮。"""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(16)

        lbl = QLabel("联系QQ")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet("font-size: 14px; color: #64748b; border: none; font-weight: 500;")
        h.addWidget(lbl)

        qq_label = QLabel(self.QQ_NUMBER)
        qq_label.setStyleSheet("font-size: 14px; font-weight: 600; border: none;")
        qq_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(qq_label)

        copy_btn = QPushButton("复制")
        copy_btn.setFixedSize(56, 30)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px; border: 1px solid rgba(128,128,128,0.25);
                border-radius: 6px; background: transparent;
                color: #64748b; padding: 2px 8px;
            }
            QPushButton:hover {
                border-color: #6366f1; color: #6366f1; background: rgba(99,102,241,0.06);
            }
        """)
        copy_btn.clicked.connect(lambda: self._copy_qq())
        h.addWidget(copy_btn)
        h.addStretch()
        return row

    def _build_github_row(self) -> QWidget:
        """GitHub 行 — 可点击超链接，跳转系统浏览器。"""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(16)

        lbl = QLabel("仓库")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet("font-size: 14px; color: #64748b; border: none; font-weight: 500;")
        h.addWidget(lbl)

        link_btn = QPushButton(self.GITHUB_URL)
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; color: #2563EB; border: none; background: transparent;
                text-decoration: underline; text-align: left; padding: 0;
            }
            QPushButton:hover {
                color: #1D4ED8;
            }
        """)
        link_btn.clicked.connect(self._open_github)
        h.addWidget(link_btn)
        h.addStretch()
        return row

    # ── 动作 ──

    def _copy_qq(self) -> None:
        """复制 QQ 号到剪贴板，并显示视觉反馈。"""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.QQ_NUMBER)
        sender = self.sender()
        if sender:
            original = sender.text()
            sender.setText("已复制")
            sender.setStyleSheet("""
                QPushButton {
                    font-size: 13px; border: 1px solid #10b981; border-radius: 6px;
                    background: rgba(16,185,129,0.10); color: #10b981; padding: 2px 8px;
                }
            """)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: sender.setText(original))
            QTimer.singleShot(1500, lambda: sender.setStyleSheet("""
                QPushButton {
                    font-size: 13px; border: 1px solid rgba(128,128,128,0.25);
                    border-radius: 6px; background: transparent;
                    color: #64748b; padding: 2px 8px;
                }
                QPushButton:hover {
                    border-color: #6366f1; color: #6366f1; background: rgba(99,102,241,0.06);
                }
            """))

    def _open_github(self) -> None:
        """用系统默认浏览器打开 GitHub 仓库。"""
        QDesktopServices.openUrl(QUrl(self.GITHUB_URL))


# ═══════════════════════════════════════════════════════════════
# 班级与名单管理
# ═══════════════════════════════════════════════════════════════

class ClassManagerView(QWidget):
    """班级与名单管理 — 粘贴文本 / 导入 Excel / 手动添加"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("classManagerView")
        self._class_cache: list[tuple[int, str]] = []
        self._loaded: bool = False  # 懒加载标记

        self._build_ui()
        # 注意：_load_classes() 已移入 _ensure_loaded()，由 SettingsPage 在首次切到该页时调用

    def _ensure_loaded(self) -> None:
        """首次访问时加载 DB 数据（避免启动时卡顿）。"""
        if self._loaded:
            return
        self._loaded = True
        self._load_classes()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(14)

        title = QLabel("👥  班级与名单管理")
        title.setStyleSheet("font-size: 22px; font-weight: bold; border: none;")
        layout.addWidget(title)

        desc = QLabel("在此管理班级和学生名单。支持粘贴文本、导入 Excel、手动添加。修改后随机点名器将自动刷新。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 16px; border: none;")
        layout.addWidget(desc)

        # ── 班级选择行 ──
        class_row = QHBoxLayout()
        class_row.setSpacing(12)
        class_row.addWidget(QLabel("班级:"))

        self._class_combo = QComboBox()
        self._class_combo.setMinimumWidth(180)
        self._class_combo.setStyleSheet("""
            QComboBox { font-size: 16px; padding: 8px 14px; min-height: 40px; }
            QComboBox QAbstractItemView { font-size: 16px; }
        """)
        self._class_combo.currentIndexChanged.connect(self._on_class_changed)
        class_row.addWidget(self._class_combo)

        self._new_class_input = QLineEdit()
        self._new_class_input.setPlaceholderText("输入新班级名称...")
        self._new_class_input.setStyleSheet("""
            QLineEdit { font-size: 15px; padding: 8px 14px; border-radius: 8px;
                border: 1px solid rgba(128,128,128,0.30); min-height: 36px; }
        """)
        self._new_class_input.setFixedWidth(200)
        class_row.addWidget(self._new_class_input)

        add_class_btn = QPushButton("➕ 新建")
        add_class_btn.setFixedHeight(40)
        add_class_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 600; padding: 8px 16px;
                background: rgba(34,197,94,0.15); color: #22c55e;
                border: 1px solid rgba(34,197,94,0.30); border-radius: 10px;
            }
            QPushButton:hover { background: rgba(34,197,94,0.25); }
        """)
        add_class_btn.clicked.connect(self._add_class)
        class_row.addWidget(add_class_btn)

        class_row.addStretch()

        # 删除当前班级按钮
        del_class_btn = QPushButton("🗑 删除本班")
        del_class_btn.setFixedHeight(40)
        del_class_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 600; padding: 8px 16px;
                background: rgba(239,68,68,0.12); color: #ef4444;
                border: 1px solid rgba(239,68,68,0.25); border-radius: 10px;
            }
            QPushButton:hover { background: rgba(239,68,68,0.22); }
        """)
        del_class_btn.clicked.connect(self._delete_class)
        class_row.addWidget(del_class_btn)

        layout.addLayout(class_row)

        # ── 分割线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(128,128,128,0.15);")
        sep.setFixedHeight(2)
        layout.addWidget(sep)

        # ── 三栏导入区 ──
        import_row = QHBoxLayout()
        import_row.setSpacing(16)

        # ① 粘贴文本
        paste_group = QGroupBox("📋 粘贴名单")
        paste_group.setStyleSheet("""
            QGroupBox {
                font-size: 15px; font-weight: bold; border: 1px solid rgba(128,128,128,0.20);
                border-radius: 10px; margin-top: 8px; padding: 16px 12px 10px 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
        """)
        paste_layout = QVBoxLayout(paste_group)
        paste_layout.setSpacing(8)

        self._paste_edit = QTextEdit()
        self._paste_edit.setPlaceholderText("每行一个姓名，如：\n张三\n李四\n王五")
        self._paste_edit.setMaximumHeight(120)
        self._paste_edit.setStyleSheet("font-size: 14px; border-radius: 8px; padding: 8px;")
        paste_layout.addWidget(self._paste_edit)

        paste_btn = QPushButton("📥 导入名单")
        paste_btn.setFixedHeight(40)
        paste_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 600; padding: 8px;
                background: #6366f1; color: #FFFFFF; border: none; border-radius: 10px;
            }
            QPushButton:hover { background: #4f46e5; }
        """)
        paste_btn.clicked.connect(self._import_paste)
        paste_layout.addWidget(paste_btn)
        import_row.addWidget(paste_group)

        # ② 导入 Excel
        excel_group = QGroupBox("📊 导入 Excel")
        excel_group.setStyleSheet("""
            QGroupBox {
                font-size: 15px; font-weight: bold; border: 1px solid rgba(128,128,128,0.20);
                border-radius: 10px; margin-top: 8px; padding: 16px 12px 10px 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
        """)
        excel_layout = QVBoxLayout(excel_group)
        excel_layout.setSpacing(8)
        excel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        excel_info = QLabel("选择 .xlsx 文件，\n自动提取第一列姓名。")
        excel_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        excel_info.setWordWrap(True)
        excel_info.setStyleSheet("color: #888; font-size: 14px; border: none;")
        excel_layout.addWidget(excel_info)

        excel_btn = QPushButton("📂 选择文件")
        excel_btn.setFixedHeight(40)
        excel_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 600; padding: 8px;
                background: #16a34a; color: #FFFFFF; border: none; border-radius: 10px;
            }
            QPushButton:hover { background: #15803d; }
        """)
        excel_btn.clicked.connect(self._import_excel)
        excel_layout.addWidget(excel_btn)
        import_row.addWidget(excel_group)

        # ③ 手动添加
        manual_group = QGroupBox("✏ 手动添加")
        manual_group.setStyleSheet("""
            QGroupBox {
                font-size: 15px; font-weight: bold; border: 1px solid rgba(128,128,128,0.20);
                border-radius: 10px; margin-top: 8px; padding: 16px 12px 10px 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
        """)
        manual_layout = QVBoxLayout(manual_group)
        manual_layout.setSpacing(8)

        self._manual_input = QLineEdit()
        self._manual_input.setPlaceholderText("输入学生姓名...")
        self._manual_input.setStyleSheet("""
            QLineEdit { font-size: 15px; padding: 8px 14px;
                border-radius: 8px; border: 1px solid rgba(128,128,128,0.30);
                min-height: 40px; }
        """)
        manual_layout.addWidget(self._manual_input)

        manual_btn = QPushButton("➕ 添加")
        manual_btn.setFixedHeight(40)
        manual_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 600; padding: 8px;
                background: #f59e0b; color: #FFFFFF; border: none; border-radius: 10px;
            }
            QPushButton:hover { background: #d97706; }
        """)
        manual_btn.clicked.connect(self._add_manual)
        manual_layout.addWidget(manual_btn)
        import_row.addWidget(manual_group)

        layout.addLayout(import_row)

        # ── 学生名单预览 ──
        preview_label = QLabel("当前名单预览")
        preview_label.setStyleSheet("font-size: 16px; font-weight: 600; border: none;")
        layout.addWidget(preview_label)

        self._student_list = QListWidget()
        self._student_list.setStyleSheet("""
            QListWidget {
                border: 1px solid rgba(128,128,128,0.20);
                border-radius: 10px; font-size: 16px;
                background: rgba(0,0,0,0.02);
            }
            QListWidget::item { padding: 10px 16px; min-height: 44px; }
            QListWidget::item:selected { background: rgba(239,68,68,0.25); }
        """)
        self._student_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._student_list.customContextMenuRequested.connect(self._on_student_context)
        layout.addWidget(self._student_list, stretch=1)

        # ── 底部操作 ──
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("选中条目可右键删除。"))

        del_selected_btn = QPushButton("🗑 删除选中")
        del_selected_btn.setFixedHeight(40)
        del_selected_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: 600; padding: 8px 20px;
                background: rgba(239,68,68,0.12); color: #ef4444;
                border: 1px solid rgba(239,68,68,0.25); border-radius: 10px;
            }
            QPushButton:hover { background: rgba(239,68,68,0.22); }
        """)
        del_selected_btn.clicked.connect(self._delete_selected)
        bottom_row.addWidget(del_selected_btn)

        self._count_label = QLabel("共 0 名学生")
        self._count_label.setStyleSheet("color: #888; font-size: 15px; border: none;")
        bottom_row.addWidget(self._count_label)
        layout.addLayout(bottom_row)

    # ═══════════════════════════════════════════════════════════
    # 班级管理
    # ═══════════════════════════════════════════════════════════

    def _load_classes(self) -> None:
        rows = db.fetch_all("SELECT id, name FROM classes ORDER BY id")
        self._class_cache = [(r["id"], r["name"]) for r in rows]
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        for cid, cname in self._class_cache:
            self._class_combo.addItem(cname, cid)
        self._class_combo.blockSignals(False)
        self._refresh_preview()

    def _add_class(self) -> None:
        name = self._new_class_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入班级名称。")
            return
        existing = db.fetch_one("SELECT id FROM classes WHERE name=?", (name,))
        if existing:
            QMessageBox.warning(self, "提示", f"班级「{name}」已存在。")
            return
        new_id = db.execute("INSERT INTO classes (name) VALUES (?)", (name,))
        self._new_class_input.clear()
        self._load_classes()
        # 选中新班级
        idx = self._class_combo.findData(new_id)
        if idx >= 0:
            self._class_combo.setCurrentIndex(idx)
        QMessageBox.information(self, "成功", f"班级「{name}」已创建。")

    def _delete_class(self) -> None:
        cid = self._class_combo.currentData()
        if cid is None:
            return
        cname = self._class_combo.currentText()
        reply = QMessageBox.question(
            self, "删除班级",
            f"确定要删除班级「{cname}」及其全部学生吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db.execute("DELETE FROM students WHERE class_id=?", (cid,))
        db.execute("DELETE FROM call_records WHERE class_id=?", (cid,))
        db.execute("DELETE FROM classes WHERE id=?", (cid,))
        self._load_classes()
        signal_bus.student_list_changed.emit()

    def _on_class_changed(self) -> None:
        self._refresh_preview()

    def _active_class_id(self) -> int:
        return self._class_combo.currentData() or 0

    # ═══════════════════════════════════════════════════════════
    # 名单预览
    # ═══════════════════════════════════════════════════════════

    def _refresh_preview(self) -> None:
        cid = self._active_class_id()
        self._student_list.clear()
        if not cid:
            self._count_label.setText("共 0 名学生")
            return
        rows = db.fetch_all(
            "SELECT id, name, gender, called_count FROM students WHERE class_id=? ORDER BY id",
            (cid,),
        )
        for r in rows:
            name = r["name"]
            suffix = f"  {r['gender']}" if r.get("gender") and r["gender"] != "未设置" else ""
            item = QListWidgetItem(f"{name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, r.get("called_count", 0))
            self._student_list.addItem(item)
        self._count_label.setText(f"共 {len(rows)} 名学生")

    # ═══════════════════════════════════════════════════════════
    # ① 粘贴文本导入
    # ═══════════════════════════════════════════════════════════

    def _import_paste(self) -> None:
        cid = self._active_class_id()
        if not cid:
            QMessageBox.warning(self, "提示", "请先选择或创建一个班级。")
            return
        text = self._paste_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先粘贴名单文本。")
            return
        names = [line.strip() for line in text.splitlines() if line.strip()]
        if not names:
            return
        self._insert_names(cid, names)
        self._paste_edit.clear()
        self._refresh_preview()
        signal_bus.student_list_changed.emit()
        QMessageBox.information(self, "导入成功", f"已导入 {len(names)} 名学生。")

    # ═══════════════════════════════════════════════════════════
    # ② Excel 导入 (stdlib zipfile + ElementTree)
    # ═══════════════════════════════════════════════════════════

    def _import_excel(self) -> None:
        cid = self._active_class_id()
        if not cid:
            QMessageBox.warning(self, "提示", "请先选择或创建一个班级。")
            return

        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel 文件", "",
            "Excel 文件 (*.xlsx);;所有文件 (*)",
        )
        if not path:
            return

        try:
            names = self._parse_xlsx(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法解析 Excel 文件:\n{e}")
            return

        if not names:
            QMessageBox.warning(self, "提示", "Excel 文件中未找到有效姓名。")
            return

        self._insert_names(cid, names)
        self._refresh_preview()
        signal_bus.student_list_changed.emit()
        QMessageBox.information(self, "导入成功", f"已导入 {len(names)} 名学生。")

    def _parse_xlsx(self, path: str) -> list[str]:
        """纯 stdlib 解析 .xlsx 第一列姓名"""
        import zipfile
        from xml.etree.ElementTree import iterparse

        names: list[str] = []
        shared_strings: list[str] = []

        with zipfile.ZipFile(path, "r") as zf:
            # 读取共享字符串表
            if "xl/sharedStrings.xml" in zf.namelist():
                with zf.open("xl/sharedStrings.xml") as f:
                    for _ev, elem in iterparse(f):
                        if elem.tag.endswith("}t"):
                            if elem.text:
                                shared_strings.append(elem.text)
                        elem.clear()

            # 读取第一个工作表
            sheet_xml = "xl/worksheets/sheet1.xml"
            if sheet_xml not in zf.namelist():
                return []

            with zf.open(sheet_xml) as f:
                for _ev, elem in iterparse(f):
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag == "row":
                        # 取该行第一个 c 元素的值
                        first_c = elem.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
                        if first_c is None:
                            first_c = elem.find("c")
                        if first_c is not None:
                            v_el = first_c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                            if v_el is None:
                                v_el = first_c.find("v")
                            if v_el is not None and v_el.text:
                                t_attr = first_c.get("t", "")
                                if t_attr == "s":
                                    idx = int(v_el.text)
                                    if 0 <= idx < len(shared_strings):
                                        names.append(shared_strings[idx])
                                else:
                                    val = v_el.text.strip()
                                    if val:
                                        names.append(val)
                        elem.clear()
        return names

    # ═══════════════════════════════════════════════════════════
    # ③ 手动添加
    # ═══════════════════════════════════════════════════════════

    def _add_manual(self) -> None:
        cid = self._active_class_id()
        if not cid:
            QMessageBox.warning(self, "提示", "请先选择或创建一个班级。")
            return
        name = self._manual_input.text().strip()
        if not name:
            return
        self._insert_names(cid, [name])
        self._manual_input.clear()
        self._refresh_preview()
        signal_bus.student_list_changed.emit()

    # ═══════════════════════════════════════════════════════════
    # 删除学生
    # ═══════════════════════════════════════════════════════════

    def _delete_selected(self) -> None:
        items = self._student_list.selectedItems()
        if not items:
            return
        ids = [it.data(Qt.ItemDataRole.UserRole) for it in items]
        reply = QMessageBox.question(
            self, "删除学生",
            f"确定要删除选中的 {len(ids)} 名学生吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for sid in ids:
            db.execute("DELETE FROM call_records WHERE student_id=?", (sid,))
            db.execute("DELETE FROM students WHERE id=?", (sid,))
        self._refresh_preview()
        signal_bus.student_list_changed.emit()

    def _on_student_context(self, pos) -> None:
        item = self._student_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        del_action = menu.addAction("🗑 删除此学生")
        action = menu.exec(self._student_list.mapToGlobal(pos))
        if action == del_action:
            sid = item.data(Qt.ItemDataRole.UserRole)
            db.execute("DELETE FROM call_records WHERE student_id=?", (sid,))
            db.execute("DELETE FROM students WHERE id=?", (sid,))
            self._refresh_preview()
            signal_bus.student_list_changed.emit()

    # ═══════════════════════════════════════════════════════════
    # 通用：批量插入
    # ═══════════════════════════════════════════════════════════

    def _insert_names(self, class_id: int, names: list[str]) -> None:
        for name in names:
            db.execute(
                "INSERT INTO students (class_id, name) VALUES (?, ?)",
                (class_id, name),
            )


# ═══════════════════════════════════════════════════════════════
# 设置主页
# ═══════════════════════════════════════════════════════════════

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")

        from PySide6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        self.api_view = APIKeysView()
        self.theme_view = ThemeView()
        self.class_view = ClassManagerView()
        self.log_view = LogManagePage()
        self.about_view = AboutView()

        self._stack.addWidget(self.api_view)      # 0
        self._stack.addWidget(self.theme_view)     # 1
        self._stack.addWidget(self.class_view)     # 2
        self._stack.addWidget(self.log_view)       # 3
        self._stack.addWidget(self.about_view)     # 4

        # Tab 栏
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        tab_layout.setContentsMargins(36, 16, 36, 8)
        tab_layout.setSpacing(8)

        self._tabs: list[QPushButton] = []
        for i, text in enumerate(["🔑 API 密钥", "🎨 主题", "� 名单", "�� 日志", "ℹ 关于"]):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    border: none; border-radius: 8px; padding: 8px 20px;
                    font-size: 16px; font-weight: 500; background: transparent;
                }
                QPushButton:hover { background: rgba(0,0,0,0.05); }
                QPushButton:checked { background: #6366f1; color: white; }
            """)
            btn.clicked.connect(lambda checked, idx=i: self._switch_tab(idx))
            tab_layout.addWidget(btn)
            self._tabs.append(btn)
        tab_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(tab_widget)
        layout.addWidget(self._stack, stretch=1)

        self._tabs[0].setChecked(True)

        self.theme_view.theme_changed.connect(self._apply_theme)

    def _switch_tab(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tabs):
            btn.setChecked(i == idx)
        # 懒加载：首次切换到某个 tab 时触发
        if idx == 2 and hasattr(self, 'class_view'):
            self.class_view._ensure_loaded()
        elif idx == 3 and hasattr(self, 'log_view'):
            if hasattr(self.log_view, '_ensure_loaded'):
                self.log_view._ensure_loaded()

    def _ensure_loaded(self) -> None:
        """由 MainWindow 在首次切换到设置页时调用。"""
        self.class_view._ensure_loaded()

    def _apply_theme(self, text: str) -> None:
        try:
            from app.utils.theme_manager import ThemeManager
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                theme_map = {"☀ 浅色": "light", "🌙 深色": "dark", "🌿 护眼绿": "green"}
                ThemeManager.apply_theme(app, theme_map.get(text, "light"))
        except Exception:
            pass
