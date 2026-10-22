import os
import subprocess
from pathlib import Path

from .agent import SubprocessSandbox

IMAGE = os.getenv("BFBOT_SANDBOX_IMAGE", "bfbot/sandbox:latest")


class DockerSandbox:
    def __init__(self, image: str | None = None) -> None:
        self.image = image or IMAGE

    def available(self) -> bool:
        try:
            proc = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            return proc.returncode == 0 and bool(proc.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            return False

    def ensure_image(self) -> bool:
        try:
            inspect = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if inspect.returncode == 0:
                return True
            context = Path(__file__).resolve().parent.parent / "sandbox"
            build = subprocess.run(
                ["docker", "build", "-t", self.image, str(context)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            return build.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def run_tests(self, workdir: str, args: list[str]) -> tuple[int, str]:
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "768m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-v",
            f"{os.path.abspath(workdir)}:/src",
            "-w",
            "/src",
            self.image,
            "pytest",
            "-p",
            "no:cacheprovider",
            *args,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
            )
            text = f"{proc.stdout}\n{proc.stderr}"
            return proc.returncode, text[-8000:]
        except subprocess.TimeoutExpired:
            return 124, "[sandbox-timeout]"


def pick_sandbox(log=None) -> SubprocessSandbox | DockerSandbox:
    printer = print if log is None else print
    sandbox = DockerSandbox()
    if sandbox.available() and sandbox.ensure_image():
        printer(f"[bfbot] sandbox=docker ({sandbox.image}, network=none)")
        return sandbox
    printer("[bfbot] sandbox=subprocess fallback (Docker tidak tersedia)")
    return SubprocessSandbox()
