#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../app_source" && pwd)"
cd "$APP_DIR" || exit 1

PYTHON="/opt/anaconda3/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

if [[ -z "$PYTHON" ]]; then
  osascript -e 'display alert "未找到 Python3" message "打包需要在开发电脑上安装 Python3 或 Anaconda。"'
  exit 1
fi

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "胰腺癌辅助诊断" \
  --add-data "data:data" \
  --exclude-module PyQt5 \
  --exclude-module PyQt6 \
  --exclude-module PySide2 \
  --exclude-module PySide6 \
  --exclude-module matplotlib \
  --exclude-module IPython \
  --exclude-module notebook \
  --exclude-module jupyter \
  --exclude-module pytest \
  --exclude-module dask \
  --exclude-module numba \
  diagnosis_app.py

STATUS=$?
if [[ "$STATUS" -eq 0 ]]; then
  /bin/cat > "dist/使用说明_发给朋友.txt" <<'EOF'
胰腺癌辅助诊断软件使用说明

1. 解压 胰腺癌辅助诊断_mac_arm64.zip。
2. 双击 胰腺癌辅助诊断.app 启动。
3. 如果 macOS 提示“无法验证开发者”或“不允许打开”：
   - 右键点击 胰腺癌辅助诊断.app
   - 选择“打开”
   - 在弹窗中再次选择“打开”
4. 本版本为 Apple Silicon / arm64 版本，适合 M1/M2/M3/M4 Mac。
5. 不需要安装 Python、Anaconda 或其他依赖。
EOF
  /usr/bin/ditto -c -k --sequesterRsrc --keepParent "dist/胰腺癌辅助诊断.app" "dist/胰腺癌辅助诊断_mac_arm64.zip"
  (cd dist && /usr/bin/zip -q -u "胰腺癌辅助诊断_mac_arm64.zip" "使用说明_发给朋友.txt")
  osascript -e 'display alert "打包完成" message "独立版已生成在 dist 文件夹中。"'
else
  osascript -e 'display alert "打包失败" message "请查看终端中的 PyInstaller 错误信息。"'
fi

exit "$STATUS"
