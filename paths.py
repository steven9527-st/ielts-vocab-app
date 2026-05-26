"""
paths.py — 运行环境路径统一管理

开发环境：所有数据在项目目录下（vocab.db / .tmp_parse）
打包环境（PyInstaller）：数据在用户 home 目录的应用专属位置
                       静态资源在 PyInstaller 解包的临时目录 sys._MEIPASS

判定逻辑：
  - 通过 sys.frozen 属性判断是否在 PyInstaller 包内
  - 也可通过环境变量 IELTSVOCAB_DATA_DIR 强制覆盖
"""
import os
import sys


APP_NAME = 'IELTSVocab'


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境中"""
    return getattr(sys, 'frozen', False)


def user_data_dir() -> str:
    """用户可写的数据目录（持久化数据，跨升级保留）

    优先级:
      1. 环境变量 IELTSVOCAB_DATA_DIR
      2. 打包环境: ~/Library/Application Support/IELTSVocab (Mac)
                   %APPDATA%/IELTSVocab (Windows)
      3. 开发环境: 项目根目录
    """
    override = os.environ.get('IELTSVOCAB_DATA_DIR')
    if override:
        os.makedirs(override, exist_ok=True)
        return override

    if is_frozen():
        if sys.platform == 'darwin':
            base = os.path.expanduser(f'~/Library/Application Support/{APP_NAME}')
        elif sys.platform == 'win32':
            base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
        else:
            base = os.path.expanduser(f'~/.local/share/{APP_NAME}')
        os.makedirs(base, exist_ok=True)
        return base

    # 开发环境：项目根目录
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir() -> str:
    """只读静态资源目录（templates / static / build_assets）

    打包后：PyInstaller 把 templates 和 static 解压到 sys._MEIPASS
    开发模式：项目根目录
    """
    if is_frozen() and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def db_path() -> str:
    """SQLite 文件路径"""
    return os.path.join(user_data_dir(), 'vocab.db')


def tmp_parse_dir() -> str:
    """临时解析数据目录"""
    path = os.path.join(user_data_dir(), '.tmp_parse')
    os.makedirs(path, exist_ok=True)
    return path
