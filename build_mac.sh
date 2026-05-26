#!/usr/bin/env bash
# IELTSVocab macOS 一键构建脚本
# 用法：bash build_mac.sh
# 输出：dist/IELTSVocab.app  +  dist/IELTSVocab.dmg

set -e

cd "$(dirname "$0")"

echo "════════════════════════════════════════"
echo "  IELTSVocab macOS Build"
echo "════════════════════════════════════════"

# 0. 检查依赖
echo "[0/4] 检查 PyInstaller..."
python3 -c "import PyInstaller" 2>/dev/null || {
  echo "  → 未安装 PyInstaller，正在安装..."
  python3 -m pip install pyinstaller pillow --quiet
}

# 1. 清理旧产物
echo "[1/4] 清理旧产物..."
rm -rf build dist

# 2. 运行 PyInstaller
echo "[2/4] PyInstaller 构建中（约 1-2 分钟）..."
python3 -m PyInstaller --noconfirm --clean IELTSVocab.spec

if [ ! -d "dist/IELTSVocab.app" ]; then
  echo "✗ 构建失败：dist/IELTSVocab.app 未生成"
  exit 1
fi

# 3. 打 .dmg（用 hdiutil，macOS 自带）
echo "[3/4] 打包 .dmg..."
DMG_PATH="dist/IELTSVocab.dmg"
rm -f "$DMG_PATH"

# 创建临时 DMG 目录结构
DMG_TMP="dist/dmg_tmp"
rm -rf "$DMG_TMP"
mkdir -p "$DMG_TMP"
cp -R "dist/IELTSVocab.app" "$DMG_TMP/"
# 在 DMG 内创建 Applications 文件夹快捷方式（用户拖进去即可安装）
ln -s /Applications "$DMG_TMP/Applications"

hdiutil create -volname "IELTSVocab" \
  -srcfolder "$DMG_TMP" \
  -ov -format UDZO \
  "$DMG_PATH" >/dev/null

rm -rf "$DMG_TMP"

# 4. 汇报
echo "[4/4] 完成 ✓"
echo ""
echo "════════════════════════════════════════"
APP_SIZE=$(du -sh dist/IELTSVocab.app | awk '{print $1}')
DMG_SIZE=$(du -sh dist/IELTSVocab.dmg | awk '{print $1}')
echo "  .app: dist/IELTSVocab.app  ($APP_SIZE)"
echo "  .dmg: dist/IELTSVocab.dmg  ($DMG_SIZE)"
echo "════════════════════════════════════════"
echo ""
echo "测试方式："
echo "  open dist/IELTSVocab.app"
echo ""
echo "分发方式："
echo "  把 dist/IELTSVocab.dmg 发给朋友，双击挂载，拖到 Applications 即可"
echo ""
echo "首次启动："
echo "  macOS 可能提示「无法验证开发者」，"
echo "  朋友需要：系统设置 → 隐私与安全性 → 仍要打开"
echo "  （因为没有 Apple 开发者证书签名，正常现象）"
