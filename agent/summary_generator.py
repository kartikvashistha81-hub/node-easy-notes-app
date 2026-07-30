"""
agent.summary_generator
========================
STEP: produce the three required markdown artifacts documenting what the
agent decided and did: execution_plan.md, changes_summary.md,
modified_files.md.
"""

from __future__ import annotations

from pathlib import Path

from .logger_setup import get_logger
from .models import (
    CodebaseAnalysis,
    FeaturePlan,
    ImplementationResult,
    RepositoryExploration,
    RollbackReport,
    VerificationReport,
)

logger = get_logger(__name__)


class SummaryGenerator:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def write_all(
        self,
        exploration: RepositoryExploration,
        analysis: CodebaseAnalysis,
        plan: FeaturePlan,
        implementation: ImplementationResult,
        verification: VerificationReport,
        rollback: RollbackReport | None = None,
    ) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_execution_plan(exploration, analysis, plan)
        self._write_changes_summary(plan, implementation, verification, rollback)
        self._write_modified_files(implementation, rollback)
        logger.info("Wrote execution_plan.md, changes_summary.md, modified_files.md to %s", self.output_dir)

    # -- execution_plan.md ------------------------------------------------

    def _write_execution_plan(
        self,
        exploration: RepositoryExploration,
        analysis: CodebaseAnalysis,
        plan: FeaturePlan,
    ) -> None:
        lines: list[str] = []
        lines.append("# Execution Plan")
        lines.append("")
        lines.append(f"**User request:** {plan.user_request}")
        lines.append("")
        lines.append(f"**Feature selected:** {plan.feature_name}")
        lines.append("")
        lines.append(plan.summary)
        lines.append("")

        lines.append("## Repository Understanding")
        lines.append("")
        lines.append(f"- Language: `{analysis.language}`")
        lines.append(f"- Framework: `{analysis.framework}`")
        lines.append(f"- Database / ORM: `{analysis.database}` / `{analysis.orm}`")
        lines.append(f"- Frontend present: `{analysis.has_frontend}`")
        lines.append(f"- Entry point: `{analysis.entry_point}`")
        lines.append("")
        lines.append("**Existing endpoints discovered:**")
        lines.append("")
        for ep in analysis.endpoints:
            lines.append(f"- `{ep.method} {ep.path}` -> `{ep.handler}` (in `{ep.source_file}`)")
        lines.append("")
        lines.append("**Existing models discovered:**")
        lines.append("")
        for model_name, fields in analysis.models.items():
            field_str = ", ".join(f"{f.name}: {f.field_type}" for f in fields) or "(no fields matched by parser)"
            lines.append(f"- `{model_name}`: {field_str}")
        lines.append("")
        if analysis.notes:
            lines.append("**Analyzer notes:**")
            lines.append("")
            for note in analysis.notes:
                lines.append(f"- {note}")
            lines.append("")

        lines.append("<details><summary>Full directory tree</summary>")
        lines.append("")
        lines.append("```")
        lines.append(exploration.directory_tree)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

        lines.append("## Decision Making")
        lines.append("")
        for i, reason in enumerate(plan.decision_rationale, start=1):
            lines.append(f"{i}. {reason}")
        lines.append("")

        if plan.alternatives_considered:
            lines.append("## Alternatives Considered")
            lines.append("")
            for alt in plan.alternatives_considered:
                lines.append(f"- {alt}")
            lines.append("")

        lines.append("## Task Breakdown")
        lines.append("")
        lines.append("| ID | Action | Title | Target |")
        lines.append("|----|--------|-------|--------|")
        for task in plan.tasks:
            lines.append(
                f"| {task.id} | {task.action.value} | {task.title} | `{task.target_component.value}` |"
            )
        lines.append("")

        for task in plan.tasks:
            lines.append(f"### {task.id}. {task.title}")
            lines.append("")
            lines.append(task.description)
            lines.append("")
            lines.append(f"*Why:* {task.rationale}")
            lines.append("")

        (self.output_dir / "execution_plan.md").write_text("\n".join(lines), encoding="utf-8")

    # -- changes_summary.md ------------------------------------------------

    def _write_changes_summary(
        self,
        plan: FeaturePlan,
        implementation: ImplementationResult,
        verification: VerificationReport,
        rollback: RollbackReport | None = None,
    ) -> None:
        lines: list[str] = []
        lines.append("# Changes Summary")
        lines.append("")
        lines.append(f"Implemented: **{plan.feature_name}**")
        lines.append("")

        if rollback and rollback.performed:
            lines.append("## 🔴 ROLLED BACK")
            lines.append("")
            lines.append(
                "Critical verification checks failed, so **every change in this run "
                "was automatically reverted** to protect existing functionality. The "
                "repository is back in its original state."
            )
            lines.append("")
            lines.append(f"**Reason:** {rollback.reason}")
            lines.append("")
            lines.append(f"- Files restored to original content: {len(rollback.restored_files)}")
            lines.append(f"- Newly created files removed: {len(rollback.deleted_files)}")
            if rollback.rollback_errors:
                lines.append(f"- ⚠ Rollback errors (manual review needed): {len(rollback.rollback_errors)}")
                for err in rollback.rollback_errors:
                    lines.append(f"  - {err}")
            lines.append("")
            lines.append(
                "The sections below describe what *was attempted* before the rollback, "
                "for debugging."
            )
            lines.append("")

        total_added = sum(c.lines_added for c in implementation.changes)
        total_removed = sum(c.lines_removed for c in implementation.changes)
        created = [c for c in implementation.changes if c.action.value == "create"]
        modified = [c for c in implementation.changes if c.action.value == "modify"]

        lines.append(
            f"- **{len(implementation.changes)}** files touched "
            f"({len(created)} created, {len(modified)} modified)"
        )
        lines.append(f"- **+{total_added} / -{total_removed}** lines")
        lines.append("")

        if implementation.errors:
            lines.append("## ⚠ Errors During Implementation")
            lines.append("")
            for err in implementation.errors:
                lines.append(f"- {err}")
            lines.append("")

        lines.append("## What Changed, File by File")
        lines.append("")
        for change in implementation.changes:
            icon = "🆕" if change.action.value == "create" else "✏️"
            lines.append(f"### {icon} `{change.relative_path}`")
            lines.append("")
            lines.append(change.description)
            lines.append(f"")
            lines.append(f"*+{change.lines_added} / -{change.lines_removed} lines*")
            lines.append("")

        lines.append("## Verification Results")
        lines.append("")
        lines.append(f"**Overall: {'✅ ALL CHECKS PASSED' if verification.all_passed else '❌ SOME CHECKS FAILED'}**")
        lines.append("")
        lines.append("| Check | Result | Critical | Detail |")
        lines.append("|-------|--------|----------|--------|")
        for check in verification.checks:
            status = "✅ PASS" if check.passed else "❌ FAIL"
            crit = "yes" if check.critical else "no"
            detail_oneline = check.detail.replace("\n", " ").strip()[:180]
            lines.append(f"| `{check.name}` | {status} | {crit} | {detail_oneline} |")
        lines.append("")

        lines.append("<details><summary>Full verification detail</summary>")
        lines.append("")
        for check in verification.checks:
            lines.append(f"**{check.name}**")
            lines.append("")
            lines.append("```")
            lines.append(check.detail)
            lines.append("```")
            lines.append("")
        lines.append("</details>")

        (self.output_dir / "changes_summary.md").write_text("\n".join(lines), encoding="utf-8")

    # -- modified_files.md ------------------------------------------------

    def _write_modified_files(
        self, implementation: ImplementationResult, rollback: RollbackReport | None = None
    ) -> None:
        lines: list[str] = []
        lines.append("# Modified Files")
        lines.append("")

        if rollback and rollback.performed:
            lines.append(
                "**Note:** all changes below were rolled back due to a critical "
                "verification failure -- none of them are present in the repository "
                "anymore. See `changes_summary.md` for the reason."
            )
            lines.append("")

        lines.append("| File | Action | Lines Added | Lines Removed |")
        lines.append("|------|--------|-------------|----------------|")
        for change in sorted(implementation.changes, key=lambda c: c.relative_path):
            lines.append(
                f"| `{change.relative_path}` | {change.action.value} | "
                f"+{change.lines_added} | -{change.lines_removed} |"
            )
        lines.append("")

        if implementation.errors:
            lines.append("## Files That Failed")
            lines.append("")
            for err in implementation.errors:
                lines.append(f"- {err}")

        (self.output_dir / "modified_files.md").write_text("\n".join(lines), encoding="utf-8")