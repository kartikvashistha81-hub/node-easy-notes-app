"""
agent.codebase_analyzer
========================
STEP 2 (continued): turn the raw file inventory from repository_explorer
into a structured understanding of the application -- what framework it
uses, what endpoints exist, what the Mongoose schema looks like, and which
file plays which architectural role.

This is deliberately heuristic/regex-based rather than a full JS parser:
for a small Express/Mongoose codebase like this one, regexes over real
file content are reliable and don't require pulling in an external JS
AST toolchain from Python. Every heuristic here is applied to the *actual*
file content discovered by the explorer -- nothing is hardcoded to a
specific filename.
"""

from __future__ import annotations

import re

from .logger_setup import get_logger
from .models import (
    CodebaseAnalysis,
    ComponentRole,
    EndpointInfo,
    RepositoryExploration,
    SchemaFieldInfo,
)

logger = get_logger(__name__)

_ROUTE_PATTERN = re.compile(
    r"""(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]\s*,\s*([\w.]+)""",
    re.IGNORECASE,
)
_SCHEMA_BLOCK_PATTERN = re.compile(
    r"(\w+)\s*=\s*(?:mongoose\.)?Schema\s*\(\s*\{(.*?)\}\s*,?\s*(?:\{.*?\})?\s*\)",
    re.DOTALL,
)
_SCHEMA_FIELD_PATTERN = re.compile(r"(\w+)\s*:\s*(String|Number|Boolean|Date|\[String\]|\[Number\])")
_MODEL_EXPORT_PATTERN = re.compile(r"mongoose\.model\(\s*['\"](\w+)['\"]")


class CodebaseAnalyzer:
    """Builds a CodebaseAnalysis from a RepositoryExploration."""

    def analyze(self, exploration: RepositoryExploration) -> CodebaseAnalysis:
        pkg = exploration.package_json or {}
        dependencies = {
            **pkg.get("dependencies", {}),
            **pkg.get("devDependencies", {}),
        }

        framework = self._detect_framework(dependencies)
        database, orm = self._detect_database(dependencies, exploration)
        entry_point = pkg.get("main")

        component_files = self._locate_components(exploration, entry_point)
        endpoints = self._extract_endpoints(exploration)
        models = self._extract_models(exploration)
        has_frontend = self._detect_frontend(exploration)

        notes: list[str] = []
        if not has_frontend:
            notes.append(
                "No frontend/static assets directory found -- this repository is a "
                "backend-only REST API. A minimal UI may need to be created from "
                "scratch to satisfy 'add search UI / filtering UI'."
            )
        if ComponentRole.DB_CONFIG in component_files:
            db_file = next(
                f for f in exploration.all_files
                if f.relative_path == component_files[ComponentRole.DB_CONFIG]
            )
            if "mongodb://" in db_file.content and "process.env" not in db_file.content:
                notes.append(
                    "Database connection string is hardcoded rather than read from "
                    "an environment variable -- worth externalizing via dotenv."
                )

        analysis = CodebaseAnalysis(
            language="javascript",
            framework=framework,
            database=database,
            orm=orm,
            has_frontend=has_frontend,
            entry_point=entry_point,
            endpoints=endpoints,
            models=models,
            dependencies=dependencies,
            component_files=component_files,
            notes=notes,
        )

        logger.info(
            "Analysis complete: framework=%s db=%s/%s endpoints=%d models=%s frontend=%s",
            framework, database, orm, len(endpoints), list(models.keys()), has_frontend,
        )
        return analysis

    # -- detection helpers ----------------------------------------------

    def _detect_framework(self, dependencies: dict[str, str]) -> str:
        if "express" in dependencies:
            return "express"
        if "koa" in dependencies:
            return "koa"
        if "fastify" in dependencies:
            return "fastify"
        return "unknown"

    def _detect_database(
        self, dependencies: dict[str, str], exploration: RepositoryExploration
    ) -> tuple[str, str]:
        if "mongoose" in dependencies:
            return "mongodb", "mongoose"
        if "sequelize" in dependencies:
            return "sql", "sequelize"
        if "pg" in dependencies:
            return "postgresql", "pg"
        for f in exploration.all_files:
            if "mongodb://" in f.content or "mongodb+srv://" in f.content:
                return "mongodb", "unknown"
        return "unknown", "unknown"

    def _detect_frontend(self, exploration: RepositoryExploration) -> bool:
        frontend_dir_names = {"public", "client", "views", "frontend", "static"}
        for f in exploration.all_files:
            top_level_dir = f.relative_path.split("/")[0]
            if top_level_dir in frontend_dir_names:
                return True
            if f.extension in {".html", ".jsx", ".tsx", ".vue"}:
                return True
        return False

    def _locate_components(
        self, exploration: RepositoryExploration, entry_point: str | None
    ) -> dict[ComponentRole, str]:
        components: dict[ComponentRole, str] = {}

        for f in exploration.all_files:
            lower_rel = f.relative_path.lower()

            if entry_point and f.relative_path == entry_point:
                components[ComponentRole.SERVER_ENTRY] = f.relative_path
            elif "app.listen" in f.content and ComponentRole.SERVER_ENTRY not in components:
                components[ComponentRole.SERVER_ENTRY] = f.relative_path

            if f.relative_path == "package.json":
                components[ComponentRole.PACKAGE_MANIFEST] = f.relative_path

            if lower_rel in {"readme.md", "readme.rst"}:
                components[ComponentRole.README] = f.relative_path

            if lower_rel == ".gitignore":
                components[ComponentRole.GITIGNORE] = f.relative_path

            if lower_rel in {".env.example", ".env.sample"}:
                components[ComponentRole.ENV_EXAMPLE] = f.relative_path

            if ("database" in lower_rel or "db.config" in lower_rel or "db" in lower_rel) and (
                "config" in lower_rel and f.extension == ".js"
            ):
                components[ComponentRole.DB_CONFIG] = f.relative_path

            if _MODEL_EXPORT_PATTERN.search(f.content) and "model" in lower_rel:
                components[ComponentRole.NOTE_MODEL] = f.relative_path

            if "controller" in lower_rel and re.search(r"exports\.\w+\s*=", f.content):
                components[ComponentRole.NOTE_CONTROLLER] = f.relative_path

            if "route" in lower_rel and _ROUTE_PATTERN.search(f.content):
                components[ComponentRole.NOTE_ROUTES] = f.relative_path

        return components

    def _extract_endpoints(self, exploration: RepositoryExploration) -> list[EndpointInfo]:
        endpoints: list[EndpointInfo] = []
        for f in exploration.all_files:
            for match in _ROUTE_PATTERN.finditer(f.content):
                method, path, handler = match.groups()
                endpoints.append(
                    EndpointInfo(
                        method=method.upper(),
                        path=path,
                        handler=handler,
                        source_file=f.relative_path,
                    )
                )
        return endpoints

    def _extract_models(
        self, exploration: RepositoryExploration
    ) -> dict[str, list[SchemaFieldInfo]]:
        models: dict[str, list[SchemaFieldInfo]] = {}
        for f in exploration.all_files:
            model_name_match = _MODEL_EXPORT_PATTERN.search(f.content)
            if not model_name_match:
                continue
            model_name = model_name_match.group(1)

            schema_match = _SCHEMA_BLOCK_PATTERN.search(f.content)
            fields: list[SchemaFieldInfo] = []
            if schema_match:
                body = schema_match.group(2)
                for field_match in _SCHEMA_FIELD_PATTERN.finditer(body):
                    fields.append(
                        SchemaFieldInfo(name=field_match.group(1), field_type=field_match.group(2))
                    )
            models[model_name] = fields
        return models