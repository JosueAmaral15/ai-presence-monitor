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
in the message. The terms also state that creators acting as affiliates receive
the affiliate commission on their own skills in addition to the 70 percent
creator share, which supports the message's 90 percent calculation under the
current terms. The claimed monthly visitor count was not independently verified
and must not be used in product copy without evidence. Commission rates and
periods remain changeable under the platform terms.

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

## Local package candidate

The reviewable source lives at
`marketplace/agensi/ai-presence-monitor/`. It contains only a `SKILL.md` and a
focused operations reference. It intentionally contains no installer, runtime,
secret, environment-variable reader, network client or executable payload.

Official references used for this assessment:

- <https://www.agensi.io/docs/packaging>
- <https://www.agensi.io/docs/review-and-approval>
- <https://www.agensi.io/terms>
