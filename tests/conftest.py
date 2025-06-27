import os
from pathlib import Path
import sys
import pytest

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

def pytest_addoption(parser):
    """Add custom CLI option to enable tests that need external API access."""
    parser.addoption(
        "--run_requires_api",
        action="store_true",
        default=False,
        help="Run tests marked with 'requires_api_key' that hit external services.",
    )

def pytest_runtest_setup(item):
    """Skip tests requiring external APIs unless the flag is provided."""
    if "requires_api_key" in item.keywords:
        run_flag = item.config.getoption("--run_requires_api")
        if not run_flag:
            pytest.skip("skipped 'requires_api_key' test (add --run_requires_api to run)") 