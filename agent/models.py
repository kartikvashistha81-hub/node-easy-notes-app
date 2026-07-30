"""
agent.models
============
Shared, strongly-typed data structures passed between agent stages.

Keeping these in one module (rather than letting each stage invent its own
ad-hoc dicts) is what makes the pipeline composable: every stage takes the
previous stage's dataclass as input and returns its own dataclass as output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ActionType(str, Enum):
    """What the implementation engine should do with a given file."""

    CREATE = "create"
    MODIFY = "modify"


class ComponentRole(str, Enum):
    """
    Logical roles the codebase analyzer assigns to files it discovers.

    The file_locator resolves a FeatureTask's `target_component` (one of
    these roles) to a concrete file path -- this indirection is what lets
    the agent avoid hardcoding paths like "app/models/note.model.js".
    """

    SERVER_ENTRY = "server_entry"
    DB_CONFIG = "db_config"
    NOTE_MODEL = "note_model"
    NOTE_CONTROLLER = "note_controller"
    NOTE_ROUTES = "note_routes"
    PACKAGE_MANIFEST = "package_manifest"
    README = "readme"
    FRONTEND_ROOT = "frontend_root"
    MIGRATION_SCRIPT = "migration_script"
    ENV_EXAMPLE = "env_example"
    GITIGNORE = "gitignore"
    TEST_SUITE = "test_suite"


@dataclass
class FileInfo:
    """A single file discovered while exploring the repository."""

    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    content: str = ""


@dataclass
class RepositoryExploration:
    """Output of repository_explorer: everything observed about the repo."""

    root_path: Path
    all_files: list[FileInfo] = field(default_factory=list)
    package_json: Optional[dict] = None
    readme_text: Optional[str] = None
    directory_tree: str = ""
    git_remote: Optional[str] = None


@dataclass
class EndpointInfo:
    """A single HTTP route discovered in the codebase."""

    method: str
    path: str
    handler: str
    source_file: str


@dataclass
class SchemaFieldInfo:
    """A single field discovered in a Mongoose schema."""

    name: str
    field_type: str


@dataclass
class CodebaseAnalysis:
    """Output of codebase_analyzer: a structured understanding of the app."""

    language: str
    framework: str
    database: str
    orm: str
    has_frontend: bool
    entry_point: Optional[str]
    endpoints: list[EndpointInfo] = field(default_factory=list)
    models: dict[str, list[SchemaFieldInfo]] = field(default_factory=dict)
    dependencies: dict[str, str] = field(default_factory=dict)
    component_files: dict[ComponentRole, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class FeatureTask:
    """A single unit of work identified by the feature planner."""

    id: str
    title: str
    description: str
    target_component: ComponentRole
    action: ActionType
    rationale: str
    # Only set when target_component doesn't map to an existing file
    # (e.g. a brand-new frontend). Gives the file_locator a hint for
    # where to create it, following the repo's existing conventions.
    suggested_relative_path: Optional[str] = None


@dataclass
class FeaturePlan:
    """Output of feature_planner: the full plan for implementing the request."""

    user_request: str
    feature_name: str
    summary: str
    decision_rationale: list[str]
    tasks: list[FeatureTask] = field(default_factory=list)
    alternatives_considered: list[str] = field(default_factory=list)


@dataclass
class LocatedFile:
    """Output of file_locator: a FeatureTask resolved to a concrete path."""

    task: FeatureTask
    absolute_path: Path
    relative_path: str
    exists: bool


@dataclass
class ChangeRecord:
    """A record of one file actually written by the implementation engine."""

    relative_path: str
    action: ActionType
    description: str
    lines_added: int
    lines_removed: int
    original_content: Optional[str] = None
    was_created: bool = False

@dataclass
class ImplementationResult:
    """Output of implementation_engine."""

    changes: list[ChangeRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RollbackReport:
    """Output or status of a rollback operation."""

    success: bool = True
    rolled_back_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """A single pass/fail verification check."""

    name: str
    passed: bool
    detail: str
    critical: bool = True


@dataclass
@dataclass
class VerificationReport:
    """Output of verification_engine."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]