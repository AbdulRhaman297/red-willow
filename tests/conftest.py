import os
import sys

# Ensure the project root (parent directory of tests) is on sys.path
# This makes `import main` work when running the test suite
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
