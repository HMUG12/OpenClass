"""
📊 系统信息 — 真实硬件信息采集与展示

- 三组卡片布局：操作系统 / 硬件 / 磁盘
- 使用 ctypes + psutil 读取真实数据
- 内存/磁盘进度条可视化
- 刷新按钮 + 异常安全降级
"""
from __future__ import annotations

import ctypes
import logging
import os
import platform
import subprocess
from ctypes import wintypes
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGroupBox, QGridLayout, QProgressBar,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

logger = logging.getLogger("OpenClass")

# ── psutil 可选依赖 ──
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    psutil = None       # type: ignore

# ── qfluentwidgets 可选依赖 ──
try:
    from qfluentwidgets import SettingCardGroup
    _HAS_FLUENT = True
except ImportError:
    _HAS_FLUENT = False


# ═══════════════════════════════════════════════════════════════
# 辅助：创建分组容器
# ═══════════════════════════════════════════════════════════════

def _make_group(title: str, parent: QWidget | None = None) -> tuple[QWidget, QVBoxLayout]:
    """创建 SettingCardGroup / QGroupBox 分组，返回 (容器, 内部layout)。"""
    if _HAS_FLUENT:
        group = SettingCardGroup(title, parent)
        gl = group.vBoxLayout
        gl.setSpacing(0)
        return group, gl
    else:
        group = QGroupBox(title, parent)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 15pt; font-weight: 600;
                border: 1px solid rgba(128,128,128,0.15);
                border-radius: 12px; margin-top: 14px;
                padding: 24px 20px 20px 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 16px; padding: 0 8px;
            }
        """)
        gl = QVBoxLayout(group)
        gl.setSpacing(10)
        return group, gl


# ═══════════════════════════════════════════════════════════════
# 辅助：单行信息 (标签 16pt | 值 18pt 加粗)
# ═══════════════════════════════════════════════════════════════

def _info_row(label: str, value: str, selectable: bool = True) -> QWidget:
    """返回 label | value 的水平行 widget。"""
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(8, 6, 8, 6)
    h.setSpacing(12)

    lbl = QLabel(label)
    lbl.setFixedWidth(100)
    lbl.setStyleSheet("font-size: 14px; color: #64748b; border: none; font-weight: 500;")
    h.addWidget(lbl)

    val = QLabel(value)
    val.setWordWrap(True)
    val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    val.setStyleSheet("font-size: 16px; font-weight: 700; border: none; color: #1e293b;")
    if selectable:
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    h.addWidget(val, stretch=1)
    return row


# ═══════════════════════════════════════════════════════════════
# 系统信息数据采集
# ═══════════════════════════════════════════════════════════════

def _get_os_display_name() -> str:
    """获取 Windows 友好显示名称，如 'Windows 10 专业版 22H2'。"""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        ) as key:
            product = winreg.QueryValueEx(key, "ProductName")[0]
            build = winreg.QueryValueEx(key, "CurrentBuild")[0]
            # DisplayVersion 或 ReleaseId
            try:
                ver = winreg.QueryValueEx(key, "DisplayVersion")[0]
            except OSError:
                try:
                    ver = winreg.QueryValueEx(key, "ReleaseId")[0]
                except OSError:
                    ver = ""
            if ver:
                return f"{product} {ver}"
            return f"{product} (Build {build})"
    except Exception:
        return f"{platform.system()} {platform.release()}"


def _get_architecture() -> str:
    """64位 或 32位。"""
    import struct
    return f"{struct.calcsize('P') * 8} 位"


def _get_install_time() -> str:
    """从注册表读取系统安装时间。"""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        ) as key:
            ts = winreg.QueryValueEx(key, "InstallDate")[0]
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.warning("Failed to read install date: %s", e)
        return "无法获取系统安装时间"


def _get_cpu_name() -> str:
    """获取 CPU 型号。优先 psutil，其次 wmic，最后 registry。"""
    if _HAS_PSUTIL:
        try:
            freq = psutil.cpu_freq()
            freq_str = f" @ {freq.max:.0f} MHz" if freq and freq.max else ""
            name = platform.processor()
            if not name or name == "Intel64 Family 6 Model ...":
                # windows 上 platform.processor() 有时返回不完整
                import winreg
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                ) as key:
                    name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
            return f"{name}{freq_str}"
        except Exception:
            pass

    # 降级：注册表
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0]
    except Exception:
        pass

    # 最终降级：wmic
    try:
        result = subprocess.run(
            'wmic cpu get Name /format:list',
            shell=True, capture_output=True, text=True,
            encoding="gbk", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in result.stdout.splitlines():
            if "=" in line and line.strip():
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return "未知 CPU"


def _get_cpu_cores() -> str:
    """逻辑核心数 / 物理核心数。"""
    if _HAS_PSUTIL:
        try:
            logical = psutil.cpu_count(logical=True)
            physical = psutil.cpu_count(logical=False)
            if physical and logical:
                return f"{physical} 核 {logical} 线程"
            return f"{logical} 逻辑处理器"
        except Exception:
            pass
    try:
        import os as _os
        return f"{_os.cpu_count()} 逻辑处理器"
    except Exception:
        return "—"


def _get_memory_info() -> tuple[float, float, float]:
    """返回 (总内存GB, 可用GB, 使用百分比)。psutil 优先，ctypes 降级。"""
    if _HAS_PSUTIL:
        try:
            mem = psutil.virtual_memory()
            return mem.total / (1024**3), mem.available / (1024**3), mem.percent
        except Exception:
            pass

    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
            ]
        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        return (
            mem.ullTotalPhys / (1024**3),
            mem.ullAvailPhys / (1024**3),
            float(mem.dwMemoryLoad),
        )
    except Exception:
        return 0, 0, 0


def _get_disk_info() -> tuple[float, float, float] | None:
    """返回 C: (总容量GB, 可用GB, 使用百分比)。psutil 优先。"""
    if _HAS_PSUTIL:
        try:
            usage = psutil.disk_usage("C:\\")
            return usage.total / (1024**3), usage.free / (1024**3), usage.percent
        except Exception:
            pass

    try:
        free = ctypes.c_ulonglong()
        total = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            "C:\\", None, ctypes.byref(total), ctypes.byref(free),
        )
        total_gb = total.value / (1024**3)
        free_gb = free.value / (1024**3)
        used_pct = ((total.value - free.value) / max(total.value, 1)) * 100
        return total_gb, free_gb, used_pct
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# 主组件
# ═══════════════════════════════════════════════════════════════

class SystemInfoView(QWidget):
    """系统信息 — 三组卡片布局 + 进度条 + 刷新。"""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("systemInfoView")
        self.setMinimumSize(600, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._mem_progress: QProgressBar | None = None
        self._disk_progress: QProgressBar | None = None
        self._mem_value_label: QLabel | None = None
        self._disk_value_label: QLabel | None = None

        self._build_ui()
        self._refresh()

    # ═══════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 20, 48, 28)
        layout.setSpacing(20)

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
        title = QLabel("📊  系统信息")
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title.setStyleSheet("border: none;")
        layout.addWidget(title)

        # ── psutil 缺失提示 ──
        self._psutil_warning = QLabel("")
        self._psutil_warning.setWordWrap(True)
        self._psutil_warning.setStyleSheet(
            "color: #d97706; font-size: 14px; border: none; "
            "background: rgba(245,158,11,0.08); border-radius: 8px; padding: 8px 14px;"
        )
        self._psutil_warning.setVisible(False)
        layout.addWidget(self._psutil_warning)

        # ═══════════════════════════════════════════════════════
        # 分组一：操作系统
        # ═══════════════════════════════════════════════════════
        os_group, os_layout = _make_group("操作系统", content)
        self._os_name_label = self._add_data_row(os_layout, "Windows 版本", "")
        self._os_arch_label = self._add_data_row(os_layout, "系统架构", "")
        self._os_install_label = self._add_data_row(os_layout, "安装时间", "")
        layout.addWidget(os_group)

        # ═══════════════════════════════════════════════════════
        # 分组二：硬件
        # ═══════════════════════════════════════════════════════
        hw_group, hw_layout = _make_group("硬件", content)
        self._cpu_name_label = self._add_data_row(hw_layout, "CPU 型号", "")
        self._cpu_cores_label = self._add_data_row(hw_layout, "核心数", "")

        # ── 内存行：值 + 进度条 ──
        mem_row = QWidget()
        mem_h = QHBoxLayout(mem_row)
        mem_h.setContentsMargins(8, 4, 8, 4)
        mem_h.setSpacing(8)
        mem_label = QLabel("内存")
        mem_label.setFixedWidth(100)
        mem_label.setStyleSheet("font-size: 14px; color: #64748b; border: none; font-weight: 500;")
        mem_h.addWidget(mem_label)

        self._mem_value_label = QLabel("—")
        self._mem_value_label.setMinimumWidth(130)
        self._mem_value_label.setStyleSheet("font-size: 16px; font-weight: 700; border: none; color: #1e293b;")
        mem_h.addWidget(self._mem_value_label)

        self._mem_progress = QProgressBar()
        self._mem_progress.setFixedHeight(20)
        self._mem_progress.setMinimumWidth(160)
        self._mem_progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._mem_progress.setRange(0, 100)
        self._mem_progress.setValue(0)
        self._mem_progress.setTextVisible(True)
        self._mem_progress.setStyleSheet("""
            QProgressBar {
                background: rgba(128,128,128,0.10); border: none; border-radius: 10px;
                font-size: 12px; font-weight: 600; text-align: center;
            }
            QProgressBar::chunk { border-radius: 10px; }
        """)
        mem_h.addWidget(self._mem_progress, stretch=1)
        hw_layout.addWidget(mem_row)

        hw_layout.addSpacing(4)

        # ── 实时刷新提示 ──
        mem_hint = QLabel("✓ 支持实时刷新（点击右下角刷新按钮）")
        mem_hint.setStyleSheet("color: #94a3b8; font-size: 12px; border: none; padding-left: 108px;")
        hw_layout.addWidget(mem_hint)

        layout.addWidget(hw_group)

        # ═══════════════════════════════════════════════════════
        # 分组三：磁盘
        # ═══════════════════════════════════════════════════════
        disk_group, disk_layout = _make_group("磁盘", content)

        # 磁盘值 + 进度条
        disk_row = QWidget()
        disk_h = QHBoxLayout(disk_row)
        disk_h.setContentsMargins(8, 4, 8, 4)
        disk_h.setSpacing(8)
        disk_label = QLabel("C 盘")
        disk_label.setFixedWidth(100)
        disk_label.setStyleSheet("font-size: 14px; color: #64748b; border: none; font-weight: 500;")
        disk_h.addWidget(disk_label)

        self._disk_value_label = QLabel("—")
        self._disk_value_label.setMinimumWidth(150)
        self._disk_value_label.setStyleSheet("font-size: 16px; font-weight: 700; border: none; color: #1e293b;")
        disk_h.addWidget(self._disk_value_label)

        self._disk_progress = QProgressBar()
        self._disk_progress.setFixedHeight(20)
        self._disk_progress.setMinimumWidth(160)
        self._disk_progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._disk_progress.setRange(0, 100)
        self._disk_progress.setValue(0)
        self._disk_progress.setTextVisible(True)
        self._disk_progress.setStyleSheet("""
            QProgressBar {
                background: rgba(128,128,128,0.10); border: none; border-radius: 10px;
                font-size: 12px; font-weight: 600; text-align: center;
            }
            QProgressBar::chunk { border-radius: 10px; }
        """)
        disk_h.addWidget(self._disk_progress, stretch=1)
        disk_layout.addWidget(disk_row)

        layout.addWidget(disk_group)

        # ── 刷新按钮 ──
        refresh_btn = QPushButton("🔄  刷新信息")
        refresh_btn.setMinimumHeight(48)
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton { font-size:18px; font-weight:bold; background:rgba(99,102,241,0.10); color:#6366f1;
                border:1px solid rgba(99,102,241,0.25); border-radius:12px; padding:8px; }
            QPushButton:hover { background:rgba(99,102,241,0.18); }
        """)
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()
        scroll.setWidget(content)

    def _add_data_row(self, parent_layout: QVBoxLayout, label: str, initial: str) -> QLabel:
        """向分组布局添加一行 label | value，返回 value QLabel 引用。"""
        row = _info_row(label, initial)
        parent_layout.addWidget(row)
        # value label 是 row.layout().itemAt(1).widget()
        vl = row.layout().itemAt(1).widget()
        assert isinstance(vl, QLabel)
        return vl

    # ═══════════════════════════════════════════════════════════
    # 数据刷新
    # ═══════════════════════════════════════════════════════════

    def _refresh(self) -> None:
        """采集所有数据并更新 UI。"""
        if not _HAS_PSUTIL:
            self._psutil_warning.setText(
                "💡 请安装 psutil 库以获取完整硬件信息：pip install psutil"
            )
            self._psutil_warning.setVisible(True)
        else:
            self._psutil_warning.setVisible(False)

        # ── 操作系统 ──
        self._os_name_label.setText(_get_os_display_name())
        self._os_arch_label.setText(_get_architecture())
        self._os_install_label.setText(_get_install_time())

        # ── 硬件 ──
        self._cpu_name_label.setText(_get_cpu_name())
        self._cpu_cores_label.setText(_get_cpu_cores())

        # 内存
        total_gb, avail_gb, mem_pct = _get_memory_info()
        if total_gb > 0:
            self._mem_value_label.setText(f"{total_gb:.1f} GB / {avail_gb:.1f} GB 可用")
            self._mem_progress.setValue(int(mem_pct))
            self._update_progress_color(self._mem_progress, mem_pct, is_danger_threshold=85)
        else:
            self._mem_value_label.setText("—")
            self._mem_progress.setValue(0)

        # ── 磁盘 ──
        disk = _get_disk_info()
        if disk:
            total, free, used_pct = disk
            used = total - free
            self._disk_value_label.setText(f"{total:.1f} GB / {free:.1f} GB 可用")
            self._disk_progress.setValue(int(used_pct))
            self._update_progress_color(self._disk_progress, used_pct, is_danger_threshold=80)
        else:
            self._disk_value_label.setText("—")
            self._disk_progress.setValue(0)

    @staticmethod
    def _update_progress_color(bar: QProgressBar, pct: float, is_danger_threshold: float = 85) -> None:
        """根据使用率给进度条染色：低→绿，中→蓝，高→橙，危险→红。"""
        if pct >= is_danger_threshold:
            color = "#EF4444"
        elif pct >= 60:
            color = "#F59E0B"
        elif pct >= 30:
            color = "#6366F1"
        else:
            color = "#22C55E"
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(128,128,128,0.10); border: none; border-radius: 10px;
                font-size: 12px; font-weight: 600; text-align: center;
            }}
            QProgressBar::chunk {{
                background: {color}; border-radius: 10px;
            }}
        """)
