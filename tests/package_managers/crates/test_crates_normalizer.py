"""
Tests for the crates normalizer.
"""

import pytest

from core.diff import DependencyType
from package_managers.crates.normalizer import (
    map_crates_dependency_type,
    normalize_crates_package,
)
from package_managers.crates.structs import (
    Crate,
    CrateDependency,
    CrateLatestVersion,
    DependencyType as CratesDependencyType,
)


class TestMapCratesDependencyType:
    """Tests for mapping crates dependency types to normalized types."""

    def test_normal_maps_to_runtime(self):
        """NORMAL (runtime) dependencies map to RUNTIME."""
        assert map_crates_dependency_type(CratesDependencyType.NORMAL) == DependencyType.RUNTIME

    def test_build_maps_to_build(self):
        """BUILD dependencies map to BUILD."""
        assert map_crates_dependency_type(CratesDependencyType.BUILD) == DependencyType.BUILD

    def test_dev_maps_to_development(self):
        """DEV dependencies map to DEVELOPMENT."""
        assert map_crates_dependency_type(CratesDependencyType.DEV) == DependencyType.DEVELOPMENT

    def test_optional_maps_to_optional(self):
        """OPTIONAL dependencies map to OPTIONAL."""
        assert map_crates_dependency_type(CratesDependencyType.OPTIONAL) == DependencyType.OPTIONAL


class TestNormalizeCratesPackage:
    """Tests for normalize_crates_package function."""

    def test_crate_with_no_version(self):
        """Crate without latest_version returns empty dependencies."""
        crate = Crate(
            id=123,
            name="test_crate",
            readme="Test readme",
            homepage="",
            repository="",
            documentation="",
        )
        crate.latest_version = None

        result = normalize_crates_package(crate)

        assert result.identifier == "123"
        assert result.dependencies == []

    def test_crate_with_no_dependencies(self):
        """Crate with version but no dependencies returns empty list."""
        crate = Crate(
            id=456,
            name="standalone",
            readme="",
            homepage="",
            repository="",
            documentation="",
        )
        crate.latest_version = CrateLatestVersion(
            id=1,
            checksum="abc",
            downloads=100,
            license="MIT",
            num="1.0.0",
            published_at="2024-01-01",
            dependencies=[],
        )

        result = normalize_crates_package(crate)

        assert result.identifier == "456"
        assert result.dependencies == []

    def test_crate_with_single_dependency(self):
        """Crate with one dependency is normalized correctly."""
        crate = Crate(
            id=789,
            name="my_crate",
            readme="",
            homepage="",
            repository="",
            documentation="",
        )
        crate.latest_version = CrateLatestVersion(
            id=1,
            checksum="def",
            downloads=500,
            license="Apache-2.0",
            num="2.0.0",
            published_at="2024-06-01",
            dependencies=[
                CrateDependency(
                    crate_id=789,
                    dependency_id=100,
                    dependency_type=CratesDependencyType.NORMAL,
                    semver_range="^1.0",
                )
            ],
        )

        result = normalize_crates_package(crate)

        assert result.identifier == "789"
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "100"
        assert result.dependencies[0].dependency_type == DependencyType.RUNTIME

    def test_crate_with_multiple_dependency_types(self):
        """Crate with various dependency types are all normalized."""
        crate = Crate(
            id=999,
            name="complex_crate",
            readme="",
            homepage="",
            repository="",
            documentation="",
        )
        crate.latest_version = CrateLatestVersion(
            id=1,
            checksum="xyz",
            downloads=1000,
            license="MIT",
            num="3.0.0",
            published_at="2024-07-01",
            dependencies=[
                CrateDependency(
                    crate_id=999,
                    dependency_id=101,
                    dependency_type=CratesDependencyType.NORMAL,
                    semver_range="^1.0",
                ),
                CrateDependency(
                    crate_id=999,
                    dependency_id=102,
                    dependency_type=CratesDependencyType.BUILD,
                    semver_range="^2.0",
                ),
                CrateDependency(
                    crate_id=999,
                    dependency_id=103,
                    dependency_type=CratesDependencyType.DEV,
                    semver_range="^3.0",
                ),
                CrateDependency(
                    crate_id=999,
                    dependency_id=104,
                    dependency_type=CratesDependencyType.OPTIONAL,
                    semver_range="^4.0",
                ),
            ],
        )

        result = normalize_crates_package(crate)

        assert result.identifier == "999"
        assert len(result.dependencies) == 4

        dep_types = {d.name: d.dependency_type for d in result.dependencies}
        assert dep_types["101"] == DependencyType.RUNTIME
        assert dep_types["102"] == DependencyType.BUILD
        assert dep_types["103"] == DependencyType.DEVELOPMENT
        assert dep_types["104"] == DependencyType.OPTIONAL

    def test_crate_with_duplicate_dependencies(self):
        """Duplicate dependencies (same dep with diff types) are all included."""
        crate = Crate(
            id=555,
            name="dup_crate",
            readme="",
            homepage="",
            repository="",
            documentation="",
        )
        crate.latest_version = CrateLatestVersion(
            id=1,
            checksum="dup",
            downloads=200,
            license="MIT",
            num="1.0.0",
            published_at="2024-01-01",
            dependencies=[
                CrateDependency(
                    crate_id=555,
                    dependency_id=200,
                    dependency_type=CratesDependencyType.NORMAL,
                    semver_range="^1.0",
                ),
                CrateDependency(
                    crate_id=555,
                    dependency_id=200,
                    dependency_type=CratesDependencyType.BUILD,
                    semver_range="^1.0",
                ),
            ],
        )

        result = normalize_crates_package(crate)

        assert len(result.dependencies) == 2
        types = [d.dependency_type for d in result.dependencies]
        assert DependencyType.RUNTIME in types
        assert DependencyType.BUILD in types
