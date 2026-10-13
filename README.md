# Frisbii agent toolkit

Skills and tools that help coding agents (Claude Code, Cursor, Codex and
others) build correct integrations with **Frisbii Billing** and **Frisbii Pay**
(the platform formerly known as Reepay).

| Skill | Use it for |
|---|---|
| `frisbii-best-practices` | Start here: product routing, auth, test vs live, handles, idempotency, errors |
| `frisbii-checkout` | Checkout sessions, embedded/modal/window, payment methods by market, SCA, settle/refund |
| `frisbii-subscriptions` | Plans, subscriptions, changes and proration, usage-based billing, discounts, dunning, Customer Portal |
| `frisbii-webhooks` | Signature verification (6 languages), delivery rules, event catalogue |
| `frisbii-migrate-from-stripe` | Object/event mapping, card export, SEPA/PayPal imports, parallel run |
| `frisbii-go-live-review` | Pre-production checklist and code scanner |

The plugin also connects the **Frisbii MCP server** (`https://mcp.frisbii.com/mcp`,
OAuth sign-in on first use). The skills work without it; with it, the agent can
inspect and set up data in the developer's (test) account while coding.

## Install

**Claude Code**

```text
/plugin marketplace add frisbii-com/frisbii-agent-toolkit
/plugin install frisbii@frisbii-agent-toolkit
```

**Cursor, Codex and other agents** (via the `skills` CLI)

```bash
npx skills add frisbii-com/frisbii-agent-toolkit --skill frisbii-best-practices   # or omit --skill to choose
```

Other agents get the skills only; add the MCP server separately with that
agent's own MCP configuration (`https://mcp.frisbii.com/mcp`, streamable HTTP).

## Design principles

- **Opinionated, not encyclopaedic.** Skills route the agent to the right
  product and encode the defaults and mistakes our integration engineers see.
  The API reference at <https://docs.frisbii.com/> (agent index:
  <https://docs.frisbii.com/llms.txt>) stays the source of truth.
- **Verified.** API facts are checked against docs.frisbii.com. Anything not
  yet verified is marked `VERIFY` (`grep -rn VERIFY plugins`).
- **No dependencies.** Scripts are Python 3.9+ standard library; webhook
  verifiers are provided for Python, Node.js, PHP, Java, C# and Go.

## Repository layout

```
.claude-plugin/marketplace.json        Claude Code marketplace
plugins/frisbii/                       the plugin
  .mcp.json                            Frisbii MCP server
  skills/<skill>/SKILL.md (+ references/, scripts/)
tests/                                 webhook verifier tests
tools/validate.py                      manifest + frontmatter checks
tools/build_skills_index.py            builds a .well-known/skills bundle (not hosted yet)
```

## Development

```bash
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/build_skills_index.py --out dist   # builds the .well-known/skills bundle (CI checks it builds)
```

## Not yet included

- **Install from docs.frisbii.com.** `build_skills_index.py` builds the bundle
  for `npx skills add https://docs.frisbii.com`, but the docs site runs on
  ReadMe, which cannot serve files under `/.well-known/`. Hosting it needs a
  Cloudflare route for `/.well-known/skills/*` to a static copy of `dist/`.
  Until then, install from GitHub as above.
