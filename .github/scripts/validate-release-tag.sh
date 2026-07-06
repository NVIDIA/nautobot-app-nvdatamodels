#!/usr/bin/env bash

set -euo pipefail

release_branch="${1:-main}"

: "${GITHUB_REF_NAME:?GITHUB_REF_NAME must be set}"
: "${GITHUB_REF_TYPE:?GITHUB_REF_TYPE must be set}"
: "${GITHUB_SHA:?GITHUB_SHA must be set}"

if [[ "${GITHUB_REF_TYPE}" != "tag" ]]; then
    echo "Kitmaker release mode can only be determined for a tag." >&2
    exit 1
fi

git fetch --no-tags origin \
    "+refs/heads/${release_branch}:refs/remotes/origin/${release_branch}"

commit_on_release_branch="false"
if git merge-base --is-ancestor "${GITHUB_SHA}" "origin/${release_branch}"; then
    commit_on_release_branch="true"
fi

version_component='(0|[1-9][0-9]*)'
stable_tag_pattern="^v${version_component}\\.${version_component}\\.${version_component}$"
release_candidate_tag_pattern="^v${version_component}\\.${version_component}\\.${version_component}rc([1-9][0-9]*)$"

if [[ "${commit_on_release_branch}" == "true" ]]; then
    if [[ ! "${GITHUB_REF_NAME}" =~ ${stable_tag_pattern} ]]; then
        echo "A tag reachable from ${release_branch} must use the exact stable format vX.Y.Z." >&2
        exit 1
    fi
elif [[ ! "${GITHUB_REF_NAME}" =~ ${release_candidate_tag_pattern} ]]; then
    echo "An off-${release_branch} tag must use the exact release candidate format vX.Y.ZrcN." >&2
    exit 1
fi

repository_root="$(git rev-parse --show-toplevel)"
project_version="$(
    python3 -c \
        'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' \
        "${repository_root}/pyproject.toml"
)"
tag_version="${GITHUB_REF_NAME#v}"
tag_base_version="${tag_version%%rc*}"
project_version_pattern="^${version_component}\\.${version_component}\\.${version_component}$"

if [[ ! "${project_version}" =~ ${project_version_pattern} ]]; then
    echo "pyproject.toml version ${project_version} must use the exact stable format X.Y.Z." >&2
    exit 1
fi

if [[ "${tag_base_version}" != "${project_version}" ]]; then
    echo "Tag base version ${tag_base_version} does not match pyproject.toml version ${project_version}." >&2
    exit 1
fi

echo "Tagged commit reachable from ${release_branch}: ${commit_on_release_branch}"
echo "Validated release tag: ${GITHUB_REF_NAME}"
