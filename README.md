<p align="center">
  <img src="openclass.ico" width="96" height="96" alt="OpenClass Logo">
</p>

<h1 align="center">OpenClass — 教师课堂工具箱</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-6.6%2B-green?logo=qt" alt="PySide6">
  <img src="https://img.shields.io/badge/qfluentwidgets-1.5%2B-purple" alt="qfluentwidgets">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/version-2.0.0-brightgreen" alt="Version">
</p>

<p align="center">
  一款面向教师的 Windows 桌面工具箱，集成课堂互动、电教管理、AI 辅助与系统运维功能。<br>
  基于 PySide6 + qfluentwidgets 构建，触控大屏友好，支持深色/浅色主题切换。
</p>

---

## 功能概览

### 实用课堂

| 工具 | 说明 |
|------|------|
| 随机点名 | 老虎机动效滚动抽取，支持排除已点 + 空格键触发 |
| 全屏计时器 | 正计时 / 倒计时，全屏超大数字 + 铃声提醒 |
| 批注白板 | 半透明全屏画布，触摸 / 数位笔 / 鼠标涂鸦 |
| **课程表悬浮窗** | 桌面置顶悬浮窗，磨砂背景，当前课程高亮闪烁，可拖拽/收起 |
| 视频播放 | VLC 内核视频播放器，播放/暂停/全屏/播放列表 |
| 音频播放 | 本地音乐播放器，QMediaPlayer + 播放列表 + 进度控制 |
| 解压工具 | 多格式解压 (7z/ZIP/RAR)，密码支持，QThread 异步 |
| 音频转换 | 音频格式批量转换 (MP3/WAV/FLAC/OGG)，pydub + FFmpeg |

### 插件中心

| 插件 | 说明 |
|------|------|
| 函数几何画板 | pyqtgraph 数学函数可视化，多函数叠加绘制 |
| 符号计算器 | SymPy 符号运算，表达式求值/化简/微积分 |
| 电子课程表 | JSON 持久化周课程表，桌面悬浮窗显示 |

> 插件系统支持：一键导入 `.zip` 插件包、启用/禁用开关、卸载管理、完整日志追踪。

### 电教工具

| 工具 | 说明 |
|------|------|
| KMS 激活 | KMS 批量激活 + HWID 永久激活，五步顺序执行 + 实时日志 |
| 系统信息 | 真实硬件采集（CPU/内存/磁盘），进度条可视化，注册表读取 |
| 网络测速 | 测试当前网络上下行速度与延迟（敬请期待） |
| 屏幕录制 | 录制课堂屏幕内容保存为视频文件（敬请期待） |

### AI Agent

| 功能 | 说明 |
|------|------|
| 多模型对话 | SSE 流式输出，支持 OpenAI 兼容 API，自定义供应商 |
| 会话管理 | 历史会话分组（今天/昨天/更早），持久化存储 |
| 键鼠代理 | Agent 控制键盘鼠标执行桌面操作 |
| 文件解析 | 拖放 PDF / DOCX 文件，自动提取文本注入上下文 |

### 设置

| 功能 | 说明 |
|------|------|
| 主题切换 | 深色 / 浅色 / 护眼绿 |
| API 配置 | 加密存储 AI 供应商密钥 (AES) |
| 班级管理 | 班级/学生名单增删改查，Excel 导入导出 |
| 插件管理 | 表格形式查看已安装插件，支持卸载 |
| 日志管理 | 分级日志记录，支持按级别筛选与导出 |

---

## 技术栈

| 类别 | 技术 |
|------|------|
| UI 框架 | PySide6 (Qt for Python) |
| 组件库 | qfluentwidgets（优先）/ 纯 PySide6 降级 |
| 数据库 | SQLite (WAL 模式) |
| 加密 | AES-CBC + PBKDF2 密钥派生 |
| 插件系统 | `plugin.json` 清单 + `importlib` 动态加载 + 完整生命周期管理 |
| 多媒体 | python-vlc (视频)、QMediaPlayer (音频)、pydub (音频转换) |
| 压缩 | py7zr / zipfile / rarfile |
| 数学 | pyqtgraph (函数绘图)、SymPy (符号计算) |
| 系统调用 | ctypes Win32 API / psutil / winreg |
| 文档解析 | PyPDF2, python-docx |
| 打包 | PyInstaller (--onefile) + Inno Setup 6 |

---

## 快速开始

### 环境要求

- Windows 10/11 (64-bit)
- Python 3.10 及以上
- **VLC 媒体播放器**（视频播放功能需要，[下载地址](https://www.videolan.org/vlc/)）
- **FFmpeg**（音频转换功能需要）

### 安装依赖

```bash
git clone https://github.com/HMUG12/OpenClass.git
cd OpenClass
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

首次启动会显示 Splash 加载动画，自动初始化数据库和配置文件。

---

## 插件系统

### 插件规范

每个插件是一个独立文件夹，包含 `plugin.json` 清单和 `main.py` 入口：

```json
{
  "id": "my_plugin",
  "name": "我的插件",
  "version": "1.0.0",
  "author": "作者名",
  "description": "插件描述",
  "icon": "🔧",
  "main": "main.py",
  "class": "MyPluginWidget"
}
```

`main.py` 中导出 `PluginWidget(QWidget)` 类，可选提供 `back_requested` 信号返回启动台。

### 安装插件

1. 将插件文件夹打包为 `.zip`
2. 在插件中心点击「导入插件」
3. 选择 `.zip` 文件即可自动安装

---

## 项目结构

```
OpenClass/
├── main.py                 # 入口文件
├── requirements.txt        # Python 依赖
├── build.py                # PyInstaller 一键打包脚本
├── setup.iss               # Inno Setup 安装包脚本
├── openclass.ico           # 应用图标
├── app/
│   ├── main_window.py      # 主窗口（FluentWindow / QMainWindow 双模式）
│   ├── application.py      # 全局应用单例 + 启动流程
│   ├── splash_screen.py    # Splash 加载动画
│   ├── database/           # SQLite 数据库 + 加密
│   │   ├── db_manager.py   # 连接池 & CRUD
│   │   ├── crypto.py       # AES 加密/解密
│   │   └── init.sql        # 建表语句
│   ├── utils/
│   │   ├── resource.py     # PyInstaller _MEIPASS 路径兼容
│   │   ├── theme_manager.py# 主题切换 + QSS 加载
│   │   ├── signal_bus.py   # 全局信号总线
│   │   ├── config.py       # 配置管理
│   │   └── plugin_manager.py # 插件生命周期管理
│   └── views/
│       ├── classroom/      # 实用课堂
│       │   ├── launcher_view.py    # 工具卡片启动台
│       │   ├── random_picker.py    # 随机点名
│       │   ├── fullscreen_timer.py # 全屏计时器
│       │   ├── whiteboard.py       # 批注白板
│       │   └── schedule_float.py   # 课程表悬浮窗
│       ├── av_tools/       # 电教工具
│       │   ├── launcher_view.py
│       │   ├── kms_activation_view.py
│       │   └── system_info_view.py
│       ├── agent/          # AI Agent
│       │   └── agent_page.py
│       ├── plugin_center/  # 插件中心
│       │   ├── plugin_center.py    # 插件网格 + 导入
│       │   └── plugin_card.py     # 插件卡片组件
│       └── settings/       # 设置页面
│           ├── settings_page.py
│           └── log_page.py
├── plugins/                # 插件目录
│   ├── function_plotter/   # 函数几何画板
│   ├── symbolic_calc/      # 符号计算器
│   ├── schedule/           # 电子课程表
│   ├── extractor/          # 解压工具
│   ├── video_player/       # 视频播放器
│   ├── audio_player/       # 音频播放器
│   └── audio_converter/    # 音频格式转换
├── data/                   # 运行时数据（自动生成）
│   ├── openclass.db        # SQLite 数据库
│   └── app_config.json     # 用户偏好配置
└── resources/              # 静态资源
    └── dark_theme.qss      # 深色主题样式
```

---

## 打包部署

### 生成 exe

```bash
# 一键打包（自动清理 + 排除冲突模块）
python build.py
```

> **注意**：PyInstaller 分析阶段需要 5-15 分钟，请耐心等待。必须在普通 PowerShell/CMD 中运行（非管理员终端）。

产物：`dist/OpenClass.exe`（约 100-200 MB 单文件）

### 生成安装包

需安装 [Inno Setup 6](https://jrsoftware.org/isdl.php)，然后执行：

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss
```

产物：`OpenClass_Setup.exe`（安装到 `Program Files\OpenClass`，自动创建桌面 + 开始菜单快捷方式）

---

## 常见问题

**Q: 启动后闪退？**
A: 确保 Python 3.10+ 且已安装所有依赖：`pip install -r requirements.txt`

**Q: 视频播放器提示"VLC 未安装"？**
A: 前往 [videolan.org](https://www.videolan.org/vlc/) 下载安装 VLC，安装时勾选「添加到系统 PATH」，重启 OpenClass 即可。

**Q: 系统信息显示不全？**
A: 安装 psutil：`pip install psutil`。若无 psutil，组件会降级使用 ctypes Win32 API 仍可显示大部分信息。

**Q: AI Agent 连接失败？**
A: 进入「设置」页面，配置有效的 API 地址与密钥。支持 OpenAI 兼容接口。

**Q: 深色主题异常？**
A: 检查 `resources/dark_theme.qss` 文件是否存在。如缺失，系统会自动降级使用内联样式。

**Q: 插件导入失败？**
A: 确保插件 `.zip` 包内包含有效的 `plugin.json` 和 `main.py`，且清单中 `id` 字段不与其他插件重复。

---

## 更新日志

### v2.0.0 (2026-06)
- **新增**插件系统：`plugin.json` 规范 + `PluggableManager` + 插件中心（导入/启用/卸载/日志）
- **新增**7 个插件：函数几何画板、符号计算器、电子课程表、解压工具、视频播放器、音频播放器、音频转换
- **新增**课程表桌面悬浮窗：磨砂背景、置顶显示、可拖拽、收起/展开、当前课程高亮闪烁
- **修复**UI 重叠与闪烁：`setParent(None)` 彻底断开 + `setUpdatesEnabled` 防闪烁
- **新增**PyInstaller 打包兼容：`_MEIPASS` 路径拆分（只读资源 vs 可写数据）

### v1.0.0 (2026-05)
- 初始版本：随机点名、全屏计时器、批注白板、KMS 激活、系统信息、AI Agent、设置页面

---

## 许可证

MIT License

---

<p align="center">
  Made with PySide6 & qfluentwidgets
</p>
