"""
Tests for the pkgx normalizer.
"""

import pytest

from core.diff import DependencyType
from package_managers.pkgx.normalizer import (
    extract_dependencies_from_blocks,
    normalize_pkgx_package,
)
from package_managers.pkgx.parser import (
    Build,
    Dependency,
    DependencyBlock,
    Distributable,
    PkgxPackage,
    Test,
    Version,
)


@pytest.fixture
def basic_distributable():
    """Basic distributable for creating PkgxPackage."""
    return [Distributable(url="https://example.com/pkg.tar.gz")]


@pytest.fixture
def basic_version():
    """Basic version for creating PkgxPackage."""
    return Version(github="owner/repo")


class TestExtractDependenciesFromBlocks:
    """Tests for extract_dependencies_from_blocks function."""

    def test_empty_blocks(self):
        """Empty block list returns empty list."""
        result = extract_dependencies_from_blocks([], DependencyType.RUNTIME)
        assert result == []

    def test_single_block_single_dep(self):
        """Single block with one dependency extracts correctly."""
        blocks = [
            DependencyBlock(
                platform="all",
                dependencies=[Dependency(name="openssl.org", semver="^1.1")],
            )
        ]

        result = extract_dependencies_from_blocks(blocks, DependencyType.RUNTIME)

        assert len(result) == 1
        assert result[0].name == "openssl.org"
        assert result[0].dependency_type == DependencyType.RUNTIME

    def test_multiple_blocks_multiple_deps(self):
        """Multiple blocks with multiple deps all extracted."""
        blocks = [
            DependencyBlock(
                platform="darwin",
                dependencies=[
                    Dependency(name="apple.com/xcode", semver="^14"),
                ],
            ),
            DependencyBlock(
                platform="linux",
                dependencies=[
                    Dependency(name="gnu.org/gcc", semver="^12"),
                    Dependency(name="cmake.org", semver="^3.20"),
                ],
            ),
        ]

        result = extract_dependencies_from_blocks(blocks, DependencyType.BUILD)

        assert len(result) == 3
        names = [d.name for d in result]
        assert "apple.com/xcode" in names
        assert "gnu.org/gcc" in names
        assert "cmake.org" in names
        assert all(d.dependency_type == DependencyType.BUILD for d in result)

    def test_empty_name_skipped(self):
        """Dependencies with empty names are skipped."""
        blocks = [
            DependencyBlock(
                platform="all",
                dependencies=[
                    Dependency(name="", semver="^1.0"),
                    Dependency(name="valid.org", semver="^2.0"),
                ],
            )
        ]

        result = extract_dependencies_from_blocks(blocks, DependencyType.RUNTIME)

        assert len(result) == 1
        assert result[0].name == "valid.org"


class TestNormalizePkgxPackage:
    """Tests for normalize_pkgx_package function."""

    def test_package_with_no_dependencies(self, basic_distributable, basic_version):
        """Package with no deps returns empty dependencies list."""
        pkg = PkgxPackage(
            distributable=basic_distributable,
            versions=basic_version,
            dependencies=[],
        )

        result = normalize_pkgx_package("example.org", pkg)

        assert result.identifier == "example.org"
        assert result.dependencies == []

    def test_package_with_runtime_deps(self, basic_distributable, basic_version):
        """Package with runtime dependencies normalized correctly."""
        pkg = PkgxPackage(
            distributable=basic_distributable,
            versions=basic_version,
            dependencies=[
                DependencyBlock(
                    platform="all",
                    dependencies=[
                        Dependency(name="zlib.net", semver="^1.2"),
                        Dependency(name="openssl.org", semver="^3.0"),
                    ],
                )
            ],
        )

        result = normalize_pkgx_package("myapp.io", pkg)

        assert result.identifier == "myapp.io"
        assert len(result.dependencies) == 2
        assert all(d.dependency_type == DependencyType.RUNTIME for d in result.dependencies)

    def test_package_with_build_deps(self, basic_distributable, basic_version):
        """Package with build dependencies normalized correctly."""
        pkg = PkgxPackage(
            distributable=basic_distributable,
            versions=basic_version,
            dependencies=[],
            build=Build(
                script="make install",
                dependencies=[
                    DependencyBlock(
                        platform="all",
                        dependencies=[Dependency(name="cmake.org", semver="^3.20")],
                    )
                ],
            ),
        )

        result = normalize_pkgx_package("buildable.app", pkg)

        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "cmake.org"
        assert result.dependencies[0].dependency_type == DependencyType.BUILD

    def test_package_with_test_deps(self, basic_distributable, basic_version):
        """Package with test dependencies normalized correctly."""
        pkg = PkgxPackage(
            distributable=basic_distributable,
            versions=basic_version,
            dependencies=[],
            test=Test(
                script="make test",
                dependencies=[
                    DependencyBlock(
                        platform="all",
                        dependencies=[Dependency(name="pytest.org", semver="^7.0")],
                    )
                ],
            ),
        )

        result = normalize_pkgx_package("testable.app", pkg)

        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "pytest.org"
        assert result.dependencies[0].dependency_type == DependencyType.TEST

    def test_package_with_all_dep_types(self, basic_distributable, basic_version):
        """Package with runtime, build, and test deps all normalized."""
        pkg = PkgxPackage(
            distributable=basic_distributable,
            versions=basic_version,
            dependencies=[
                DependencyBlock(
                    platform="all",
                    dependencies=[Dependency(name="runtime.dep", semver="^1.0")],
                )
            ],
            build=Build(
                script="build.sh",
                dependencies=[
                    DependencyBlock(
                        platform="all",
                        dependencies=[Dependency(name="build.dep", semver="^2.0")],
                    )
                ],
            ),
            test=Test(
                script="test.sh",
                dependencies=[
                    DependencyBlock(
                        platform="all",
                        dependencies=[Dependency(name="test.dep", semver="^3.0")],
                    )
                ],
            ),
        )

        result = normalize_pkgx_package("full.app", pkg)

        assert len(result.dependencies) == 3
        dep_map = {d.name: d.dependency_type for d in result.dependencies}
        assert dep_map["runtime.dep"] == DependencyType.RUNTIME
        assert dep_map["build.dep"] == DependencyType.BUILD
        assert dep_map["test.dep"] == DependencyType.TEST

    def test_package_with_none_build_test(self, basic_distributable, basic_version):
        """Package with None build/test doesn't error."""
        pkg = PkgxPackage(
            distributable=basic_distributable,
            versions=basic_version,
            dependencies=[
                DependencyBlock(
                    platform="all",
                    dependencies=[Dependency(name="only.runtime", semver="^1.0")],
                )
            ],
            build=None,
            test=None,
        )

        result = normalize_pkgx_package("simple.app", pkg)

        assert len(result.dependencies) == 1
        assert result.dependencies[0].dependency_type == DependencyType.RUNTIME
