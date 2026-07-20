# Omytea-Almighty organization sync contract

> **START HERE — binding for humans and agents.** Canonical repository:
> `Omytea-Almighty/omytea-protocol` (GitHub repository ID `1286751239`). Expected
> visibility: **public**. Policy version: `2026-07-19.4`.

## One-screen rule

Work normally, review deliberately, and make an intentional commit. Managed
`post-commit` and `post-rewrite` hooks queue the already-created commit for
the organization sync controller. Ordinary direct `git push` is denied. The
controller may perform a normal fast-forward push of the verified current head
of the exact queued branch/ref only after it proves the queued SHA is an
ancestor and verifies repository identity, expected visibility, origin,
ancestry, committed-content safety, policy/workflow definitions, and the remote SHA.
Actions health is audited after publication. The controller never decides what
to commit.

Every committed byte is public. An intentional commit is the publication
decision; only commits created in this independent public checkout may
synchronize. Never copy or rsync private or uncommitted source-tree content.

## Authority

- The canonical owner is `Omytea-Almighty`; the default branch is `master`.
- This repository is public; organization membership is not required to read it.
- Ordinary members may create repositories and upload to repositories they own.
  They must not modify, delete, transfer, archive, or change the visibility of
  another owner's repository without explicit authorization.
- Repository visibility is human-administered policy. No hook, local controller,
  agent, or GitHub workflow may change it.
- The personal private skills archive `Adonyth/almighty` is out of scope and
  must never be transferred to, mirrored into, or synchronized by this organization.
- `Omytea-Almighty/omytea-org-sync` is a private, manually reviewed control-plane
  source repository. It is not an automatic sync target and never self-deploys.

## Required flow

1. Read this file and the nearest `AGENTS.md` before editing.
2. Confirm `origin` is exactly `https://github.com/Omytea-Almighty/omytea-protocol.git`.
3. Stage only reviewed paths and create a normal commit under this repo's rules.
4. Managed `post-commit` and `post-rewrite` hooks durably queue the current SHA.
5. Registered linked worktrees are supported only when their common Git directory
   exactly matches the canonical checkout; arbitrary clones or forged pointers block.
6. The managed `pre-push` hook denies ordinary direct pushes. Do not bypass it.
7. The single-writer controller fetches metadata and refs, proves each queued SHA
   is an ancestor of the verified current local branch head, then either pushes
   that head fast-forward through its isolated transport or records a visible
   `BLOCKED_*` result.
8. Success exists only when the remote reads back equal to the verified local
   branch head; every completed queued SHA must be an ancestor covered by that head.
9. A periodic full audit reconciles registered current branches, policy,
   governance, and remote drift. Inactive unqueued refs are outside automatic recovery.

## Fail-closed invariants

Automation must **never**:

- run `git add`, create a commit, include uncommitted files, or alter the index;
- pull, merge, rebase, reset, force-push, delete a ref, push a tag, or rewrite history;
- push when owner, numeric repository ID, visibility, origin, branch ancestry, or
  required policy files or workflow definition is absent or mismatched;
- print secret values, execute repository code as a preflight, bypass any
  organization-managed sync, security, publication, or release gate, or
  silently edit this policy/verifier to make a failure pass;
- use `git push --no-verify`, set or override `core.hooksPath`, or otherwise
  bypass the managed direct-push guard. A repository-local `git commit --no-verify`
  exception is allowed only when that repository's documented hook policy
  expressly permits it and the operator records why; it never bypasses the
  organization sync hook.

A dirty working tree may coexist with a push of an earlier reviewed commit, but
those dirty bytes remain strictly local and are reported. A non-fast-forward or
unreachable API leaves the commit local and produces a durable blocked receipt.
The same rule applies in a controller-registered linked worktree: only committed
branch history through the verified current head is eligible; uncommitted
working-tree bytes never are.

## Lanes and public-release boundary

This repository is lane `direct-public`.
Every intentional commit in this public checkout is a publication decision.
The automated scan detects only configured high-confidence secret patterns; it
does not decide whether ordinary text, PII, licensing, research, or commercial
content is suitable for publication. Never copy or rsync uncommitted or private
parent/source-tree content into this repository; publish only deliberately
reviewed commits created inside this independent public checkout.

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
result; never work around the gate. Unknown existing managed-hook paths or backup
files block installation pending an explicit exact-hash composition decision;
they are never silently overwritten or executed from a backup.
