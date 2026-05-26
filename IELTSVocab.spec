# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — IELTSVocab macOS .app

构建：
    pyinstaller --noconfirm IELTSVocab.spec

输出：
    dist/IELTSVocab.app
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 项目根目录（spec 所在目录）
PROJECT_ROOT = os.path.abspath(os.path.dirname(SPEC))

# 资源文件：templates / static 必须打进包内
datas = [
    (os.path.join(PROJECT_ROOT, 'templates'), 'templates'),
    (os.path.join(PROJECT_ROOT, 'static'), 'static'),
]

# pdfplumber 和 openpyxl 都有不少需要 collect_all 才能拉全的子模块
hidden_imports = []
for pkg in ('pdfplumber', 'pdfminer', 'pdfminer.six', 'openpyxl'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        hidden_imports += h
    except Exception:
        pass

# Flask 相关 hidden imports（pyinstaller 一般能自动识别，这里给个保险）
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
    console=False,           # macOS .app 隐藏终端窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name='IELTSVocab.app',
    icon=os.path.join(PROJECT_ROOT, 'build_assets', 'icon.icns'),
    bundle_identifier='com.steven9527.ieltsvocab',
    version='1.0.0',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSBackgroundOnly': 'False',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1',
        'NSHumanReadableCopyright': 'Copyright © 2026 steven9527',
        # 应用名称（Dock 上显示）
        'CFBundleName': 'IELTSVocab',
        'CFBundleDisplayName': 'IELTS Vocab',
    },
)
