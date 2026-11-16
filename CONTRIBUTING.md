# Contributing

Write every commit message in English using Conventional Commits:

```text
type(scope): summary
```

The scope is optional, so `type: summary` is also valid. Use one of these types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `revert`. Keep the subject at most 72 characters, and give each commit one purpose. Use an imperative, descriptive summary, such as `fix(audio): handle missing input device`.

For a breaking change, add `!` before the colon (for example, `feat(api)!: remove legacy endpoint`) and explain it in a `BREAKING CHANGE:` footer. The validator checks that the entire message, including its body, uses ASCII characters. ASCII is only an aid to English writing; review the wording yourself.

## Local commit check

Install the shared validator as a Git `commit-msg` hook from the repository root:

```sh
git config --local core.hooksPath .githooks
```

The hook runs for new commits. To check a message directly:

```sh
node scripts/check_commit_messages.js --message-file path/to/message.txt
```

For example, a file containing `feat: add lobby timer` should pass; a file containing `feature: add lobby timer` should fail. The pull request check runs the same validator on every new commit in the PR. The historical `Initial commit` and Git-generated merge commits are exempt. Changes to `main` must be submitted through a pull request after the repository rule is enabled.
