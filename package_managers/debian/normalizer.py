"""
Normalizer for Debian package data.

Converts DebianData objects into NormalizedPackage for use with shared diff logic.
"""

from core.diff import DependencyType, NormalizedPackage, ParsedDependency
from package_managers.debian.structs import DebianData, Depends


def extract_dependencies_from_depends(
    depends_list: list[Depends], dep_type: DependencyType
) -> list[ParsedDependency]:
    """
    Extract ParsedDependency objects from a list of Depends.

    Args:
        depends_list: List of Depends objects (each has package name)
        dep_type: The normalized dependency type to assign

    Returns:
        List of ParsedDependency objects
    """
    result: list[ParsedDependency] = []

    for dep in depends_list:
        if not dep.package:
            continue
        dep_name = f"debian/{dep.package}"
        result.append(ParsedDependency(name=dep_name, dependency_type=dep_type))

    return result


def normalize_debian_package(import_id: str, data: DebianData) -> NormalizedPackage:
    """
    Convert DebianData to a NormalizedPackage.

    Extracts dependencies from:
    - data.depends (runtime)
    - data.build_depends (build)
    - data.recommends (runtime - mapped per existing behavior)
    - data.suggests (runtime - mapped per existing behavior)

    Args:
        import_id: The package identifier (e.g., "debian/curl")
        data: The DebianData object from parsed package data

    Returns:
        NormalizedPackage with identifier and dependencies list
    """
    dependencies: list[ParsedDependency] = []

    dependencies.extend(
        extract_dependencies_from_depends(data.depends, DependencyType.RUNTIME)
    )
    dependencies.extend(
        extract_dependencies_from_depends(data.build_depends, DependencyType.BUILD)
    )
    dependencies.extend(
        extract_dependencies_from_depends(data.recommends, DependencyType.RUNTIME)
    )
    dependencies.extend(
        extract_dependencies_from_depends(data.suggests, DependencyType.RUNTIME)
    )

    return NormalizedPackage(
        identifier=import_id,
        dependencies=dependencies,
    )
