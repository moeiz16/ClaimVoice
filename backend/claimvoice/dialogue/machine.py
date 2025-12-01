"""Per-call dialogue engine (to be implemented against docs/API_CONTRACT.md Part 5).

Responsibilities:
* hold the live call state (stage, slots, attempts, language, consent, recording flag, resume stage);
* for each final caller turn: redact card numbers first, call `LanguageUnderstanding.understand`, apply slot values
  and corrections, decide the stage event from the script's completion rules, apply `stages.next_stage`, then pick
  the next prompt from the script (with read-back of corrected items);
* run mid-call tools through `claimvoice.tools.base.run_tool` with their budgets;
* report every fact to the platform through `claimvoice.contracts.CallSink` (turns, slots, stages, flags, tools,
  hand-off, end). It never writes to the database itself.
"""

from __future__ import annotations
