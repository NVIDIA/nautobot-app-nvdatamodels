#!/usr/bin/env bash

set -euo pipefail

release_branch="${1:-main}"

: "${GITHUB_REF_NAME:?GITHUB_REF_NAME must be set}"
: "${GITHUB_REF_TYPE:?GITHUB_REF_TYPE must be set}"
: "${GITHUB_SHA:?GITHUB_SHA must be set}"

if [[ "${GITHUB_REF_TYPE}" != "tag" ]]; then
    echo "Release policy can only be determined for a tag." >&2
    exit 1
fi

git fetch --no-tags origin \
    "+refs/heads/${release_branch}:refs/remotes/origin/${release_branch}"

commit_on_release_branch="false"
if git merge-base --is-ancestor "${GITHUB_SHA}" "origin/${release_branch}"; then
    commit_on_release_branch="true"
fi

version_component='(0|[1-9][0-9]*)'
stable_tag_pattern="^${version_component}\\.${version_component}\\.${version_component}$"
release_candidate_tag_pattern="^${version_component}\\.${version_component}\\.${version_component}-rc\\.([1-9][0-9]*)$"

if [[ "${GITHUB_REF_NAME}" =~ ${stable_tag_pattern} ]]; then
    tag_kind="stable"
elif [[ "${GITHUB_REF_NAME}" =~ ${release_candidate_tag_pattern} ]]; then
    tag_kind="release-candidate"
else
    echo "Release tags must use X.Y.Z or X.Y.Z-rc.N." >&2
    exit 1
fi

repository_root="$(git rev-parse --show-toplevel)"
project_version="$(
    python3 -c \
        'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' \
        "${repository_root}/pyproject.toml"
)"
tag_version="${GITHUB_REF_NAME}"
tag_base_version="${tag_version%%-rc.*}"
project_version_pattern="^${version_component}\\.${version_component}\\.${version_component}$"

if [[ ! "${project_version}" =~ ${project_version_pattern} ]]; then
    echo "pyproject.toml version ${project_version} must use the exact stable format X.Y.Z." >&2
    exit 1
fi

if [[ "${tag_base_version}" != "${project_version}" ]]; then
    echo "Tag base version ${tag_base_version} does not match pyproject.toml version ${project_version}." >&2
    exit 1
fi

if [[ "${commit_on_release_branch}" == "true" ]]; then
    if [[ "${tag_kind}" != "stable" ]]; then
        echo "A tag reachable from ${release_branch} must use the stable format X.Y.Z." >&2
        exit 1
    fi
    pypi_publish="true"
else
    if [[ "${tag_kind}" != "release-candidate" ]]; then
        echo "A tag not reachable from ${release_branch} must use the release candidate format X.Y.Z-rc.N." >&2
        exit 1
    fi
    pypi_publish="false"
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "pypi_publish=${pypi_publish}" >>"${GITHUB_OUTPUT}"
fi

echo "Tagged commit reachable from ${release_branch}: ${commit_on_release_branch}"
echo "Validated release tag: ${GITHUB_REF_NAME}"
echo "Publish to PyPI: ${pypi_publish}"
