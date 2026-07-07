#!/usr/bin/env bash

set -euo pipefail

upload="${1:?Usage: kitmaker-release.sh <true|false> [asset-file]}"
asset_file="${2:-dist/github-wheel-assets.tsv}"

if [[ "${upload}" != "true" && "${upload}" != "false" ]]; then
    echo "The upload argument must be either true or false." >&2
    exit 1
fi

: "${KITMAKER_API_TOKEN:?KITMAKER_API_TOKEN must be set}"
: "${KITMAKER_PROJECT_ID:?KITMAKER_PROJECT_ID must be set}"
: "${KITMAKER_PIC_EMAIL:?KITMAKER_PIC_EMAIL must be set}"
: "${KITMAKER_PROJECT_NAME:?KITMAKER_PROJECT_NAME must be set}"

if [[ ! -s "${asset_file}" ]]; then
    echo "GitHub wheel asset list ${asset_file} is missing or empty." >&2
    exit 1
fi

kitmaker_base_url="${KITMAKER_BASE_URL:-https://kitmaker-portal.nvidia.com/api/v0}"
poll_interval="${KITMAKER_POLL_INTERVAL_SECONDS:-15}"
poll_timeout="${KITMAKER_POLL_TIMEOUT_SECONDS:-1800}"

if ! [[ "${poll_interval}" =~ ^[1-9][0-9]*$ && "${poll_timeout}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Kitmaker poll interval and timeout must be positive integers." >&2
    exit 1
fi

payload="[]"
while IFS=$'\t' read -r wheel_name wheel_url; do
    if [[ -z "${wheel_name}" || ! "${wheel_url}" =~ ^https://github\.com/ ]]; then
        echo "Invalid GitHub wheel asset entry: ${wheel_name}<tab>${wheel_url}" >&2
        exit 1
    fi
    payload="$(
        jq \
            --arg pic "${KITMAKER_PIC_EMAIL}" \
            --arg url "${wheel_url}" \
            --argjson upload "${upload}" \
            '. + [{pic: $pic, job_type: "wheel-release-job", url: $url, upload: $upload}]' \
            <<<"${payload}"
    )"
done <"${asset_file}"

request_body="$(
    jq -n \
        --arg project_name "${KITMAKER_PROJECT_NAME}" \
        --argjson payload "${payload}" \
        '{project_name: $project_name, payload: $payload}'
)"

response_file="$(mktemp)"
trap 'rm -f "${response_file}"' EXIT

release_url="${kitmaker_base_url}/projects/${KITMAKER_PROJECT_ID}/releases"
http_status="$(
    curl \
        --silent \
        --show-error \
        --output "${response_file}" \
        --write-out "%{http_code}" \
        --request POST \
        --header "Authorization: Bearer ${KITMAKER_API_TOKEN}" \
        --header "Content-Type: application/json" \
        --data "${request_body}" \
        "${release_url}"
)"

if [[ ! "${http_status}" =~ ^2[0-9][0-9]$ ]]; then
    echo "Kitmaker rejected the release request with HTTP ${http_status}:" >&2
    jq . "${response_file}" >&2 2>/dev/null || cat "${response_file}" >&2
    exit 1
fi

release_uuid="$(jq --exit-status --raw-output '.release_uuid' "${response_file}")"
echo "Kitmaker accepted release ${release_uuid} (upload=${upload})."

status_url="${kitmaker_base_url}/status/${release_uuid}"
deadline=$((SECONDS + poll_timeout))

while (( SECONDS < deadline )); do
    http_status="$(
        curl \
            --silent \
            --show-error \
            --output "${response_file}" \
            --write-out "%{http_code}" \
            --header "Authorization: Bearer ${KITMAKER_API_TOKEN}" \
            "${status_url}"
    )"

    if [[ ! "${http_status}" =~ ^2[0-9][0-9]$ ]]; then
        echo "Kitmaker status request failed with HTTP ${http_status}:" >&2
        jq . "${response_file}" >&2 2>/dev/null || cat "${response_file}" >&2
        exit 1
    fi

    status="$(jq --exit-status --raw-output '.status' "${response_file}")"
    echo "Kitmaker release ${release_uuid}: ${status}"

    case "${status}" in
        completed)
            exit 0
            ;;
        failed)
            jq . "${response_file}" >&2
            exit 1
            ;;
        pending|processing|building|in_progress)
            sleep "${poll_interval}"
            ;;
        *)
            echo "Kitmaker returned unknown release status: ${status}" >&2
            jq . "${response_file}" >&2
            exit 1
            ;;
    esac
done

echo "Timed out waiting for Kitmaker release ${release_uuid}." >&2
exit 1
