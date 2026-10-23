#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print '请先按 README.md 创建 Python 3.10+ 环境并安装 requirements.txt。'
  read '?按回车关闭'
  exit 1
fi
exec .venv/bin/python -m pixel_number
