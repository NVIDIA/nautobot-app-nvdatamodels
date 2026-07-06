# GitLab Kitmaker release jobs

The GitLab project is a mirror of the GitHub repository. GitHub remains the
source of truth and creates the GitHub Release and its wheel assets. A mirrored
`v*` tag starts this pipeline, which waits for those public assets before it
calls Kitmaker from an NVIDIA-network runner.

Configure these GitLab CI/CD variables:

| Variable | Required | Protection | Purpose |
| --- | --- | --- | --- |
| `KITMAKER_API_TOKEN` | Yes | Masked, hidden, protected | Authenticates to Kitmaker. |
| `KITMAKER_PROJECT_ID` | Yes | Protected | Selects the Kitmaker project. |
| `KITMAKER_PIC_EMAIL` | Yes | Protected | Sets the person-in-charge field for the Kitmaker request. |
| `GITHUB_API_TOKEN` | Recommended | Masked, hidden, protected | Avoids the low unauthenticated GitHub API rate limit while waiting for release assets. It only needs read access to this public repository. |

The mirror must include branches and tags and be configured to trigger
pipelines when mirrored refs are updated. Protect the `v*` tag pattern so the
protected Kitmaker variables are available to release pipelines.

The jobs follow the Cerebro GitLab convention: the mirrored Alpine image runs
on a `dca`, `linux/amd64`, `docker` runner and installs `bash`, `curl`, `git`,
`jq`, and `python3`. That runner must be able to reach
`kitmaker-portal.nvidia.com`.

Stable tags (`vX.Y.Z`) must point to a commit reachable from the default branch;
they are checked and published. Release candidate tags (`vX.Y.ZrcN`) must point
to an off-default-branch commit and are checked without publishing. In both
cases the tag's base version must match `project.version` in `pyproject.toml`.
