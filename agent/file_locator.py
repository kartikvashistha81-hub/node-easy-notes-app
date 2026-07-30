"""
agent.file_locator
===================
STEP 4: resolve each FeatureTask's logical `target_component` to an actual
file path on disk.

For MODIFY tasks, the path comes from `CodebaseAnalysis.component_files`,
which codebase_analyzer populated by *pattern-matching real file content*
(e.g. "which file calls mongoose.model(...)"), never by assuming a
filename. For CREATE tasks, the task's `suggested_relative_path` is used,
resolved against the repository root discovered by the explorer -- again,
no path is baked into this module itself.
"""

from __future__ import annotations

from pathlib import Path

from .logger_setup import get_logger
from .models import ActionType, CodebaseAnalysis, FeaturePlan, LocatedFile

logger = get_logger(__name__)


class FileLocationError(Exception):
    """Raised when a MODIFY task's target component can't be found in the repo."""


class FileLocator:
    """Resolves a FeaturePlan's tasks against a repository root + analysis."""

    def locate(
        self,
        repo_root: Path,
        analysis: CodebaseAnalysis,
        plan: FeaturePlan,
    ) -> list[LocatedFile]:
        located: list[LocatedFile] = []

        for task in plan.tasks:
            if task.action == ActionType.MODIFY:
                relative_path = analysis.component_files.get(task.target_component)
                if relative_path is None:
                    raise FileLocationError(
                        f"Task {task.id} ('{task.title}') needs to modify component "
                        f"'{task.target_component.value}', but no matching file was "
                        f"discovered in the repository during analysis."
                    )
                exists = True
            else:  # CREATE
                if not task.suggested_relative_path:
                    raise FileLocationError(
                        f"Task {task.id} ('{task.title}') is a CREATE task but has "
                        f"no suggested_relative_path to create at."
                    )
                relative_path = task.suggested_relative_path
                exists = (repo_root / relative_path).exists()

            absolute_path = (repo_root / relative_path).resolve()
            located.append(
                LocatedFile(
                    task=task,
                    absolute_path=absolute_path,
                    relative_path=relative_path,
                    exists=exists,
                )
            )
            logger.info(
                "%s -> %s (%s)",
                task.id,
                relative_path,
                "exists" if exists else "will be created",
            )

        return located