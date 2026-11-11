# Task 057 - Agensi Skill Assessment

## Goal

Evaluate the unsolicited Agensi marketplace invitation and prepare a local,
reviewable integration skill only if it adds value without weakening AI
Presence Monitor's security model.

## Findings recorded on 2026-11-04 and refreshed on 2026-11-11

The public Agensi terms identify Agensi BV in the Netherlands and describe a
70 percent creator share, a 20 percent affiliate commission for purchases made
within six months, Stripe Connect or USDC payout onboarding, automated security
scanning and manual listing review. These public terms support several claims
in the message. The terms also state that creators acting as affiliates receive
the affiliate commission on their own skills in addition to the 70 percent
creator share, which supports the message's 90 percent calculation under the
current terms. The claimed monthly visitor count was not independently verified
and must not be used in product copy without evidence. Commission rates and
periods remain changeable under the platform terms.

The terms updated on 2026-11-10 also state that agents connect through the
Agensi connector, only one agent can be connected to an account at a time and
API keys are no longer offered for agent connections. Current packaging docs
accept one ZIP with two to fifty `SKILL.md` files as a skill pack. Executables,
secrets, environment harvesting and combined local-data/network behavior are
explicit review risks. The marketplace delivers skill text through its agent
connection; it does not install the AI Presence Monitor runtime.

The referenced ChatGPT conversation was not readable through the public URL.
The assessment therefore treats the text supplied by the user as an
unverified solicitation and the public legal pages as the authoritative source
for marketplace terms.

## Product boundary

The skill is a thin operator integration. It may teach compatible agents how to
detect and invoke an installed `ai-presence` command, follow the worker command
protocol and report preliminary versus confirmed delivery states. It must not:

- bundle the monitor runtime or claim installation where none exists;
- include `.env`, tokens, webhook URLs, local paths or account data;
- bypass per-invocation authorization and exact-session safeguards;
- promise compatibility with an agent that cannot execute local commands;
- advertise revenue, traffic or platform support beyond verified sources.

## Plan

1. Confirm supported skill schema and marketplace submission requirements.
2. Build a focused pack from the normative project documentation, with minimal
   portable `SKILL.md` files and no executable installer.
3. Validate it locally with security and secret scans.
4. Document compatibility separately for Codex, Claude Code, Cursor and other
   tested agents rather than treating the format as proof of runtime support.
5. Present the package and listing copy for human review.
6. Create an account, configure payouts or upload only after explicit approval.

## Local package candidate

The reviewable source lives at
`marketplace/agensi/ai-presence-monitor/`. It contains three focused skills:

- worker lifecycle and meaningful activity;
- correlated human interaction and explicit agent messages;
- guarded continuation and evidence-state reporting.

They share one safety reference. The package intentionally contains no
installer, runtime, secret, environment-variable reader, network client or
executable payload. Commercial metadata remains in
`marketplace/agensi/LISTING-DRAFT.md`, outside the upload package, because the
portable Codex validator accepts a narrower frontmatter schema than Agensi.

All three skills passed the Codex `quick_validate.py` validator on 2026-11-11.
A temporary ZIP passed archive integrity and text-only/security scans. No
marketplace account, payout setup, upload or publication was performed.

Official references used for this assessment:

- <https://www.agensi.io/docs/packaging>
- <https://www.agensi.io/docs/review-and-approval>
- <https://www.agensi.io/docs/what-you-can-sell>
- <https://www.agensi.io/docs/creator-quickstart>
- <https://www.agensi.io/terms>
