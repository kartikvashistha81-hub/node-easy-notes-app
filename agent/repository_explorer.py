"""
agent.repository_explorer
==========================
STEP 1 & 2 of the agent workflow: clone (or open) the target repository and
walk its full structure, reading every source/config/doc file so later
stages have real content to reason about instead of guessing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

from .logger_setup import get_logger
from .models import FileInfo, RepositoryExploration

logger = get_logger(__name__)

# Directories we never want to walk into -- dependency trees, VCS internals,
# build artifacts. Kept as a constant rather than hardcoded inline so it's
# easy to extend for other ecosystems later.
IGNORED_DIR_NAMES = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".venv",
    "venv",
}

# Extensions worth reading the *content* of. Anything else is still listed
# in the directory tree, but its content isn't loaded into memory.
TEXT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".env",
    ".yml",
    ".yaml",
    ".html",
    ".css",
    ".txt",
    "",  # dotfiles like .gitignore have empty suffix
}

MAX_FILE_BYTES = 300_000  # guard against accidentally reading huge files


class RepositoryExplorer:
    """Clones a git repository (if given a URL) or opens a local path, then
    inventories it into a RepositoryExploration object."""

    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir

    def obtain_repository(self, repo_source: str) -> Path:
        """
        Accepts either a git URL or a local filesystem path and returns the
        local path to the repository root, cloning it first if necessary.
        """
        looks_like_url = repo_source.startswith(("http://", "https://", "git@"))

        if not looks_like_url:
            local_path = Path(repo_source).expanduser().resolve()
            if not local_path.exists():
                raise FileNotFoundError(f"Repository path does not exist: {local_path}")
            logger.info("Opening existing local repository at %s", local_path)
            return local_path

        repo_name = repo_source.rstrip("/").split("/")[-1].removesuffix(".git")
        target_path = self.workspace_dir / repo_name

        if target_path.exists():
            logger.info("Repository already cloned at %s, reusing it", target_path)
            return target_path

        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Cloning %s into %s", repo_source, target_path)
        result = subprocess.run(
            ["git", "clone", repo_source, str(target_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

        return target_path

    def explore(self, repo_source: str) -> RepositoryExploration:
        """Full exploration entrypoint: obtain the repo, then inventory it."""
        root_path = self.obtain_repository(repo_source)

        all_files = self._walk(root_path)
        package_json = self._read_package_json(root_path)
        readme_text = self._read_readme(root_path)
        directory_tree = self._render_tree(root_path)
        git_remote = self._read_git_remote(root_path)

        exploration = RepositoryExploration(
            root_path=root_path,
            all_files=all_files,
            package_json=package_json,
            readme_text=readme_text,
            directory_tree=directory_tree,
            git_remote=git_remote,
        )

        logger.info(
            "Explored %d files under %s (package.json=%s, readme=%s)",
            len(all_files),
            root_path,
            bool(package_json),
            bool(readme_text),
        )
        return exploration

    # -- internal helpers ---------------------------------------------------

    def _walk(self, root_path: Path) -> list[FileInfo]:
        files: list[FileInfo] = []
        for path in sorted(root_path.rglob("*")):
            if not path.is_file():
                continue
            if any(part in IGNORED_DIR_NAMES for part in path.parts):
                continue

            size = path.stat().st_size
            content = ""
            if path.suffix in TEXT_EXTENSIONS and size <= MAX_FILE_BYTES:
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.warning("Could not read %s: %s", path, exc)

            files.append(
                FileInfo(
                    path=path,
                    relative_path=str(path.relative_to(root_path)),
                    extension=path.suffix,
                    size_bytes=size,
                    content=content,
                )
            )
        return files

    def _read_package_json(self, root_path: Path) -> Optional[dict]:
        pkg_path = root_path / "package.json"
        if not pkg_path.exists():
            return None
        try:
            return json.loads(pkg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not parse package.json: %s", exc)
            return None

    def _read_readme(self, root_path: Path) -> Optional[str]:
        for candidate in ("README.md", "Readme.md", "readme.md", "README.rst"):
            p = root_path / candidate
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace")
        return None

    def _read_git_remote(self, root_path: Path) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(root_path), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() or None
        except (subprocess.SubprocessError, OSError):
            return None

    def _render_tree(self, root_path: Path, max_depth: int = 4) -> str:
        lines: list[str] = [root_path.name + "/"]

        def walk(dir_path: Path, prefix: str, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                entries = sorted(
                    [p for p in dir_path.iterdir() if p.name not in IGNORED_DIR_NAMES],
                    key=lambda p: (p.is_file(), p.name.lower()),
                )
            except PermissionError:
                return
            for i, entry in enumerate(entries):
                connector = "└── " if i == len(entries) - 1 else "├── "
                suffix = "/" if entry.is_dir() else ""
                lines.append(f"{prefix}{connector}{entry.name}{suffix}")
                if entry.is_dir():
                    extension = "    " if i == len(entries) - 1 else "│   "
                    walk(entry, prefix + extension, depth + 1)

        walk(root_path, "", 1)
        return "\n".join(lines)