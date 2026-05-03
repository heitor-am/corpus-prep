---
name: commit-style
description: Project commit conventions for corpus-prep — Conventional Commits, ASCII-only English, ≤80-char subject, hyphen-bulleted body ≤8 lines / 400 chars, no Co-Authored-By, no bare M<digits> shorthand. Invoke whenever a commit is being prepared in this repo, or when reviewing/rewriting a commit message that violated the rules.
---

# Commit style — corpus-prep

Codifies the conventions enforced by `.claude/hooks/git-guard.sh`. Use this skill **before** running `git commit` or `gh pr (create|edit) --title`. The hook blocks violations with exit code 2; this skill exists so messages comply on the first try.

## When to use

Invoke this skill whenever:

- Preparing a `git commit` (any size)
- Setting `--title` on `gh pr create` / `gh pr edit`
- Rewriting a message after the hook blocked one

Skip it for `git rebase --no-edit`, automatic merge commits, or `--amend` that preserves the original message.

## Rules (hook-enforced)

### Subject (line 1)

- Format: `<type>(<scope>)?!?: <subject>` — Conventional Commits.
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- Scopes used in this repo: `parsers`, `pdf`, `html`, `docling`, `textlike`, `detect`, `normalize`, `filter`, `dedup`, `shard`, `pipeline`, `cli`, `schemas`, `utils`, `tests`, `docs`, `ci`, `deps`, plus milestone scopes `m1`-`m7` (lowercase). Lowercase + hyphens only.
- ≤ **80 characters**.
- ASCII only — no accented characters, no em-dashes (`—`), no smart quotes.

### Body (after a blank line)

- ≤ **8 non-blank lines** AND ≤ **400 characters total**.
- Each item starts with `- ` (hyphen + space). One fact per line.
- A blank line separates subject from body.
- Describe **what changed and why**, not the investigation, not the timeline.
- ASCII only.
- Optional. Subject-only commits are fine for trivial changes.

### Forbidden anywhere in the message

- Non-ASCII characters (Portuguese, accented vowels, em-dashes).
- Bare uppercase `M<digits>` shorthand (e.g. `addresses M3`). Milestone numbers belong in `PRD.md`, not in commit prose. The lowercase scope `feat(m1):` is allowed because the hook check is case-sensitive.
- `Co-Authored-By: Claude …` trailer (per the user's standing preference).
- Process narration: "as discussed", "based on the research", "after testing".
- Mentioning specific PR numbers or issue IDs (the PR description handles those).

## Workflow

1. Run in parallel:
   - `git status` — see what is staged vs. unstaged.
   - `git diff --staged` (or `git diff` if nothing is staged) — read the actual change.
   - `git log --oneline -5` — confirm the existing commit style on this branch.
2. Decide whether the changes split into multiple logical commits. If yes, group them and produce one message per commit.
3. Draft the subject:
   - Imperative mood ("add", "fix", "rename"), present tense, no trailing period.
   - Pick the most-specific applicable scope.
   - Count characters; if it overflows 80, drop adjectives or move detail into the body.
4. Draft the body (only when it adds value):
   - 2-6 bullets is usually right. Do not pad to fill the limit.
   - Lead with the user-visible outcome, then any constraint or follow-up.
5. Sanity-check the message against every rule above before invoking `git commit`.
6. Emit the commit with one of:
   - `-m "subject"` for subject-only.
   - `-F <tmpfile>` for messages with bodies — write the message to `/tmp/commit_msg_<topic>.txt` first. The heredoc form (`-m "$(cat <<EOF ...)"`) tends to confuse the hook's pattern matcher.
7. Show the user the message **before** committing and ask for confirmation. The global rule "never commit unless the user explicitly asks" stands.
8. If the hook blocks, do **not** rewrite to bypass — read the rule it cited and fix the message.

## PR titles

The same subject rules apply to `gh pr (create|edit) --title "..."`. The hook validates the title argument. Bodies do not apply to PR titles.

## Examples

### Good

Subject only, trivial change:

```
docs(readme): clarify quickstart command
```

Subject + body, real feature:

```
feat(m1): schemas, registry pattern, and textlike parsers

- ParseResult and Document Pydantic v2 models
- UUIDv7 helper (sortable IDs)
- BaseParser ABC with ParserError / UnsupportedFormatError
- Registry pattern: @register decorator, get_parser, is_supported
- Parsers for TXT, MD, CSV, JSON with Latin-1 fallback
- 27 unit tests covering schemas, registry, and all four parsers
```

Bug fix with context:

```
fix(parsers): preserve PT chars in JSON output

- Pass ensure_ascii=False to json.dumps so 'cao' renders as 'cao'
- Indent stays at 2 to keep diffs readable
- Regression test in tests/test_parsers_textlike.py
```

### Bad (hook will block)

| Message | Rule violated |
|---|---|
| `add timeout` | No `<type>:` prefix |
| `Feat: timeout` | Uppercase type |
| `feat(Parsers): timeout` | Uppercase scope |
| `fix:bug` | Missing space after colon |
| `fix(parsers): correção de bug` | Non-ASCII (`çã`) |
| `fix(parsers): roll back to spec from M2` | Bare `M2` shorthand |
| Subject 90 chars | Subject > 80 |
| Body of 12 bullet lines | Body > 8 lines |
| Trailing `Co-Authored-By: Claude Opus …` | Forbidden trailer |

## Anti-patterns to avoid in the body

- **Narrating the investigation:** "Tried X, then Y, finally settled on Z." — the diff is the place for that.
- **Repeating the diff:** "Add field `foo` to model `Bar`." — the diff already says that. Explain the *purpose*.
- **Listing every file touched:** Reviewers can read the diff. Group by intent.
- **Apologizing or hedging:** "Quick fix", "should work", "ideally we'd refactor X". Either fix it or open an issue.

## Cross-references

- `.claude/hooks/git-guard.sh` — the actual enforcement.
- `.claude/settings.json` — wires the hook into PreToolUse.
- `PRD.md` §10 — milestones (referenced by `m<digits>` scopes).
