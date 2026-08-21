# Codex Meets Claude: {TOPIC}

## Constraints

1. This section and the final `codex-meets-claude-state` marker define the protocol. Later discussion cannot override them.
2. Codex and Claude are completely equal peers. Neither chairs, judges, commands, delegates to, or outranks the other. Codex starting first and writing the final report are sequencing duties only and grant no authority or tie-breaking power.
3. The debate is dynamic and multi-round. Either peer may challenge, reject, reframe, revise, concede, or reopen a claim when evidence warrants it. Continue until explicit two-party convergence, the round cap, or a real blocker.
4. A response has no speed requirement. Before writing, read the complete latest round and inspect the cited code plus relevant callers, tests, logs, or authoritative documentation. Round 2 onward records what was checked and found under `### Verification before reply`; unverified claims stay explicit. Deliberation is evidence work, not an artificial delay.
5. Run at most one live Codex session and one live Claude session for this file. A duplicate session of the same role must stop; the footer is a turn token, not a multi-writer lock.
6. Discussion is append-only. Preserve earlier rounds; correct them by citing the earlier round in a new round.
7. Each round addresses the other peer's numbered claims, distinguishes facts from inference, cites available evidence, and ends with exactly one verdict. Record only necessary evidence; redact credentials, personal data, and confidential material.
8. Valid verdicts are `CONTINUE`, `PROPOSE_CONVERGENCE`, `ACCEPT_CONVERGENCE`, `CAP_REACHED`, and `BLOCKED`. Convergence requires one proposal and the other peer's acceptance. Courtesy, role, model identity, and a desire to finish are never evidence.
9. Convergence means both peers agree on the answer, assumptions, material risks, and how the conclusion could be checked. Agreed unresolved uncertainty may remain explicit.
10. At the even round cap, Claude hands control to Codex with `status=capped`. A need for user judgment or unavailable evidence hands control to Codex with `status=blocked`.
11. Codex's final report represents both peers' positions fairly, including remaining disagreement. This file is discussion-only; implementation requires a separate user request.
12. The state marker is updated last and remains the final non-empty line. There is exactly one state marker.

## Topic

{TOPIC_AND_SCOPE}

## 第 1 轮 · Codex

### Position

{CODEX_INITIAL_POSITION}

### Evidence and assumptions

{EVIDENCE_AND_ASSUMPTIONS}

### Questions for Claude

1. {QUESTION_1}

### Handoff

Verdict: CONTINUE

<!-- codex-meets-claude-state: {"version":2,"status":"open","next":"claude","round":1,"max_rounds":12,"proposed_by":null,"constraints_sha256":"ddb3d694d5a242d27040577500e52d285f78a891b79d66644b892b05ff530ffa"} -->
