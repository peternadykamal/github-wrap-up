# GitHub Year in Review

A portable Agent Skill that researches GitHub history, builds an evidence-backed vertical timeline, and creates a personalized Wrapped with an offline HTML export. Supports one person, a team, an organization, or people scoped to an organization. Low, Medium (default), and High combine research depth with runtime-supported model/effort choices.

The reusable entrypoint is [SKILL.md](SKILL.md), following the [Agent Skills format](https://agentskills.io/specification). Collection, accounting, evidence review and presentation use local scripts rather than a particular agent SDK. Codex-specific UI metadata is optional and isolated in `agents/openai.yaml`.

## Requirements

- A harness that can read files, run local commands and write research artifacts; skill discovery is convenient, but manual invocation also works.
- Python 3.11+, Git, authenticated `gh`, and network access to the target GitHub host. The user signs in with `gh auth login` if needed. No model API key is required by the helpers; the harness handles its own model access.
- Node.js 22.13+ and npm when building the presentation.
- Optional subagents, model/effort controls and browser preview. Unsupported controls are reported and have explicit fallbacks; they are not assumed from the harness name.

## Install with one prompt

Copy this into your coding agent and attach `github-year-in-review.zip`, or include the repository URL in the same message:

```text
Install GitHub Year in Review from the attached ZIP or the repository link in this message for the coding agent I am using. Follow INSTALL.md, choose the correct skill directory automatically, verify the installation and prerequisites, and tell me how to invoke it. Let me complete any GitHub sign-in.
```

The agent handles download/extraction, destination selection and installation. It only needs your help if the source is inaccessible, the destination is genuinely ambiguous, or installation/sign-in requires permissions it does not have. The installed skill remains separate from a research run.

For link-only installation, include the real published repository URL. The source must be accessible to the agent; a ZIP works without publishing anything.

## Manual installation

Clone or copy this repository, then run the installer from its root. Supply the **parent skills directory**, not a path ending with the skill name:

```sh
python3 scripts/install_skill.py --skills-dir ~/.claude/skills
```

The installer creates `<skills-dir>/github-year-in-review/`, copies only reusable files and refuses to overwrite another installation. Add `--dry-run` to inspect the destination or `--link` for a live checkout link on systems supporting symlinks. Do not install a skill inside its own source checkout. Restart or refresh your harness if it caches skill discovery.

| Harness | Example skills directory | Invoke |
|---|---|---|
| Codex | Existing `~/.codex/skills/` installation, or a supported `.agents/skills/` directory | `$github-year-in-review` |
| Claude Code | Personal `~/.claude/skills/`, project `.claude/skills/` | `/github-year-in-review` |
| GitHub Copilot | Personal `~/.copilot/skills/`, project `.github/skills/` | Ask it to use `github-year-in-review` |
| Another Agent Skills host | Its documented skill directory | Its native skill invocation |
| A harness without skill discovery | Keep this checkout accessible | Ask it to read `SKILL.md` and follow it, supplying the target and mode |

Locations and loading behavior follow the installed harness version and organization policy. See the official [Claude Code skills guide](https://code.claude.com/docs/en/skills) and [Copilot skills guide](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills). These installation paths do not imply that a restricted chat or review session can execute the workflow.

Example request: “Use GitHub Year in Review for @example within example-org, this calendar year, Medium.” If scope is missing, the skill asks who to research; it never assumes the authenticated `gh` account is the subject.

## Runtime portability

Read [harness compatibility](references/harnesses.md) for capability negotiation. New runs use a provider-neutral runtime catalog and native JSON argument mapping. A harness may call its reasoning control `effort`, use a numeric thinking budget, expose it in an agent definition, or provide no override at all. The resolver supports these differences without shipping model IDs or invoking a vendor SDK.

A harness with model-only control can use selected workers while labeling effort inherited/unknown. Without suitable agent/model controls, research continues sequentially with the current conversation and a visible limitation. High's independent challenge requires an actual separate context. No helper silently changes the parent conversation's settings, starts another paid client, or changes a harness's global configuration.

## Verify and package

```sh
python3 -m unittest discover -s scripts -p '*_tests.py'
python3 scripts/package_skill.py --output artifacts/github-year-in-review.zip
```

Run these commands from this checkout. Packaging excludes Git history, caches, installed dependencies and run directories. Keep private evidence outside the distributable skill, preferably in a separate run directory. The generated frontend has its own checks, build and single-HTML export instructions.

Compatibility is tested with offline fixtures, including relocated copies, alternate tool/configuration interfaces, non-OpenAI documentation, numeric effort controls and sequential execution. Native end-to-end launches in every harness/provider are not certified. The runtime catalog records what the current host actually supports.
