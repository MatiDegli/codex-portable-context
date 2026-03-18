# Cross-Device Continuity Guardrails

## Purpose

This document defines the allowed scope for experimental cross-device continuity in `codex-portable-context`.

It is intentionally product-facing, not legal advice.

Its goal is to keep continuity work aligned with:

- the repo's local-first, read-only architecture
- official product guidance from OpenAI Codex and Claude Code
- the repo's provider policy guardrails

An implementation-oriented follow-up lives in [experimental-cross-device-continuity-checklist.md](./experimental-cross-device-continuity-checklist.md).

## Short Answer

Experimental cross-device continuity is acceptable only when it is built on normalized derived artifacts.

That means:

- `mirror`
- `handoff.json`
- `handoff.md`
- summaries
- reader artifacts

It does not mean:

- syncing live provider state
- syncing credentials
- cloning raw session stores
- impersonating official continuity features

## Allowed Model

The allowed continuity model is:

1. read local provider data on the source machine
2. generate derived artifacts locally
3. move only those derived artifacts across devices
4. re-enter work on the destination device through:
   - a new provider session
   - a local reader
   - a local handoff workflow

This is a `resume-like` flow, not a live session clone.

## OpenAI Codex

Current posture:

- `allowed` for experimental continuity through derived artifacts

Why:

- Codex documents local state under `~/.codex`
- Codex documents session files under `~/.codex/sessions/`
- Codex documents account auth handling, including moving `auth.json` to trusted environments, but treats it as highly sensitive

Guardrails:

- continuity should consume only derived artifacts
- do not sync `~/.codex` as live mutable state
- do not treat `auth.json` as a portability artifact
- do not assume raw session formats are a stable API

## Claude Code

Current posture:

- `allowed with caution` for experimental continuity through derived artifacts

Why:

- Claude documents fresh-session behavior plus continuity through `CLAUDE.md` and memory
- Claude documents official Remote Control for continuing a local session from another device
- Claude legal/compliance guidance explicitly restricts OAuth token use to Claude Code and Claude.ai

Guardrails:

- continuity should remain complementary to official Claude flows
- do not reimplement Remote Control semantics
- do not reuse OAuth tokens outside official Claude surfaces
- do not claim account-level or cloud-level session continuation from local-only artifacts

## Explicit Non-Goals

This continuity work must not become:

- raw-state sync
- credential sync
- write-back into provider session stores
- a provider-specific resume engine
- a replacement for official Remote Control or similar first-party continuity features

## Provider Exclusions

These guardrails do not override provider policy gating.

At the moment:

- Codex: continuity via derived artifacts is acceptable
- Claude Code: continuity via derived artifacts is acceptable with caution
- Antigravity: not an enabled live provider path; any future support must start from manual exports or another official provider-approved surface

## Source References

OpenAI Codex:

- https://developers.openai.com/codex/config-advanced
- https://developers.openai.com/codex/cli/features
- https://developers.openai.com/codex/auth
- https://developers.openai.com/codex/auth/ci-cd-auth

Claude Code:

- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/remote-control
- https://code.claude.com/docs/en/vs-code
- https://code.claude.com/docs/en/legal-and-compliance
