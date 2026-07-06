#!/usr/bin/env bash

set -euo pipefail

dist_dir="${1:-dist}"
tag="${GITHUB_REF_NAME:?GITHUB_REF_NAME must be set}"

if [[ "${GITHUB_REF_TYPE:-}" != "tag" ]]; then
    echo "GitHub Release assets can only be published from a tag." >&2
    exit 1
fi

shopt -s nullglob
assets=("${dist_dir}"/*.whl "${dist_dir}"/*.tar.gz)

if (( ${#assets[@]} == 0 )); then
    echo "No wheel or source distribution found in ${dist_dir}." >&2
    exit 1
fi

expected_prerelease="false"
release_options=(--generate-notes --title "${tag}" --verify-tag)
if [[ "${tag}" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)rc([1-9][0-9]*)$ ]]; then
    expected_prerelease="true"
    release_options+=(--prerelease)
fi

if ! gh release view "${tag}" >/dev/null 2>&1; then
    gh release create "${tag}" "${assets[@]}" "${release_options[@]}"
    exit 0
fi

actual_prerelease="$(gh release view "${tag}" --json isPrerelease --jq '.isPrerelease')"
if [[ "${actual_prerelease}" != "${expected_prerelease}" ]]; then
    echo "GitHub Release ${tag} has an incorrect prerelease classification." >&2
    echo "Expected isPrerelease=${expected_prerelease}, found ${actual_prerelease}." >&2
    exit 1
fi

temp_dir="$(mktemp -d)"
trap 'rm -rf "${temp_dir}"' EXIT

for asset in "${assets[@]}"; do
    asset_name="$(basename "${asset}")"
    downloaded_asset="${temp_dir}/${asset_name}"

    if gh release download "${tag}" --pattern "${asset_name}" --dir "${temp_dir}" 2>/dev/null; then
        if ! cmp --silent "${asset}" "${downloaded_asset}"; then
            echo "Release asset ${asset_name} already exists with different contents." >&2
            exit 1
        fi
        echo "Release asset ${asset_name} already exists and matches the build."
        continue
    fi

    gh release upload "${tag}" "${asset}"
done
