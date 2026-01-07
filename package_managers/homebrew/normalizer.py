"""
Normalizer for Homebrew package data.

Converts Homebrew Actual objects into NormalizedPackage for use with shared diff logic.
"""

from core.diff import DependencyType, NormalizedPackage, ParsedDependency
from package_managers.homebrew.structs import Actual


def extract_dependencies_from_list(
    dep_names: list[str] | None, dep_type: DependencyType
) -> list[ParsedDependency]:
    """
    Extract ParsedDependency objects from a list of dependency names.

    Args:
        dep_names: List of dependency names (or None)
        dep_type: The normalized dependency type to assign

    Returns:
        List of ParsedDependency objects
    """
    if not dep_names:
        return []

    result: list[ParsedDependency] = []
    for name in dep_names:
        if not name:
            continue
        result.append(ParsedDependency(name=name, dependency_type=dep_type))

    return result


def normalize_homebrew_package(pkg: Actual) -> NormalizedPackage:
    """
    Convert a Homebrew Actual to a NormalizedPackage.

    Extracts dependencies from:
    - pkg.dependencies (runtime)
    - pkg.build_dependencies (build)
    - pkg.test_dependencies (test)
    - pkg.recommended_dependencies (recommended)
    - pkg.optional_dependencies (optional)

    Args:
        pkg: The Actual (Homebrew formula) object

    Returns:
        NormalizedPackage with identifier and dependencies list
    """
    dependencies: list[ParsedDependency] = []

    dependencies.extend(
        extract_dependencies_from_list(pkg.dependencies, DependencyType.RUNTIME)
    )
    dependencies.extend(
        extract_dependencies_from_list(pkg.build_dependencies, DependencyType.BUILD)
    )
    dependencies.extend(
        extract_dependencies_from_list(pkg.test_dependencies, DependencyType.TEST)
    )
    dependencies.extend(
        extract_dependencies_from_list(
            pkg.recommended_dependencies, DependencyType.RECOMMENDED
        )
    )
    dependencies.extend(
        extract_dependencies_from_list(
            pkg.optional_dependencies, DependencyType.OPTIONAL
        )
    )

    return NormalizedPackage(
        identifier=pkg.formula,
        dependencies=dependencies,
    )
