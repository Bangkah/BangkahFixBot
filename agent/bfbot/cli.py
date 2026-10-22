"""CLI entrypoints.

  python -m bfbot.cli demo    -> run the loop end-to-end against a toy repo (mock or live)
  python -m bfbot.cli usage   -> print last session token/cost report
"""

import json
import os
import sys
from pathlib import Path

from .agent import SubprocessSandbox, run_fix_loop
from .sandbox import pick_sandbox
from .tokenfactory import MockTokenFactoryClient, TokenFactoryClient

TOY_ISSUE = {
    "title": "slugify drops leading dash and swallows digits",
    "body": (
        "utils.slugify('Hello--World 123') returns 'hello-world' but it should "
        "return 'hello-world-123'. Also slugify(' -x ') returns 'x' instead of "
        "'x' trimmed... wait, it should be 'x'. Repro: `python -c "
        '"from utils import slugify; print(slugify(\'Hello--World 123\'))"` prints '
        "'hello-world'.\n\nExpected: 'hello-world-123'."
    ),
}


def build_client() -> TokenFactoryClient:
    if os.getenv("NEBIUS_API_KEY"):
        return TokenFactoryClient()
    print("[bfbot] NEBIUS_API_KEY not set -> MOCK mode cascading")
    return MockTokenFactoryClient()


def make_toy_repo(root: Path) -> Path:
    repo = root / "toy-repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "utils.py").write_text(
        "def slugify(text: str) -> str:\n"
        "    text = text.lower().strip()\n"
        "    text = text.replace('_', '-')\n"
        "    text = '-'.join(text.split('-'))\n"
        "    out = []\n"
        "    for ch in text:\n"
        "        out.append(ch if ch.isalnum() or ch == '-' else '-')\n"
        "    return ''.join(out).replace('--', '-').strip('-')\n",
        encoding="utf-8",
    )
    (repo / "test_utils.py").write_text(
        "from utils import slugify\n\n"
        "def test_basic():\n"
        "    assert slugify('Hello World') == 'hello-world'\n",
        encoding="utf-8",
    )
    if not (repo / ".git").exists():
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def cmd_demo() -> int:
    root = Path(".bfbot/demo").absolute()
    repo = make_toy_repo(root)
    tf = build_client()
    if not tf.live:
        print(
            "[bfbot] MOCK mode: canned outputs will fail verification by design;\n"
            "         demo only proves the pipeline mechanics (triage->plan->test->patch->verify)."
        )
    session = run_fix_loop(tf, TOY_ISSUE, str(repo), pick_sandbox())
    print("== Triage ==")
    print(session.triage.model_dump_json(indent=2))
    print("== Plan ==")
    print(session.plan.model_dump_json(indent=2))
    print("== Attempts ==")
    print(json.dumps(session.attempts, indent=2))
    report = tf.usage_report()
    print("== Usage ==")
    print(json.dumps(report, indent=2))
    return 0 if (session.verification.fix_confirmed or not tf.live) else 1


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] == "demo":
        return cmd_demo()
    if argv[0] == "usage":
        raise SystemExit("usage report printed at end of demo; persisted reports come with the API")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
