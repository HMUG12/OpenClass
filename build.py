"""
OpenClass 一键打包脚本
用法: 在项目根目录打开 PowerShell，执行 python build.py
"""
import subprocess
import sys
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# 清理旧产物
for d in ["build", "dist"]:
    if os.path.exists(d):
        shutil.rmtree(d)
for f in ["OpenClass.spec"]:
    if os.path.exists(f):
        os.remove(f)

print("=" * 60)
print("OpenClass — PyInstaller 打包")
print("=" * 60)

# 确保 resources 目录存在
os.makedirs("resources", exist_ok=True)
qss = os.path.join("resources", "dark_theme.qss")
if not os.path.exists(qss):
    with open(qss, "w", encoding="utf-8") as f:
        f.write("/* Dark theme placeholder */")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name=OpenClass",
    "--icon=openclass.ico",
    "--add-data=app;app",
    "--add-data=resources;resources",
    "--add-data=data;data",
    "--hidden-import=qfluentwidgets",
    "--hidden-import=PySide6.QtXml",
    "--hidden-import=PySide6.QtNetwork",
    # 排除环境中残留的 PyQt5 / torch，避免冲突和膨胀
    "--exclude-module=PyQt5",
    "--exclude-module=PyQt5.QtCore",
    "--exclude-module=PyQt5.QtGui",
    "--exclude-module=PyQt5.QtWidgets",
    "--exclude-module=torch",
    "--exclude-module=torchvision",
    "--log-level=WARN",
    "main.py",
]

print(f"\n命令: {' '.join(cmd)}\n")
sys.stdout.flush()

proc = subprocess.Popen(cmd)
proc.wait()

if proc.returncode != 0:
    print(f"\n打包失败，退出码: {proc.returncode}")
    sys.exit(1)

exe_path = os.path.join("dist", "OpenClass.exe")
if not os.path.exists(exe_path):
    print("\n错误: dist/OpenClass.exe 未生成")
    sys.exit(1)

size_mb = os.path.getsize(exe_path) / (1024 * 1024)
print(f"\n{'=' * 60}")
print(f"打包成功! {exe_path} ({size_mb:.1f} MB)")
print(f"{'=' * 60}")
