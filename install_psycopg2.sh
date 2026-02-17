#!/usr/bin/env bash
# Install psycopg2-binary into the project venv (fixes "No module named psycopg2").
# Run from project root: ./install_psycopg2.sh

set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "No venv found. Create one first: python3 -m venv venv"
  exit 1
fi

echo "Installing psycopg2-binary into venv..."
./venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org psycopg2-binary

echo "Done. Run the server with: source venv/bin/activate && python manage.py runserver"
# Or: ./venv/bin/python manage.py runserver
