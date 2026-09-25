"""Container-path contract tests — Phase 7 assumptions, checked without a daemon.

There is no Docker in the development environment, so `docker compose up` (and the
image build it implies) cannot be rehearsed here. That leaves a real gap: a change
can silently invalidate the deploy — a module moves out of a package and vanishes
from the wheel, `.dockerignore` starts excluding something the runtime reads, a
compose path no longer exists — and nothing in the suite would notice.

These tests pin the assumptions the image and the compose stack actually rely on,
statically and hermetically. They are **not** a substitute for running the stack:
they cannot prove the image builds, that `pip install .` resolves on python:3.12-slim,
or that `init_db` succeeds against a real PostGIS. They narrow the blast radius to
exactly those things, and they fail loudly when a change breaks the deploy contract.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import pathlib
import re
import sys
import tomllib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
APP = BACKEND / "app"

STDLIB = set(sys.stdlib_module_names)

# Imported directly by app/main.py, but shipped as a hard dependency of fastapi, so
# it is always present after `pip install .` — noted rather than treated as a gap.
TRANSITIVE_OK = {"starlette"}


def _pyproject() -> dict:
    with open(BACKEND / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def _runtime_modules() -> list[pathlib.Path]:
    return sorted(APP.rglob("*.py"))


def _packaged_dirs() -> set[str]:
    """Mirror setuptools' find_packages(where=backend, include=["app*"]).

    A directory ships only if it holds an __init__.py and its top-level name
    matches the include pattern — hence "every runtime module lives in one".
    """
    include = _pyproject()["tool"]["setuptools"]["packages"]["find"]["include"]
    prefixes = tuple(p.rstrip("*") for p in include)
    found = set()
    for init in APP.rglob("__init__.py"):
        parts = init.parent.relative_to(BACKEND).parts
        if parts and parts[0].startswith(prefixes):
            found.add(".".join(parts))
    return found


def _third_party_imports() -> set[str]:
    found: set[str] = set()
    for path in _runtime_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] if node.level == 0 else []
            else:
                continue
            for name in names:
                head = name.split(".")[0]
                if head and head != "app" and head not in STDLIB:
                    found.add(head.lower().replace("_", "-"))
    return found


# --------------------------------------------------------------- packaging


def test_every_runtime_module_lives_in_a_packaged_directory():
    """A module outside a package ships nowhere, so the image would fail to import it."""
    packaged = _packaged_dirs()
    runtime_dirs = {
        str(p.parent.relative_to(BACKEND)).replace("\\", "/")
        for p in _runtime_modules()
        if p.name != "__init__.py"
    }
    unpackaged = sorted(
        d for d in runtime_dirs if d.replace("/", ".") not in packaged
    )
    assert unpackaged == [], f"not packaged, so absent from the image: {unpackaged}"


@pytest.mark.parametrize(
    "module",
    [
        "app",
        "app.main",
        "app.scripts.init_db",
        "app.providers.weather.imd",
        "app.providers.weather.open_meteo",
        "app.providers.weather.met_norway",
        "app.services.response.provenance",
        "app.services.sources.registry",
    ],
)
def test_module_ships_in_the_image(module):
    """A module ships when the package that holds it is packaged."""
    packaged = _packaged_dirs()
    if module in packaged:  # the root package itself
        return
    path = BACKEND / (module.replace(".", "/") + ".py")
    assert path.exists(), f"{module} does not exist"
    assert module.rsplit(".", 1)[0] in packaged, (
        f"{module.rsplit('.', 1)[0]} is not packaged, so {module} never reaches the image"
    )


def test_pyproject_references_no_file_dockerignore_would_exclude():
    """`readme = "README.md"` would break the build: .dockerignore excludes *.md."""
    project = _pyproject()["project"]
    assert "readme" not in project
    assert "license-files" not in project


# ------------------------------------------------------- dependency closure


def test_runtime_dependencies_are_declared():
    declared = {
        re.split(r"[><=\[!; ]", dep.strip())[0].lower().replace("_", "-")
        for dep in _pyproject()["project"]["dependencies"]
    }
    undeclared = sorted(_third_party_imports() - declared - TRANSITIVE_OK)
    assert undeclared == [], f"runtime imports not installable by `pip install .`: {undeclared}"


def test_runtime_never_imports_the_dev_extra():
    """The image runs `pip install .` with no dev extra."""
    assert not (_third_party_imports() & {"pytest", "pytest-asyncio"})


# ------------------------------------------------- Linux vs Windows traps


def test_app_internal_imports_resolve_with_exact_case():
    """Windows matches paths case-insensitively; Linux does not, so mismatches only
    break inside the container."""
    on_disk = {str(p.relative_to(BACKEND)).replace("\\", "/") for p in _runtime_modules()}
    mismatches: list[str] = []
    for path in _runtime_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets = [node.module] if node.module.startswith("app") else []
            elif isinstance(node, ast.Import):
                targets = [a.name for a in node.names if a.name.startswith("app")]
            for target in targets:
                if target == "app":
                    continue
                rel = target.replace(".", "/")
                if f"{rel}.py" not in on_disk and f"{rel}/__init__.py" not in on_disk:
                    mismatches.append(f"{path.name}: {target}")
    assert mismatches == [], f"case/name mismatch breaks on Linux: {mismatches}"


def test_no_hardcoded_windows_paths_in_runtime_code():
    offenders = [
        f"{path.name}:{i}"
        for path in _runtime_modules()
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"[A-Za-z]:\\\\", line)
    ]
    assert offenders == [], f"Windows-only paths would break the Linux image: {offenders}"


# ------------------------------------------------------- .dockerignore vs runtime


def _dockerignore_patterns() -> list[str]:
    return [
        line.strip()
        for line in (BACKEND / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _excluded(path: str) -> bool:
    for pattern in _dockerignore_patterns():
        stripped = pattern.rstrip("/")
        if fnmatch.fnmatch(path, stripped) or fnmatch.fnmatch(path, stripped + "/*"):
            return True
        if "/" not in stripped and fnmatch.fnmatch(pathlib.PurePosixPath(path).name, stripped):
            return True
    return False


@pytest.mark.parametrize(
    "needed",
    [
        # COPY'd by the Dockerfile...
        "pyproject.toml",
        "app/main.py",
        "app/providers/weather/met_norway.py",
        # ...and the seed files the app resolves relative to WORKDIR /app.
        "data/cities_seed.json",
        "data/stations_sample.json",
    ],
)
def test_dockerignore_keeps_what_the_image_needs(needed):
    assert not _excluded(needed), f"{needed} is docker-ignored but the image needs it"


def test_dockerfile_copy_sources_exist_in_the_build_context():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    sources = re.findall(r"^COPY\s+(\S+)", dockerfile, re.MULTILINE)
    assert sources, "expected the Dockerfile to COPY the app"
    missing = [s for s in sources if not (BACKEND / s).exists()]
    assert missing == [], f"COPY sources not in the build context: {missing}"


def test_runtime_never_reads_the_dockerignored_fixtures_directory():
    """fixtures/ is docker-ignored, so a runtime read of it would fail in the image.

    Checked through the AST (string constants, minus docstrings) because a *comment*
    mentioning fixtures/ is not a dependency — an earlier grep-based check flagged one.
    """
    offenders: list[str] = []
    for path in _runtime_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        strings = [
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        if any("fixtures" in s and s not in docstrings for s in strings):
            offenders.append(str(path.relative_to(BACKEND)))
    assert offenders == [], f"runtime reads docker-ignored fixtures/: {offenders}"


# ------------------------------------------------------------- Dockerfile contract


def test_dockerfile_runs_as_non_root_and_agrees_with_compose_ports():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile
    assert "--uid 10001" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "api/v1/health" in dockerfile  # the healthcheck target exists as a route

    cmd = re.search(r"CMD\s+(\[.*?\])", dockerfile, re.DOTALL)
    tokens = json.loads(cmd.group(1)) if cmd else []
    assert "--port" in tokens, f"CMD not in array form: {tokens}"
    assert tokens[tokens.index("--port") + 1] == "8000"


# ------------------------------------------------------------- compose contract


@pytest.fixture
def compose() -> dict:
    yaml = pytest.importorskip("yaml", reason="PyYAML is not in the dev extra")
    return yaml.safe_load((ROOT / "infra/docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_publishes_the_port_the_image_exposes(compose):
    backend = compose["services"]["backend"]
    assert backend["ports"] == ["8000:8000"]
    # No healthcheck here on purpose: compose inherits the image's.
    assert "healthcheck" not in backend


def test_compose_gates_startup_on_healthy_dependencies(compose):
    depends = compose["services"]["backend"]["depends_on"]
    assert depends["postgis"]["condition"] == "service_healthy"
    assert depends["redis"]["condition"] == "service_healthy"


def test_compose_in_cluster_urls_are_literal_not_interpolated(compose):
    """Compose interpolates from the compose file's directory, so a root `.env`
    referenced as ${VAR} would be silently ignored with `-f infra/...`."""
    environment = compose["services"]["backend"]["environment"]
    assert "${" not in json.dumps(environment)
    assert environment["REDIS_URL"] == "redis://redis:6379/0"
    assert environment["DATABASE_URL"].startswith(
        "postgresql+asyncpg://weathergpt:weathergpt@postgis:5432"
    )


def test_web_profile_serves_the_pwa_and_proxies_to_the_real_service(compose):
    infra = ROOT / "infra"
    web = compose["services"]["web"]
    assert web["ports"] == ["8080:80"]
    assert web["depends_on"]["backend"]["condition"] == "service_healthy"

    sources = [volume.split(":")[1] for volume in web["volumes"]]
    host_paths = [volume.split(":")[0] for volume in web["volumes"]]
    assert "/usr/share/nginx/html" in sources
    for host in host_paths:
        assert (infra / host).exists(), f"compose mount source missing: {host}"

    nginx = (infra / "nginx.conf").read_text(encoding="utf-8")
    assert "proxy_pass http://backend:8000" in nginx


def test_single_origin_bundle_is_present_for_both_serving_paths():
    """nginx `web` profile and Render's WEB_DIR both serve this committed bundle."""
    assert (ROOT / "frontend/build/web/index.html").exists()
    assert (ROOT / "frontend/build/web/main.dart.js").exists()
