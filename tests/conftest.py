"""
Pytest configuration for DJ File Browser Panel tests.

The example project is made importable so ``example_project.settings``
resolves regardless of the invocation directory.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_PROJECT_DIR = os.path.join(BASE_DIR, "example_project")
if EXAMPLE_PROJECT_DIR not in sys.path:
    sys.path.insert(0, EXAMPLE_PROJECT_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")
