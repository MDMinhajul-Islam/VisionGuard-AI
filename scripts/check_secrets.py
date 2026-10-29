from __future__ import annotations

import re
import subprocess
from pathlib import Path


PATTERNS = {
    "GitHub token": re.compile(r"(?:gh[opsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "populated auth secret": re.compile(r"VISIONGUARD_AUTH_SECRET\s*=\s*[^\s#]{20,}"),
}
ALLOWLIST = {".env.example", ".github/workflows/security-ci.yml", "backend/tests/conftest.py"}


def main() -> int:
    files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    findings: list[str] = []
    for relative in files:
        if not relative or relative.replace("\\", "/") in ALLOWLIST:
            continue
        path = Path(relative)
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative}: credential pattern: {name}")
    if findings:
        print("\n".join(findings))
        return 1
    print("No credential-shaped values found in tracked text files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
