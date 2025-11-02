#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Ensure project root (parent of this file's directory) is on sys.path so local apps import
PROJECT_DIR = Path(__file__).resolve().parent  # .../shopproject
REPO_ROOT = PROJECT_DIR.parent  # repo root containing apps like 'core', 'products'
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shopproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH environment variable? Did you forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
