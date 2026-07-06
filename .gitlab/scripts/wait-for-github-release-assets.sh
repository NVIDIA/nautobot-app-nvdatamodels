#!/usr/bin/env bash

set -euo pipefail

output_file="${1:-dist/github-wheel-assets.tsv}"

: "${CI_COMMIT_TAG:?CI_COMMIT_TAG must be set}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"

poll_interval="${GITHUB_RELEASE_POLL_INTERVAL_SECONDS:-30}"
poll_timeout="${GITHUB_RELEASE_POLL_TIMEOUT_SECONDS:-1800}"

if ! [[ "${poll_interval}" =~ ^[1-9][0-9]*$ && "${poll_timeout}" =~ ^[1-9][0-9]*$ ]]; then
    echo "GitHub Release poll interval and timeout must be positive integers." >&2
    exit 1
fi

api_url="https://api.github.com/repos/${GITHUB_REPOSITORY}/releases/tags/${CI_COMMIT_TAG}"
response_file="$(mktemp)"
trap 'rm -f "${response_file}"' EXIT
mkdir -p "$(dirname "${output_file}")"

headers=(--header "Accept: application/vnd.github+json")
if [[ -n "${GITHUB_API_TOKEN:-}" ]]; then
    headers+=(--header "Authorization: Bearer ${GITHUB_API_TOKEN}")
fi

deadline=$((SECONDS + poll_timeout))
while (( SECONDS < deadline )); do
    http_status="$(
        curl \
            --silent \
            --show-error \
            --output "${response_file}" \
            --write-out "%{http_code}" \
            "${headers[@]}" \
            "${api_url}"
    )"

    if [[ "${http_status}" == "200" ]]; then
        jq --raw-output \
            '.assets[] | select(.state == "uploaded" and (.name | endswith(".whl"))) | [.name, .browser_download_url] | @tsv' \
            "${response_file}" >"${output_file}"
        if [[ -s "${output_file}" ]]; then
            echo "Found $(wc -l <"${output_file}" | tr -d ' ') wheel asset(s) for ${CI_COMMIT_TAG}."
            exit 0
        fi
        echo "GitHub Release ${CI_COMMIT_TAG} exists but has no uploaded wheel yet."
    elif [[ "${http_status}" == "404" ]]; then
        echo "GitHub Release ${CI_COMMIT_TAG} is not available yet."
    else
        echo "GitHub Release lookup failed with HTTP ${http_status}:" >&2
        jq . "${response_file}" >&2 2>/dev/null || cat "${response_file}" >&2
        exit 1
    fi

    sleep "${poll_interval}"
done

echo "Timed out waiting for wheel assets on GitHub Release ${CI_COMMIT_TAG}." >&2
exit 1
