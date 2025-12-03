# ADR 0003: An explicit state machine owns the conversation; language understanding only fills values

**Status:** accepted

## Context
A first-notice-of-loss call has obligations in a fixed order: consent before anything is kept, identity before
personal details, a safety question early, a read-back before the claim number. Regulators and quality reviewers
need to see that every call followed the script. Callers interrupt, correct themselves, switch language and ask
off-script questions. A free-running language model is good at understanding the words and bad at guaranteeing
order, so it cannot be in charge.

## Decision
- **Stages and events are code** (`dialogue/stages.py`): ten scripted stages (greeting, consent, identity, safety,
  loss type, loss details, photos, coverage, read-back, wrap-up) plus hand-off and ended, a transition table, and
  global events (urgent safety, a request for a person, low confidence, distress, a failed lookup, take-over, hang-up,
  silence) valid in every stage. People see the ten stages as seven steps (Consent · Policy · Safety · What happened ·
  Photos · Coverage · Read-back).
- **Safety right after identity.** "Is everyone safe?" is asked as soon as the caller is identified, and urgent
  safety is watched on every turn, before consent too.
- **Language understanding works inside a stage**: given the stage, the expected values and the utterance (already
  cleared of card numbers), it returns an intent, values with character spans, and safety/distress signals. It never
  returns a next stage. The fake is pattern-based (EN/FR); the cloud adapter uses a JSON schema and a 600 ms timeout.
- **Every spoken line comes from the script or a fixed template.** Scripts are versioned per loss type and edited in
  Settings; a live call keeps the version it started with. A supervisor's whisper can add one question to the
  current stage; it is never spoken as the supervisor's words.
- **Corrections** supersede earlier values and keep their history and spans; the read-back re-reads only what
  changed.
- **Every fact leaves the engine through `CallSink`**, in order, with the turn and span it came from.

## Consequences
- The stage table is unit-tested (hand-off reachable from every stage, in-stage events never move the call, hand-back
  resumes the interrupted stage) and the call-quality rubric can check order mechanically.
- Some natural conversations feel slightly more structured than a human would make them; the off-script handler and
  the "I'll note that" path keep it polite.
- Changing the order of the script is a code change reviewed with this ADR, not a prompt edit.
