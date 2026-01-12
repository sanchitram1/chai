#!/usr/bin/env pkgx uv run

from datetime import datetime
from uuid import UUID, uuid4

from core.config import Config
from core.diff import diff_dependencies
from core.logger import Logger
from core.models import URL, LegacyDependency, Package, PackageURL
from core.structs import Cache, URLKey
from core.utils import is_github_url
from package_managers.debian.db import DebianDB
from package_managers.debian.normalizer import normalize_debian_package
from package_managers.debian.parser import DebianData


class DebianDiff:
    def __init__(self, config: Config, caches: Cache, db: DebianDB, logger: Logger):
        self.config = config
        self.now = datetime.now()
        self.caches = caches
        self.db = db
        self.logger = logger

    def diff_pkg(
        self, import_id: str, debian_data: DebianData
    ) -> tuple[UUID, Package | None, dict | None]:
        """
        Checks if the given package is in the package_cache.

        Returns:
          - pkg_id: the id of the package
          - package: If new, returns a new package object. If existing, returns None
          - changes: a dictionary of changes (description updates)
        """
        self.logger.debug(f"Diffing package: {import_id}")

        if import_id not in self.caches.package_map:
            # new package
            name = import_id.split("/")[1]
            p = Package(
                id=uuid4(),
                derived_id=import_id,
                name=name,
                package_manager_id=self.config.pm_config.pm_id,
                import_id=import_id,
                readme=debian_data.description,
                created_at=self.now,
                updated_at=self.now,
            )
            pkg_id: UUID = p.id
            return pkg_id, p, {}
        else:
            # the package exists, check if description has changed
            existing_pkg = self.caches.package_map[import_id]
            pkg_id = existing_pkg.id

            # Check if description (readme) has changed
            if existing_pkg.readme != debian_data.description:
                update_payload = {
                    "id": pkg_id,
                    "readme": debian_data.description,
                    "updated_at": self.now,
                }
                return pkg_id, None, update_payload
            else:
                return pkg_id, None, None

    def diff_url(
        self, import_id: str, debian_data: DebianData, new_urls: dict[URLKey, URL]
    ) -> dict[UUID, UUID]:
        """Given a package's URLs, returns the resolved URL for this specific package"""
        resolved_urls: dict[UUID, UUID] = {}

        # Generate the URLs for this package
        urls = self._generate_chai_urls(debian_data)

        # Process each URL
        for url_key in urls:
            # guard: _generate_chai_urls could be None for a url type
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
        self, import_id: str, debian_data: DebianData
    ) -> tuple[list[LegacyDependency], list[LegacyDependency]]:
        """
        Takes in a debian package and figures out what dependencies have changed.

        Uses the normalized dependency diffing approach:
        1. Normalize the package to a NormalizedPackage
        2. Use shared diff_dependencies() for the core algorithm

        Returns:
          - new_deps: a list of new dependencies
          - removed_deps: a list of removed dependencies
        """
        normalized = normalize_debian_package(import_id, debian_data)
        return diff_dependencies(
            normalized,
            self.caches,
            self.config.dependency_types,
            now=self.now,
        )

    def _generate_chai_urls(self, debian_data: DebianData) -> list[URLKey]:
        """Generate URLs for a debian package"""
        urls = []

        # Homepage URL
        if debian_data.homepage:
            urls.append(URLKey(debian_data.homepage, self.config.url_types.homepage))

        # Source URL
        source_url = (
            debian_data.vcs_git if debian_data.vcs_git else debian_data.vcs_browser
        )
        if source_url:
            urls.append(URLKey(source_url, self.config.url_types.source))

        # Repository URL
        if is_github_url(source_url):
            urls.append(URLKey(source_url, self.config.url_types.repository))

        return urls
