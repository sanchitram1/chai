"""
Tests for the homebrew normalizer.
"""

from core.diff import DependencyType
from package_managers.homebrew.normalizer import (
    extract_dependencies_from_list,
    normalize_homebrew_package,
)
from package_managers.homebrew.structs import Actual


class TestExtractDependenciesFromList:
    """Tests for extract_dependencies_from_list function."""

    def test_none_returns_empty(self):
        """None input returns empty list."""
        result = extract_dependencies_from_list(None, DependencyType.RUNTIME)
        assert result == []

    def test_empty_list_returns_empty(self):
        """Empty list returns empty list."""
        result = extract_dependencies_from_list([], DependencyType.RUNTIME)
        assert result == []

    def test_single_dependency(self):
        """Single dependency extracted correctly."""
        result = extract_dependencies_from_list(["openssl@3"], DependencyType.RUNTIME)

        assert len(result) == 1
        assert result[0].name == "openssl@3"
        assert result[0].dependency_type == DependencyType.RUNTIME

    def test_multiple_dependencies(self):
        """Multiple dependencies all extracted."""
        deps = ["gettext", "libidn2", "openssl@1.1"]

        result = extract_dependencies_from_list(deps, DependencyType.BUILD)

        assert len(result) == 3
        names = [d.name for d in result]
        assert "gettext" in names
        assert "libidn2" in names
        assert "openssl@1.1" in names
        assert all(d.dependency_type == DependencyType.BUILD for d in result)

    def test_empty_names_skipped(self):
        """Empty string names are skipped."""
        deps = ["valid", "", "also_valid"]

        result = extract_dependencies_from_list(deps, DependencyType.RUNTIME)

        assert len(result) == 2
        names = [d.name for d in result]
        assert "valid" in names
        assert "also_valid" in names


class TestNormalizeHomebrewPackage:
    """Tests for normalize_homebrew_package function."""

    def test_package_with_no_dependencies(self):
        """Package with all None dependencies returns empty list."""
        pkg = Actual(
            formula="standalone",
            description="A standalone package",
            license="MIT",
            homepage="https://example.com",
            source="https://example.com/src.tar.gz",
            repository=None,
            dependencies=None,
            build_dependencies=None,
            test_dependencies=None,
            recommended_dependencies=None,
            optional_dependencies=None,
        )

        result = normalize_homebrew_package(pkg)

        assert result.identifier == "standalone"
        assert result.dependencies == []

    def test_package_with_runtime_deps_only(self):
        """Package with only runtime dependencies."""
        pkg = Actual(
            formula="wget",
            description="Internet file retriever",
            license="GPL-3.0",
            homepage="https://www.gnu.org/software/wget/",
            source="https://ftp.gnu.org/gnu/wget/wget-1.21.tar.gz",
            repository=None,
            dependencies=["gettext", "libidn2", "openssl@1.1"],
            build_dependencies=None,
            test_dependencies=None,
            recommended_dependencies=None,
            optional_dependencies=None,
        )

        result = normalize_homebrew_package(pkg)

        assert result.identifier == "wget"
        assert len(result.dependencies) == 3
        assert all(
            d.dependency_type == DependencyType.RUNTIME for d in result.dependencies
        )

    def test_package_with_all_dependency_types(self):
        """Package with all five dependency types."""
        pkg = Actual(
            formula="complex_pkg",
            description="A complex package",
            license="MIT",
            homepage="https://example.com",
            source="https://example.com/src.tar.gz",
            repository="https://github.com/example/complex_pkg",
            dependencies=["runtime_dep"],
            build_dependencies=["build_dep"],
            test_dependencies=["test_dep"],
            recommended_dependencies=["recommended_dep"],
            optional_dependencies=["optional_dep"],
        )

        result = normalize_homebrew_package(pkg)

        assert result.identifier == "complex_pkg"
        assert len(result.dependencies) == 5

        dep_map = {d.name: d.dependency_type for d in result.dependencies}
        assert dep_map["runtime_dep"] == DependencyType.RUNTIME
        assert dep_map["build_dep"] == DependencyType.BUILD
        assert dep_map["test_dep"] == DependencyType.TEST
        assert dep_map["recommended_dep"] == DependencyType.RECOMMENDED
        assert dep_map["optional_dep"] == DependencyType.OPTIONAL

    def test_package_with_multiple_deps_per_type(self):
        """Package with multiple dependencies of each type."""
        pkg = Actual(
            formula="multi_dep",
            description="Package with multiple deps",
            license="MIT",
            homepage="https://example.com",
            source="https://example.com/src.tar.gz",
            repository=None,
            dependencies=["dep1", "dep2"],
            build_dependencies=["build1", "build2", "build3"],
            test_dependencies=None,
            recommended_dependencies=None,
            optional_dependencies=None,
        )

        result = normalize_homebrew_package(pkg)

        assert len(result.dependencies) == 5
        runtime_deps = [
            d
            for d in result.dependencies
            if d.dependency_type == DependencyType.RUNTIME
        ]
        build_deps = [
            d for d in result.dependencies if d.dependency_type == DependencyType.BUILD
        ]
        assert len(runtime_deps) == 2
        assert len(build_deps) == 3

    def test_package_formula_as_identifier(self):
        """Formula name is used as the identifier."""
        pkg = Actual(
            formula="special-formula-name",
            description="Test",
            license="MIT",
            homepage="https://example.com",
            source="https://example.com/src.tar.gz",
            repository=None,
            dependencies=None,
            build_dependencies=None,
            test_dependencies=None,
            recommended_dependencies=None,
            optional_dependencies=None,
        )

        result = normalize_homebrew_package(pkg)

        assert result.identifier == "special-formula-name"
