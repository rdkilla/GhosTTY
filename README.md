# GhosTTY

## Problem Statement
GhosTTY is intended to make terminal session sharing and replay simple for teams that need to explain, debug, or demonstrate command-line workflows without requiring everyone to be live in the same shell at the same time. It solves the common problem of “it works on my terminal” by capturing reproducible command interactions, preserving context, and enabling asynchronous review so teammates can understand what happened, why it happened, and how to repeat it.

## MVP Features
- **Session capture:** Record a terminal session (commands, output, and timestamps) into a portable artifact.
- **Deterministic replay:** Re-run or play back a captured session in order, with clear step boundaries.
- **Sharable session bundle:** Export/import a single bundle format that can be attached to issues or sent to teammates.
- **Basic redaction controls:** Mask obvious sensitive values (e.g., tokens/password-like patterns) before sharing.
- **CLI-first workflow:** Provide a small command set for capture, replay, and inspect operations from the shell.

## Non-Goals for v1
- Real-time collaborative multi-user terminals.
- Full TTY emulation parity across every shell/platform edge case.
- Enterprise-grade access control, SSO, and advanced audit policy features.
- Rich web UI editing/annotation beyond basic CLI inspection.

## Definition of Done (v1)
- [ ] A documented launch command works from a clean checkout.
- [ ] One end-to-end demo workflow is documented and reproducible (capture → share/import → replay).
- [ ] Core MVP commands return predictable exit codes and user-facing help text.
- [ ] Sensitive-value redaction is applied in at least baseline cases and covered by tests.
- [ ] Basic automated tests pass in CI for the supported runtime/platform matrix.
- [ ] A sample session bundle is included for manual verification.

## Basic Architecture Sketch
### Components
1. **CLI Frontend**
   - Parses commands/flags and dispatches to application services.
2. **Capture Engine**
   - Hooks into PTY/session execution, streams command/output events, and emits normalized records.
3. **Session Store**
   - Serializes/deserializes session bundles (metadata + event stream + optional assets).
4. **Replay Engine**
   - Reconstructs session flow for playback or deterministic re-execution modes.
5. **Redaction Layer**
   - Applies configurable masking rules before persistence/export.

### Interfaces
- **CLI ↔ Application Services:** Typed command/request objects and structured result objects with exit codes.
- **Capture/Replay ↔ Session Store:** Versioned bundle schema (read/write contract) to ensure compatibility.
- **Capture/Replay ↔ Redaction:** Event-level filter interface (`apply(event) -> redacted_event`) used pre-save and pre-display.
- **Session Store ↔ External Users:** File-based import/export API for sharing bundles across environments.

### Data Flow (MVP)
1. User runs `ghostty capture ...` from CLI.
2. Capture Engine records terminal events and passes them through Redaction Layer.
3. Session Store writes a versioned bundle.
4. Teammate imports bundle and runs `ghostty replay ...`.
5. Replay Engine reads bundle from Session Store and renders ordered output.
