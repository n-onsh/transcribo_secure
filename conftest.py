import sys
from pathlib import Path

# Add the repository root to sys.path so absolute imports work.
repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))
