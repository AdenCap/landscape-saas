#!/usr/bin/env python
# Run during build to verify config.wsgi is loadable: python check_wsgi.py
# Exit 0 = OK; non-zero = config/wsgi.py missing or application not defined.
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from config.wsgi import application
except ImportError as e:
    print("ERROR: config.wsgi could not be imported:", e, file=sys.stderr)
    sys.exit(1)
if not callable(application):
    print("ERROR: config.wsgi.application is not callable", file=sys.stderr)
    sys.exit(1)
print("OK: config.wsgi:application is loadable")
