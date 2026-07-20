# Omytea-Almighty organization sync contract

> **START HERE — binding for humans and agents.** Canonical repository:
> `Omytea-Almighty/omytea-protocol` (GitHub repository ID `1286751239`). Expected
> visibility: **public**. Policy version: `2026-07-19.2`.

## One-screen rule

Work normally, review deliberately, and make an intentional commit. The installed
hook then queues that already-created commit for the organization sync controller.
The controller may perform a normal fast-forward push of the current branch only
after it verifies repository identity, expected visibility, origin, ancestry,
committed-content safety, and the remote SHA. It never decides what to commit.

Every committed byte is public. Review for secrets and private references before committing; successful committed branches may then synchronize.

## Authority

- The canonical owner is `Omytea-Almighty`; the default branch is `master`.
- Organization members can read private project repositories through the
  organization base permission. Non-members cannot.
- Ordinary members may create repositories and upload to repositories they own.
  They must not modify, delete, transfer, archive, or change the visibility of
  another owner's repository without explicit authorization.
- Repository visibility is human-administered policy. No hook, local controller,
  agent, or GitHub workflow may change it.

## Required flow

1. Read this file and the nearest `AGENTS.md` before editing.
2. Confirm `origin` is exactly the organization HTTPS or SSH URL for this repo.
3. Stage only reviewed paths and create a normal commit under this repo's rules.
4. The composable `post-commit`/rewrite hook durably queues the current SHA.
5. The single-writer controller fetches metadata and refs, then either pushes the
   same branch fast-forward or records a visible `BLOCKED_*` result.
6. Success exists only when the remote branch SHA reads back equal to local HEAD.
7. A periodic full audit reconciles missed hooks, policy drift, and remote drift.

## Fail-closed invariants

Automation must **never**:

- run `git add`, create a commit, include uncommitted files, or alter the index;
- pull, merge, rebase, reset, force-push, delete a ref, push a tag, or rewrite history;
- push when owner, numeric repository ID, visibility, origin, branch ancestry, or
  public-release evidence is absent or mismatched;
- print secret values, execute repository code as a preflight, bypass any
  organization-managed sync, security, publication, or release gate, or
  silently edit this policy/verifier to make a failure pass;
- use `git push --no-verify`. A repository-local `git commit --no-verify`
  exception is allowed only when that repository's documented hook policy
  expressly permits it and the operator records why; it never bypasses the
  organization sync hook.

A dirty working tree may coexist with a push of an earlier reviewed commit, but
those dirty bytes remain strictly local and are reported. A non-fast-forward or
unreachable API leaves the commit local and produces a durable blocked receipt.

## Lanes and public-release boundary

This repository is lane `direct-public`.

- `direct-private`: synchronize committed objects only after private visibility
  is confirmed live.
- `direct-public`: synchronize committed objects only after the public-content
  scan passes; the commit is already a publication decision.
- `curated-public`: additionally require a PASS receipt bound to the exact HEAD;
  never generic-rsync a private source tree into a public mirror.
- `remote-only`: audit identity and visibility, but do not push without an
  explicitly registered canonical checkout.

## Operate and recover

Run `omytea-org-sync audit` for a read-only status report, or
`omytea-org-sync reconcile` to retry safe pending committed work. Inspect durable
receipts under `~/.local/state/omytea-org-sync/`. Fix the cause of a `BLOCKED_*`
result; never work around the gate. Existing Git LFS and commit-message hooks are
part of repository behavior and must be composed, not overwritten.
