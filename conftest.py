# conftest.py
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
# Add your source directories to sys.path so modules can be imported in tests.
sys.path.insert(0, str(root / "backend-api" / "src"))
sys.path.insert(0, str(root / "frontend" / "src"))
sys.path.insert(0, str(root / "transcriber" / "src"))
