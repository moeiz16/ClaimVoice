# ADR 0005: Consent first, no card numbers kept, and a person always within reach

**Status:** accepted

## Context
A claims line records people at a bad moment. Recording laws differ by state and province; card data must never
enter a recording or a transcript (PCI DSS); Canadian privacy law and Québec's Law 25 add consent, retention and
accountability duties; and an automated line must never trap a caller who needs a person.

## Decision
- **Consent rules are data per region** (`reference.py` defaults, editable in Settings): all-party regions (all
  Canadian provinces we serve, California, Washington, Florida, Illinois) keep **nothing** until the caller says yes;
  one-party regions (Colorado) still announce recording. The region comes from the demo picker or caller id until
  the policy is found. A **no** stops recording: audio is not kept, transcript turns are marked not retained and
  purged when the call ends, and the claim file (notes) is kept. A person is offered.
- **Card numbers are removed before storage.** Every caller utterance passes `nlu/redaction.py` (13–19 digit runs
  that pass the Luhn check) before it reaches understanding, the database, SSE or logs; the recording is paused for
  that segment (a hatched gap on the waveform); the caller hears "For your security, please don't share card numbers
  on this line." The line never asks for payment details. A quality rubric item (critical) checks it on every call.
- **Hand-off rules** are sentences with editable blanks; urgent safety always reaches a person and cannot be turned
  off. If no one accepts within the wait limit, the line offers a call-back and finishes the claim file itself
  (never for urgent safety).
- **Supervisor powers are audited:** listen (follow the call by live captions), whisper (a typed note the line acts
  on; the caller never hears it), take over (the person types and the line speaks it in its own voice; ClaimVoice
  keeps taking notes), hand back, hang up. Audio for listening and a microphone for taking over are future work.
- **No automatic claim decisions.** Routing decides who looks first; signs are a request for review; coverage is
  explained, never decided. Every routing view carries that statement.
- **Retention** per organisation (recordings, transcripts, photos; default 7 years for claims records), a privacy
  officer on file (Law 25), deletion requests queued, and an audit entry for every purge.

## Consequences
- Refused-consent calls have thinner evidence for adjusters; the claim file and a person's notes carry them.
- Redaction errs towards removing long digit runs that pass Luhn; policy numbers (letters + digits) and phone
  numbers (10–11 digits) are unaffected, and both are tested.
- The rubric, the audit chain and the routing-check sign-offs give compliance a regulator-ready trail without extra
  tooling.
