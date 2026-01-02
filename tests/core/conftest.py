"""
Fixtures for testing core/diff.py shared dependency diffing logic.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from core.diff import DependencyType, NormalizedPackage, ParsedDependency
from core.models import Package
from core.structs import Cache


@pytest.fixture
def fixed_now():
    """Fixed timestamp for deterministic testing."""
    return datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture
def package_ids():
    """Consistent package UUIDs for testing."""
    return {
        "main": uuid4(),
        "dep_a": uuid4(),
        "dep_b": uuid4(),
        "dep_c": uuid4(),
    }


@pytest.fixture
def packages(package_ids):
    """Test packages in the cache."""
    now = datetime.now()
    return {
        "main": Package(
            id=package_ids["main"],
            name="main_pkg",
            derived_id="test/main_pkg",
            package_manager_id=uuid4(),
            import_id="main_pkg",
            created_at=now,
            updated_at=now,
        ),
        "dep_a": Package(
            id=package_ids["dep_a"],
            name="dep_a",
            derived_id="test/dep_a",
            package_manager_id=uuid4(),
            import_id="dep_a",
            created_at=now,
            updated_at=now,
        ),
        "dep_b": Package(
            id=package_ids["dep_b"],
            name="dep_b",
            derived_id="test/dep_b",
            package_manager_id=uuid4(),
            import_id="dep_b",
            created_at=now,
            updated_at=now,
        ),
        "dep_c": Package(
            id=package_ids["dep_c"],
            name="dep_c",
            derived_id="test/dep_c",
            package_manager_id=uuid4(),
            import_id="dep_c",
            created_at=now,
            updated_at=now,
        ),
    }


@pytest.fixture
def cache_factory(packages):
    """Factory to create Cache objects with specific configurations."""

    def create_cache(
        package_map: dict[str, Package] | None = None,
        dependencies: dict | None = None,
    ) -> Cache:
        if package_map is None:
            package_map = {pkg.import_id: pkg for pkg in packages.values()}

        return Cache(
            package_map=package_map,
            url_map={},
            package_urls={},
            dependencies=dependencies or {},
        )

    return create_cache


@pytest.fixture
def normalized_package_factory():
    """Factory to create NormalizedPackage objects."""

    def create_normalized(
        identifier: str, deps: list[tuple[str, DependencyType]]
    ) -> NormalizedPackage:
        return NormalizedPackage(
            identifier=identifier,
            dependencies=[
                ParsedDependency(name=name, dependency_type=dep_type)
                for name, dep_type in deps
            ],
        )

    return create_normalized
