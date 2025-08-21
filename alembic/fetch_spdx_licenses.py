#!/usr/bin/env pkgx uv run
"""
SPDX License Fetching Script

Fetches SPDX license data from GitHub and generates SQL INSERT statements
for the licenses table. Designed to be piped directly to psql.
"""

from __future__ import annotations

import json
import logging
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def setup_logging() -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Log to stderr so stdout is clean for SQL
    )
    return logging.getLogger(__name__)


def fetch_license_directory() -> list[str]:
    """
    Fetch the directory listing of SPDX license files from GitHub API.
    
    Returns:
        List of license filenames (without .txt extension)
        
    Raises:
        Exception: If unable to fetch directory listing
    """
    api_url = "https://api.github.com/repos/spdx/license-list-data/contents/text"
    
    try:
        req = Request(api_url)
        req.add_header("User-Agent", "CHAI-OSS-License-Fetcher/1.0")
        
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            
        # Filter for .txt files and exclude deprecated licenses
        license_files = []
        for item in data:
            if (
                item["type"] == "file"
                and item["name"].endswith(".txt")
                and not item["name"].startswith("deprecated_")
            ):
                # Remove .txt extension to get license name
                license_name = item["name"][:-4]
                license_files.append(license_name)
                
        return license_files
        
    except (HTTPError, URLError, json.JSONDecodeError) as e:
        raise Exception(f"Failed to fetch license directory: {e}") from e


def fetch_license_text(license_name: str) -> str | None:
    """
    Fetch the text content of a specific SPDX license.
    
    Args:
        license_name: Name of the license (without .txt extension)
        
    Returns:
        License text content or None if failed to fetch
    """
    raw_url = f"https://raw.githubusercontent.com/spdx/license-list-data/refs/heads/main/text/{license_name}.txt"
    
    try:
        req = Request(raw_url)
        req.add_header("User-Agent", "CHAI-OSS-License-Fetcher/1.0")
        
        with urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
            
    except (HTTPError, URLError, UnicodeDecodeError) as e:
        logging.warning(f"Failed to fetch license {license_name}: {e}")
        return None


def escape_sql_string(text: str) -> str:
    """Escape single quotes in SQL string values."""
    return text.replace("'", "''")


def generate_license_sql(licenses: dict[str, str]) -> str:
    """
    Generate SQL INSERT statements for licenses.
    
    Args:
        licenses: Dictionary mapping license names to their text content
        
    Returns:
        SQL INSERT statement with ON CONFLICT handling
    """
    if not licenses:
        return "-- No licenses to insert\n"
        
    values = []
    for name, text in licenses.items():
        escaped_name = escape_sql_string(name)
        escaped_text = escape_sql_string(text)
        values.append(f"('{escaped_name}', '{escaped_text}')")
    
    values_clause = ",\n".join(values)
    
    return f"""-- SPDX License data
INSERT INTO "licenses" ("name", "text") VALUES
{values_clause}
ON CONFLICT (name) DO UPDATE SET 
    text = EXCLUDED.text,
    updated_at = NOW();
"""


def main() -> None:
    """Main function to fetch SPDX licenses and output SQL."""
    logger = setup_logging()
    
    try:
        logger.info("Fetching SPDX license directory...")
        license_names = fetch_license_directory()
        logger.info(f"Found {len(license_names)} licenses to process")
        
        licenses = {}
        failed_count = 0
        
        for license_name in license_names:
            logger.info(f"Fetching license: {license_name}")
            license_text = fetch_license_text(license_name)
            
            if license_text is not None:
                licenses[license_name] = license_text
            else:
                failed_count += 1
        
        logger.info(f"Successfully fetched {len(licenses)} licenses, {failed_count} failed")
        
        # Generate and output SQL
        sql = generate_license_sql(licenses)
        print(sql)  # Print to stdout for piping to psql
        
        if failed_count > 0:
            logger.warning(f"Failed to fetch {failed_count} licenses")
            
    except Exception as e:
        logger.error(f"License fetching failed: {e}")
        # Output a comment so psql doesn't fail
        print("-- SPDX license fetching failed, continuing with migration")
        sys.exit(0)  # Don't fail the migration


if __name__ == "__main__":
    main()