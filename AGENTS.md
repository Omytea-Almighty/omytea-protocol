<!-- OMYTEA_ORG_SYNC_POLICY_START -->
# START HERE — Omytea-Almighty organization contract

Read [`ORG-SYNC.md`](ORG-SYNC.md) before editing, committing, or publishing.
The only canonical GitHub repository is
`https://github.com/Omytea-Almighty/omytea-protocol.git`.

A normal reviewed commit or rewrite in the canonical checkout or a registered
linked worktree is queued by managed hooks; ordinary direct push is denied.
Never automate `git add` or commit creation; never pull, merge, rebase,
force-push, delete refs, change visibility, use `git push --no-verify`, set or
override `core.hooksPath`, or bypass managed sync, security, publication, or
release gates. A repository-local `git commit --no-verify` exception is allowed
only when the repository's documented hook policy expressly permits it and the
operator records why. If any identity, visibility, origin, ancestry, policy,
hook, governance, content scan, or remote-SHA gate fails, preserve the local
commit and report `BLOCKED_*`.
For this `direct-public` repository, an intentional commit is the publication
decision. Secret scanning is not a privacy, PII, licensing, or commercial-
sensitivity review; never mirror private or uncommitted source-tree content here.

Members may create and upload to repositories they own. Modifying, deleting,
transferring, archiving, or changing visibility of another owner's repository
requires explicit authorization.

The personal skills archive `Adonyth/almighty` is excluded. The private
`Omytea-Almighty/omytea-org-sync` control-plane source is manually reviewed,
is not an automatic sync target, and never self-deploys.

<!-- OMYTEA_ORG_SYNC_POLICY_END -->
