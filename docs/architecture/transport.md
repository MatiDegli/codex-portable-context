# Transport

## Transport Philosophy

Transport is optional and external to the core project.

The core tool creates a derived mirror under `out/` or `out-redacted/`. Moving that mirror between devices is a separate step you control. This repo does not automate background sync and does not treat transport as part of the core mirror logic.

Recommended transport unit:

- the derived mirror only

Because the mirror now includes a root `README.md`, a copied or synced mirror has a natural entrypoint for browsing on the destination device.

Not recommended as transport:

- raw `~/.codex`
- `~/.codex/auth.json`
- `~/.codex/config.toml`
- `~/.codex/state_*.sqlite`
- `~/.codex/logs_*.sqlite`
- `~/.codex/tmp/`
- `~/.codex/shell_snapshots/`

The derived mirror is safer to move because it is read-only exporter output, but it may still contain sensitive content unless you intentionally generate a redacted export.

## Syncthing

### Recommended Folder Choice

Sync only one of these:

- `out/`
- `out-redacted/`

If you expect the mirror to move more broadly, prefer `out-redacted/`.

### Recommended Topology

Best default for laptop and desktop:

- one machine generates the mirror
- that machine shares the derived mirror folder
- the receiving machine uses it as a read-oriented context copy

Recommended folder types:

- `send-only` on the machine that generates the mirror
- `receive-only` on the machine that mainly consumes it

This keeps ownership clear and lowers conflict risk.

### When To Use Each Folder Type

Use `send-only` plus `receive-only` when:

- one machine is the clear producer
- the other machine mainly reads the mirror
- you want the safest practical setup

Use `send-receive` only when:

- you understand that both devices may touch the same derived paths
- you are effectively serializing writes
- or you are not regenerating the same mirror folder concurrently on both devices

In practice, if both devices generate mirrors, separate folders are usually safer than one shared send-receive folder.

### Conflict Caution

The mirror is easier to transport than raw Codex state, but it is still mutable export output. If two devices independently regenerate the same shared mirror folder, conflicts are possible.

Practical recommendation:

- prefer one writer per shared mirror folder
- if both devices export mirrors, keep those mirrors in separate folders
- sync a read-oriented copy rather than a collaboratively updated folder

### `.stignore` Strategy

Often you do not need `.stignore` at all if you sync only `out/` or only `out-redacted/`.

If you do want a local Syncthing ignore rule, keep it simple and device-specific. For example, a receiving machine that only needs readable artifacts may choose to ignore the local incremental bookkeeping file:

```text
.codex-session-mirror-state.jsonl
```

Important:

- `.stignore` is local Syncthing behavior on each device
- it is not part of the core mirror format
- different devices may intentionally have different ignore rules

Use it carefully. Local ignore rules can make one device's view of the mirror differ from another.

## rsync

`rsync` is often the simplest transport option when you want strict directional control.

Good fit for:

- copying to an external disk
- pushing a mirror to another machine you control
- manual or scheduled sync outside the core project

### External Disk Example

```bash
rsync -av --delete ~/Projects/codex-sync/out/ /run/media/$USER/PortableSSD/codex-portable-context/out/
```

### Redacted Export Example

```bash
rsync -av --delete ~/Projects/codex-sync/out-redacted/ /run/media/$USER/PortableSSD/codex-portable-context/out-redacted/
```

### Local Network Example

```bash
rsync -av --delete ~/Projects/codex-sync/out/ desktop.local:/home/matidegli/codex-portable-context-mirror/out/
```

If you want a tiny wrapper around this pattern, the repo includes:

```bash
./scripts/transport/rsync-derived-mirror DESTINATION
```

This helper is optional. It is only a thin convenience wrapper around one-way `rsync`.

You can point it at a redacted mirror with:

```bash
./scripts/transport/rsync-derived-mirror --out-dir ./out-redacted DESTINATION
```

`rsync` is a good default when you want:

- one-way movement
- predictable overwrite behavior
- no always-on sync service

## Safe Usage Notes

Prefer redacted exports when:

- the mirror will leave your primary machine
- the destination device is less trusted
- the mirror may be shared more broadly than your personal workstation

Do not transport a mirror casually when:

- it contains project names, paths, prompts, or tool outputs you would not want copied elsewhere
- you need hard privacy guarantees rather than best-effort reduction of obvious sensitive details
- you have not reviewed whether a non-redacted mirror is appropriate

Redaction helps, but it is not a guaranteed DLP or privacy system.

Treat portable mirror output as useful but potentially sensitive developer context.
