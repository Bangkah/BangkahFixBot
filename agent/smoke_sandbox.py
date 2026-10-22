"""Smoke test the Docker sandbox: pass/fail/exit-code contract + read-only mount."""

import tempfile
from pathlib import Path

from bfbot.sandbox import DockerSandbox

PASSING = (
    "from math_utils import add\n\n"
    "def test_add_ok():\n"
    "    assert add(2, 3) == 5\n"
)
FAILING = (
    "from math_utils import add\n\n"
    "def test_add_uses_wrong_op():\n"
    "    assert add(2, 3) == 6\n"
)
BUGGY = "def add(a: int, b: int) -> int:\n    return a + b\n"


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="bfbox-"))
    (root / "math_utils.py").write_text(BUGGY, encoding="utf-8")
    (root / "test_pass.py").write_text(PASSING, encoding="utf-8")
    (root / "test_fail.py").write_text(FAILING, encoding="utf-8")

    s = DockerSandbox()
    if not s.available():
        raise SystemExit("docker not available")

    rc_pass, out_pass = s.run_tests(str(root), ["test_pass.py"])
    assert rc_pass == 0, f"expected 0 got {rc_pass}: {out_pass[-500:]}"

    rc_fail, out_fail = s.run_tests(str(root), ["test_fail.py"])
    assert rc_fail == 1, f"expected 1 got {rc_fail}: {out_fail[-500:]}"

    rc_all, out_all = s.run_tests(str(root), ["-q"])
    assert rc_all in (1,), f"expected 1 got {rc_all}: {out_all[-500:]}"

    assert "1 passed, 1 failed" in out_all or "1 failed, 1 passed" in out_all, out_all[-500:]

    left = [p.name for p in root.iterdir()]
    extra = [n for n in left if not n.endswith(".py")]
    assert not extra, f"sandbox wrote to ro mount: {extra}"

    print(f"smoke OK  pass={rc_pass} fail={rc_fail}  files_left={left}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
