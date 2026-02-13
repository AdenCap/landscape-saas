#!/bin/bash
# Run the Landscape SaaS Django development server

cd "$(dirname "$0")"

# Try venv_mac first (Mac-native, fixes PIL/Pillow compatibility)
if [ -f "venv_mac/bin/python" ]; then
    exec venv_mac/bin/python manage.py runserver
fi

# Try venv/bin (Mac/Linux venv)
if [ -f "venv/bin/python" ]; then
    exec venv/bin/python manage.py runserver
fi

# Try venv/Scripts (Windows venv on Mac - use system Python with site-packages)
if [ -d "venv/Lib/site-packages" ]; then
    # Need Python 3.10+ for Django 5.2 (NoneType in types module)
    for py in /opt/homebrew/opt/python@3.14/bin/python3.14 \
             /opt/homebrew/opt/python@3/bin/python3 \
             /usr/local/opt/python@3.11/bin/python3.11 \
             python3.12 python3.11 python3.10 python3; do
        if [ -x "$py" ] 2>/dev/null || command -v "$py" &>/dev/null; then
            ver=$("$py" -c "import sys; print(sys.version_info.major * 100 + sys.version_info.minor)" 2>/dev/null) || continue
            if [ "$ver" -ge 310 ] 2>/dev/null; then
                echo "Using $py with venv site-packages"
                exec env PYTHONPATH="venv/Lib/site-packages" "$py" manage.py runserver
            fi
        fi
    done
    echo "Error: Django 5.2 requires Python 3.10+. Install with: brew install python@3.11"
    exit 1
fi

# No venv - try system python
if command -v python3 &>/dev/null; then
    exec python3 manage.py runserver
fi

echo "Error: No Python found. Create a venv: python3 -m venv venv && source venv/bin/activate && pip install django"
exit 1
