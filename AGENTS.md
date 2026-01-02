# AGENTS.md

This document provides guidance for AI agents working on the CHAI codebase.

## Project Overview

CHAI is an open-source data pipeline for indexing package managers (crates, homebrew, debian, pkgx, npm). Each package manager has its own indexer in `package_managers/` that fetches, parses, and diffs package data against the CHAI database.

## Repository Structure

```
chai/
├── core/                    # Shared infrastructure (models, config, db, logging)
│   ├── models/              # SQLAlchemy ORM models
│   ├── config.py            # Configuration classes (URLs, dependency types, etc.)
│   ├── db.py                # Database connection utilities
│   ├── structs.py           # Shared data structures (Cache, DiffResult, etc.)
│   └── diff.py              # Shared diffing logic (normalized dependency diffing)
├── package_managers/        # Package manager-specific indexers
│   ├── crates/              # Rust/Cargo crates indexer
│   ├── homebrew/            # macOS Homebrew indexer
│   ├── debian/              # Debian packages indexer
│   └── pkgx/                # pkgx package indexer
├── tests/                   # Test suite
│   ├── conftest.py          # Shared pytest fixtures
│   └── package_managers/    # Package manager-specific tests
├── ranker/                  # TeaRank algorithm
└── scripts/                 # Utility scripts
```

## Development Workflow

### Environment Setup

```bash
# Sync all dependencies (indexers + ranker + dev tools)
uv sync --all-groups

# Install the package in editable mode (required for imports to work)
uv pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest

# Run tests for a specific package manager
pytest tests/package_managers/crates/

# Run with coverage
pytest --cov=.
```

### Linting & Formatting

```bash
# Check linting issues
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
ruff format .
```

### Git Workflow

- **Primary remote**: `fork` (contributor's fork)
- **Upstream remote**: `origin` (teaxyz/chai)
- Create feature branches from `main` on `fork`

```bash
# Push to fork
git push fork <branch-name>
```

## Code Conventions

### Python Style

- Python 3.11+ required
- Use type hints for all function signatures
- Use dataclasses for data structures
- Follow existing patterns in neighboring files
- No comments unless code is complex and requires context

### Testing Patterns

- Tests live in `tests/` mirroring the source structure
- Use pytest fixtures from `conftest.py`
- Mock database operations; test core logic directly
- Use the `@pytest.mark.*` decorators for categorization (unit, integration, transformer, etc.)

### Package Manager Indexers

Each package manager follows a similar structure:
- `main.py` - Entry point and orchestration
- `diff.py` - Diffing logic (packages, URLs, dependencies)
- `structs.py` - Package manager-specific data structures
- `normalizer.py` - Converts PM-specific data to normalized format

## Key Data Structures

### Cache (core/structs.py)

```python
@dataclass
class Cache:
    package_map: dict[str, Package]           # import_id -> Package
    url_map: dict[URLKey, URL]                # (url, type_id) -> URL
    package_urls: dict[UUID, set[PackageURL]] # pkg_id -> PackageURL links
    dependencies: dict[UUID, set[LegacyDependency]]  # pkg_id -> deps
```

### Dependency Types

Priority order (highest to lowest):
1. RUNTIME (normal dependencies)
2. BUILD (build-time dependencies)
3. TEST (test dependencies)
4. DEVELOPMENT (dev dependencies)
5. OPTIONAL (optional features)
6. RECOMMENDED (suggested packages)

## Common Tasks

### Adding a New Package Manager

1. Create `package_managers/<name>/` directory
2. Implement `structs.py` with PM-specific data classes
3. Implement `normalizer.py` to convert to normalized format
4. Implement `diff.py` using shared `core/diff.py` functions
5. Add tests in `tests/package_managers/<name>/`

### Modifying Dependency Diffing

The shared diffing logic lives in `core/diff.py`. Package manager-specific extraction is handled by normalizers in each PM's `normalizer.py`.
