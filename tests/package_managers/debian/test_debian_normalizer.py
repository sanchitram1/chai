"""
Tests for the debian normalizer.
"""

import pytest

from core.diff import DependencyType
from package_managers.debian.normalizer import (
    extract_dependencies_from_depends,
    normalize_debian_package,
)
from package_managers.debian.structs import DebianData, Depends


class TestExtractDependenciesFromDepends:
    """Tests for extract_dependencies_from_depends function."""

    def test_empty_list_returns_empty(self):
        """Empty list returns empty list."""
        result = extract_dependencies_from_depends([], DependencyType.RUNTIME)
        assert result == []

    def test_single_dependency(self):
        """Single Depends object extracted correctly."""
        depends = [Depends(package="libc6", semver=">=2.17")]

        result = extract_dependencies_from_depends(depends, DependencyType.RUNTIME)

        assert len(result) == 1
        assert result[0].name == "debian/libc6"
        assert result[0].dependency_type == DependencyType.RUNTIME

    def test_multiple_dependencies(self):
        """Multiple Depends objects all extracted."""
        depends = [
            Depends(package="libc6", semver=">=2.17"),
            Depends(package="libcurl4", semver=">=7.50"),
            Depends(package="zlib1g", semver=">=1:1.2.0"),
        ]

        result = extract_dependencies_from_depends(depends, DependencyType.BUILD)

        assert len(result) == 3
        names = [d.name for d in result]
        assert "debian/libc6" in names
        assert "debian/libcurl4" in names
        assert "debian/zlib1g" in names
        assert all(d.dependency_type == DependencyType.BUILD for d in result)

    def test_empty_package_name_skipped(self):
        """Depends with empty package name are skipped."""
        depends = [
            Depends(package="valid", semver=">=1.0"),
            Depends(package="", semver=">=2.0"),
        ]

        result = extract_dependencies_from_depends(depends, DependencyType.RUNTIME)

        assert len(result) == 1
        assert result[0].name == "debian/valid"

    def test_debian_prefix_added(self):
        """Dependency names have 'debian/' prefix added."""
        depends = [Depends(package="curl", semver="")]

        result = extract_dependencies_from_depends(depends, DependencyType.RUNTIME)

        assert result[0].name == "debian/curl"


class TestNormalizeDebianPackage:
    """Tests for normalize_debian_package function."""

    def test_package_with_no_dependencies(self):
        """Package with no dependencies returns empty list."""
        data = DebianData(
            package="standalone",
            description="A standalone package",
        )

        result = normalize_debian_package("debian/standalone", data)

        assert result.identifier == "debian/standalone"
        assert result.dependencies == []

    def test_package_with_runtime_deps(self):
        """Package with depends (runtime) dependencies."""
        data = DebianData(
            package="curl",
            description="Command line tool for transferring data",
            depends=[
                Depends(package="libc6", semver=">=2.17"),
                Depends(package="libcurl4", semver=">=7.50"),
            ],
        )

        result = normalize_debian_package("debian/curl", data)

        assert result.identifier == "debian/curl"
        assert len(result.dependencies) == 2
        assert all(d.dependency_type == DependencyType.RUNTIME for d in result.dependencies)

    def test_package_with_build_deps(self):
        """Package with build_depends (build) dependencies."""
        data = DebianData(
            package="buildpkg",
            description="A package with build deps",
            build_depends=[
                Depends(package="debhelper", semver=">=12"),
                Depends(package="cmake", semver=">=3.16"),
            ],
        )

        result = normalize_debian_package("debian/buildpkg", data)

        assert len(result.dependencies) == 2
        assert all(d.dependency_type == DependencyType.BUILD for d in result.dependencies)

    def test_recommends_maps_to_runtime(self):
        """Recommends dependencies map to RUNTIME (per existing behavior)."""
        data = DebianData(
            package="recpkg",
            description="Package with recommends",
            recommends=[
                Depends(package="recommended-pkg", semver=""),
            ],
        )

        result = normalize_debian_package("debian/recpkg", data)

        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "debian/recommended-pkg"
        assert result.dependencies[0].dependency_type == DependencyType.RUNTIME

    def test_suggests_maps_to_runtime(self):
        """Suggests dependencies map to RUNTIME (per existing behavior)."""
        data = DebianData(
            package="sugpkg",
            description="Package with suggests",
            suggests=[
                Depends(package="suggested-pkg", semver=""),
            ],
        )

        result = normalize_debian_package("debian/sugpkg", data)

        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "debian/suggested-pkg"
        assert result.dependencies[0].dependency_type == DependencyType.RUNTIME

    def test_package_with_all_dep_types(self):
        """Package with depends, build_depends, recommends, and suggests."""
        data = DebianData(
            package="fullpkg",
            description="Full package",
            depends=[Depends(package="runtime", semver="")],
            build_depends=[Depends(package="build", semver="")],
            recommends=[Depends(package="recommended", semver="")],
            suggests=[Depends(package="suggested", semver="")],
        )

        result = normalize_debian_package("debian/fullpkg", data)

        assert len(result.dependencies) == 4

        dep_map = {d.name: d.dependency_type for d in result.dependencies}
        assert dep_map["debian/runtime"] == DependencyType.RUNTIME
        assert dep_map["debian/build"] == DependencyType.BUILD
        assert dep_map["debian/recommended"] == DependencyType.RUNTIME
        assert dep_map["debian/suggested"] == DependencyType.RUNTIME

    def test_import_id_used_as_identifier(self):
        """The import_id parameter is used as the identifier."""
        data = DebianData(package="pkg", description="Test")

        result = normalize_debian_package("debian/custom-id", data)

        assert result.identifier == "debian/custom-id"
