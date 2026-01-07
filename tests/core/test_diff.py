"""
Tests for the shared dependency diffing logic in core/diff.py.

These tests verify the core algorithm independently of any package manager.
"""

import pytest

from core.diff import (
    DEPENDENCY_PRIORITY,
    DependencyType,
    NormalizedPackage,
    ParsedDependency,
    deduplicate_dependencies,
    diff_dependencies,
    resolve_dependency_type_id,
)
from core.models import LegacyDependency
from core.structs import Cache


class TestDependencyType:
    """Tests for the DependencyType enum."""

    def test_priority_order(self):
        """Verify RUNTIME has highest priority (lowest number)."""
        assert (
            DEPENDENCY_PRIORITY[DependencyType.RUNTIME]
            < DEPENDENCY_PRIORITY[DependencyType.BUILD]
        )
        assert (
            DEPENDENCY_PRIORITY[DependencyType.BUILD]
            < DEPENDENCY_PRIORITY[DependencyType.TEST]
        )
        assert (
            DEPENDENCY_PRIORITY[DependencyType.TEST]
            < DEPENDENCY_PRIORITY[DependencyType.DEVELOPMENT]
        )
        assert (
            DEPENDENCY_PRIORITY[DependencyType.DEVELOPMENT]
            < DEPENDENCY_PRIORITY[DependencyType.OPTIONAL]
        )
        assert (
            DEPENDENCY_PRIORITY[DependencyType.OPTIONAL]
            < DEPENDENCY_PRIORITY[DependencyType.RECOMMENDED]
        )

    def test_all_types_have_priority(self):
        """Ensure all DependencyType values have a priority defined."""
        for dep_type in DependencyType:
            assert dep_type in DEPENDENCY_PRIORITY

    def test_str_representation(self):
        """Test string representation is lowercase name."""
        assert str(DependencyType.RUNTIME) == "runtime"
        assert str(DependencyType.BUILD) == "build"
        assert str(DependencyType.TEST) == "test"


class TestParsedDependency:
    """Tests for the ParsedDependency dataclass."""

    def test_creation(self):
        """Test basic ParsedDependency creation."""
        dep = ParsedDependency(name="serde", dependency_type=DependencyType.RUNTIME)
        assert dep.name == "serde"
        assert dep.dependency_type == DependencyType.RUNTIME

    def test_frozen(self):
        """ParsedDependency should be immutable (frozen)."""
        dep = ParsedDependency(name="serde", dependency_type=DependencyType.RUNTIME)
        with pytest.raises(AttributeError):
            dep.name = "other"

    def test_hashable(self):
        """ParsedDependency should be hashable for use in sets."""
        dep1 = ParsedDependency(name="serde", dependency_type=DependencyType.RUNTIME)
        dep2 = ParsedDependency(name="serde", dependency_type=DependencyType.RUNTIME)
        assert hash(dep1) == hash(dep2)
        assert {dep1, dep2} == {dep1}


class TestNormalizedPackage:
    """Tests for the NormalizedPackage dataclass."""

    def test_creation(self):
        """Test basic NormalizedPackage creation."""
        deps = [
            ParsedDependency(name="dep_a", dependency_type=DependencyType.RUNTIME),
            ParsedDependency(name="dep_b", dependency_type=DependencyType.BUILD),
        ]
        pkg = NormalizedPackage(identifier="my_package", dependencies=deps)
        assert pkg.identifier == "my_package"
        assert len(pkg.dependencies) == 2

    def test_empty_dependencies(self):
        """Package can have no dependencies."""
        pkg = NormalizedPackage(identifier="standalone", dependencies=[])
        assert pkg.dependencies == []


class TestDeduplicateDependencies:
    """Tests for the deduplicate_dependencies function."""

    def test_no_duplicates(self):
        """When no duplicates exist, all deps are preserved."""
        deps = [
            ParsedDependency(name="a", dependency_type=DependencyType.RUNTIME),
            ParsedDependency(name="b", dependency_type=DependencyType.BUILD),
            ParsedDependency(name="c", dependency_type=DependencyType.TEST),
        ]
        result = deduplicate_dependencies(deps)
        assert len(result) == 3
        assert result["a"] == DependencyType.RUNTIME
        assert result["b"] == DependencyType.BUILD
        assert result["c"] == DependencyType.TEST

    def test_duplicate_keeps_higher_priority(self):
        """When duplicates exist, keep the highest priority type."""
        deps = [
            ParsedDependency(name="serde", dependency_type=DependencyType.BUILD),
            ParsedDependency(name="serde", dependency_type=DependencyType.RUNTIME),
        ]
        result = deduplicate_dependencies(deps)
        assert len(result) == 1
        assert result["serde"] == DependencyType.RUNTIME

    def test_duplicate_order_independent(self):
        """Priority wins regardless of order in list."""
        deps_runtime_first = [
            ParsedDependency(name="x", dependency_type=DependencyType.RUNTIME),
            ParsedDependency(name="x", dependency_type=DependencyType.TEST),
        ]
        deps_test_first = [
            ParsedDependency(name="x", dependency_type=DependencyType.TEST),
            ParsedDependency(name="x", dependency_type=DependencyType.RUNTIME),
        ]
        assert (
            deduplicate_dependencies(deps_runtime_first)["x"] == DependencyType.RUNTIME
        )
        assert deduplicate_dependencies(deps_test_first)["x"] == DependencyType.RUNTIME

    def test_multiple_duplicates(self):
        """Multiple deps with same name resolve to highest priority."""
        deps = [
            ParsedDependency(name="multi", dependency_type=DependencyType.RECOMMENDED),
            ParsedDependency(name="multi", dependency_type=DependencyType.TEST),
            ParsedDependency(name="multi", dependency_type=DependencyType.BUILD),
        ]
        result = deduplicate_dependencies(deps)
        assert result["multi"] == DependencyType.BUILD

    def test_empty_name_skipped(self):
        """Dependencies with empty names are skipped."""
        deps = [
            ParsedDependency(name="", dependency_type=DependencyType.RUNTIME),
            ParsedDependency(name="valid", dependency_type=DependencyType.RUNTIME),
        ]
        result = deduplicate_dependencies(deps)
        assert len(result) == 1
        assert "valid" in result

    def test_empty_list(self):
        """Empty input returns empty dict."""
        result = deduplicate_dependencies([])
        assert result == {}


class TestResolveDependencyTypeId:
    """Tests for resolve_dependency_type_id function."""

    def test_all_types_resolve(self, mock_dependency_types):
        """All DependencyType values can be resolved."""
        assert (
            resolve_dependency_type_id(DependencyType.RUNTIME, mock_dependency_types)
            == mock_dependency_types.runtime
        )
        assert (
            resolve_dependency_type_id(DependencyType.BUILD, mock_dependency_types)
            == mock_dependency_types.build
        )
        assert (
            resolve_dependency_type_id(DependencyType.TEST, mock_dependency_types)
            == mock_dependency_types.test
        )
        assert (
            resolve_dependency_type_id(
                DependencyType.DEVELOPMENT, mock_dependency_types
            )
            == mock_dependency_types.development
        )
        assert (
            resolve_dependency_type_id(DependencyType.OPTIONAL, mock_dependency_types)
            == mock_dependency_types.optional
        )
        assert (
            resolve_dependency_type_id(
                DependencyType.RECOMMENDED, mock_dependency_types
            )
            == mock_dependency_types.recommended
        )


class TestDiffDependencies:
    """Tests for the main diff_dependencies function."""

    def test_new_dependency(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """New dependency is detected when not in cache."""
        cache = cache_factory(dependencies={})
        normalized = normalized_package_factory(
            "main_pkg", [("dep_a", DependencyType.RUNTIME)]
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 1
        assert len(removed_deps) == 0
        assert new_deps[0].package_id == package_ids["main"]
        assert new_deps[0].dependency_id == package_ids["dep_a"]
        assert new_deps[0].dependency_type_id == mock_dependency_types.runtime

    def test_existing_dependency_no_change(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Existing dependency with same type produces no changes."""
        existing_dep = LegacyDependency(
            id=1,
            package_id=package_ids["main"],
            dependency_id=package_ids["dep_a"],
            dependency_type_id=mock_dependency_types.runtime,
            created_at=fixed_now,
            updated_at=fixed_now,
        )
        cache = cache_factory(dependencies={package_ids["main"]: {existing_dep}})
        normalized = normalized_package_factory(
            "main_pkg", [("dep_a", DependencyType.RUNTIME)]
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 0
        assert len(removed_deps) == 0

    def test_removed_dependency(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Dependency in cache but not in normalized is marked removed."""
        existing_dep = LegacyDependency(
            id=1,
            package_id=package_ids["main"],
            dependency_id=package_ids["dep_a"],
            dependency_type_id=mock_dependency_types.runtime,
            created_at=fixed_now,
            updated_at=fixed_now,
        )
        cache = cache_factory(dependencies={package_ids["main"]: {existing_dep}})
        normalized = normalized_package_factory("main_pkg", [])

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 0
        assert len(removed_deps) == 1
        assert removed_deps[0].dependency_id == package_ids["dep_a"]

    def test_dependency_type_changed(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Changing dependency type shows as remove + add."""
        existing_dep = LegacyDependency(
            id=1,
            package_id=package_ids["main"],
            dependency_id=package_ids["dep_a"],
            dependency_type_id=mock_dependency_types.build,
            created_at=fixed_now,
            updated_at=fixed_now,
        )
        cache = cache_factory(dependencies={package_ids["main"]: {existing_dep}})
        normalized = normalized_package_factory(
            "main_pkg", [("dep_a", DependencyType.RUNTIME)]
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 1
        assert len(removed_deps) == 1
        assert new_deps[0].dependency_type_id == mock_dependency_types.runtime
        assert removed_deps[0].dependency_type_id == mock_dependency_types.build

    def test_multiple_deps_with_same_name_deduped(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Duplicate deps (same name, different types) are deduplicated."""
        cache = cache_factory(dependencies={})
        normalized = NormalizedPackage(
            identifier="main_pkg",
            dependencies=[
                ParsedDependency(name="dep_a", dependency_type=DependencyType.BUILD),
                ParsedDependency(name="dep_a", dependency_type=DependencyType.RUNTIME),
            ],
        )

        new_deps, _ = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 1
        assert new_deps[0].dependency_type_id == mock_dependency_types.runtime

    def test_package_not_in_cache(
        self,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Package not in cache returns empty lists."""
        cache = cache_factory(package_map={})
        normalized = normalized_package_factory(
            "unknown_pkg", [("dep_a", DependencyType.RUNTIME)]
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert new_deps == []
        assert removed_deps == []

    def test_dependency_not_in_cache_skipped(
        self, packages, package_ids, cache_factory, mock_dependency_types, fixed_now
    ):
        """Dependencies not in package_map are skipped."""
        cache = cache_factory(
            package_map={"main_pkg": packages["main"]},
            dependencies={},
        )
        normalized = NormalizedPackage(
            identifier="main_pkg",
            dependencies=[
                ParsedDependency(
                    name="unknown_dep", dependency_type=DependencyType.RUNTIME
                ),
            ],
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 0
        assert len(removed_deps) == 0

    def test_multiple_new_deps(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Multiple new dependencies are all detected."""
        cache = cache_factory(dependencies={})
        normalized = normalized_package_factory(
            "main_pkg",
            [
                ("dep_a", DependencyType.RUNTIME),
                ("dep_b", DependencyType.BUILD),
                ("dep_c", DependencyType.TEST),
            ],
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 3
        assert len(removed_deps) == 0
        dep_ids = {d.dependency_id for d in new_deps}
        assert dep_ids == {
            package_ids["dep_a"],
            package_ids["dep_b"],
            package_ids["dep_c"],
        }

    def test_mixed_add_remove_keep(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """Complex scenario with adds, removes, and unchanged deps."""
        existing_a = LegacyDependency(
            id=1,
            package_id=package_ids["main"],
            dependency_id=package_ids["dep_a"],
            dependency_type_id=mock_dependency_types.runtime,
            created_at=fixed_now,
            updated_at=fixed_now,
        )
        existing_b = LegacyDependency(
            id=2,
            package_id=package_ids["main"],
            dependency_id=package_ids["dep_b"],
            dependency_type_id=mock_dependency_types.build,
            created_at=fixed_now,
            updated_at=fixed_now,
        )
        cache = cache_factory(
            dependencies={package_ids["main"]: {existing_a, existing_b}}
        )
        normalized = normalized_package_factory(
            "main_pkg",
            [
                ("dep_a", DependencyType.RUNTIME),
                ("dep_c", DependencyType.TEST),
            ],
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert len(new_deps) == 1
        assert new_deps[0].dependency_id == package_ids["dep_c"]

        assert len(removed_deps) == 1
        assert removed_deps[0].dependency_id == package_ids["dep_b"]

    def test_timestamps_set_correctly(
        self,
        packages,
        package_ids,
        cache_factory,
        normalized_package_factory,
        mock_dependency_types,
        fixed_now,
    ):
        """New deps have correct timestamps."""
        cache = cache_factory(dependencies={})
        normalized = normalized_package_factory(
            "main_pkg", [("dep_a", DependencyType.RUNTIME)]
        )

        new_deps, _ = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        assert new_deps[0].created_at == fixed_now
        assert new_deps[0].updated_at == fixed_now

    def test_first_run_with_new_dependencies(
        self,
        packages,
        package_ids,
        mock_dependency_types,
        fixed_now,
    ):
        """
        First run scenario: all packages in cache, all dependencies are new.

        This simulates the corrected behavior where the cache is properly
        pre-populated with all packages (including those with no existing
        dependencies). Dependencies that reference packages in the cache
        should be recorded, even on the first run.
        """
        # Simulate first-run scenario: all packages exist, but no dependencies yet
        cache = Cache(
            package_map={
                "main_pkg": packages["main"],
                "dep_a": packages["dep_a"],
                "dep_b": packages["dep_b"],
            },
            url_map={},
            package_urls={},
            dependencies={},  # Empty: no existing dependencies yet
        )

        normalized = NormalizedPackage(
            identifier="main_pkg",
            dependencies=[
                ParsedDependency(name="dep_a", dependency_type=DependencyType.RUNTIME),
                ParsedDependency(name="dep_b", dependency_type=DependencyType.BUILD),
            ],
        )

        new_deps, removed_deps = diff_dependencies(
            normalized, cache, mock_dependency_types, now=fixed_now
        )

        # Now that cache is properly populated, all dependencies should be detected
        assert len(new_deps) == 2
        assert len(removed_deps) == 0
        assert {d.dependency_id for d in new_deps} == {
            package_ids["dep_a"],
            package_ids["dep_b"],
        }
