"""
🔑 激活助手 — KMS 批量激活 / HWID 永久激活

- QButtonGroup 切换两种模式（KMS / HWID）
- KMS 五步顺序执行 + 状态标签实时反馈
- HWID 一键激活 (PowerShell + irm)
- QThread 后台执行，不卡 UI
- ctypes ShellExecuteW 管理员提权
- 底部公共日志区 QTextEdit
"""
from __future__ import annotations

import logging
import subprocess
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFrame, QDialog, QMessageBox, QApplication,
    QSizePolicy, QStackedWidget, QButtonGroup, QRadioButton,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

logger = logging.getLogger("OpenClass")


# ═══════════════════════════════════════════════════════════════
# 后台命令执行线程
# ═══════════════════════════════════════════════════════════════

class _CmdWorker(QThread):
    """后台线程 — 以管理员身份执行 CMD 命令，捕获输出。"""
    output_line = Signal(str)
    finished_signal = Signal(int)

    def __init__(self, command: str, admin: bool = True, parent=None):
        super().__init__(parent)
        self._command = command
        self._admin = admin

    def run(self) -> None:
        try:
            if not self._admin:
                self._run_subprocess()
            else:
                self._run_admin_shell_execute()
        except Exception as e:
            self.output_line.emit(f"[错误] {e}")
            logger.error("CmdWorker exception: %s", e)
            self.finished_signal.emit(1)

    def _run_subprocess(self) -> None:
        """普通 subprocess（不需要管理员提权）。"""
        proc = subprocess.Popen(
            self._command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="gbk",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in proc.stdout:
            self.output_line.emit(line.rstrip())
        proc.wait()
        self.finished_signal.emit(proc.returncode)

    def _run_admin_shell_execute(self) -> None:
        """通过 ShellExecuteW + runas 以管理员身份运行命令并捕获输出。"""
        import ctypes
        import tempfile
        import os

        # 将命令写入临时 bat 文件，用 > 重定向输出以便捕获
        fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="kms_oc_")
        out_path = bat_path + ".out"
        try:
            with os.fdopen(fd, "w", encoding="gbk") as f:
                f.write("@echo off\r\n")
                f.write(f'{self._command} > "{out_path}" 2>&1\r\n')

            self.output_line.emit("正在请求管理员权限...")
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", bat_path, None, None, 0,  # SW_HIDE
            )
            if ret <= 32:
                self.output_line.emit(f"[错误] 提权失败 (错误码: {ret})，请以管理员身份运行 OpenClass")
                self.finished_signal.emit(1)
                return

            # 轮询等待输出文件
            for _ in range(60):
                time.sleep(1)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    time.sleep(1)  # 再等1秒让写入完成
                    break
            else:
                self.output_line.emit("[提示] 命令已在管理员窗口中执行，请查看弹出的 CMD 窗口。")
                self.finished_signal.emit(0)
                return

            with open(out_path, "r", encoding="gbk", errors="replace") as f:
                for line in f:
                    self.output_line.emit(line.rstrip())
            self.finished_signal.emit(0)
        except PermissionError:
            self.output_line.emit("[错误] 权限不足，请以管理员身份运行 OpenClass")
            logger.error("Permission denied during admin execution")
            self.finished_signal.emit(1)
        finally:
            # 延迟清理临时文件
            def _cleanup():
                time.sleep(3)
                for p in (bat_path, out_path):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            import threading
            threading.Thread(target=_cleanup, daemon=True).start()


# ═══════════════════════════════════════════════════════════════
# 确认对话框
# ═══════════════════════════════════════════════════════════════

class _ConfirmDialog(QDialog):
    """安全确认弹窗 — 触控适配大按钮。"""

    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ 安全确认")
        self.setMinimumSize(460, 280)
        self.resize(560, 340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            QDialog { background: #1e1e2e; border: 2px solid #f59e0b; border-radius: 16px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 20)
        layout.setSpacing(16)

        warn = QLabel(title)
        warn.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        warn.setStyleSheet("color: #f59e0b; border: none;")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setFont(QFont("Microsoft YaHei", 14))
        body_label.setStyleSheet("color: #e0e0e0; border: none; line-height: 1.6;")
        body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(body_label)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        cancel = QPushButton("取消")
        cancel.setMinimumHeight(48)
        cancel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cancel.setStyleSheet("""
            QPushButton { font-size:16px; font-weight:bold; background:rgba(128,128,128,0.15);
                color:#a0a0a0; border:none; border-radius:10px; padding:12px 28px; }
            QPushButton:hover { background:rgba(128,128,128,0.25); }
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel, stretch=1)

        confirm = QPushButton("确认执行")
        confirm.setMinimumHeight(48)
        confirm.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        confirm.setStyleSheet("""
            QPushButton { font-size:16px; font-weight:bold; background:#16a34a; color:#FFF;
                border:none; border-radius:10px; padding:12px 32px; }
            QPushButton:hover { background:#15803d; }
        """)
        confirm.clicked.connect(self.accept)
        btn_row.addWidget(confirm, stretch=1)

        layout.addLayout(btn_row)


# ═══════════════════════════════════════════════════════════════
# 激活助手 — 主界面
# ═══════════════════════════════════════════════════════════════

# ── KMS 五步定义 ──
KMS_STEPS = [
    ("卸载原密钥", "slmgr /upk"),
    ("安装新密钥", ""),       # 动态填充: slmgr /ipk {key}
    ("设置服务器", ""),        # 动态填充: slmgr /skms {host}
    ("执行激活",   "slmgr /ato"),
    ("检查状态",   "slmgr /xpr"),
]

KMS_DEFAULT_KEY = "W269N-WFGWX-YVC9B-4J6C9-T83GX"
KMS_DEFAULT_HOST = "zh.us.to"


class KMSActivationView(QWidget):
    """激活助手 — KMS 批量激活 / HWID 永久激活。"""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("kmsActivationView")
        self._worker: _CmdWorker | None = None
        self._running = False

        self._build_ui()
        self.setMinimumSize(600, 500)

    # ═══════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # ── 根布局：Expanding 策略，自适应容器尺寸 ──
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 20, 48, 32)
        layout.setSpacing(14)

        # ── 返回按钮 ──
        back_btn = QPushButton("←  返回工具列表")
        back_btn.setMinimumHeight(48)
        back_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton { font-size:18px; font-weight:bold; background:rgba(128,128,128,0.08);
                color:#6366f1; border:1px solid rgba(128,128,128,0.15); border-radius:12px; padding:12px 28px; }
            QPushButton:hover { background:rgba(99,102,241,0.10); border-color:rgba(99,102,241,0.30); }
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_btn)

        # ── 标题 ──
        title = QLabel("🔑  激活助手")
        title.setFont(QFont("Microsoft YaHei", 26, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(title)

        # ── 模式切换 ──
        mode_widget = self._build_mode_switcher()
        layout.addWidget(mode_widget)

        # ── 模式页面堆栈 ──
        self._mode_stack = QStackedWidget()
        self._mode_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._kms_page = self._build_kms_page()
        self._hwid_page = self._build_hwid_page()

        self._mode_stack.addWidget(self._kms_page)   # 0
        self._mode_stack.addWidget(self._hwid_page)   # 1
        layout.addWidget(self._mode_stack, stretch=1)

        # ── 分割线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(128,128,128,0.12);")
        sep.setMinimumHeight(2)
        sep.setMaximumHeight(2)
        layout.addWidget(sep)

        # ── 日志区 ──
        log_label = QLabel("📋 执行日志")
        log_label.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.DemiBold))
        log_label.setStyleSheet("border: none;")
        layout.addWidget(log_label)

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setMinimumHeight(150)
        self._log_output.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._log_output.setStyleSheet("""
            QTextEdit {
                font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: 14px; padding: 12px 14px;
                border: 1px solid rgba(128,128,128,0.25);
                border-radius: 10px;
                background: rgba(0,0,0,0.03);
                color: #334155;
            }
        """)
        layout.addWidget(self._log_output, stretch=1)

        # ── 清空日志 ──
        clear_btn = QPushButton("清空日志")
        clear_btn.setMinimumSize(100, 32)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        clear_btn.setStyleSheet("""
            QPushButton { font-size:13px; background:rgba(128,128,128,0.08); color:#888;
                border:none; border-radius:8px; }
            QPushButton:hover { background:rgba(128,128,128,0.18); }
        """)
        clear_btn.clicked.connect(self._log_output.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

    # ═══════════════════════════════════════════════════════════
    # 模式切换
    # ═══════════════════════════════════════════════════════════

    def _build_mode_switcher(self) -> QWidget:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        texts = ["KMS 批量激活", "HWID 永久激活"]
        for i, text in enumerate(texts):
            btn = QRadioButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet("""
                QRadioButton { font-size:16px; font-weight:600; padding:10px 24px;
                    border:1px solid rgba(128,128,128,0.20); border-radius:10px;
                    margin: 3px; }
                QRadioButton:hover { border-color:#6366f1; background:rgba(99,102,241,0.05); }
                QRadioButton:checked { color:#6366f1; border-color:#6366f1; background:rgba(99,102,241,0.08); }
            """)
            btn.setChecked(i == 0)
            self._mode_group.addButton(btn)
            h.addWidget(btn, stretch=1)

        h.addStretch()
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        return container

    def _on_mode_changed(self, btn) -> None:
        idx = 0 if "KMS" in btn.text() else 1
        self._mode_stack.setCurrentIndex(idx)

    # ═══════════════════════════════════════════════════════════
    # KMS 页面
    # ═══════════════════════════════════════════════════════════

    def _build_kms_page(self) -> QWidget:
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # ── 产品密钥 ──
        key_label = QLabel("产品密钥")
        key_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.DemiBold))
        key_label.setStyleSheet("border: none;")
        layout.addWidget(key_label)

        # 输入框行 — QHBoxLayout 保证输入框拉伸填满
        key_row = QHBoxLayout()
        key_row.setSpacing(12)
        self._key_input = QLineEdit()
        self._key_input.setText(KMS_DEFAULT_KEY)
        self._key_input.setMinimumHeight(35)
        self._key_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._key_input.setStyleSheet("""
            QLineEdit { font-size:16px; padding:6px 14px;
                border:1px solid rgba(128,128,128,0.30); border-radius:8px; }
            QLineEdit:focus { border-color:#6366f1; }
        """)
        key_row.addWidget(self._key_input, stretch=1)
        layout.addLayout(key_row)

        # ── KMS 服务器 ──
        host_label = QLabel("KMS 服务器地址")
        host_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.DemiBold))
        host_label.setStyleSheet("border: none;")
        layout.addWidget(host_label)

        # 输入框行
        host_row = QHBoxLayout()
        host_row.setSpacing(12)
        self._host_input = QLineEdit()
        self._host_input.setText(KMS_DEFAULT_HOST)
        self._host_input.setMinimumHeight(35)
        self._host_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._host_input.setStyleSheet("""
            QLineEdit { font-size:16px; padding:6px 14px;
                border:1px solid rgba(128,128,128,0.30); border-radius:8px; }
            QLineEdit:focus { border-color:#6366f1; }
        """)
        host_row.addWidget(self._host_input, stretch=1)
        layout.addLayout(host_row)

        # ── 激活按钮 ──
        self._kms_start_btn = QPushButton("⚡ 开始 KMS 激活")
        self._kms_start_btn.setMinimumHeight(56)
        self._kms_start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._kms_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kms_start_btn.setStyleSheet("""
            QPushButton { font-size:20px; font-weight:bold; background:#2563EB; color:#FFF;
                border:none; border-radius:14px; padding:8px; }
            QPushButton:hover { background:#1D4ED8; }
            QPushButton:pressed { background:#1E40AF; }
            QPushButton:disabled { background:rgba(128,128,128,0.15); color:rgba(128,128,128,0.40); }
        """)
        self._kms_start_btn.clicked.connect(self._start_kms)
        layout.addWidget(self._kms_start_btn)

        # ── 五步状态标签（垂直排列，可自动换行） ──
        self._kms_step_labels: list[QLabel] = []
        for step_name, _ in KMS_STEPS:
            lbl = QLabel(f"  {step_name}  ")
            lbl.setFont(QFont("Microsoft YaHei", 12))
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            lbl.setStyleSheet("""
                color: #94a3b8; border:1px solid rgba(128,128,128,0.15);
                border-radius:6px; padding:4px 10px;
            """)
            layout.addWidget(lbl)
            self._kms_step_labels.append(lbl)

        layout.addStretch()
        return page

    # ═══════════════════════════════════════════════════════════
    # HWID 页面
    # ═══════════════════════════════════════════════════════════

    def _build_hwid_page(self) -> QWidget:
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(14)

        desc = QLabel("适用于 Windows 10/11 专业版/个人版，一键永久激活（需联网）")
        desc.setWordWrap(True)
        desc.setFont(QFont("Microsoft YaHei", 14))
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        desc.setStyleSheet("color: #64748b; border: none; line-height: 1.6;")
        layout.addWidget(desc)

        self._hwid_start_btn = QPushButton("✅ 执行 HWID 永久激活")
        self._hwid_start_btn.setMinimumHeight(56)
        self._hwid_start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hwid_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hwid_start_btn.setStyleSheet("""
            QPushButton { font-size:20px; font-weight:bold; background:#16a34a; color:#FFF;
                border:none; border-radius:14px; padding:8px; }
            QPushButton:hover { background:#15803d; }
            QPushButton:pressed { background:#166534; }
            QPushButton:disabled { background:rgba(128,128,128,0.15); color:rgba(128,128,128,0.40); }
        """)
        self._hwid_start_btn.clicked.connect(self._start_hwid)
        layout.addWidget(self._hwid_start_btn)

        layout.addStretch()
        return page

    # ═══════════════════════════════════════════════════════════
    # 按钮状态管理
    # ═══════════════════════════════════════════════════════════

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._running = not enabled
        self._kms_start_btn.setEnabled(enabled)
        self._hwid_start_btn.setEnabled(enabled)
        for btn in self._mode_group.buttons():
            btn.setEnabled(enabled)

    # ═══════════════════════════════════════════════════════════
    # KMS 激活流程
    # ═══════════════════════════════════════════════════════════

    def _start_kms(self) -> None:
        key = self._key_input.text().strip()
        host = self._host_input.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入产品密钥。")
            return
        if not host:
            QMessageBox.warning(self, "提示", "请输入 KMS 服务器地址。")
            return

        dlg = _ConfirmDialog(
            "⚠️ 确认 KMS 激活",
            f"产品密钥: {key}\nKMS 服务器: {host}\n\n请确保您拥有合法的 Windows 授权。"
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._log("用户取消了 KMS 激活操作。")
            return

        self._set_buttons_enabled(False)
        self._log_output.clear()
        # 重置步骤标签
        for lbl in self._kms_step_labels:
            lbl.setStyleSheet("color:#94a3b8; border:1px solid rgba(128,128,128,0.15); border-radius:6px; padding:4px 10px;")

        self._log("=" * 50)
        self._log(f"KMS 激活开始 — 服务器: {host}")
        self._log("=" * 50)

        self._kms_step = 0
        self._run_kms_step()

    def _run_kms_step(self) -> None:
        """执行当前步骤，成功则前进到下一步。"""
        if self._kms_step >= len(KMS_STEPS):
            self._log("=" * 50)
            self._log("所有步骤执行完毕。请查看上方输出确认结果。")
            self._set_buttons_enabled(True)
            return

        step_name, cmd_template = KMS_STEPS[self._kms_step]
        key = self._key_input.text().strip()
        host = self._host_input.text().strip()

        # 动态构造命令
        if self._kms_step == 1:
            cmd = f"slmgr /ipk {key}"
        elif self._kms_step == 2:
            cmd = f"slmgr /skms {host}"
        else:
            cmd = cmd_template

        self._log(f"\n── 步骤 {self._kms_step + 1}: {step_name} ──")
        self._log(f"执行: {cmd}")

        self._worker = _CmdWorker(cmd, admin=True, parent=self)
        self._worker.output_line.connect(self._log)
        self._worker.finished_signal.connect(self._on_kms_step_done)
        self._worker.start()

    def _on_kms_step_done(self, returncode: int) -> None:
        """单步完成回调 — 更新标签状态，决定下一步。"""
        step_name = KMS_STEPS[self._kms_step][0]
        lbl = self._kms_step_labels[self._kms_step]

        if returncode == 0:
            lbl.setText(f"  ✅ {step_name}  ")
            lbl.setStyleSheet("color:#16a34a; border:1px solid #16a34a; border-radius:6px; padding:4px 10px;")
            self._log(f"[完成] {step_name}")
            self._kms_step += 1
            self._run_kms_step()
        else:
            lbl.setText(f"  ❌ {step_name}  ")
            lbl.setStyleSheet("color:#EF4444; border:1px solid #EF4444; border-radius:6px; padding:4px 10px;")
            self._log(f"[失败] {step_name} — 返回码: {returncode}")
            # 标记后续步骤为跳过
            for i in range(self._kms_step + 1, len(KMS_STEPS)):
                self._kms_step_labels[i].setStyleSheet(
                    "color:rgba(128,128,128,0.30); border:1px solid rgba(128,128,128,0.10); border-radius:6px; padding:4px 10px;"
                )
            self._set_buttons_enabled(True)

    # ═══════════════════════════════════════════════════════════
    # HWID 激活流程
    # ═══════════════════════════════════════════════════════════

    def _start_hwid(self) -> None:
        dlg = _ConfirmDialog(
            "⚠️ 确认 HWID 永久激活",
            "此操作将从网络下载并执行 Microsoft Activation Scripts。\n"
            "请确保网络连接正常且拥有合法的 Windows 授权。"
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._log("用户取消了 HWID 激活操作。")
            return

        self._set_buttons_enabled(False)
        self._log_output.clear()
        self._log("=" * 50)
        self._log("HWID 永久激活开始")
        self._log("=" * 50)

        # 非管理员路径：尝试提权
        self._log("正在检测管理员权限...")
        hwid_cmd = 'echo 1 | powershell -Command "irm https://get.activated.win | iex"'

        # 尝试通过 admin bat 执行
        worker = _CmdWorker(hwid_cmd, admin=True, parent=self)
        worker.output_line.connect(self._log)
        worker.finished_signal.connect(self._on_hwid_done)
        worker.start()
        self._worker = worker

    def _on_hwid_done(self, returncode: int) -> None:
        """HWID 执行完成。"""
        if returncode != 0:
            self._log("\n[提示] 无法自动完成 HWID 激活。")
            self._log("请以管理员身份打开 PowerShell，手动粘贴执行以下命令：")
            self._log('echo 1 | powershell -Command "irm https://get.activated.win | iex"')
            # 复制到剪贴板
            QApplication.clipboard().setText(hwid_cmd := 'irm https://get.activated.win | iex')
            self._log("\n(完整命令已复制到剪贴板)")
        else:
            self._log("\n[完成] HWID 激活命令已执行，请查看输出确认结果。")
        self._log("=" * 50)
        self._set_buttons_enabled(True)

    # ═══════════════════════════════════════════════════════════
    # 日志
    # ═══════════════════════════════════════════════════════════

    def _log(self, text: str) -> None:
        self._log_output.append(text)
        bar = self._log_output.verticalScrollBar()
        bar.setValue(bar.maximum())
