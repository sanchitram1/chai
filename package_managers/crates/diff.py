from datetime import datetime
from uuid import UUID, uuid4

from core.config import Config
from core.diff import diff_dependencies
from core.logger import Logger
from core.models import URL, LegacyDependency, Package, PackageURL
from core.structs import Cache, URLKey
from package_managers.crates.normalizer import normalize_crates_package
from package_managers.crates.structs import Crate


class Diff:
    def __init__(self, config: Config, caches: Cache):
        self.config = config
        self.now = datetime.now()
        self.caches = caches
        self.logger = Logger("crates_diff")

    def diff_pkg(self, pkg: Crate) -> tuple[UUID, Package | None, dict | None]:
        """
        Checks if the given pkg is in the package_cache.

        Returns:
            pkg_id: UUID, the id of the package in the db
            pkg_obj: Package | None, the package object if it's new
            update_payload: dict | None, the update payload if it's an update
        """
        pkg_id: UUID
        crate_id: str = str(pkg.id)  # import_ids are strings in the db
        if crate_id not in self.caches.package_map:
            # new package
            p = Package(
                id=uuid4(),
                derived_id=f"crates/{pkg.name}",
                name=pkg.name,
                package_manager_id=self.config.pm_config.pm_id,
                import_id=crate_id,
                readme=pkg.readme,
                created_at=self.now,
                updated_at=self.now,
            )
            pkg_id = p.id
            return pkg_id, p, {}
        else:
            # it's in the cache, so check for changes
            p = self.caches.package_map[crate_id]
            pkg_id = p.id
            # check for changes
            # right now, that's just the readme
            if p.readme != pkg.readme:
                return (
                    pkg_id,
                    None,
                    {"id": p.id, "readme": pkg.readme, "updated_at": self.now},
                )
            else:
                # existing package, no change
                return pkg_id, None, None

    def diff_url(self, pkg: Crate, new_urls: dict[URLKey, URL]) -> dict[UUID, UUID]:
        """
        Identifies the correct URL for this crate, based on fetched data and all URL
        strings collected so far

        Returns:
            resolved_urls: dict[UUID, UUID], the resolved URL for this crate
        """
        resolved_urls: dict[UUID, UUID] = {}

        urls: list[URLKey] = [
            URLKey(pkg.homepage, self.config.url_types.homepage),
            URLKey(pkg.repository, self.config.url_types.repository),
            URLKey(pkg.documentation, self.config.url_types.documentation),
        ] + ([URLKey(pkg.source, self.config.url_types.source)] if pkg.source else [])

        for url_key in urls:
            url = url_key.url
            url_type = url_key.url_type_id

            # guard: no URL
            if not url:
                continue

            resolved_url_id: UUID

            if url_key in new_urls:
                # if we've already tried to create this URL, use that one
                resolved_url_id = new_urls[url_key].id
            elif url_key in self.caches.url_map:
                # if it's already in the database, let's use that one
                resolved_url_id = self.caches.url_map[url_key].id
            else:
                # most will be here because it's the first run of clean data
                new_url = URL(
                    id=uuid4(),
                    url=url,
                    url_type_id=url_type,
                    created_at=self.now,
                    updated_at=self.now,
                )
                resolved_url_id = new_url.id

                # NOTE: THIS IS SUPER IMPORTANT
                # we're adding to new_urls here, not just in main
                new_urls[url_key] = new_url

            resolved_urls[url_type] = resolved_url_id

        return resolved_urls

    def diff_pkg_url(
        self, pkg_id: UUID, resolved_urls: dict[UUID, UUID]
    ) -> tuple[list[PackageURL], list[dict]]:
        """Takes in a package_id and resolved URLs from diff_url, and generates
        new PackageURL objects as well as a list of changes to existing ones

        Inputs:
          - pkg_id: the id of the package
          - resolved_urls: a map of url types to final URL ID for this pkg

        Outputs:
          - new_package_urls: a list of new PackageURL objects
          - updated_package_urls: a list of changes to existing PackageURL objects

        TODO:
          - We're updating every single package_url entity, which takes time. We should
            check if the latest URL has changed, and if so, only update that one.
        """
        new_links: list[PackageURL] = []
        updates: list[dict] = []

        # what are the existing links?
        existing: set[UUID] = {
            pu.url_id for pu in self.caches.package_urls.get(pkg_id, set())
        }

        # for the correct URL type / URL for this package:
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
                # TODO: this should only happen for `latest` URLs
                # there is an existing link between this URL and this package
                # let's find it
                existing_pu = next(
                    pu for pu in self.caches.package_urls[pkg_id] if pu.url_id == url_id
                )
                existing_pu.updated_at = self.now
                updates.append({"id": existing_pu.id, "updated_at": self.now})

        return new_links, updates

    def diff_deps(
        self, pkg: Crate
    ) -> tuple[list[LegacyDependency], list[LegacyDependency]]:
        """
        Identifies new and removed dependencies for a given crate.

        Uses the normalized dependency diffing approach:
        1. Normalize the crate to a NormalizedPackage
        2. Use shared diff_dependencies() for the core algorithm

        Returns:
            new_deps: list[LegacyDependency], the new dependencies
            removed_deps: list[LegacyDependency], the removed dependencies
        """
        normalized = normalize_crates_package(pkg)
        return diff_dependencies(
            normalized,
            self.caches,
            self.config.dependency_types,
            now=self.now,
        )
