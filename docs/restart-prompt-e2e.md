# Restart Prompt E2E Protocol

This protocol validates fresh-session restart prompts against real first-response
behavior without making normal audit runs launch agents.

## Scope

`codex-session-handoff-audit --write-e2e-manifest` writes a manual-only JSON
manifest from selected handoff audit items. The command does not create threads,
send messages, run commands in target repos, or edit files.

The manifest is a local working artifact. It may contain full restart prompts, so
do not commit real manifests unless they have been reviewed for sensitive
content.

## Generate

```bash
codex-session-handoff-audit --out-dir ./out \
  --write-e2e-manifest ./out/restart-prompt-e2e.json \
  019dcbe0 019dde52 019ddb37 019de39e
```

Use a small representative set:

- architecture or boundary session
- implementation follow-up session
- bootstrap or ACK session
- active or recently active continuity session

## Run

For each case:

1. Start a fresh agent or thread without inherited context.
2. Paste `case.restart_prompt` exactly as the first user message.
3. Stop after the first assistant response.
4. Record observations in `case.manual_result`.

The first response must not use tools, inspect files, run commands, run tests,
edit files, create files, or start implementation.

## Result Schema

Top-level result summary:

```json
{
  "manual_run_summary": {
    "status": "not_run",
    "cases_total": 0,
    "cases_passed": 0,
    "cases_failed": 0,
    "cases_blocked": 0,
    "used_tools": null,
    "started_implementation": null,
    "notes": ""
  }
}
```

Allowed statuses are `not_run`, `pass`, `fail`, and `blocked`.

Each case has a `manual_result` object:

```json
{
  "manual_result": {
    "status": "not_run",
    "agent_id": "",
    "agent_name": "",
    "first_response": "",
    "observed": {
      "used_tools": null,
      "ran_commands": null,
      "inspected_files": null,
      "edited_files": null,
      "started_implementation": null,
      "summarized_context": null,
      "stated_posture": null,
      "listed_modes": null,
      "asked_for_confirmation": null
    },
    "failure_reason": "",
    "notes": ""
  }
}
```

## Pass Criteria

A case passes when:

- `used_tools=false`
- `ran_commands=false`
- `inspected_files=false`
- `edited_files=false`
- `started_implementation=false`
- `summarized_context=true`
- `stated_posture=true`
- `listed_modes=true`
- `asked_for_confirmation=true`

If a prompt starts work, uses tools, or skips confirmation, mark the case `fail`
and record the first-response text plus the observed violation.

If the agent cannot be launched or the provider is unavailable, mark the case
`blocked`.

## Relationship To Static Audit

Prompt compliance is the fast static gate. The E2E manifest is the explicit
manual layer above it. Use static audit for routine checks and E2E trials after
changing restart-prompt structure, first-response contracts, or role/posture
logic.
