# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — IELTSVocab Windows .exe

构建（在 Windows 上）：
    pyinstaller --noconfirm IELTSVocab_win.spec

输出：
    dist\\IELTSVocab\\IELTSVocab.exe   （文件夹模式，含所有依赖）

说明：
- 用 onedir（文件夹）模式而非 onefile：启动更快，运行更稳，缺点是包含很多 dll
- console=False 隐藏命令行窗口
- 图标用 build_assets/icon.ico
"""
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

PROJECT_ROOT = os.path.abspath(os.path.dirname(SPEC))

# 资源文件
datas = [
    (os.path.join(PROJECT_ROOT, 'templates'), 'templates'),
    (os.path.join(PROJECT_ROOT, 'static'), 'static'),
]

# 第三方包的 hidden imports / data
hidden_imports = []
for pkg in ('pdfplumber', 'pdfminer', 'pdfminer.six', 'openpyxl'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        hidden_imports += h
    except Exception:
        pass

hidden_imports += [
    'flask',
    'jinja2',
    'werkzeug',
    'sqlite3',
]


a = Analysis(
    [os.path.join(PROJECT_ROOT, 'app.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy.testing',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='IELTSVocab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # 关键：隐藏命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'build_assets', 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='IELTSVocab',
)
