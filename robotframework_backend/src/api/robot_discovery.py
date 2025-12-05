import os
from typing import List, Optional

from src.core.settings import settings


# PUBLIC_INTERFACE
def discover_robot_tests(root: Optional[str] = None) -> List[str]:
    """Discover .robot test files under the given root (defaults to ROBOT_PROJECT_ROOT)."""
    root_dir = root or settings.ROBOT_PROJECT_ROOT
    results: List[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith(".robot"):
                abs_path = os.path.join(dirpath, f)
                results.append(abs_path)
    return results
