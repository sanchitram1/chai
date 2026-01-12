from datetime import datetime
from uuid import UUID, uuid4

from core.config import Config
from core.diff import diff_dependencies
from core.logger import Logger
from core.models import URL, LegacyDependency, Package, PackageURL
from core.structs import Cache, URLKey
from package_managers.homebrew.normalizer import normalize_homebrew_package
from package_managers.homebrew.structs import Actual


class Diff:
    def __init__(self, config: Config, caches: Cache):
        self.config = config
        self.now = datetime.now()
        self.caches = caches
        self.logger = Logger("homebrew_diff")

    def diff_pkg(self, pkg: Actual) -> tuple[UUID, Package | None, dict | None]:
        """
        Checks if the given pkg is in the package_cache.

        Returns:
          - pkg_id: the id of the package
          - package: If new, returns a new package object. If existing, returns None
          - changes: a dictionary of changes
        """
        self.logger.debug(f"Diffing package: {pkg.formula}")
        pkg_id: UUID
        if pkg.formula not in self.caches.package_map:
            # new package
            p = Package(
                id=uuid4(),
                derived_id=f"homebrew/{pkg.formula}",
                name=pkg.formula,
                package_manager_id=self.config.pm_config.pm_id,
                import_id=pkg.formula,
                readme=pkg.description,
                created_at=self.now,
                updated_at=self.now,
            )
            pkg_id: UUID = p.id
            # no update payload, so that's empty
            return pkg_id, p, {}
        else:
            p = self.caches.package_map[pkg.formula]
            pkg_id = p.id
            # check for changes
            # right now, that's just the readme
            if p.readme != pkg.description:
                self.logger.debug(f"Description changed for {pkg.formula}")
                return (
                    pkg_id,
                    None,
                    {"id": p.id, "readme": pkg.description, "updated_at": self.now},
                )
            else:
                # existing package, no change
                return pkg_id, None, None

    def diff_url(
        self, pkg: Actual, new_urls: dict[tuple[str, UUID], URL]
    ) -> dict[UUID, UUID]:
        """Given a package's URLs, returns the resolved URL or this specific formula"""
        resolved_urls: dict[UUID, UUID] = {}

        # we need to check if (a) URLs are in our cache, or (b) if we've already handled
        # them before. if so, we should use that
        urls = (
            (pkg.homepage, self.config.url_types.homepage),
            (pkg.source, self.config.url_types.source),
            (pkg.repository, self.config.url_types.repository),
        )

        for url, url_type in urls:
            # guard: no URL
            if not url:
                continue

            url_key = URLKey(url, url_type)
            resolved_url_id: UUID
            if url_key in new_urls:
                resolved_url_id = new_urls[url_key].id
            elif url_key in self.caches.url_map:
                resolved_url_id = self.caches.url_map[url_key].id
            else:
                self.logger.debug(f"URL {url} for {url_type} is entirely new")
                new_url = URL(
                    id=uuid4(),
                    url=url,
                    url_type_id=url_type,
                    created_at=self.now,
                    updated_at=self.now,
                )
                resolved_url_id = new_url.id

                # NOTE: THIS IS SUPER IMPORTANT
                # we're not just borrowing this value, we're mutating it as well
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
                # here is an existing link between this URL and this package
                # let's find it
                existing_pu = next(
                    pu for pu in self.caches.package_urls[pkg_id] if pu.url_id == url_id
                )
                existing_pu.updated_at = self.now
                updates.append({"id": existing_pu.id, "updated_at": self.now})

        return new_links, updates

    def diff_deps(
        self, pkg: Actual
    ) -> tuple[list[LegacyDependency], list[LegacyDependency]]:
        """
        Takes in a Homebrew formula and figures out what dependencies have changed.

        Uses the normalized dependency diffing approach:
        1. Normalize the formula to a NormalizedPackage
        2. Use shared diff_dependencies() for the core algorithm

        Returns:
          - new_deps: a list of new dependencies
          - removed_deps: a list of removed dependencies
        """
        normalized = normalize_homebrew_package(pkg)
        return diff_dependencies(
            normalized,
            self.caches,
            self.config.dependency_types,
            now=self.now,
        )
