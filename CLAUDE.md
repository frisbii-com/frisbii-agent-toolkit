# CLAUDE.md — frisbii-agent-toolkit

Guidance for Claude Code working in this repository. See [README.md](README.md)
for what the toolkit is, how it is installed and the repository layout.

## Checks

```bash
python3 tools/validate.py
python3 -m pytest -q tests
```

## Keep the Confluence skills library in sync

Every skill has a page in the **Skills Central** Confluence space (key `SKILL`,
site `https://billwerk.atlassian.net`, cloud ID
`102181e0-b1c2-4d5f-9ec7-e5e7feaa3ed8`). Whenever a change adds, removes,
renames or changes a skill — its `SKILL.md`, `references/`, `scripts/`, or the
install instructions and plugin version — update the matching page in the
same piece of work:

- **Changed skill:** update the page sections the change affects (one-line
  summary, What it does, When the agent uses it, Example use cases, What's
  included, Notes and limitations). Bump **Status** to the plugin version in
  `plugins/frisbii/.claude-plugin/plugin.json` when it changes.
- **New skill:** create a child page of the parent page, following the
  template page, and add the skill to the parent page's skills table.
- **Renamed or removed skill:** rename the page or mark it **Retired**
  (do not delete it), and update the parent page's table.
- **Owner** is Martyn Arbon unless told otherwise.
- Read the page first and edit only what changed. Set a version message that
  names the change (and the PR, when there is one).
- Mention the Confluence updates in the PR description.

| Page | ID |
|---|---|
| Skill page template | 11604262921 |
| Frisbii Agent Toolkit (parent) | 11604099086 |
| frisbii-best-practices | 11603705858 |
| frisbii-checkout | 11604328460 |
| frisbii-subscriptions | 11604557825 |
| frisbii-webhooks | 11604262942 |
| frisbii-migrate-from-stripe | 11603902474 |
| frisbii-go-live-review | 11603836935 |

Page URL: `https://billwerk.atlassian.net/wiki/spaces/SKILL/pages/<id>`. Add
the ID of any new page to this table.

If Confluence is not reachable from the session, finish the code change and
say clearly which pages still need updating and what to change.
