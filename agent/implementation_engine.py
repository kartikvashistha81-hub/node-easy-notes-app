"""
agent.implementation_engine
============================
STEP 5: actually write the feature. Every method below returns complete,
runnable source code -- no TODOs, no placeholders. Each generator is
dispatched by the FeatureTask.id assigned in feature_planner, and writes
against the LocatedFile.absolute_path resolved by file_locator (never a
hardcoded path).

Every write is backed up first (original content for modified files,
"was newly created" flag for new files) so `rollback()` can undo the
entire implementation byte-for-byte if verification later finds a
critical regression -- see agent.planner for when rollback is triggered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from . import code_templates as tmpl
from .logger_setup import get_logger
from .models import (
    ActionType,
    ChangeRecord,
    CodebaseAnalysis,
    ImplementationResult,
    LocatedFile,
    RollbackReport,
)

logger = get_logger(__name__)


class ImplementationError(Exception):
    """Raised for implementation failures that aren't simple per-task errors
    (e.g. a content generator itself is missing) -- collected by `implement`
    rather than propagated, but given its own type so callers/tests can
    distinguish "a generator bug" from "a filesystem error" if needed."""


class ImplementationEngine:
    """Writes every located file's new content to disk, with backups."""

    def __init__(self) -> None:
        # Maps FeatureTask.id -> a function(LocatedFile) -> new file content.
        # T7 (frontend) is intentionally absent: it's a multi-file task
        # handled by _write_frontend instead of a single generator.
        self._generators: dict[str, Callable[[LocatedFile], str]] = {
            "T1": lambda lf: tmpl.note_model(),
            "T2": lambda lf: tmpl.note_controller(),  # T2 & T3 both land in note.controller.js
            "T3": lambda lf: tmpl.note_controller(),
            "T4": lambda lf: tmpl.note_routes(),
            "T5": lambda lf: tmpl.database_config(),
            "T6": lambda lf: tmpl.server_entry(),
            "T8": lambda lf: tmpl.migration_script(),
            "T9": lambda lf: tmpl.package_json(lf.absolute_path),
            "T10": lambda lf: tmpl.smoke_test(),
            "T11": lambda lf: tmpl.readme(lf.absolute_path),
            "T12": lambda lf: tmpl.env_example(),
            "T13": lambda lf: tmpl.gitignore(lf.absolute_path),
        }

    def implement(
        self, located_files: list[LocatedFile], analysis: CodebaseAnalysis
    ) -> ImplementationResult:
        """Writes every located file. Never raises: individual task failures
        are collected into result.errors so one bad task doesn't abort the
        whole run, and so verification/rollback can react to them."""
        result = ImplementationResult()

        # T2 and T3 both target note.controller.js -- only write it once,
        # since both tasks' logic lives in the single note_controller()
        # template; writing it twice would just redundantly regenerate the
        # same content and double-count it as a "change".
        already_written: set[str] = set()

        for lf in located_files:
            try:
                if lf.task.id == "T7":
                    result.changes.extend(self._write_frontend(lf.absolute_path))
                    continue

                if lf.relative_path in already_written:
                    logger.info(
                        "Skipping %s -- %s was already written by an earlier task",
                        lf.task.id,
                        lf.relative_path,
                    )
                    continue

                generator = self._generators.get(lf.task.id)
                if generator is None:
                    raise ImplementationError(
                        f"No content generator registered for task id '{lf.task.id}'"
                    )

                new_content = generator(lf)
                if not new_content or not new_content.strip():
                    raise ImplementationError(
                        f"Generator for {lf.task.id} produced empty content -- refusing to write"
                    )

                change = self._write_file(lf, new_content)
                result.changes.append(change)
                already_written.add(lf.relative_path)

            except (OSError, ImplementationError, ValueError) as exc:
                logger.error("Failed to implement %s (%s): %s", lf.task.id, lf.relative_path, exc)
                result.errors.append(f"{lf.task.id} ({lf.relative_path}): {exc}")

        return result

    def rollback(self, repo_root: Path, implementation: ImplementationResult, reason: str) -> RollbackReport:
        """Undoes every change recorded in `implementation`, restoring the
        repository to exactly the state it was in before this run: files
        that were modified get their original content back, files that were
        newly created get deleted. Best-effort -- collects per-file errors
        rather than stopping partway through."""
        report = RollbackReport(performed=True, reason=reason)

        # Restore in reverse order so unwinding is symmetric with the order
        # changes were originally applied in.
        for change in reversed(implementation.changes):
            absolute_path = repo_root / change.relative_path
            try:
                if change.was_created:
                    if absolute_path.exists():
                        absolute_path.unlink()
                        report.deleted_files.append(change.relative_path)
                        logger.info("Rollback: deleted %s", change.relative_path)
                elif change.original_content is not None:
                    absolute_path.write_text(change.original_content, encoding="utf-8")
                    report.restored_files.append(change.relative_path)
                    logger.info("Rollback: restored %s to its original content", change.relative_path)
            except OSError as exc:
                msg = f"Could not roll back {change.relative_path}: {exc}"
                logger.error(msg)
                report.rollback_errors.append(msg)

        if report.rollback_errors:
            logger.error(
                "Rollback completed with %d error(s) -- repository may be in a partially "
                "modified state. Manual review recommended.",
                len(report.rollback_errors),
            )
        else:
            logger.info(
                "Rollback complete: %d file(s) restored, %d file(s) deleted.",
                len(report.restored_files),
                len(report.deleted_files),
            )

        return report

    # -- internals -----------------------------------------------------

    def _write_file(self, lf: LocatedFile, new_content: str) -> ChangeRecord:
        old_content: Optional[str] = None
        if lf.exists:
            old_content = lf.absolute_path.read_text(encoding="utf-8", errors="replace")

        lf.absolute_path.parent.mkdir(parents=True, exist_ok=True)
        lf.absolute_path.write_text(new_content, encoding="utf-8")

        old_lines = (old_content or "").splitlines()
        new_lines = new_content.splitlines()
        added, removed = self._diff_counts(old_lines, new_lines)

        logger.info(
            "%s %s (+%d/-%d lines)",
            "Modified" if lf.exists else "Created",
            lf.relative_path,
            added,
            removed,
        )

        return ChangeRecord(
            relative_path=lf.relative_path,
            action=lf.task.action,
            description=lf.task.description,
            lines_added=added,
            lines_removed=removed,
            original_content=old_content,
            was_created=not lf.exists,
        )

    def _diff_counts(self, old_lines: list[str], new_lines: list[str]) -> tuple[int, int]:
        import difflib

        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        return added, removed

    def _write_frontend(self, public_dir: Path) -> list[ChangeRecord]:
        changes = []
        files = {
            "index.html": tmpl.frontend_index_html(),
            "app.js": tmpl.frontend_app_js(),
            "style.css": tmpl.frontend_style_css(),
        }
        for filename, content in files.items():
            path = public_dir / filename
            existed = path.exists()
            old_content = path.read_text(encoding="utf-8", errors="replace") if existed else None

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            lines = len(content.splitlines())
            logger.info("%s public/%s (+%d lines)", "Modified" if existed else "Created", filename, lines)
            changes.append(
                ChangeRecord(
                    relative_path=f"public/{filename}",
                    action=ActionType.MODIFY if existed else ActionType.CREATE,
                    description="Search & filter UI",
                    lines_added=lines,
                    lines_removed=0,
                    original_content=old_content,
                    was_created=not existed,
                )
            )
        return changes