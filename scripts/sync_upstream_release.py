#!/usr/bin/env python3
"""Update the SeerrNG YunoHost manifest to the latest stable GitHub release."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.toml"
REPOSITORY = os.environ.get("SEERRNG_UPSTREAM_REPO", "snapetech/seerrng")
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ARCHES = {"amd64": "x64", "arm64": "arm64"}


def github_json(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "seerrng-yunohost-release-sync",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        raise RuntimeError(f"GitHub API request failed for {url}: {error}") from error


def github_text(url: str) -> str:
    headers = {"User-Agent": "seerrng-yunohost-release-sync"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        raise RuntimeError(f"Could not read release checksum {url}: {error}") from error


def checksum_for(assets: dict[str, dict], asset_name: str) -> str:
    checksum_name = f"{asset_name.removesuffix('.tar.gz')}.sha256"
    checksum_asset = assets.get(checksum_name)
    binary_asset = assets.get(asset_name)
    if not checksum_asset or not binary_asset:
        raise RuntimeError(f"Release is missing {asset_name} or {checksum_name}")

    checksum_file = github_text(checksum_asset["browser_download_url"]).strip()
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", checksum_file)
    if not match or match.group(2) != asset_name:
        raise RuntimeError(f"Unexpected checksum file contents for {checksum_name}")

    checksum = match.group(1).lower()
    api_digest = binary_asset.get("digest")
    if api_digest and api_digest != f"sha256:{checksum}":
        raise RuntimeError(f"Checksum sidecar disagrees with GitHub digest for {asset_name}")
    return checksum


def replace_once(source: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, lambda _: replacement, source, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} entry in manifest.toml; found {count}")
    return updated


def main() -> int:
    release = github_json(API_URL)
    tag = release.get("tag_name", "")
    version_match = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag)
    if release.get("draft") or release.get("prerelease") or not version_match:
        raise RuntimeError(f"Latest GitHub release has an unsupported tag: {tag!r}")
    upstream_version = version_match.group(1)

    assets = {asset["name"]: asset for asset in release.get("assets", [])}
    manifest = MANIFEST.read_text(encoding="utf-8")
    current_version = re.search(r'^version = "([^"]+)"$', manifest, re.MULTILINE)
    if not current_version:
        raise RuntimeError("Could not find package version in manifest.toml")
    revision = re.search(r"~ynh(\d+)$", current_version.group(1))
    package_revision = f"~ynh{revision.group(1)}" if revision else "~ynh1"
    updated = replace_once(
        manifest,
        r'^version = "[^"]+"$',
        f'version = "{upstream_version}{package_revision}"',
        "package version",
    )

    for yunohost_arch, release_arch in ARCHES.items():
        asset_name = f"seerrng-{tag}-linux-{release_arch}.tar.gz"
        asset = assets.get(asset_name)
        if not asset:
            raise RuntimeError(f"Release {tag} is missing {asset_name}")
        checksum = checksum_for(assets, asset_name)
        updated = replace_once(
            updated,
            rf'^[ \t]*{yunohost_arch}\.url = "[^"]+"$',
            f'    {yunohost_arch}.url = "{asset["browser_download_url"]}"',
            f"{yunohost_arch} URL",
        )
        updated = replace_once(
            updated,
            rf'^[ \t]*{yunohost_arch}\.sha256 = "[^"]+"$',
            f'    {yunohost_arch}.sha256 = "{checksum}"',
            f"{yunohost_arch} SHA-256",
        )

    if updated == manifest:
        print(f"YunoHost manifest is already synced to SeerrNG {tag}.")
        return 0

    if "--check" in sys.argv[1:]:
        print(f"YunoHost manifest needs an update to SeerrNG {tag}.")
        return 1

    MANIFEST.write_text(updated, encoding="utf-8")
    print(f"Updated YunoHost manifest to SeerrNG {tag}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Release sync failed: {error}", file=sys.stderr)
        raise SystemExit(1)
