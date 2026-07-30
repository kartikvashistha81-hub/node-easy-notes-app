"""
agent.planner
=============
Top-level orchestrator. Wires every stage together in the exact order
described in the assignment:

    Receive task
      -> Explore repository
      -> Understand architecture
      -> Create execution plan
      -> Identify files
      -> Modify code
      -> Run verification
      -> Roll back if verification found a critical regression
      -> Generate summary

Each stage's output is the next stage's input (see agent.models) -- this
class contains no business logic of its own, only sequencing + logging.

ROLLBACK POLICY: if any *critical* verification check fails (syntax errors,
a crash on server boot, a failing test suite, invalid package.json, or a
task that flat-out failed to write), every file this run touched is
restored to its pre-run state. This is what "the agent should never break
existing functionality" means in practice -- verification isn't just a
report, it gates whether the change is kept. `npm_install` failing does
NOT trigger rollback by itself (it's frequently an environment/network
issue unrelated to the code the agent wrote), but every other check is
critical by default (see CheckResult.critical in agent.models). Pass
`allow_rollback=False` to inspect a failed run's changes anyway (useful
for debugging).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .codebase_analyzer import CodebaseAnalyzer
from .feature_planner import FeaturePlanner
from .file_locator import FileLocator
from .implementation_engine import ImplementationEngine
from .logger_setup import get_logger
from .models import (
    CodebaseAnalysis,
    FeaturePlan,
    ImplementationResult,
    RepositoryExploration,
    RollbackReport,
    VerificationReport,
)
from .repository_explorer import RepositoryExplorer
from .summary_generator import SummaryGenerator
from .verification_engine import VerificationEngine

logger = get_logger(__name__)

# Checks whose failure should NOT trigger a rollback -- see module
# docstring. Everything else defaults to critical=True on CheckResult.
NON_CRITICAL_CHECK_NAMES = {"npm_install"}


@dataclass
class AgentRunResult:
    repo_root: Path
    exploration: RepositoryExploration
    analysis: CodebaseAnalysis
    plan: FeaturePlan
    implementation: ImplementationResult
    verification: VerificationReport
    rollback: Optional[RollbackReport] = None

    @property
    def succeeded(self) -> bool:
        return (
            not self.implementation.errors
            and self.verification.all_passed
            and (self.rollback is None or not self.rollback.performed)
        )


class AgentPlanner:
    """Runs the full agent pipeline end to end against one repository."""

    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir
        self.explorer = RepositoryExplorer(workspace_dir)
        self.analyzer = CodebaseAnalyzer()
        self.feature_planner = FeaturePlanner()
        self.file_locator = FileLocator()
        self.implementation_engine = ImplementationEngine()

    def run(
        self,
        repo_source: str,
        user_request: str,
        reports_dir: Path | None = None,
        allow_rollback: bool = True,
    ) -> AgentRunResult:
        logger.info("=" * 70)
        logger.info("STEP 1-2: Exploring repository: %s", repo_source)
        exploration = self.explorer.explore(repo_source)

        logger.info("=" * 70)
        logger.info("STEP 2: Analyzing codebase architecture")
        analysis = self.analyzer.analyze(exploration)

        logger.info("=" * 70)
        logger.info("STEP 3: Planning feature implementation for request: %r", user_request)
        plan = self.feature_planner.plan(user_request, analysis)

        logger.info("=" * 70)
        logger.info("STEP 4: Locating target files for %d tasks", len(plan.tasks))
        located_files = self.file_locator.locate(exploration.root_path, analysis, plan)

        logger.info("=" * 70)
        logger.info("STEP 5: Implementing feature")
        implementation = self.implementation_engine.implement(located_files, analysis)

        logger.info("=" * 70)
        logger.info("STEP 6: Verifying the modified repository")
        verifier = VerificationEngine(exploration.root_path)
        verification = self._mark_criticality(verifier.verify(implementation))

        logger.info("=" * 70)
        rollback_report: Optional[RollbackReport] = None
        critical_failures = verification.critical_failures
        if critical_failures:
            reasons = "; ".join(f"{c.name}: {c.detail[:120]}" for c in critical_failures)
            logger.error(
                "STEP 6b: %d critical check(s) failed: %s",
                len(critical_failures), reasons,
            )
            if allow_rollback:
                logger.error("STEP 6b: Rolling back all changes from this run.")
                rollback_report = self.implementation_engine.rollback(
                    exploration.root_path, implementation, reason=reasons
                )
            else:
                logger.warning(
                    "STEP 6b: allow_rollback=False -- leaving failed changes in place for inspection."
                )
        else:
            logger.info("STEP 6b: No critical failures -- keeping all changes.")

        logger.info("=" * 70)
        logger.info("STEP 7: Generating summary reports")
        reports_dir = reports_dir or exploration.root_path
        SummaryGenerator(reports_dir).write_all(
            exploration, analysis, plan, implementation, verification, rollback_report
        )

        logger.info("=" * 70)
        if rollback_report and rollback_report.performed:
            status = "ROLLED BACK (critical verification failure)"
        elif verification.all_passed and not implementation.errors:
            status = "SUCCEEDED"
        else:
            status = "COMPLETED WITH ISSUES"
        logger.info("Agent run %s.", status)

        return AgentRunResult(
            repo_root=exploration.root_path,
            exploration=exploration,
            analysis=analysis,
            plan=plan,
            implementation=implementation,
            verification=verification,
            rollback=rollback_report,
        )

    def _mark_criticality(self, verification: VerificationReport) -> VerificationReport:
        for check in verification.checks:
            if check.name in NON_CRITICAL_CHECK_NAMES:
                check.critical = False
        return verification