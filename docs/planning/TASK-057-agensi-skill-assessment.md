# Task 057 - Agensi Skill Assessment

## Goal

Evaluate the unsolicited Agensi marketplace invitation and prepare a local,
reviewable integration skill only if it adds value without weakening AI
Presence Monitor's security model.

## Findings recorded on 2026-11-04

The public Agensi terms identify Agensi BV in the Netherlands and describe a
70 percent creator share, a 20 percent affiliate commission for purchases made
within six months, Stripe Connect or USDC payout onboarding, automated security
scanning and manual listing review. These public terms support several claims
in the message. The claimed monthly visitor count and the statement that a
creator keeps 90 percent on purchases of their own skill were not independently
verified as contractual guarantees and must not be used in product copy without
evidence.

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
2. Build the skill from the normative project documentation, with a minimal
   `SKILL.md` and no executable installer.
3. Validate it locally with security and secret scans.
4. Document compatibility separately for Codex, Claude Code, Cursor and other
   tested agents rather than treating the format as proof of runtime support.
5. Present the package and listing copy for human review.
6. Create an account, configure payouts or upload only after explicit approval.

