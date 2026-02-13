#!/bin/bash
# Create a Mac-native venv with properly compiled dependencies (fixes PIL/Pillow on Mac)

cd "$(dirname "$0")"

PYTHON="/opt/homebrew/opt/python@3.14/bin/python3.14"
[ -x "$PYTHON" ] || PYTHON="/opt/homebrew/opt/python@3/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3.11"
[ -x "$PYTHON" ] || PYTHON="python3"

echo "Using: $($PYTHON --version)"
$PYTHON -m venv venv_mac
source venv_mac/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo ""
echo "Done! Run: source venv_mac/bin/activate && python manage.py runserver"
echo "Or use: ./run_server.sh"
