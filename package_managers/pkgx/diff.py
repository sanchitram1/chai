#!/usr/bin/env pkgx uv run

from datetime import datetime
from uuid import UUID, uuid4

from core.config import Config
from core.diff import diff_dependencies
from core.logger import Logger
from core.models import URL, LegacyDependency, Package, PackageURL
from core.structs import Cache, URLKey
from package_managers.pkgx.db import DB
from package_managers.pkgx.normalizer import normalize_pkgx_package
from package_managers.pkgx.parser import PkgxPackage
from package_managers.pkgx.url import generate_chai_urls


class PkgxDiff:
    def __init__(self, config: Config, caches: Cache, db: DB, logger: Logger):
        self.config = config
        self.now = datetime.now()
        self.caches = caches
        self.db = db
        self.logger = logger

    def diff_pkg(
        self, import_id: str, pkg: PkgxPackage
    ) -> tuple[UUID, Package | None, dict | None]:
        """
        Checks if the given pkg is in the package_cache.

        Returns:
          - pkg_id: the id of the package
          - package: If new, returns a new package object. If existing, returns None
          - changes: a dictionary of changes
        """
        self.logger.debug(f"Diffing package: {import_id}")

        if import_id not in self.caches.package_map:
            # new package
            p = Package(
                id=uuid4(),
                derived_id=f"pkgx/{import_id}",
                name=import_id,
                package_manager_id=self.config.pm_config.pm_id,
                import_id=import_id,
                readme="",  # NOTE: pkgx doesn't have a description field
                created_at=self.now,
                updated_at=self.now,
            )
            pkg_id: UUID = p.id
            return pkg_id, p, {}
        else:
            # the package exists, but since pkgx doesn't maintain a readme or
            # description field, we can just return
            pkg_id = self.caches.package_map[import_id].id
            return pkg_id, None, None

    def diff_url(
        self, import_id: str, pkg: PkgxPackage, new_urls: dict[URLKey, URL]
    ) -> dict[UUID, UUID]:
        """Given a package's URLs, returns the resolved URL for this specific package"""
        resolved_urls: dict[UUID, UUID] = {}

        # Generate the URLs for this package
        urls = generate_chai_urls(
            self.config, self.db, import_id, pkg.distributable[0].url, self.logger
        )

        # Process each URL
        for url_key in urls:
            # guard: generate_chai_urls could be None for a url type
            if url_key is None:
                continue

            resolved_url_id: UUID

            if url_key in new_urls:
                resolved_url_id = new_urls[url_key].id
            elif url_key in self.caches.url_map:
                resolved_url_id = self.caches.url_map[url_key].id
            else:
                self.logger.debug(
                    f"URL {url_key.url} as {url_key.url_type_id} is entirely new"
                )
                new_url = URL(
                    id=uuid4(),
                    url=url_key.url,
                    url_type_id=url_key.url_type_id,
                    created_at=self.now,
                    updated_at=self.now,
                )
                resolved_url_id = new_url.id
                new_urls[url_key] = new_url

            resolved_urls[url_key.url_type_id] = resolved_url_id

        return resolved_urls

    def diff_pkg_url(
        self, pkg_id: UUID, resolved_urls: dict[UUID, UUID]
    ) -> tuple[list[PackageURL], list[dict]]:
        """Takes in a package_id and resolved URLs from diff_url, and generates
        new PackageURL objects as well as a list of changes to existing ones"""

        new_links: list[PackageURL] = []
        updates: list[dict] = []

        # what are the existing links?
        existing: set[UUID] = {
            pu.url_id for pu in self.caches.package_urls.get(pkg_id, set())
        }

        # for each URL type/URL for this package:
        for _url_type, url_id in resolved_urls.items():
            if url_id not in existing:
                # new link!
                new_links.append(
                    PackageURL(
                        id=uuid4(),
                        package_id=pkg_id,
                        url_id=url_id,
                        created_at=self.now,
                        updated_at=self.now,
                    )
                )
            else:
                # existing link - update timestamp
                existing_pu = next(
                    pu for pu in self.caches.package_urls[pkg_id] if pu.url_id == url_id
                )
                existing_pu.updated_at = self.now
                updates.append({"id": existing_pu.id, "updated_at": self.now})

        return new_links, updates

    def diff_deps(
        self, import_id: str, pkg: PkgxPackage
    ) -> tuple[list[LegacyDependency], list[LegacyDependency]]:
        """
        Takes in a pkgx package and figures out what dependencies have changed.

        Uses the normalized dependency diffing approach:
        1. Normalize the package to a NormalizedPackage
        2. Use shared diff_dependencies() for the core algorithm

        Returns:
          - new_deps: a list of new dependencies
          - removed_deps: a list of removed dependencies
        """
        normalized = normalize_pkgx_package(import_id, pkg)
        return diff_dependencies(
            normalized,
            self.caches,
            self.config.dependency_types,
            now=self.now,
        )
