---
name: commit-message
description: Generate git commit messages based on git diff and user specifications. Activate when the user asks to write, generate, or format a commit message.
---

# Commit Message Skill Instructions

When generating a commit message:

1. **Check Git Status & Diff**:
   - Inspect staged changes (`git diff --cached`).
   - If no changes are staged, check unstaged changes (`git diff`) and notify the user.

2. **Read Custom Specifications**:
   - Read the user's commit message rules from `conventional_commits.md` in this skill directory (`.agents/skills/commit-message/conventional_commits.md`).
   - Apply all rules defined in `conventional_commits.md` (formatting, conventional commit types, max line length, scopes, emoji usage, casing, body formatting).

3. **Generate Commit Message**:
   - Craft a clear, descriptive commit message that strictly complies with the specifications in `conventional_commits.md`.
   - Provide the commit message in a copyable code block or offer to execute `git commit` for the user.
