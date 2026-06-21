"""
🤖 AI Agent — 左历史 + 右聊天工作区 | SSE 流式 | Markdown | 键鼠代理 | 文件解析

布局:
  ┌─ 左侧 260px ───┬─ 聊天工作区 ──────────────────────────────────────┐
  │ [+ 新会话]      │  ┌──────────────────────────────────────────────┐ │
  │ ─ 今天 ─       │  │  用户气泡(右)  /  AI气泡(左, Markdown)      │ │
  │  会话1         │  │  错误卡片(居中, 红色)                        │ │
  │  会话2         │  │                                              │ │
  │ ─ 昨天 ─       │  └──────────────────────────────────────────────┘ │
  │  会话3         │  ┌─ 底部工具栏 ─────────────────────────────────┐ │
  │ ─ 更早 ─       │  │ [文件标签] [供应商▾] [模型▾] [键鼠开关]     │ │
  │                │  │ ┌─────────────────────────────────┬──────┐   │ │
  │                │  │ │ 输入框 (Shift+Enter换行)        │ 发送 │   │ │
  │                │  │ └─────────────────────────────────┴──────┘   │ │
  │                │  └──────────────────────────────────────────────┘ │
  └────────────────┴──────────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import re
import html as html_mod
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QFileDialog, QSplitter,
    QScrollArea, QSizePolicy, QMessageBox, QDialog, QApplication,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QThread, QEvent, QPoint
from PySide6.QtGui import (
    QFont, QDragEnterEvent, QDropEvent, QColor, QIcon, QTextCursor,
    QKeyEvent, QResizeEvent,
)

from qfluentwidgets import (
    PrimaryPushButton, PushButton, FluentIcon,
    SwitchButton, ComboBox, LineEdit,  # qfluentwidgets ComboBox/LineEdit
    InfoBar, InfoBarPosition, BodyLabel, StrongBodyLabel,
    isDarkTheme, ToolButton,
)
from qfluentwidgets.components.dialog_box import MessageBoxBase

from app.database.db_manager import db
from app.database.crypto import decrypt
from app.utils.signal_bus import signal_bus

# ═══════════════════════════════════════════════════════════════
# 文件解析器
# ═══════════════════════════════════════════════════════════════

def _read_text_file(path: str) -> str | None:
    """读取文本文件，自动检测编码（UTF-8 → GBK）。"""
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def parse_file(path: str) -> str | None:
    """
    解析文件内容（.txt / .pdf / .docx）。
    返回文本内容，失败返回 None。
    """
    ext = Path(path).suffix.lower()

    if ext == ".txt":
        return _read_text_file(path)

    if ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            return "\n\n".join(parts) if parts else None
        except Exception:
            return None

    if ext == ".docx":
        try:
            from docx import Document
            doc = Document(path)
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(parts) if parts else None
        except Exception:
            return None

    # fallback：当 txt 读
    return _read_text_file(path)


# ═══════════════════════════════════════════════════════════════
# Markdown → 简易 HTML（无 markdown 库时的降级渲染）
# ═══════════════════════════════════════════════════════════════

def _escape_html(text: str) -> str:
    return html_mod.escape(text)


def render_markdown(text: str) -> str:
    """将 Markdown 文本转换为 HTML。优先使用 markdown 库。"""
    try:
        import markdown
        return markdown.markdown(
            text,
            extensions=["fenced_code", "codehilite", "tables", "nl2br"]
        )
    except ImportError:
        pass

    # ── 简易降级渲染 ──
    t = _escape_html(text)

    # 代码块 ```
    t = re.sub(r"```(\w*)\n(.*?)```", r'<pre><code>\2</code></pre>', t, flags=re.DOTALL)
    # 行内代码 `...`
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    # **粗体**
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    # *斜体*
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
    # ### 标题
    t = re.sub(r"^### (.+)$", r"<h4>\1</h4>", t, flags=re.MULTILINE)
    t = re.sub(r"^## (.+)$", r"<h3>\1</h3>", t, flags=re.MULTILINE)
    t = re.sub(r"^# (.+)$", r"<h2>\1</h2>", t, flags=re.MULTILINE)
    # 无序列表
    t = re.sub(r"^- (.+)$", r"<li>\1</li>", t, flags=re.MULTILINE)
    # 换行 → <br>
    t = t.replace("\n", "<br>")

    return f"<div style='font-size:16px; line-height:1.8;'>{t}</div>"


# ═══════════════════════════════════════════════════════════════
# 消息气泡 Widget
# ═══════════════════════════════════════════════════════════════

class MessageBubble(QFrame):
    """聊天消息气泡 — 用户右对齐(紫底白字) / AI 左对齐(Markdown) / 错误居中"""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.setObjectName("messageBubble")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        dark = isDarkTheme()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setOpenExternalLinks(True)
        self._text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        if role == "user":
            # 右对齐，紫色背景
            layout.addStretch(1)
            self._text.setStyleSheet("""
                QLabel {
                    background: #7C3AED; color: #FFFFFF;
                    border-radius: 14px;
                    padding: 12px 20px;
                    font-size: 16px;
                }
            """)
            self._text.setText(_escape_html(content))
            layout.addWidget(self._text, alignment=Qt.AlignmentFlag.AlignRight)

        elif role == "assistant":
            # 左对齐，markdown 渲染
            bg = "rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.03)"
            color = "#E4E4E7" if dark else "#1E293B"
            self._text.setStyleSheet(f"""
                QLabel {{
                    background: {bg}; color: {color};
                    border-radius: 14px;
                    padding: 12px 20px;
                    font-size: 16px;
                }}
            """)
            self._text.setText(render_markdown(content))
            layout.addWidget(self._text, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addStretch(1)

        elif role == "system":
            # 居中系统消息
            layout.addStretch(1)
            self._text.setStyleSheet("""
                QLabel {
                    color: #94a3b8; font-size: 16px;
                    padding: 6px 14px; background: transparent;
                }
            """)
            self._text.setText(content)
            self._text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._text)
            layout.addStretch(1)

        elif role == "error":
            # 居中错误卡片
            layout.addStretch(1)
            self._text.setStyleSheet("""
                QLabel {
                    background: rgba(239,68,68,0.10);
                    border: 1px solid rgba(239,68,68,0.30);
                    color: #EF4444; border-radius: 12px;
                    padding: 14px 22px; font-size: 16px;
                }
            """)
            self._text.setText(f"⚠️ {content}")
            layout.addWidget(self._text)
            layout.addStretch(1)

        elif role == "timeout":
            # 超时错误卡片 — 带重试按钮
            layout.addStretch(1)
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(10)

            self._timeout_label = QLabel()
            self._timeout_label.setStyleSheet("""
                QLabel {
                    background: rgba(245,158,11,0.12);
                    border: 1px solid rgba(245,158,11,0.35);
                    color: #F59E0B; border-radius: 12px;
                    padding: 14px 22px; font-size: 16px;
                }
            """)
            self._timeout_label.setWordWrap(True)
            self._timeout_label.setText(
                "⚠️ 请求超时，请检查网络或 Base URL 配置"
            )
            card_layout.addWidget(self._timeout_label)

            self._retry_btn = QPushButton("🔄 重试")
            self._retry_btn.setFixedHeight(38)
            self._retry_btn.setStyleSheet("""
                QPushButton {
                    font-size: 15px; font-weight: bold;
                    background: #F59E0B; color: #FFFFFF;
                    border: none; border-radius: 8px; padding: 6px 20px;
                }
                QPushButton:hover { background: #D97706; }
            """)
            self._retry_btn.setFixedWidth(120)
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            btn_row.addWidget(self._retry_btn)
            btn_row.addStretch()
            card_layout.addLayout(btn_row)

            layout.addWidget(card)
            layout.addStretch(1)

    def append_content(self, delta: str) -> None:
        """流式输出时追加内容（仅 AI 气泡）。"""
        current = self._text.text()
        self._text.setText(current + delta)
        # 滚动到底部会在外部处理

    def finalize(self, content: str) -> None:
        """流式结束后渲染最终 Markdown。"""
        self._text.setText(render_markdown(content))


# ═══════════════════════════════════════════════════════════════
# SSE 流式 API 调用器
# ═══════════════════════════════════════════════════════════════

class SSEStreamer(QThread):
    """后台线程 — HTTP POST + SSE stream，逐 chunk 发信号。"""

    chunk_received = Signal(str)    # 增量文本
    stream_finished = Signal(str)   # 完整文本
    stream_error = Signal(str)      # 错误信息
    stream_timeout = Signal()       # 超时专用信号

    def __init__(self, base_url: str, api_key: str, model: str,
                 messages: list[dict], timeout: int = 10, parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._messages = messages
        self._timeout = timeout
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        url = f"{self._base_url}/chat/completions"
        body = json.dumps({
            "model": self._model,
            "messages": self._messages,
            "stream": True,
            "temperature": 0.7,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "text/event-stream",
        }

        for attempt in range(2):  # 最多 2 次（含一次重试）
            if self._cancelled:
                return
            try:
                req = Request(url, data=body, headers=headers)
                with urlopen(req, timeout=self._timeout) as resp:
                    full_text = ""
                    buffer = b""

                    while not self._cancelled:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        buffer += chunk

                        # 按 SSE 协议解析行
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            if not line.startswith(b"data: "):
                                continue
                            data_str = line[6:].decode("utf-8", errors="replace")

                            if data_str == "[DONE]":
                                break

                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0]["delta"]
                                text = delta.get("content", "")
                                if text:
                                    full_text += text
                                    self.chunk_received.emit(text)
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue

                    self.stream_finished.emit(full_text)
                    return

            except URLError as e:
                if attempt == 0:
                    # 第一次失败，重试
                    time.sleep(1)
                    continue
                reason = str(e.reason) if hasattr(e, 'reason') else str(e)
                if "timeout" in reason.lower() or "timed out" in reason.lower():
                    self.stream_timeout.emit()
                else:
                    self.stream_error.emit(f"网络请求失败: {e}")
                return
            except Exception as e:
                self.stream_error.emit(f"请求异常: {e}")
                return

        self.stream_timeout.emit()


# ═══════════════════════════════════════════════════════════════
# 键鼠代理 — 安全确认对话框 (5s 倒计时)
# ═══════════════════════════════════════════════════════════════

class PyAutoGUIConfirmDialog(MessageBoxBase):
    """安全确认弹窗 — 5s 倒计时自动取消。"""

    def __init__(self, action_description: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ 键鼠代理 — 安全确认")
        self.titleLabel.setText("确认执行键鼠操作")
        self._seconds = 5
        self._confirmed = False

        body = (
            f"AI 请求执行以下操作:\n\n"
            f"  {action_description}\n\n"
            f"请在 {self._seconds} 秒内确认，超时自动取消。\n"
            f"安全提示: 请确保操作不会影响关键任务。"
        )
        self.textLayout.setText(body)

        self.yesButton.setText(f"确认执行 ({self._seconds}s)")
        self.yesButton.setStyleSheet("""
            QPushButton {
                background: #EF4444; color: white; font-weight: bold;
                border-radius: 8px; padding: 8px 24px;
            }
            QPushButton:hover { background: #DC2626; }
        """)
        self.cancelButton.setText("取消")

        # 倒计时
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick)
        self._countdown_timer.start(1000)

        self.yesButton.clicked.connect(self._on_confirm)
        self.cancelButton.clicked.connect(self.reject)

    def _tick(self) -> None:
        self._seconds -= 1
        if self._seconds <= 0:
            self._countdown_timer.stop()
            self.reject()
            return
        self.yesButton.setText(f"确认执行 ({self._seconds}s)")

    def _on_confirm(self) -> None:
        self._countdown_timer.stop()
        self._confirmed = True
        self.accept()

    def is_confirmed(self) -> bool:
        return self._confirmed

    def closeEvent(self, event) -> None:
        self._countdown_timer.stop()
        super().closeEvent(event)


class PyAutoGUIExecutor:
    """键鼠操作安全执行器 — 拦截危险组合键(Alt+F4 等)。"""

    DANGEROUS_PATTERNS = [
        r"alt\s*\+\s*f4", r"ctrl\s*\+\s*alt\s*\+\s*del",
        r"ctrl\s*\+\s*shift\s*\+\s*esc", r"win\s*\+\s*[rl]",
        r"super\s*\+\s*[rl]", r"cmd\s*\+\s*[qQ]",
        r"shutdown", r"restart", r"reboot", r"format",
        r"rm\s+-rf", r"del\s+/[fFsS]",
    ]

    @classmethod
    def is_dangerous(cls, text: str) -> str | None:
        """检查文本是否包含危险操作，返回匹配的描述或 None。"""
        lower = text.lower()
        for pat in cls.DANGEROUS_PATTERNS:
            m = re.search(pat, lower)
            if m:
                return f"检测到危险操作模式: \"{m.group(0)}\""
        return None

    @classmethod
    def execute(cls, action_text: str, parent=None) -> tuple[bool, str]:
        """
        执行键鼠操作（安全确认后）。
        返回 (是否执行, 说明)。
        """
        # 1) 检查危险操作
        danger = cls.is_dangerous(action_text)
        if danger:
            return False, danger + "\n已拦截，不执行。"

        # 2) 弹窗确认
        dlg = PyAutoGUIConfirmDialog(action_text, parent)
        dlg.exec()

        if not dlg.is_confirmed():
            return False, "操作已被用户取消 (超时或点击取消)。"

        # 3) 执行 PyAutoGUI
        try:
            import pyautogui
            pyautogui.FAILSAFE = True  # 启用故障安全（鼠标移角落抛出异常）

            # 简单 NLP 解析常见指令
            lower = action_text.lower()

            # 鼠标移动
            m = re.search(r"移动[到至]?\s*[(（]?\s*(\d+)\s*[,，\s]\s*(\d+)\s*[)）]?", action_text)
            if m:
                x, y = int(m.group(1)), int(m.group(2))
                pyautogui.moveTo(x, y, duration=0.5)
                return True, f"鼠标已移至 ({x}, {y})。"

            m = re.search(r"move\s*(?:to)?\s*[(（]?\s*(\d+)\s*[,，\s]\s*(\d+)", lower)
            if m:
                x, y = int(m.group(1)), int(m.group(2))
                pyautogui.moveTo(x, y, duration=0.5)
                return True, f"鼠标已移至 ({x}, {y})。"

            # 点击
            if re.search(r"(单击|点击|click|左键)", lower):
                pyautogui.click()
                return True, "已执行左键单击。"

            if re.search(r"(双击|double\s*click)", lower):
                pyautogui.doubleClick()
                return True, "已执行左键双击。"

            if re.search(r"(右键|right\s*click)", lower):
                pyautogui.rightClick()
                return True, "已执行右键单击。"

            # 滚轮
            m = re.search(r"滚轮?\s*(\d+)", lower)
            if m:
                pyautogui.scroll(int(m.group(1)))
                return True, f"已滚动滚轮 {m.group(1)}。"

            # 键盘输入
            m = re.search(r"输入\s*[:：]?\s*(.+?)(?:\s*$)", action_text)
            if m and not any(k in lower for k in ("移动", "点击", "move", "click", "scroll", "滚轮")):
                pyautogui.typewrite(m.group(1).strip(), interval=0.05)
                return True, f"已输入: {m.group(1).strip()}。"

            # 按键
            m = re.search(r"按下?\s*[:：]?\s*(\w+)", action_text)
            if m:
                key = m.group(1).strip()
                pyautogui.press(key)
                return True, f"已按键: {key}。"

            # 截图
            if "截屏" in lower or "screenshot" in lower:
                from io import BytesIO
                img = pyautogui.screenshot()
                buf = BytesIO()
                img.save(buf, "PNG")
                return True, f"截图已生成 ({img.size[0]}x{img.size[1]}px)。"

            # fallback: 整句作为 pyautogui 命令
            # 不支持 generic eval，直接返回
            return False, f"无法解析操作指令: {action_text}\n当前支持: 移动鼠标(x,y) / 单击/双击/右键 / 滚轮N / 输入文本 / 按键 / 截屏"

        except ImportError:
            return False, "PyAutoGUI 未安装。请运行: pip install pyautogui"
        except pyautogui.FailSafeException:
            return False, "故障安全触发 — 鼠标移至屏幕角落，已中止操作。"
        except Exception as e:
            return False, f"执行异常: {e}"


# ═══════════════════════════════════════════════════════════════
# 会话管理器 — DB 读写 chat_sessions / chat_messages
# ═══════════════════════════════════════════════════════════════

class SessionManager:
    """管理聊天会话和消息的持久化。"""

    @staticmethod
    def create_session(title: str = "新会话") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return db.execute(
            "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?,?,?)",
            (title, now, now)
        )

    @staticmethod
    def save_message(session_id: int, role: str, content: str, tool_calls_json: str | None = None) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 更新会话 updated_at
        db.execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))
        return db.execute(
            "INSERT INTO chat_messages (session_id, role, content, tool_calls_json, created_at) "
            "VALUES (?,?,?,?,?)",
            (session_id, role, content, tool_calls_json, now)
        )

    @staticmethod
    def load_messages(session_id: int) -> list[dict]:
        return db.fetch_all(
            "SELECT role, content, tool_calls_json, created_at "
            "FROM chat_messages WHERE session_id=? ORDER BY id",
            (session_id,)
        )

    @staticmethod
    def get_sessions() -> list[dict]:
        return db.fetch_all(
            "SELECT id, title, created_at, updated_at "
            "FROM chat_sessions ORDER BY updated_at DESC"
        )

    @staticmethod
    def get_api_config(provider_name: str) -> dict | None:
        row = db.fetch_one(
            "SELECT api_key_encrypted, base_url, default_model, is_active "
            "FROM api_configs WHERE provider_name=? AND is_active=1",
            (provider_name,)
        )
        if not row:
            return None
        key = ""
        try:
            key = decrypt(row["api_key_encrypted"]) if row["api_key_encrypted"] else ""
        except Exception:
            pass
        return {
            "api_key": key,
            "base_url": row["base_url"],
            "model": row["default_model"],
        }

    @staticmethod
    def get_active_providers() -> list[str]:
        rows = db.fetch_all(
            "SELECT provider_name FROM api_configs WHERE is_active=1 ORDER BY id"
        )
        return [r["provider_name"] for r in rows]

    @staticmethod
    def update_session_title(session_id: int, title: str) -> None:
        db.execute("UPDATE chat_sessions SET title=?, updated_at=? WHERE id=?",
                   (title, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session_id))

    @staticmethod
    def delete_session(session_id: int) -> None:
        db.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))


# ═══════════════════════════════════════════════════════════════
# 会话历史侧栏
# ═══════════════════════════════════════════════════════════════

class ChatHistorySidebar(QWidget):
    session_selected = Signal(int)     # 选中会话
    new_session_requested = Signal()   # 新建会话

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatHistorySidebar")
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(12)

        # 标题 + 新建按钮
        header = QHBoxLayout()
        title = StrongBodyLabel("💬 对话历史")
        header.addWidget(title)
        header.addStretch()
        new_btn = ToolButton(FluentIcon.ADD, self)
        new_btn.setToolTip("新建会话")
        new_btn.clicked.connect(self.new_session_requested.emit)
        header.addWidget(new_btn)
        layout.addLayout(header)

        # 滚动列表
        self._list = QListWidget()
        self._list.setObjectName("sessionList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.setStyleSheet("""
            QListWidget#sessionList {
                border: none;
                background: transparent;
                font-size: 16px;
                outline: none;
            }
            QListWidget#sessionList::item {
                padding: 12px 14px;
                border-radius: 8px;
                min-height: 48px;
            }
            QListWidget#sessionList::item:hover {
                background: rgba(0,0,0,0.04);
            }
            QListWidget#sessionList::item:selected {
                background: rgba(124,58,237,0.12);
            }
            QListWidget#sessionList::item:pressed {
                background: rgba(124,58,237,0.20);
            }
        """)
        layout.addWidget(self._list)

    def refresh(self) -> None:
        """从 DB 加载会话列表，按 今天/昨天/更早 分组。"""
        sessions = SessionManager.get_sessions()
        self._list.clear()

        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)

        groups: dict[str, list[dict]] = {"今天": [], "昨天": [], "更早": []}
        for s in sessions:
            try:
                dt = datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M:%S")
                d = dt.date()
            except (ValueError, TypeError):
                d = today
            if d == today:
                groups["今天"].append(s)
            elif d == yesterday:
                groups["昨天"].append(s)
            else:
                groups["更早"].append(s)

        for label in ["今天", "昨天", "更早"]:
            if not groups[label]:
                continue
            # 分组标题
            sep = QListWidgetItem(f"── {label} ──")
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            sep.setForeground(QColor("#94a3b8"))
            font = QFont()
            font.setPointSize(10)
            sep.setFont(font)
            self._list.addItem(sep)

            for s in groups[label]:
                title = s["title"] or "无标题"
                item = QListWidgetItem(f"  {title}")
                item.setData(Qt.ItemDataRole.UserRole, s["id"])
                self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid is not None:
            self.session_selected.emit(sid)

    def _on_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        delete_action = menu.addAction("🗑 删除会话")
        action = menu.exec(self._list.viewport().mapToGlobal(pos))
        if action == delete_action:
            SessionManager.delete_session(sid)
            self.refresh()
            self.session_selected.emit(-1)  # 通知清空


# ═══════════════════════════════════════════════════════════════
# Agent 主页面
# ═══════════════════════════════════════════════════════════════

class AgentPage(QWidget):
    """AI Agent — 多模型对话 + 键鼠代理 + 文件上传"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("agentPage")
        self.setAcceptDrops(True)

        # ── 内部状态 ──
        self._session_id: int | None = None
        self._messages: list[dict] = []           # [{role, content}]
        self._file_context: str = ""              # 上传文件内容
        self._is_streaming: bool = False
        self._active_bubble: MessageBubble | None = None
        self._stream_full_text: str = ""
        self._sse_thread: SSEStreamer | None = None
        self._last_sent_text: str = ""  # 用于超时重试
        self._loaded: bool = False     # 懒加载标记

        self._build_ui()

        # 信号连接（无 DB 操作，始终安全）
        signal_bus.signal_api_updated.connect(self._on_api_updated)

        # 注意：DB 操作已移入 _ensure_loaded()，由 MainWindow 在首次切到该页时调用

    # ═══════════════════════════════════════════════════════════
    # 懒加载
    # ═══════════════════════════════════════════════════════════

    def _ensure_loaded(self) -> None:
        """首次访问时加载 DB 数据（避免启动时卡顿）。"""
        if self._loaded:
            return
        self._loaded = True
        self._load_providers()
        self._history_sidebar.refresh()
        self._check_api_status()

    # ═══════════════════════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 左侧会话历史 ──
        self._history_sidebar = ChatHistorySidebar()
        self._history_sidebar.session_selected.connect(self._load_session)
        self._history_sidebar.new_session_requested.connect(self._new_session)
        root.addWidget(self._history_sidebar)

        # 分割线
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet("color: rgba(0,0,0,0.06);")
        root.addWidget(div)

        # ── 右侧聊天工作区 ──
        workspace = QWidget()
        workspace.setObjectName("chatWorkspace")
        ws_layout = QVBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(0)

        # ─── 消息滚动区 ───
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._message_container = QWidget()
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(20, 20, 20, 12)
        self._message_layout.setSpacing(4)
        self._message_layout.addStretch(1)
        self._scroll_area.setWidget(self._message_container)
        ws_layout.addWidget(self._scroll_area, stretch=1)

        # ─── API 密钥缺失红色横幅 ───
        self._api_warning = QLabel(
            "⚠️ 请前往【设置】-【API密钥设置】添加并激活您的 API 密钥"
        )
        self._api_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._api_warning.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        self._api_warning.setFixedHeight(48)
        self._api_warning.setStyleSheet("""
            QLabel {
                background: #EF4444; color: #FFFFFF;
                border-radius: 0px; padding: 0px 16px;
            }
        """)
        self._api_warning.setVisible(False)
        ws_layout.addWidget(self._api_warning)

        # ─── 底部工具栏 ───
        toolbar = QWidget()
        toolbar.setObjectName("chatToolbar")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(20, 8, 20, 12)
        toolbar_layout.setSpacing(8)

        # 文件标签行
        self._file_tags = QHBoxLayout()
        self._file_tags.setSpacing(6)
        toolbar_layout.addLayout(self._file_tags)
        self._file_tags.addStretch()

        # 供应商/模型/键鼠开关
        config_row = QHBoxLayout()
        config_row.setSpacing(12)

        config_row.addWidget(QLabel("供应商:"))
        self._provider_combo = ComboBox()
        self._provider_combo.setMinimumWidth(120)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        config_row.addWidget(self._provider_combo)

        config_row.addWidget(QLabel("模型:"))
        self._model_combo = ComboBox()
        self._model_combo.setMinimumWidth(160)
        self._model_combo.addItems(["gpt-4", "gpt-3.5-turbo", "gpt-4o", "deepseek-chat", "claude-3-opus-20240229"])
        config_row.addWidget(self._model_combo)

        config_row.addSpacing(20)

        config_row.addWidget(QLabel("键鼠代理:"))
        self._kb_switch = SwitchButton()
        self._kb_switch.setOnText("开")
        self._kb_switch.setOffText("关")
        self._kb_switch.setChecked(False)
        config_row.addWidget(self._kb_switch)

        config_row.addStretch()

        upload_btn = PushButton(FluentIcon.UP, "上传文件")
        upload_btn.clicked.connect(self._upload_file)
        config_row.addWidget(upload_btn)

        toolbar_layout.addLayout(config_row)

        # 输入行
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self._input_box = QTextEdit()
        self._input_box.setPlaceholderText("输入消息... Shift+Enter 换行, Enter 发送 | 开启键鼠代理后 AI 可操控桌面")
        self._input_box.setMaximumHeight(100)
        self._input_box.setMinimumHeight(44)
        self._input_box.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(0,0,0,0.10);
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 16px;
            }
            QTextEdit:focus {
                border-color: #7C3AED;
            }
        """)
        self._input_box.installEventFilter(self)
        input_row.addWidget(self._input_box, stretch=1)

        self._send_btn = PrimaryPushButton(FluentIcon.SEND, "")
        self._send_btn.setFixedSize(48, 48)
        self._send_btn.clicked.connect(self._send_message)
        input_row.addWidget(self._send_btn)

        toolbar_layout.addLayout(input_row)
        ws_layout.addWidget(toolbar)
        root.addWidget(workspace, stretch=1)

    # ═══════════════════════════════════════════════════════════
    # 键盘事件 — Enter 发送, Shift+Enter 换行
    # ═══════════════════════════════════════════════════════════

    def eventFilter(self, obj, event: QEvent) -> bool:
        if obj is self._input_box and event.type() == QEvent.Type.KeyPress:
            kev = event
            if kev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if kev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False  # 让 QTextEdit 处理换行
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    # ═══════════════════════════════════════════════════════════
    # 拖放上传
    # ═══════════════════════════════════════════════════════════

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._input_box.setStyleSheet(self._input_box.styleSheet() +
                "QTextEdit { border: 2px dashed #7C3AED; }")

    def dragLeaveEvent(self, event) -> None:
        self._input_box.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(0,0,0,0.10); border-radius: 12px;
                padding: 12px 16px; font-size: 16px;
            }
            QTextEdit:focus { border-color: #7C3AED; }
        """)

    def dropEvent(self, event: QDropEvent) -> None:
        self.dragLeaveEvent(None)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self._process_file(path)

    # ═══════════════════════════════════════════════════════════
    # 文件上传
    # ═══════════════════════════════════════════════════════════

    def _upload_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "文档文件 (*.txt *.pdf *.docx);;所有文件 (*.*)"
        )
        if path:
            self._process_file(path)

    def _process_file(self, path: str) -> None:
        text = parse_file(path)
        if text is None:
            InfoBar.error(
                "文件解析失败",
                f"无法解析文件: {Path(path).name}\n请确认文件未损坏且为支持的格式。",
                duration=5000,
                position=InfoBarPosition.TOP,
                parent=self
            )
            return

        fname = Path(path).name
        self._file_context += f"\n\n【文件: {fname}】\n{text}\n"

        # 文件标签
        tag = QFrame()
        tag.setStyleSheet("""
            QFrame {
                background: rgba(124,58,237,0.10);
                border: 1px solid rgba(124,58,237,0.30);
                border-radius: 8px; padding: 4px 10px;
            }
        """)
        tag_layout = QHBoxLayout(tag)
        tag_layout.setContentsMargins(0, 0, 0, 0)
        tag_layout.addWidget(QLabel(f"📎 {fname}"))
        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(24, 24)
        rm_btn.setStyleSheet("border: none; font-size: 16px; color: #EF4444;")
        rm_btn.clicked.connect(lambda: self._remove_file_tag(tag, fname))
        tag_layout.addWidget(rm_btn)

        # 插入到文件标签行最前面
        self._file_tags.insertWidget(0, tag)

        self._add_system_message(f"📎 已读取文件: {fname} ({len(text)} 字符)")

    def _remove_file_tag(self, tag: QFrame, fname: str) -> None:
        self._file_tags.removeWidget(tag)
        tag.deleteLater()
        # 从 file_context 中移除
        marker = f"\n\n【文件: {fname}】"
        idx = self._file_context.find(marker)
        if idx >= 0:
            self._file_context = self._file_context[:idx]
        self._add_system_message(f"🗑 已移除文件: {fname}")

    # ═══════════════════════════════════════════════════════════
    # 供应商 / 模型
    # ═══════════════════════════════════════════════════════════

    def _load_providers(self) -> None:
        providers = SessionManager.get_active_providers()
        self._provider_combo.clear()
        for p in providers or ["OpenAI"]:
            self._provider_combo.addItem(p)
        self._on_provider_changed(self._provider_combo.currentText())

    def _on_provider_changed(self, name: str) -> None:
        cfg = SessionManager.get_api_config(name)
        if cfg and cfg.get("model"):
            self._model_combo.setCurrentText(cfg["model"])

    # ═══════════════════════════════════════════════════════════
    # API 密钥状态检查
    # ═══════════════════════════════════════════════════════════

    def _check_api_status(self) -> bool:
        """检查数据库是否存在可用 API 密钥。返回 True 表示有可用密钥。"""
        row = db.fetch_one(
            "SELECT COUNT(*) as cnt FROM api_configs WHERE is_active = 1"
        )
        count = row["cnt"] if row else 0
        has_key = count > 0
        self._api_warning.setVisible(not has_key)
        return has_key

    def _on_api_updated(self) -> None:
        """API 密钥保存后：刷新供应商列表 + 关闭横幅。"""
        self._load_providers()
        self._check_api_status()

    # ═══════════════════════════════════════════════════════════
    # 会话管理
    # ═══════════════════════════════════════════════════════════

    def _new_session(self) -> None:
        self._session_id = None
        self._messages = []
        self._file_context = ""
        self._clear_messages_ui()
        self._history_sidebar.refresh()

    def _load_session(self, sid: int) -> None:
        if sid < 0:
            self._new_session()
            return
        self._session_id = sid
        self._clear_messages_ui()

        msgs = SessionManager.load_messages(sid)
        for m in msgs:
            role = m["role"]
            content = m["content"]
            if role == "tool":
                continue
            bubble = MessageBubble(role, content)
            self._insert_bubble(bubble)
            self._messages.append({"role": role, "content": content})

    def _clear_messages_ui(self) -> None:
        # 移除所有气泡 (保留 stretch)
        for i in reversed(range(self._message_layout.count())):
            item = self._message_layout.itemAt(i)
            w = item.widget()
            if w and isinstance(w, MessageBubble):
                w.deleteLater()
            elif item.spacerItem():
                pass

    def _ensure_session(self) -> None:
        if self._session_id is None:
            self._session_id = SessionManager.create_session()
            # 用第一条用户消息作标题
            self._history_sidebar.refresh()

    # ═══════════════════════════════════════════════════════════
    # 发送消息
    # ═══════════════════════════════════════════════════════════

    def _send_message(self) -> None:
        if self._is_streaming:
            InfoBar.warning("请等待", "AI 正在生成回复，请稍候...",
                           duration=2000, position=InfoBarPosition.TOP, parent=self)
            return

        # ── 前置拦截：无可用 API 密钥 ──
        if not self._check_api_status():
            InfoBar.warning(
                "无可用 API 密钥",
                "请前往【设置】-【API密钥设置】添加并激活您的 API 密钥",
                duration=4000,
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        text = self._input_box.toPlainText().strip()
        if not text:
            return

        self._input_box.clear()
        self._input_box.setReadOnly(True)
        self._send_btn.setEnabled(False)
        self._is_streaming = True
        self._last_sent_text = text  # 保存用于超时重试

        # 确保有会话
        self._ensure_session()

        # 添加用户消息
        self._add_user_message(text)
        SessionManager.save_message(self._session_id, "user", text)
        # 更新标题（用第一条消息）
        if len(self._messages) <= 1:
            title = text[:30] + ("..." if len(text) > 30 else "")
            SessionManager.update_session_title(self._session_id, title)
            self._history_sidebar.refresh()

        # 构建系统提示
        system_prompt = (
            "你是一位教师课堂助手，名为 OpenClass Agent，运行在教师的 Windows 桌面上。"
            "请用简洁、专业的中文回答。"
        )
        if self._file_context:
            system_prompt += f"\n\n【已上传文件内容】\n{self._file_context}"

        if self._kb_switch.isChecked():
            system_prompt += (
                "\n\n【键鼠代理已启用】你可以通过自然语言操控教师的桌面。"
                "可用的操作包括: 鼠标移动(x,y)、单击、双击、右键点击、"
                "滚轮滚动、键盘输入、按键、截屏。"
                "当你想要执行键鼠操作时，请用格式: [ACTION] 具体操作描述 [/ACTION]"
            )

        # 构建消息列表
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(self._messages)

        # 检查键鼠代理请求
        if self._kb_switch.isChecked():
            action_text = self._extract_action(text)
            if action_text:
                self._execute_pyautogui(action_text)
                self._input_box.setReadOnly(False)
                self._send_btn.setEnabled(True)
                self._is_streaming = False
                return

        # 获取 API 配置
        provider = self._provider_combo.currentText()
        cfg = SessionManager.get_api_config(provider)
        if not cfg or not cfg.get("api_key"):
            self._add_error_message(f"未配置 {provider} 的 API 密钥，请前往「设置 → API 密钥」进行配置。")
            self._input_box.setReadOnly(False)
            self._send_btn.setEnabled(True)
            self._is_streaming = False
            return

        # 添加流式回复占位气泡
        self._active_bubble = MessageBubble("assistant", "")
        self._insert_bubble(self._active_bubble)
        self._stream_full_text = ""

        # 启动 SSE 流式线程
        self._sse_thread = SSEStreamer(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            model=self._model_combo.currentText().strip(),
            messages=api_messages,
            timeout=10,
            parent=self,
        )
        self._sse_thread.chunk_received.connect(self._on_chunk_received)
        self._sse_thread.stream_finished.connect(self._on_stream_finished)
        self._sse_thread.stream_error.connect(self._on_stream_error)
        self._sse_thread.stream_timeout.connect(self._on_stream_timeout)
        self._sse_thread.start()

    def _extract_action(self, text: str) -> str | None:
        """从用户消息中提取 [ACTION]...[/ACTION] 标签。"""
        m = re.search(r"\[ACTION\](.*?)\[/ACTION\]", text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _execute_pyautogui(self, action_text: str) -> None:
        """执行键鼠代理操作（带确认）。"""
        ok, msg = PyAutoGUIExecutor.execute(action_text, self)

        if ok:
            self._add_system_message(f"🖱️ 键鼠代理: {msg}")
        else:
            self._add_error_message(f"键鼠代理: {msg}")

        # 如果是安全拦截，把反馈发给 AI
        self._messages.append({"role": "user", "content": f"[键鼠代理结果] {msg}"})

    # ═══════════════════════════════════════════════════════════
    # SSE 回调
    # ═══════════════════════════════════════════════════════════

    def _on_chunk_received(self, text: str) -> None:
        if self._active_bubble:
            self._active_bubble.append_content(text)
            self._stream_full_text += text
            self._scroll_to_bottom()

    def _on_stream_finished(self, full_text: str) -> None:
        if self._active_bubble:
            self._active_bubble.finalize(full_text or self._stream_full_text)
        final = full_text or self._stream_full_text
        # 检查 AI 是否请求键鼠操作
        if self._kb_switch.isChecked() and final:
            action = self._extract_action(final)
            if action:
                self._execute_pyautogui(action)

        # 保存到 DB
        self._messages.append({"role": "assistant", "content": final})
        self._ensure_session()
        SessionManager.save_message(self._session_id, "assistant", final)
        self._finish_stream()

    def _on_stream_error(self, msg: str) -> None:
        self._add_error_message(msg)
        if self._active_bubble:
            self._active_bubble.deleteLater()
            self._active_bubble = None
        self._finish_stream()

    def _on_stream_timeout(self) -> None:
        """超时 → 显示友好错误卡片 + 重试按钮。"""
        if self._active_bubble:
            self._active_bubble.deleteLater()
            self._active_bubble = None

        bubble = MessageBubble("timeout", "")
        self._insert_bubble(bubble)
        # 连接重试按钮
        if hasattr(bubble, '_retry_btn'):
            bubble._retry_btn.clicked.connect(self._retry_last_message)
        self._scroll_to_bottom()
        self._finish_stream()

    def _retry_last_message(self) -> None:
        """重新发送上一条消息。"""
        if not self._last_sent_text:
            return
        text = self._last_sent_text
        self._last_sent_text = ""
        self._input_box.setText(text)
        self._send_message()

    def _finish_stream(self) -> None:
        self._is_streaming = False
        self._input_box.setReadOnly(False)
        self._send_btn.setEnabled(True)
        self._input_box.setFocus()
        self._active_bubble = None
        self._sse_thread = None

    # ═══════════════════════════════════════════════════════════
    # UI 辅助
    # ═══════════════════════════════════════════════════════════

    def _insert_bubble(self, bubble: MessageBubble) -> None:
        idx = self._message_layout.count() - 1  # before stretch
        self._message_layout.insertWidget(max(idx, 0), bubble)

    def _add_user_message(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})
        bubble = MessageBubble("user", text)
        self._insert_bubble(bubble)
        self._scroll_to_bottom()

    def _add_system_message(self, text: str) -> None:
        bubble = MessageBubble("system", text)
        self._insert_bubble(bubble)
        self._scroll_to_bottom()

    def _add_error_message(self, text: str) -> None:
        bubble = MessageBubble("error", text)
        self._insert_bubble(bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(20, lambda: self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        ))
