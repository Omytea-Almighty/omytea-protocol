# Omytea-Almighty repository instructions

Read [`ORG-SYNC.md`](../ORG-SYNC.md) before editing or publishing. The canonical
remote is `Omytea-Almighty/omytea-protocol`. Automatic synchronization is only for
already-created, reviewed commits. Managed `post-commit` and `post-rewrite`
hooks queue; ordinary direct push is denied; registered linked worktrees are
supported. Never stage or commit dirty work, rewrite history, force-push,
delete refs, change visibility, use `git push --no-verify`, set or override
`core.hooksPath`, or bypass managed sync, security, publication, or release
gates. A repository-local `git commit --no-verify` exception is allowed only
when the repository's documented hook policy expressly permits it and the
operator records why. Any gate uncertainty fails closed as `BLOCKED_*` while
the local commit remains intact. `Adonyth/almighty` is excluded; the private
`omytea-org-sync` source is manual-review/manual-deploy and never self-syncs.
This is `direct-public`: every intentional commit is a publication decision.
Secret scanning does not judge PII, licensing, research, or commercial
sensitivity; never mirror private or uncommitted source-tree content here.
