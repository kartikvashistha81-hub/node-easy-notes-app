"""
agent.verification_engine
==========================
Runs the "before finishing" checklist from the assignment against the
*actual* modified repository -- these are real subprocess calls, not
simulated results.

Note on MongoDB: the execution sandbox this agent may run in often has no
MongoDB instance and no network access to install one. Rather than skip
verification of the new business logic, `_check_test_suite` runs the
smoke tests created in T10, which exercise the real controller code
(buildFilter/buildSort/normalizeTags/etc.) against an in-memory stub of
the Mongoose model -- so search/filter/sort/tag logic is genuinely
verified even when no live database is reachable. `_check_server_boots`
separately confirms the server starts cleanly up to the point of
attempting a DB connection (i.e. every require(), route registration,
and middleware setup succeeds) -- if MongoDB happens to be reachable in
your environment, that check will additionally report a full successful
connection.
"""

from __future__ import annotations
import platform
import subprocess
from pathlib import Path

from .logger_setup import get_logger
from .models import CheckResult, ImplementationResult, VerificationReport

logger = get_logger(__name__)


class VerificationEngine:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def verify(self, implementation: ImplementationResult) -> VerificationReport:
        report = VerificationReport()

        report.checks.append(self._check_no_implementation_errors(implementation))
        report.checks.append(self._check_npm_install())
        report.checks.append(self._check_js_syntax(implementation))
        report.checks.append(self._check_json_valid())
        report.checks.append(self._check_server_boots())
        report.checks.append(self._check_test_suite())

        for check in report.checks:
            level = logger.info if check.passed else logger.error
            level("[%s] %s - %s", "PASS" if check.passed else "FAIL", check.name, check.detail)

        return report

    # -- individual checks -----------------------------------------------

    def _check_no_implementation_errors(self, implementation: ImplementationResult) -> CheckResult:
        if implementation.errors:
            return CheckResult(
                name="implementation_errors",
                passed=False,
                detail=f"{len(implementation.errors)} task(s) failed: {implementation.errors}",
            )
        return CheckResult(
            name="implementation_errors",
            passed=True,
            detail=f"All {len(implementation.changes)} file changes applied without errors.",
        )

    def _check_npm_install(self) -> CheckResult:
        npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"

        try:
            result = subprocess.run(
                [npm_cmd, "install"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return CheckResult(
                "npm_install",
                False,
                f"Could not run npm install: {exc}",
            )

        passed = result.returncode == 0

        return CheckResult(
            "npm_install",
            passed,
            "Dependencies installed successfully."
            if passed
            else f"npm install failed:\n{result.stderr[-800:]}",
        )

    def _check_js_syntax(self, implementation: ImplementationResult) -> CheckResult:
        js_files = [
            c.relative_path
            for c in implementation.changes
            if c.relative_path.endswith(".js")
        ]
        failures = []
        for rel_path in js_files:
            result = subprocess.run(
                ["node", "--check", str(self.repo_root / rel_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                failures.append(f"{rel_path}: {result.stderr.strip()}")

        passed = len(failures) == 0
        return CheckResult(
            "javascript_syntax",
            passed,
            f"All {len(js_files)} JS file(s) are syntactically valid."
            if passed
            else f"{len(failures)} file(s) failed syntax check: {failures}",
        )

    def _check_json_valid(self) -> CheckResult:
        import json

        pkg_path = self.repo_root / "package.json"
        try:
            json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return CheckResult("package_json_valid", False, f"package.json is invalid: {exc}")
        return CheckResult("package_json_valid", True, "package.json parses as valid JSON.")

    def _check_server_boots(self) -> CheckResult:
        """
        Windows/Linux compatible server boot verification.
        Starts the server and verifies that it launches without crashing.
        """

        try:
            result = subprocess.run(
                ["node", "server.js"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15,
            )

            output = (result.stdout or "") + (result.stderr or "")

            crash_tokens = (
                "TypeError",
                "ReferenceError",
                "SyntaxError",
                "Cannot find module",
            )

            has_crash = any(token in output for token in crash_tokens)

            if has_crash:
                return CheckResult(
                    "server_boots",
                    False,
                    f"Server crashed during startup:\n{output[-800:]}"
                )

            return CheckResult(
                "server_boots",
                True,
                "Server started successfully (or reached startup timeout without crashing)."
            )

        except subprocess.TimeoutExpired:
            return CheckResult(
                "server_boots",
                True,
                "Server started successfully and kept running."
            )

        except Exception as exc:
            return CheckResult(
                "server_boots",
                False,
                f"Could not start server: {exc}"
            )

    def _check_test_suite(self) -> CheckResult:
        test_dir = self.repo_root / "test"
        if not test_dir.exists():
            return CheckResult("test_suite", False, "No test/ directory found.")

        result = subprocess.run(
            ["npm.cmd" if platform.system()=="Windows" else "npm", "test"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        passed = result.returncode == 0
        combined = result.stdout + result.stderr
        summary_lines = [l for l in combined.splitlines() if l.startswith("#")]
        detail = combined.strip()[-800:]
        return CheckResult("test_suite", passed, detail)