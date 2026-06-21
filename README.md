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
</p>

<p align="center">
  一款面向教师的 Windows 桌面工具箱，集成课堂互动、电教管理、AI 辅助与系统运维功能。<br>
  基于 PySide6 + qfluentwidgets 构建，触控大屏友好，支持深色/浅色主题切换。
</p>

---

## 功能概览

| 模块 | 工具 | 说明 |
|------|------|------|
| **实用课堂** | 随机点名 | 老虎机动效滚动抽取，支持排除已点 + 空格键触发 |
| | 全屏计时器 | 正计时 / 倒计时，全屏超大数字 + 铃声提醒 |
| | 批注白板 | 半透明全屏画布，触摸 / 数位笔 / 鼠标涂鸦 |
| **电教工具** | KMS 激活 | KMS 批量激活 + HWID 永久激活，五步顺序执行 + 实时日志 |
| | 系统信息 | 真实硬件采集（CPU/内存/磁盘），进度条可视化，注册表读取 |
| | 网络测速 | 测试当前网络上下行速度与延迟 |
| | 屏幕录制 | 录制课堂屏幕内容保存为视频文件 |
| **AI Agent** | 多模型对话 | SSE 流式输出，支持 OpenAI 兼容 API，自定义供应商 |
| | 会话管理 | 历史会话分组（今天/昨天/更早），持久化存储 |
| | 键鼠代理 | Agent 控制键盘鼠标执行桌面操作 |
| | 文件解析 | 拖放 PDF / DOCX 文件，自动提取文本注入上下文 |
| **设置** | 主题切换 | 深色 / 浅色 / 护眼绿，霓虹发光特效 |
| | API 配置 | 加密存储 AI 供应商密钥 (AES) |
| | 班级管理 | 班级/学生名单增删改查，Excel 导入导出 |
| | 日志管理 | 分级日志记录，支持按级别筛选与导出 |

> 标注 "网络测速" 和 "屏幕录制" 当前为敬请期待占位，后续版本实现。

---

## 技术栈

| 类别 | 技术 |
|------|------|
| UI 框架 | PySide6 (Qt for Python) |
| 组件库 | qfluentwidgets（优先）/ 纯 PySide6 降级 |
| 数据库 | SQLite (WAL 模式) |
| 加密 | AES-CBC + PBKDF2 密钥派生 |
| 系统调用 | ctypes Win32 API / psutil / winreg |
| 文档解析 | PyPDF2, python-docx |
| 打包 | PyInstaller + Inno Setup |

---

## 快速开始

### 环境要求

- Windows 10/11 (64-bit)
- Python 3.10 及以上

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

## 项目结构

```
OpenClass/
├── main.py                 # 入口文件
├── requirements.txt        # Python 依赖
├── build.py                # PyInstaller 一键打包脚本
├── setup.iss               # Inno Setup 安装包脚本
├── openclass.ico           # 应用图标
├── app/
│   ├── main_window.py      # 主窗口（FluentWindow / QMainWindow）
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
│   │   └── config.py       # 配置管理
│   └── views/
│       ├── classroom/      # 实用课堂
│       │   ├── launcher_view.py
│       │   ├── random_picker.py
│       │   ├── fullscreen_timer.py
│       │   └── whiteboard.py
│       ├── av_tools/       # 电教工具
│       │   ├── launcher_view.py
│       │   ├── kms_activation_view.py
│       │   └── system_info_view.py
│       ├── agent/          # AI Agent
│       │   └── agent_page.py
│       └── settings/       # 设置页面
│           ├── settings_page.py
│           └── log_page.py
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

# 或手动执行
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name=OpenClass --icon=openclass.ico ^
  --add-data="app;app" ^
  --add-data="resources;resources" ^
  --add-data="data;data" ^
  --hidden-import=qfluentwidgets ^
  --hidden-import=PySide6.QtXml ^
  --hidden-import=PySide6.QtNetwork ^
  --exclude-module=PyQt5 ^
  --exclude-module=PyQt5.QtCore ^
  --exclude-module=PyQt5.QtGui ^
  --exclude-module=PyQt5.QtWidgets ^
  --exclude-module=torch ^
  --exclude-module=torchvision ^
  main.py
```

产物：`dist/OpenClass.exe`

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

**Q: 系统信息显示不全？**
A: 安装 psutil：`pip install psutil`。若无 psutil，组件会降级使用 ctypes Win32 API 仍可显示大部分信息。

**Q: AI Agent 连接失败？**
A: 进入"设置"页面，配置有效的 API 地址与密钥。支持 OpenAI 兼容接口。

**Q: 深色主题异常？**
A: 检查 `resources/dark_theme.qss` 文件是否存在。如缺失，系统会自动降级使用内联样式。

---

## 许可证

MIT License

---

<p align="center">
  Made with PySide6 & qfluentwidgets
</p>
