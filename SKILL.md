---
name: codex-meets-claude
description: Use when the user explicitly asks to start or join a resumable, evidence-based technical workshop between Codex and Claude through one shared Markdown file.
---

# Codex Meets Claude

Use one append-only Markdown document as the interface. The document's constraint section and final state marker are authoritative. Only the role named by `next` may append a round.

## Core rules

Codex and Claude are equal peers. Starting first and writing the final report are Codex's sequencing duties, not authority: neither role chairs, judges, delegates to, or outranks the other. Either may challenge, reject, reframe, revise, or reopen a point based on evidence.

The debate is dynamic and multi-round. Continue until both peers explicitly converge, reach the round cap, or identify a real blocker. Agreement must follow independent verification, never politeness or a desire to finish.

There is no immediate-response requirement. Before every response, read the complete latest round, inspect the cited code plus relevant callers, tests, logs, or documentation, and decide which claims the evidence supports. Record this under `### Verification before reply`; identify unverified claims explicitly. Deliberation means evidence work, not an artificial sleep.

## Start from Codex

Claude cannot start a debate. If the current agent is Claude and no existing debate file was supplied, tell the user to invoke this skill from Codex first.

When Codex receives a new topic:

1. Put the document under `<git-root>/.agent-debates/`; outside Git, use `<cwd>/.agent-debates/`. Use a timestamped descriptive filename.
2. Run `python3 <skill-dir>/scripts/debate_protocol.py init <file> --first codex --max-rounds 12`, then replace every placeholder while keeping the constraints intact. Write `第 1 轮 · Codex` with Codex's framing, evidence, numbered questions, and `Verdict: CONTINUE`.
3. Set the footer to `status=open`, `next=claude`, `round=1`. Default `max_rounds` to 12; honor an explicit even limit of at least 4.
4. Run `python3 <skill-dir>/scripts/debate_protocol.py validate <file>`.
5. Send the absolute file path immediately as a progress update so the user can open Claude there. This update does not complete the host turn and must not be a final response.
6. In the same host turn, immediately start the foreground wait with `python3 <skill-dir>/scripts/debate_protocol.py wait <file> --role codex --after 1`. Keep the tool call attached and use a 30-minute timeout unless the user specified another limit. If the host cannot keep that wait alive, report the limitation and stop.

## Join from Claude

Claude requires the existing file path. Read the complete file, validate it, and obey its `next` field. If it is not Claude's turn, wait instead of writing. Otherwise append the next numbered round, update the footer last, validate, then wait for Codex using the new round number as `--after`.

## Continue

After `wait` returns:

1. Re-read and validate the complete document; the wait result is only a wake-up signal.
2. Investigate before drafting. Record inspected code, commands, and findings under `### Verification before reply`, then address the other peer's numbered claims and questions. Append one round; preserve all earlier rounds byte-for-byte.
3. Update the single footer last, then validate.
4. If discussion remains open, start the next foreground wait in the same host turn. Keep the tool call attached; progress notices and heartbeats never end the turn.

On timeout or interruption, terminate any waiter started by this session, then report the file path and current `next` role. A later invocation resumes from the footer; do not invent a new debate.

If the skill itself fails or any required template, validator, or polling step is broken, tell the user immediately and stop. Do not repair, bypass, or improvise around it; the user will handle the repair.

## Convergence and completion

Use the verdicts defined in the document. Convergence requires a two-party handshake:

- A proposer writes `PROPOSE_CONVERGENCE`; the other role writes `ACCEPT_CONVERGENCE` or `CONTINUE`.
- Claude's acceptance sets `status=converged,next=codex`. Codex then appends `Final Summary` and closes.
- Codex may accept Claude's proposal and append `Final Summary` in the same turn.
- At the even round cap, Claude sets `status=capped,next=codex`. Missing evidence or required human judgment sets `status=blocked,next=codex`.

Codex is responsible for final reporting without gaining decision authority. It represents both peers' positions fairly, appends a final summary covering outcome, consensus, remaining disputes, assumptions, evidence, and recommended next action; then sets `status=closed,next=null`, validates, and reports the result to the user. A closed debate never edits project code automatically.

## Write discipline

- Discussion is append-only after the constraint section. Correct earlier claims in a new round.
- Run one live session per role per file; the footer cannot arbitrate two Codex or two Claude writers.
- Treat the footer as a turn token, not merely metadata. Update it only after the round is complete.
- Keep exactly one footer at the final non-empty line.
- Inspect project material read-only. Implementation requires a separate user request after the debate.
- The document is the durable record; chat messages are progress notices, not protocol state.
