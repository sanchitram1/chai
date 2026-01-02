"""
Normalizer for Crates (Rust) package data.

Converts Crate objects into NormalizedPackage for use with shared diff logic.
"""

from core.diff import DependencyType, NormalizedPackage, ParsedDependency
from package_managers.crates.structs import Crate
from package_managers.crates.structs import DependencyType as CratesDependencyType


def map_crates_dependency_type(crates_type: CratesDependencyType) -> DependencyType:
    """Map crates.io dependency type to normalized DependencyType."""
    type_map = {
        CratesDependencyType.NORMAL: DependencyType.RUNTIME,
        CratesDependencyType.BUILD: DependencyType.BUILD,
        CratesDependencyType.DEV: DependencyType.DEVELOPMENT,
        CratesDependencyType.OPTIONAL: DependencyType.OPTIONAL,
    }
    return type_map.get(crates_type, DependencyType.RUNTIME)


def normalize_crates_package(crate: Crate) -> NormalizedPackage:
    """
    Convert a Crate to a NormalizedPackage.

    Extracts dependencies from crate.latest_version.dependencies and maps
    each CrateDependency to a ParsedDependency with normalized types.

    Args:
        crate: The Crate object from crates.io data

    Returns:
        NormalizedPackage with identifier and dependencies list
    """
    dependencies: list[ParsedDependency] = []

    if crate.latest_version:
        for dep in crate.latest_version.dependencies:
            dep_name = str(dep.dependency_id)

            if not dep_name:
                continue

            if dep.dependency_type is None:
                continue

            normalized_type = map_crates_dependency_type(dep.dependency_type)
            dependencies.append(
                ParsedDependency(name=dep_name, dependency_type=normalized_type)
            )

    return NormalizedPackage(
        identifier=str(crate.id),
        dependencies=dependencies,
    )
