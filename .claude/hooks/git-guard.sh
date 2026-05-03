#!/bin/bash
# Claude Code PreToolUse hook for the corpus-prep repo.
#
# Reads JSON from stdin with tool_input. Exits with code 2 to block the tool;
# stderr is shown to Claude so it can self-correct.
#
# Repo flow: single `main` branch, feature work via topic branches + GitHub PRs
# (no separate `develop`). Direct push to main is blocked from inside Claude
# sessions — escape hatch is to push from a regular shell outside the session.
#
# Rules applied to commit messages AND `gh pr {create,edit} --title`:
#   1. Conventional Commits subject:
#         <type>(<scope>)?!?: <subject>
#      Types: feat fix docs style refactor perf test build ci chore revert
#   2. Subject ≤ 80 chars.
#   3. ASCII-only (English commit messages).
#   4. No bare `M<digits>` references in body text — milestone numbers belong
#      in PRD.md, not in shorthand inside commit prose. Lowercase `m<digits>`
#      as a scope (e.g. `feat(m1):`) is allowed (case-sensitive check).
#   5. No `Co-Authored-By:` trailer.
#
# Commit-only rules:
#   6. Body ≤ 8 non-blank lines and ≤ 400 chars.

set -uo pipefail

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# ─────────────────────── shared validation helpers ───────────────────────

fail() {
  local label=$1 content=$2 reason=$3
  {
    echo "HOOK BLOCKED: $reason"
    echo ""
    echo "Received $label:"
    echo "$content" | sed 's/^/  /'
    echo ""
    echo "Rules (see .claude/hooks/git-guard.sh header):"
    echo "  - Conventional Commits subject"
    echo "  - Subject <= 80 chars"
    echo "  - English / ASCII only"
    echo "  - No bare M<digits> shorthand (use m1 lowercase as scope only)"
    echo "  - No Co-Authored-By trailer"
    if [[ "$label" == "commit message" ]]; then
      echo "  - Body <= 8 non-blank lines, <= 400 chars"
    fi
  } >&2
  exit 2
}

validate_subject_and_markers() {
  local subj=$1 text=$2 label=$3 content=$4

  # 1. Conventional Commits subject
  local conv_re='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9-]+\))?!?: .{3,}'
  if ! [[ "$subj" =~ $conv_re ]]; then
    fail "$label" "$content" "$label does not follow Conventional Commits"
  fi

  # 2. Subject ≤ 80 chars
  if [[ ${#subj} -gt 80 ]]; then
    fail "$label" "$content" "subject is ${#subj} chars (max 80)"
  fi

  # 3. ASCII-only
  if echo "$text" | LC_ALL=C grep -qP '[^\x00-\x7F]'; then
    local bad
    bad=$(echo "$text" | LC_ALL=C grep -oP '[^\x00-\x7F]' | sort -u | tr -d '\n')
    fail "$label" "$content" "$label contains non-ASCII characters ($bad)"
  fi

  # 4. No bare uppercase M<digits> shorthand in body text
  if echo "$text" | grep -qE '\bM[0-9]+\b'; then
    fail "$label" "$content" "$label uses bare M<digits> shorthand (write 'milestone N' or use lowercase scope)"
  fi

  # 5. No Co-Authored-By trailer
  if echo "$text" | grep -qiE '^[[:space:]]*Co-Authored-By:'; then
    fail "$label" "$content" "$label includes Co-Authored-By trailer (forbidden)"
  fi
}

# ─────────────────────── git-specific rules ───────────────────────

# Block direct push to main from inside Claude sessions.
# Allow remote-ref deletions and explicit refspecs to other targets.
if [[ "$command" =~ (^|[[:space:]]|\()git[[:space:]]+push ]]; then
  branch=$(git --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || echo "")
  if [[ "$branch" == "main" ]]; then
    if echo "$command" | grep -qE -- '--delete|[[:space:]]:[[:alnum:]/_.-]+'; then
      :
    elif echo "$command" | grep -qE '[[:alnum:]/_.-]+:[[:alnum:]/_.-]+'; then
      :
    else
      echo "HOOK BLOCKED: direct push to 'main' is not allowed from inside Claude." >&2
      echo "" >&2
      echo "Open a topic branch and a GitHub PR, or push from a normal shell" >&2
      echo "outside the Claude Code session if this is intentional." >&2
      exit 2
    fi
  fi
fi

# Validate commit message
if [[ "$command" =~ (^|[[:space:]]|\()git[[:space:]]+commit ]]; then
  full_msg=""

  # Heredoc form first (the -m form would otherwise capture the literal $(cat <<...) substitution).
  if echo "$command" | grep -qE "cat[[:space:]]+<<[[:space:]]*'?EOF'?"; then
    full_msg=$(echo "$command" | awk "/cat[[:space:]]+<</{flag=1; next} /^[[:space:]]*EOF[[:space:]]*\)?/{flag=0} flag" 2>/dev/null || true)
  elif [[ "$command" =~ -F[[:space:]]+([^[:space:]\"\']+) ]]; then
    msg_file="${BASH_REMATCH[1]}"
    if [[ -f "$msg_file" ]]; then
      full_msg=$(cat "$msg_file")
    fi
  elif [[ "$command" =~ -m[[:space:]]+\"([^\"]*)\" ]]; then
    full_msg="${BASH_REMATCH[1]}"
  elif [[ "$command" =~ -m[[:space:]]+\'([^\']*)\' ]]; then
    full_msg="${BASH_REMATCH[1]}"
  fi

  # No message extracted (amend / editor commit) — allow.
  if [[ -n "$full_msg" ]]; then
    subject=$(echo "$full_msg" | grep -v '^[[:space:]]*$' | head -1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    body=$(echo "$full_msg" | awk '
      BEGIN{state="subject"}
      state=="subject" && /^[[:space:]]*$/{state="body"; next}
      state=="body"{print}
    ')

    validate_subject_and_markers "$subject" "$full_msg" "commit message" "$full_msg"

    if [[ -n "$body" ]]; then
      body_lines=$(echo "$body" | awk '/./{c++} END{print c+0}')
      body_chars=$(echo -n "$body" | wc -c | tr -d ' ')
      if [[ $body_lines -gt 8 ]]; then
        fail "commit message" "$full_msg" "body is $body_lines non-blank lines (max 8)"
      fi
      if [[ $body_chars -gt 400 ]]; then
        fail "commit message" "$full_msg" "body is $body_chars chars (max 400)"
      fi
    fi
  fi
fi

# ─────────────────────── gh pr title rules ───────────────────────

# Catch `gh pr {create,edit} ... --title ...`.
if [[ "$command" =~ (^|[[:space:]])gh[[:space:]]+pr[[:space:]]+(create|edit) ]]; then
  title=""
  if [[ "$command" =~ --title[[:space:]]+\"([^\"]*)\" ]]; then
    title="${BASH_REMATCH[1]}"
  elif [[ "$command" =~ --title[[:space:]]+\'([^\']*)\' ]]; then
    title="${BASH_REMATCH[1]}"
  elif [[ "$command" =~ --title=\"([^\"]*)\" ]]; then
    title="${BASH_REMATCH[1]}"
  elif [[ "$command" =~ --title=\'([^\']*)\' ]]; then
    title="${BASH_REMATCH[1]}"
  elif [[ "$command" =~ --title=([^[:space:]\"\'][^[:space:]]*) ]]; then
    title="${BASH_REMATCH[1]}"
  fi

  if [[ -n "$title" ]]; then
    validate_subject_and_markers "$title" "$title" "PR title" "$title"
  fi
fi

exit 0
