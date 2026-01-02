"""
Shared dependency diffing logic for all package managers.

This module provides a normalized approach to dependency diffing that can be
used across all package managers (crates, homebrew, debian, pkgx, etc.).

The flow is:
    PM-specific data → normalize_*() → NormalizedPackage → diff_dependencies() → results
"""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from uuid import UUID

from core.logger import Logger
from core.models import LegacyDependency, Package
from core.structs import Cache

logger = Logger("core_diff")


class DependencyType(IntEnum):
    """
    Normalized dependency types across all package managers.

    Priority order (lower number = higher priority):
    - RUNTIME: Normal runtime dependencies (highest priority)
    - BUILD: Build-time dependencies
    - TEST: Test dependencies
    - DEVELOPMENT: Development dependencies
    - OPTIONAL: Optional/feature dependencies
    - RECOMMENDED: Recommended/suggested packages (lowest priority)
    """

    RUNTIME = 1
    BUILD = 2
    TEST = 3
    DEVELOPMENT = 4
    OPTIONAL = 5
    RECOMMENDED = 6

    def __str__(self) -> str:
        return self.name.lower()


DEPENDENCY_PRIORITY: dict[DependencyType, int] = {
    DependencyType.RUNTIME: 1,
    DependencyType.BUILD: 2,
    DependencyType.TEST: 3,
    DependencyType.DEVELOPMENT: 4,
    DependencyType.OPTIONAL: 5,
    DependencyType.RECOMMENDED: 6,
}


@dataclass(frozen=True)
class ParsedDependency:
    """
    A single dependency extracted from package manager data.

    Attributes:
        name: The dependency identifier (import_id in CHAI)
        dependency_type: The normalized dependency type
    """

    name: str
    dependency_type: DependencyType


@dataclass
class NormalizedPackage:
    """
    Package data normalized for dependency diffing.

    Attributes:
        identifier: The package's import_id in CHAI
        dependencies: List of parsed dependencies
    """

    identifier: str
    dependencies: list[ParsedDependency]


def deduplicate_dependencies(
    dependencies: list[ParsedDependency],
) -> dict[str, DependencyType]:
    """
    Deduplicate dependencies by name, keeping the highest priority type.

    When the same dependency appears with multiple types (e.g., both runtime
    and build), we keep only the highest priority type to satisfy the DB's
    unique constraint on (package_id, dependency_id).

    Args:
        dependencies: List of parsed dependencies (may contain duplicates)

    Returns:
        Dict mapping dependency name to its highest-priority type
    """
    deduped: dict[str, DependencyType] = {}

    for dep in dependencies:
        if not dep.name:
            continue

        if dep.name in deduped:
            existing_priority = DEPENDENCY_PRIORITY.get(deduped[dep.name], 999)
            new_priority = DEPENDENCY_PRIORITY.get(dep.dependency_type, 999)

            if new_priority < existing_priority:
                deduped[dep.name] = dep.dependency_type
        else:
            deduped[dep.name] = dep.dependency_type

    return deduped


def resolve_dependency_type_id(
    dep_type: DependencyType, dependency_types_config: object
) -> UUID:
    """
    Map a normalized DependencyType to the corresponding UUID from config.

    Args:
        dep_type: The normalized dependency type
        dependency_types_config: Config object with dependency type UUIDs

    Returns:
        The UUID for the dependency type from the database
    """
    type_map = {
        DependencyType.RUNTIME: dependency_types_config.runtime,
        DependencyType.BUILD: dependency_types_config.build,
        DependencyType.TEST: dependency_types_config.test,
        DependencyType.DEVELOPMENT: dependency_types_config.development,
        DependencyType.OPTIONAL: dependency_types_config.optional,
        DependencyType.RECOMMENDED: dependency_types_config.recommended,
    }

    if dep_type not in type_map:
        raise ValueError(f"Unknown dependency type: {dep_type}")

    return type_map[dep_type]


def diff_dependencies(
    normalized_pkg: NormalizedPackage,
    cache: Cache,
    dependency_types_config: object,
    now: datetime | None = None,
) -> tuple[list[LegacyDependency], list[LegacyDependency]]:
    """
    Compute new and removed dependencies for a normalized package.

    This is the shared diffing algorithm used by all package managers. It:
    1. Deduplicates dependencies by name (keeping highest priority type)
    2. Resolves dependency names to package IDs via the cache
    3. Compares against existing dependencies in the cache
    4. Returns lists of new and removed LegacyDependency objects

    Args:
        normalized_pkg: Package with normalized dependency data
        cache: The CHAI cache containing package_map and dependencies
        dependency_types_config: Config object with dependency type UUIDs
        now: Timestamp for created_at/updated_at (defaults to datetime.now())

    Returns:
        Tuple of (new_deps, removed_deps) as LegacyDependency lists
    """
    if now is None:
        now = datetime.now()

    package = cache.package_map.get(normalized_pkg.identifier)
    if not package:
        logger.debug(
            f"Package {normalized_pkg.identifier} not in cache, skipping deps"
        )
        return [], []

    pkg_id: UUID = package.id

    deduped = deduplicate_dependencies(normalized_pkg.dependencies)

    actual: set[tuple[UUID, UUID]] = set()
    for dep_name, dep_type in deduped.items():
        dependency_pkg: Package | None = cache.package_map.get(dep_name)
        if not dependency_pkg:
            logger.debug(f"{dep_name}, dep of {normalized_pkg.identifier} not in cache")
            continue

        dep_type_id = resolve_dependency_type_id(dep_type, dependency_types_config)
        actual.add((dependency_pkg.id, dep_type_id))

    existing: set[tuple[UUID, UUID]] = {
        (dep.dependency_id, dep.dependency_type_id)
        for dep in cache.dependencies.get(pkg_id, set())
    }

    new_tuples = actual - existing
    removed_tuples = existing - actual

    new_deps: list[LegacyDependency] = [
        LegacyDependency(
            package_id=pkg_id,
            dependency_id=dep_id,
            dependency_type_id=type_id,
            created_at=now,
            updated_at=now,
        )
        for dep_id, type_id in new_tuples
    ]

    removed_deps: list[LegacyDependency] = []
    cache_deps: set[LegacyDependency] = cache.dependencies.get(pkg_id, set())
    for removed_dep_id, removed_type_id in removed_tuples:
        try:
            existing_dep = next(
                dep
                for dep in cache_deps
                if dep.dependency_id == removed_dep_id
                and dep.dependency_type_id == removed_type_id
            )
            removed_deps.append(existing_dep)
        except StopIteration as exc:
            cache_deps_str = "\n".join(
                [f"{dep.dependency_id} / {dep.dependency_type_id}" for dep in cache_deps]
            )
            raise ValueError(
                f"Removing {removed_dep_id} / {removed_type_id} for {pkg_id} "
                f"but not in Cache:\n{cache_deps_str}"
            ) from exc

    return new_deps, removed_deps
