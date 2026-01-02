"""
Normalizer for pkgx package data.

Converts PkgxPackage objects into NormalizedPackage for use with shared diff logic.
"""

from core.diff import DependencyType, NormalizedPackage, ParsedDependency
from package_managers.pkgx.parser import DependencyBlock, PkgxPackage


def extract_dependencies_from_blocks(
    blocks: list[DependencyBlock], dep_type: DependencyType
) -> list[ParsedDependency]:
    """
    Extract ParsedDependency objects from a list of DependencyBlocks.

    Args:
        blocks: List of DependencyBlock (each has platform and dependencies)
        dep_type: The normalized dependency type to assign

    Returns:
        List of ParsedDependency objects
    """
    result: list[ParsedDependency] = []

    for block in blocks:
        for dep in block.dependencies:
            if not dep.name:
                continue
            result.append(ParsedDependency(name=dep.name, dependency_type=dep_type))

    return result


def normalize_pkgx_package(import_id: str, pkg: PkgxPackage) -> NormalizedPackage:
    """
    Convert a PkgxPackage to a NormalizedPackage.

    Extracts dependencies from:
    - pkg.dependencies (runtime)
    - pkg.build.dependencies (build)
    - pkg.test.dependencies (test)

    Args:
        import_id: The package identifier (e.g., "gnu.org/wget")
        pkg: The PkgxPackage object from parsed YAML

    Returns:
        NormalizedPackage with identifier and dependencies list
    """
    dependencies: list[ParsedDependency] = []

    dependencies.extend(
        extract_dependencies_from_blocks(pkg.dependencies, DependencyType.RUNTIME)
    )

    if pkg.build:
        dependencies.extend(
            extract_dependencies_from_blocks(
                pkg.build.dependencies, DependencyType.BUILD
            )
        )

    if pkg.test:
        dependencies.extend(
            extract_dependencies_from_blocks(pkg.test.dependencies, DependencyType.TEST)
        )

    return NormalizedPackage(
        identifier=import_id,
        dependencies=dependencies,
    )
