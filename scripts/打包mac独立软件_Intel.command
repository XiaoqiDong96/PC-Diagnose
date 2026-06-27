#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../app_source" && pwd)"
cd "$APP_DIR" || exit 1

PYTHON="/usr/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  osascript -e 'display alert "未找到系统 Python3" message "Intel 打包需要 macOS 系统 Python3 和 Rosetta。"'
  exit 1
fi

if ! /usr/bin/arch -x86_64 "$PYTHON" -c 'import platform; raise SystemExit(0 if platform.machine() == "x86_64" else 1)' 2>/dev/null; then
  osascript -e 'display alert "缺少 Rosetta" message "请先安装 Rosetta：softwareupdate --install-rosetta --agree-to-license"'
  exit 1
fi

VENV="$APP_DIR/.venv_intel"
if [[ ! -x "$VENV/bin/python" ]]; then
  /usr/bin/arch -x86_64 "$PYTHON" -m venv "$VENV" || exit 1
fi

/usr/bin/arch -x86_64 "$VENV/bin/python" -m pip install --upgrade pip wheel setuptools || exit 1
/usr/bin/arch -x86_64 "$VENV/bin/python" -m pip install \
  "pyinstaller>=6.0" \
  "numpy<2.1" \
  "pandas<2.3" \
  "scipy<1.14" \
  "scikit-learn<1.6" \
  "openpyxl>=3.1" || exit 1

rm -rf build_intel dist_intel

/usr/bin/arch -x86_64 "$VENV/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --target-arch x86_64 \
  --name "胰腺癌辅助诊断" \
  --distpath "dist_intel" \
  --workpath "build_intel" \
  --specpath "build_intel" \
  --add-data "$APP_DIR/data:data" \
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
  /bin/cat > "dist_intel/使用说明_发给朋友.txt" <<'EOF'
胰腺癌辅助诊断软件使用说明

1. 解压 胰腺癌辅助诊断_mac_intel.zip。
2. 双击 胰腺癌辅助诊断.app 启动。
3. 如果 macOS 提示“无法验证开发者”或“不允许打开”：
   - 右键点击 胰腺癌辅助诊断.app
   - 选择“打开”
   - 在弹窗中再次选择“打开”
4. 本版本为 Intel / x86_64 版本，适合 Intel Core i5/i7/i9 Mac。
5. 不需要安装 Python、Anaconda 或其他依赖。
EOF
  /usr/bin/ditto -c -k --sequesterRsrc --keepParent "dist_intel/胰腺癌辅助诊断.app" "dist_intel/胰腺癌辅助诊断_mac_intel.zip"
  (cd dist_intel && /usr/bin/zip -q -u "胰腺癌辅助诊断_mac_intel.zip" "使用说明_发给朋友.txt")
  osascript -e 'display alert "Intel版打包完成" message "独立版已生成在 dist_intel 文件夹中。"'
else
  osascript -e 'display alert "Intel版打包失败" message "请查看终端中的 PyInstaller 错误信息。"'
fi

exit "$STATUS"
