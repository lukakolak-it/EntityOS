"""Privacy and repository safety checks."""

from __future__ import annotations

import fnmatch
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


FORBIDDEN_TRACKED_PATTERNS = (
    ".env",
    ".env.*",
    "data/*",
    "logs/*",
    "exports/*",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.log",
    "profiles.local.*",
)

REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "data/*",
    "logs/",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.log",
    "exports/",
    "profiles.local.*",
)

SECRET_ASSIGNMENT = re.compile(
    r"\b[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{8,})"
)


@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    severity: str
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def run_privacy_check(root: str | Path = ".") -> dict[str, object]:
    """Check local-first repository assumptions."""

    root_path = Path(root).resolve()
    findings: list[PrivacyFinding] = []
    tracked_files = _tracked_files(root_path)

    findings.extend(_check_tracked_forbidden_files(tracked_files))
    findings.extend(_check_gitignore(root_path))
    findings.extend(_check_env_example(root_path))
    findings.extend(_scan_tracked_files_for_secrets(root_path, tracked_files))

    return {
        "ok": not any(finding.severity == "error" for finding in findings),
        "findings": [finding.to_dict() for finding in findings],
        "tracked_file_count": len(tracked_files),
    }


def _tracked_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return [
            str(path.relative_to(root)).replace("\\", "/")
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
    return [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _check_tracked_forbidden_files(tracked_files: list[str]) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for path in tracked_files:
        if path.endswith("/.gitkeep"):
            continue
        for pattern in FORBIDDEN_TRACKED_PATTERNS:
            if path == ".env.example":
                continue
            if fnmatch.fnmatch(path, pattern):
                findings.append(
                    PrivacyFinding(
                        severity="error",
                        code="tracked_local_data",
                        message="Local runtime data or secret-like file is tracked.",
                        path=path,
                    )
                )
                break
    return findings


def _check_gitignore(root: Path) -> list[PrivacyFinding]:
    path = root / ".gitignore"
    if not path.exists():
        return [
            PrivacyFinding(
                severity="error",
                code="missing_gitignore",
                message=".gitignore is missing.",
                path=".gitignore",
            )
        ]

    content = path.read_text(encoding="utf-8")
    findings: list[PrivacyFinding] = []
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in content:
            findings.append(
                PrivacyFinding(
                    severity="error",
                    code="missing_gitignore_pattern",
                    message=f"Required ignore pattern is missing: {pattern}",
                    path=".gitignore",
                )
            )
    return findings


def _check_env_example(root: Path) -> list[PrivacyFinding]:
    path = root / ".env.example"
    if not path.exists():
        return []

    findings: list[PrivacyFinding] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if "API_KEY" in key.upper() and value.strip():
            findings.append(
                PrivacyFinding(
                    severity="error",
                    code="env_example_secret",
                    message=f"{key} in .env.example must stay empty.",
                    path=".env.example",
                )
            )
    return findings


def _scan_tracked_files_for_secrets(
    root: Path,
    tracked_files: list[str],
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for relative in tracked_files:
        path = root / relative
        if not path.exists() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line in text.splitlines():
            if SECRET_ASSIGNMENT.search(line) and "REDACTED" not in line:
                if relative == ".env.example" and line.rstrip().endswith("="):
                    continue
                findings.append(
                    PrivacyFinding(
                        severity="error",
                        code="possible_secret",
                        message="Tracked file contains a possible secret assignment.",
                        path=relative,
                    )
                )
                break
    return findings
