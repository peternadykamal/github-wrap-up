# Collecting GitHub evidence

The collector performs read-only remote requests and writes a private local research archive. GitHub CLI, Git and Python 3.11+ with an IANA timezone database are prerequisites. It never executes repository source, build steps, Git hooks or instructions embedded in commits/issues. A GitHub UI session is not required for collection; initial `gh` authorization or an organization’s SSO approval can require the user’s browser.

## Invoke

Run preflight before selecting targets so the “Me” option can name the authenticated login:

```sh
python3 <skill-dir>/scripts/collect.py --preflight
```

For Enterprise, add `--host <hostname>`. This reports versions, the authenticated login and profile URL, or a prerequisite/authentication action. It does not reveal tokens. If preflight fails, explain the specific missing prerequisite; do not substitute an unauthenticated public-only run or silently change accounts.

Resolve the user’s requested subjects and reporting window using `resolve_scope.py` and the instructions in the entrypoint, then collect:

```sh
python3 <skill-dir>/scripts/collect.py --config /absolute/path/scope.json --output /absolute/path/run
```

Re-running the same command resumes completed repositories and cached requests. `--refresh` refetches metadata and Git references; preserve a copy of a completed run before refreshing if its evidence must remain immutable. A changed input configuration requires a new run directory, preventing accidental mixing of incompatible scopes. Do not launch another collection against the same output concurrently.

The collector is sequential across repositories to keep API and Git load bounded. The later research agents can run concurrently under the agent scheduler. Interruptions leave atomic cache/checkpoint files; a repository with a detected error is retried on resume. Bounded retries back off on transient service/rate failures and ultimately report partial coverage; they never wait indefinitely or silently drop the failed dimension.

## Configuration

`schemaVersion: 1`. The canonical shape is:

```json
{
  "schemaVersion": 1,
  "host": "github.com",
  "window": {
    "start": "2026-01-01T00:00:00Z",
    "endExclusive": "2027-01-01T00:00:00Z",
    "timezone": "UTC",
    "timezoneConfirmed": false,
    "dateBasis": "authored"
  },
  "subjects": [
    {
      "id": "octocat",
      "login": "octocat",
      "aliases": {"logins": [], "emails": []}
    }
  ],
  "orgs": [],
  "repos": [],
  "expandOrganizationContributors": false,
  "patches": {"maxFiles": 12, "maxChars": 80000, "perFileChars": 10000}
}
```

The scope resolver supplies actual dates, clamps an ongoing year to collection time and preserves the requested ending separately. This example describes structure; it is not a ready-made target selection. Unknown window metadata, including `requestedEndExclusive`, `timezoneConfirmed` and `weekendDays`, is preserved in the manifest. Date filtering is `[start, endExclusive)` with timezone-aware instants. `dateBasis` defaults to authored; both author and committer timestamps remain available. Source Git history is traversed without a committer-date cutoff, so a rebase outside the year cannot silently hide an authored-in-year commit.

Subject IDs and logins are GitHub usernames; resolve profile URLs before writing the config. Aliases must be explicitly confirmed or independently supported exact identities. Cross-person alias collisions fail validation. GitHub account associations take precedence over a conflicting raw Git email; unresolved authors remain unresolved. Display-name matching is never used. Co-authored commits retain their coauthor list separately; they do not become a second primary-author commit.

Explicit `repos` and the accessible inventory of `orgs` define the repository boundary. Unscoped user discovery combines owned repositories, partitioned author/commenter/reviewer searches, commit search and contribution hints. If a subject is the authenticated viewer, it also includes that account’s accessible private/collaborator/organization repository inventory. This broad discovery remains a documented lower bound: hidden/inaccessible repositories, deleted repositories and unindexed branches cannot be guaranteed discoverable.

For a whole-organization target, `expandOrganizationContributors: true` adds source-associated accounts from the selected organization’s in-window Git history and PR/review/issue/comment/timeline records. This includes visible former members and nonmember contributors, not just the current roster. An organization with zero API-visible members can still collect repositories and discover contributors from history. Known bot identities are excluded from automatic subject expansion; unresolved Git identities remain a coverage issue. Explicit user lists scoped to an organization leave expansion false so the collector cannot widen the requested people.

## Stable output structure

```text
run/
  manifest.json
  coverage.json
  api-pages.json
  cache/<request-hash>.json
  mirrors/<owner>__<repository>/
  repos/<owner>__<repository>/
    metadata.json
    refs.json
    api-index.json
    coverage.json
    records.jsonl
    commits.jsonl
    prs.jsonl
    issues.jsonl
    reviews.jsonl
    comments.jsonl
    timeline.jsonl
    workflows.jsonl
    releases.jsonl
    deployments.jsonl
    changes/<sha>.json
  users/<canonical-login>/
    index.json
    repos/<owner>__<repository>/
      index.json
      months/YYYY-MM/
        index.json
        records.jsonl
```

Shared metadata and Git objects are collected once per repository. Person/month files hold references and explicit roles rather than duplicating entire source records. A person/repository view is created when relevant activity is observed, or when that repository was explicitly requested. Calendar-year reports include all twelve month folders, distinguishing upcoming months from no observed activity and partial coverage. Custom date ranges enumerate their intersecting months. The person index still exists when no repository activity is observed.

The archive and newly created files use private directory/file permissions. Raw API payloads and Git objects can contain sensitive source material and historical identity emails; **none of `cache/`, `mirrors/`, or raw records is a presentation asset**. Build a separate allowlisted, redacted presentation dataset. Do not publish the run directory, credential environment or Git configuration.

## Canonical record contract

Every shared `records.jsonl` line contains:

- `id`: globally scoped `host/owner/repository#kind:key`.
- `kind`: `commit`, `pull_request`, `issue`, `review`, `comment`, `timeline`, `workflow`, `release`, or `deployment`.
- `repo`, canonical `actor` (or source account or null), `occurredAt`, `url`, `title`, `body`, and `data`.

`commit.data` contains `sha`, `merge`, `authoredAt`, `committedAt`, `sourceAccount`, `attribution`, `coauthors`, `paths`, `additions`, `deletions`, run-relative `detail`, and `inspected: false`. Raw author/committer names and emails remain in this private layer. A shared SHA appearing in several repositories produces several repository records; descriptive totals deduplicate by SHA globally.

`pull_request.data` contains `number`, `author`, `createdAt`, `updatedAt`, `mergedAt`, `closedAt`, `mergedBy`, `state`, `draft`, `base`, `head`, head/base SHAs, linked commit SHAs, labels, assignees, milestone and returned changed paths/statistics. Its canonical `occurredAt` is creation time even when outside the year: retain the object as context and count each lifecycle event using its own timestamp. Do not count an old PR as newly opened because it merged this year.

Reviews have their own submission timestamp, state and `prNumber`. Conversation and inline comments have distinct scoped IDs and channels. If only a comment edit falls inside the year, `activityBasis: edited` preserves that distinction; it is not a new submitted comment. Timeline records retain recorded actors/events. PR merger roles use merge time, not the original opening time, and do not transfer implementation authorship.

Workflow records retain their triggering actor, attempt, SHA, branch and conclusion; deployments retain `targetSha`, latest returned `status`, `statusObservedAt`, environment and returned status history. A workflow success is not a production deployment. Deployment statuses may have expired; absent status is unknown. Releases preserve tag, publication metadata and returned asset summaries; tags also remain visible in Git refs.

## Collection depth and bounds

Nonshallow bare Git clones fetch current branches and tags, then explicit historical PR-head refs. Deleted or rewritten history outside all retained references may be absent. The collector never mutates the user’s working checkout. Git credentials are requested through `gh auth git-credential`, not embedded in repository URLs or written to helper configuration.

Account/stat enrichment uses batched GraphQL commit queries. Missing/null objects and paginated coauthor lists that exceed their retained bound are reported. Complete changed-file footprints come from Git trees for selected authors/coauthors. Source patches are bounded by the configured file/character limits, sensitive-path filtering and redaction; each detail states truncation and `inspected: false`. An empty or absent patch does not establish that no source changed.

PR and issue inventories include older objects with activity during the reporting year. Reviews, comments and timelines are fully paginated at collection; canonical activity rows are filtered to their own relevant timestamps. Full API responses remain in the private cache, and each repository’s `api-index.json` locates them. When reconstructing ready-for-review intervals or historical discussion context, inspect those raw responses for events preceding the reporting boundary instead of treating the filtered annual stream as the entire lifetime.

Searches partition over time when they exceed 1,000 results and fail visibly if a one-second partition still exceeds the ceiling. `incomplete_results` is an error, not a successful partial page. The PR commit-list endpoint’s 250-commit bound and file endpoint’s 3,000-file bound are checked and disclosed; fetched Git PR refs provide a separate history source. Filtered workflow runs have a 1,000-result ceiling in this implementation and become partial when reached. It does not invent an all-year success rate from a truncated workflow set.

`coverage.status` is `complete`, `partial`, or `collecting`; root `coverage.complete` is true only for a completed bounded collection without detected errors. Complete means requested, implemented collection dimensions returned successfully. It does not mean every historical GitHub fact exists, every identity resolved, or any code was inspected/executed. Errors, unresolved identity counts, source-excerpt bounds and uncollected dimensions are explicit. Discussion/Projects histories, organization audit logs, historical popularity snapshots, expired logs/artifacts, and deleted unreachable history are not collected by this implementation. Additional scoped evidence can be added deliberately and documented; never silently imply exhaustive access.

## Verify

```sh
python3 <skill-dir>/scripts/collector_tests.py
```

The offline suite covers real temporary Git history with authored/committed dates in different years, account alias precedence, source excerpts, cache replay and pagination, capped/incomplete searches, an old PR merged in-year, merger dates, monthly perspectives, whole-organization expansion, private viewer inventory, unresolved commit objects, complete fixture collection/resume, and private file permissions. It uses mocks for network operations and does not constitute a live full-year collection.
