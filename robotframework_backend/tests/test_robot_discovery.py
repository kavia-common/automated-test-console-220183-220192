import os

from src.api.robot_discovery import discover_robot_tests
from src.core.settings import settings


def test_discover_robot_tests_finds_robot_files(tmp_path):
    # create dummy robot files
    base = settings.ROBOT_PROJECT_ROOT
    os.makedirs(base, exist_ok=True)
    f1 = os.path.join(base, "a.robot")
    f2dir = os.path.join(base, "nested")
    os.makedirs(f2dir, exist_ok=True)
    f2 = os.path.join(f2dir, "b.ROBOT")
    with open(f1, "w", encoding="utf-8") as f:
        f.write("*** Test Cases ***")
    with open(f2, "w", encoding="utf-8") as f:
        f.write("*** Test Cases ***")

    discovered = discover_robot_tests()
    assert f1 in discovered
    assert f2 in discovered
