#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../app_source" && pwd)"
cd "$APP_DIR" || exit 1

# macOS may quarantine scripts copied from WeChat, AirDrop, email, or web downloads.
/usr/bin/xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
/bin/chmod +r "$APP_DIR/diagnosis_app.py" "$APP_DIR/diagnosis_model.py" 2>/dev/null || true

PYTHON="/opt/anaconda3/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

if [[ -z "$PYTHON" ]]; then
  osascript -e 'display alert "未找到 Python3" message "请先安装 Python3 或 Anaconda 后再启动。"'
  exit 1
fi

"$PYTHON" "$APP_DIR/diagnosis_app.py"
STATUS=$?

if [[ "$STATUS" -ne 0 ]]; then
  osascript -e 'display alert "启动失败" message "请确认已安装依赖，并已在 app_source/data 中准备本地训练数据。"'
fi

exit "$STATUS"
