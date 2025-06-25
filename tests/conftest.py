import os
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    # If python-dotenv is not installed, silently ignore – tests that rely on env vars will skip.
    load_dotenv = None  # type: ignore

# Automatically load a .env file at workspace root if present
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / '.env'
if load_dotenv and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=False)
# Ensure project root in sys.path
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR)) 