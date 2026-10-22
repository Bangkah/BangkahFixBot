"""Test-first fix loop.

Pipeline: triage (nano) -> plan (super) -> failing test (super)
       -> patch (super, ultra on retry) -> verify in sandbox -> PR payload.

Sandbox execution is injected so the loop stays testable.
"""

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .schemas import FixPlan, IssueTriage, PatchProposal, TestSpec, VerificationResult
from .tokenfactory import TokenFactoryClient


class Sandbox(Protocol):
    def run_tests(self, workdir: str, args: list[str]) -> tuple[int, str]:
        ...


class SubprocessSandbox:
    """Run pytest in a local clone. Docker-based isolation lands next."""

    def run_tests(self, workdir: str, args: list[str]) -> tuple[int, str]:
        cmd = [sys.executable, "-m", "pytest", *args]
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        return proc.returncode, (proc.stdout + proc.stderr)[-8000:]


@dataclass
class FixSession:
    issue: dict
    workdir: str
    tier: str = "mock"

    triage: IssueTriage | None = None
    plan: FixPlan | None = None
    test: TestSpec | None = None
    patch: PatchProposal | None = None
    verification: VerificationResult | None = None
    attempts: list[dict] = field(default_factory=list)


def triage_issue(tf: TokenFactoryClient, issue: dict) -> IssueTriage:
    messages = [
        {
            "role": "system",
            "content": "You triage bug reports for a Python repository. Be precise and complete.",
        },
        {
            "role": "user",
            "content": f"Title: {issue.get('title', '')}\n\nBody:\n{issue.get('body', '')}",
        },
    ]
    return tf.structured("nano", IssueTriage, messages)


def plan_fix(tf: TokenFactoryClient, session: FixSession) -> FixPlan:
    messages = [
        {
            "role": "system",
            "content": (
                "You plan minimal, safe bug fixes. Root-cause first, "
                "then describe the regression test that must go red before the patch."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Triage:\n{session.triage.model_dump_json(indent=2)}\n\n"
                f"Repository at: {session.workdir}"
            ),
        },
    ]
    return tf.structured("super", FixPlan, messages)


def write_failing_test(tf: TokenFactoryClient, session: FixSession) -> TestSpec:
    messages = [
        {
            "role": "system",
            "content": (
                "You write one focused pytest regression test that fails because "
                "of the reported bug. The test must be self-contained and deterministic."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Plan:\n{session.plan.model_dump_json(indent=2)}\n\n"
                f"Repository at: {session.workdir}"
            ),
        },
    ]
    return tf.structured("super", TestSpec, messages)


def propose_patch(tf: TokenFactoryClient, session: FixSession, tier: str = "super") -> PatchProposal:
    messages = [
        {
            "role": "system",
            "content": (
                "You produce minimal unified diffs that fix the root cause. "
                "Only touch code required by the plan."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Plan:\n{session.plan.model_dump_json(indent=2)}\n\n"
                f"Failing test:\n{session.test.model_dump_json(indent=2)}"
            ),
        },
    ]
    return tf.structured(tier, PatchProposal, messages)


def verify(session: FixSession, sandbox: Sandbox) -> VerificationResult:
    rc_fail, out_fail = sandbox.run_tests(session.workdir, [session.test.target_file])
    failed_before = rc_fail != 0
    code, out = apply_patch_and_run(session, sandbox)
    passed = code == 0
    return VerificationResult(
        tests_run=session.verification.tests_run if session.verification else 1,
        tests_passed=int(passed),
        fix_confirmed=passed,
        regressions_detected=not passed,
        notes=f"PURPOSE_FAIL={failed_before}",
    )


def write_test_file(test: TestSpec, workdir: str) -> str:
    import re
    from pathlib import Path

    safe = re.sub(r"[^0-9A-Za-z_./-]", "_", test.target_file)
    path = Path(workdir) / safe
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(test.test_code + "\n", encoding="utf-8")
    return str(path)


def apply_patch_and_run(session: FixSession, sandbox: Sandbox) -> tuple[int, str]:
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".diff", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(session.patch.unified_diff)
        diff_path = fh.name
    proc = subprocess.run(
        ["git", "apply", diff_path],
        cwd=session.workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return proc.returncode, f"[apply-failed] {proc.stdout}{proc.stderr}"[-4000:]
    return sandbox.run_tests(session.workdir, [session.test.target_file])


def run_fix_loop(
    tf: TokenFactoryClient, issue: dict, workdir: str, sandbox: Sandbox, max_attempts: int = 3
) -> FixSession:
    session = FixSession(issue=issue, workdir=workdir)
    session.triage = triage_issue(tf, issue)
    session.plan = plan_fix(tf, session)
    session.test = write_failing_test(tf, session)
    written = write_test_file(session.test, workdir)
    session.tier = "super"
    session.attempts.append({"step": "test-written", "path": written})
    for attempt in range(1, max_attempts + 1):
        tier = "super" if attempt < max_attempts else "ultra"
        session.tier = tier
        session.patch = propose_patch(tf, session, tier=tier)
        result = verify(session, sandbox)
        session.attempts.append(
            {"attempt": attempt, "tier": tier, "verification": result.model_dump()}
        )
        session.verification = result
        if result.fix_confirmed:
            break
    return session
