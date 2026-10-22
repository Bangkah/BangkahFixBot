from pydantic import BaseModel, Field


class IssueTriage(BaseModel):
    title: str = Field(description="Short imperative title of the bug")
    symptom: str = Field(description="Observed incorrect behavior")
    expected: str = Field(description="Correct behavior")
    repro_steps: list[str] = Field(description="Concrete reproduction steps")
    suspected_files: list[str] = Field(description="Files likely involved, best-effort")


class FixPlan(BaseModel):
    root_cause: str = Field(description="Most likely root cause with reasoning")
    approach: str = Field(description="How the fix will be implemented")
    test_strategy: str = Field(description="What a regression test should assert")
    risky_areas: list[str] = Field(description="Things the patch must not break")


class TestSpec(BaseModel):
    test_name: str = Field(description="Name of the regression test")
    target_file: str = Field(description="Path of the test file to create/extend")
    test_code: str = Field(description="Full pytest test code")
    should_fail_before_fix: bool = Field(description="Whether the test must fail pre-fix")


class PatchProposal(BaseModel):
    target_file: str = Field(description="File to patch")
    unified_diff: str = Field(description="Unified diff applying the fix")
    explanation: str = Field(description="Why this diff fixes the root cause")


class VerificationResult(BaseModel):
    tests_run: int
    tests_passed: int
    fix_confirmed: bool = Field(description="True if regression test went red->green")
    regressions_detected: bool
    notes: str = Field(default="")
