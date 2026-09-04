import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"


def _tracked_screenshots() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "screenshots"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    # A move is visible in the working tree before it is staged. Ignoring removed index paths lets
    # this guard validate the same tree before and after `git add`.
    return {
        path
        for path in result.stdout.splitlines()
        if path and (REPO_ROOT / path).is_file()
    }


def _test_screenshot_outputs() -> set[str]:
    outputs: set[str] = set()
    for test_path in TESTS_DIR.rglob("test_*.py"):
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Div)
                and isinstance(node.left, ast.Name)
                and node.left.id == "SCREENSHOTS"
                and isinstance(node.right, ast.Constant)
                and isinstance(node.right.value, str)
                and node.right.value.endswith(".png")
            ):
                continue
            outputs.add(f"screenshots/{node.right.value}")
    return outputs


def _file_list(paths: set[str]) -> str:
    return "\n".join(f"  - {path}" for path in sorted(paths))


def test_tracked_screenshots_and_test_outputs_match() -> None:
    """Keep screenshots/ test-owned in both directions.

    Design records live under docs/design/ instead: they preserve reasoning, are not regenerated
    or compared by tests, and are outside this guard by construction. Screenshots are the opposite:
    every tracked file there is written by a test, and every declared test output is tracked.

    Write each screenshot path as ``SCREENSHOTS / "name.png"`` at its call site. This AST guard
    cannot resolve a path assembled any other way.
    """
    tracked = _tracked_screenshots()
    outputs = _test_screenshot_outputs()
    orphaned = tracked - outputs
    untracked = outputs - tracked
    failures = []
    if orphaned:
        failures.append(
            "Tracked screenshots with no test write "
            "(this screenshot has no test that writes it):\n"
            f"{_file_list(orphaned)}"
        )
    if untracked:
        failures.append(
            "Test screenshot outputs missing from Git "
            "(this test writes an untracked screenshot output):\n"
            f"{_file_list(untracked)}"
        )
    assert not failures, "\n\n".join(failures)
