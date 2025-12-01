# Nautobot NV Data Model App Contribution Guidelines

Welcome to the Nautobot NV Data Model App project!
This document outlines the procedures and standards for contributing to the NV Data Model source code.
Adherence to these guidelines ensures code quality, readability, and maintainability.
We look forward to your contributions!

## Identifying the Feature or Fix

Contributors looking to add features or fixes are encouraged to reach out to the team by creating issues on the project's issue tracker.
This step ensures that efforts are not duplicated and that the proposed changes align with the project's goals.
Please communicate with the main developers before starting work to avoid the potential for your PR not being accepted.

## Development and Coding Standards

Adhering to coding standards is crucial for maintaining the quality of the codebase.
Here are the guidelines you should follow:

- **General Principles**
  - **User-oriented**: make it easy for end users, even at the cost of writing more code in the background
  - **Robust**: make it hard for users to make mistakes.
  - **Well-tested**: please add simple, fast unittests. Consider adding CI tests for end-to-end functionality.
  - **Reusable**: for every piece of code, think about how it can be reused in the future and make it easy to be reused.
  - **Readable**: code should be easier to read.
  - **Legal**: if you copy even one line of code from the Internet, make sure that the code allows the license that this project supports.
    Give credit and link back to the code.
  - **Sensible**: code should make sense. If you think a piece of code might be confusing, write comments.

- **Code Formatting and Style:**
  - Follow PEP 8 standards for coding style, emphasizing readability and proper documentation.
  - Use four spaces for indentation and maintain line length under 100 characters.
  - All Python code should have the license header.
    There should be a single blank line after the header if it is an import line.
    If there are no import statements and a class definition appears directly, there should be two blank lines.
  - There should be two blank lines between class definitions.
  - Use Google style for docstrings to ensure consistency and readability.
  - There should be no trailing spaces or blank lines at the end of files.
  - If adding documentation, each sentence in the file should be on a separate line.
    Markdown parsing and HTML rendering will collapse the spaces, and having each sentence on a separate line makes reading the diff if the file is updated much easier.
  - Use Python 3 type hints.

- **Branch and Commit Guidelines:**
  - Fork the repository and create branches for changes in your fork.
  - The `dev` branch is the primary branch to develop off of.
    - PRs intended to add new features should be sourced from the `dev` branch.
    - PRs intended to fix issues in the Nautobot LTM compatible release should be sourced from the latest `ltm-<major.minor>` branch instead of `dev`.
  - If you need to work on another branch that someone has implemented but not merged to the `dev` branch, checkout that branch first and create a new branch on it.
    Do not copy and paste files; we lose all commit histories with this approach.
  - Commit messages should be readable and understandable.
    Avoid vague messages like "bugfix" or "feature."
    Commit messages should provide sufficient information for reviewers.
  - Aim for multiple small commits rather than a large one for easier code reviews and rebasing.

- **Linting and Testing:**
  - Ensure your code passes all linters set up in the CI workflow.
    Linters run automatically when you push changes to the remote repository, but you can also run them locally.

- **Signing Your Work:**
  - We require all contributors to sign off on their commits, certifying that the contribution is their original work or that they have rights to submit it under a compatible license.
    Any contribution which contains commits that are not Signed-Off will not be accepted.
  - To sign off on a commit you simply use the `--signoff` (or `-s`) option when committing your changes:
  ```bash
  $ git commit -s -m "Add cool feature."
  ```
  This will append the following to your commit message:
  ```
  Signed-off-by: Your Name <your@email.com>
  ```
  - By signing off on commits, you certify compliance with the [Developer Certificate of Origin v1.1](https://developercertificate.org/).
  

## Pull Request (PR) Creation

- Read [Development and Coding Standards](#development-and-coding-standards) above.
- Make sure to sign your commits.
- Target the appropriate branch (`dev` or `ltm-<major.minor>`).
- If your code has not been tested, mark the PR as a draft.
- Follow the merge request template, which includes fields for summary and test plan.
  - Ensure your PR has a readable and understandable subject, avoiding generic titles like "bugfix" or "feature1."
- Use bullet points in the summary to clearly outline your contributions.
- In the test plan section, detail the experiments and commands run, attaching stdout of your command to demonstrate the effectiveness of your code and to help other contributors understand how to validate and run your code.
- Contributors are responsible for rebasing their branch if the main branch has been updated while they are working on their branch.
- Ensure that all pipeline stages pass without any error.
  - In case of failure, check the pipeline stage output and update your code accordingly.
- Create your PR and request a review.
- Your pull requests must pass all checks and peer-review before they can be merged.

Thanks in advance for your patience as we review your contributions; we do appreciate them!
