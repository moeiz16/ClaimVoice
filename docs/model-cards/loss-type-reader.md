# Loss-type reader fact sheet

*What kind of loss is the caller describing, if any?* Part of the offline reader (`LLM_FAKE=true`, the default).

## What it is for

- Reads a caller turn, in English or Canadian French, while the line still doesn't know what happened (the opening
  statement, the identity and safety answers, the "tell me what happened" question) and names one of seven labels:
  collision, hail, wind, water, fire, theft, or *not a description* (a yes, a date, a policy number, a question).
- Only when the rules heard no loss type. The rules answer first; this covers the open wording they miss ("a pickup
  clipped my car", "water dripping through my ceiling", "the storm ripped shingles off").
- It proposes a value inside the current stage. The state machine still decides every step.

## What it is not for

- Choosing what the line says or does next, or ending a call. It never sees the stage machine.
- Reading anything other than the loss type. Dates, places, parts, injuries and the rest come from the rules and
  their word lists (`nlu/extract.py`, `nlu/lexicon.py`), each with the words it was heard in.
- Judging the caller. It reads words only: no voice, accent, speech rate or pitch.

## How it decides

| Confidence (after temperature scaling) | What the line does |
|---|---|
| 0.84 or more | Keeps the loss type, pointing at the word that decided it |
| 0.30 to 0.84 | Asks "Just so I have it right: is this about water damage?"; only a yes keeps it |
| Below 0.30, or *not a description* | Adds nothing; the line asks what happened, then which kind of loss it was |

A "no" to the confirmation is a question answered, not a miss: the line asks which kind of loss it was. Only two
turns in a row the line can't place bring in a person, as before.

## What it is

- Features: word unigrams and bigrams and character 3- to 5-grams inside word boundaries (16,902 kept), TF-IDF with
  sublinear term frequency. Character pieces carry spelling slips, inflections and French/English cognates.
- Model: multinomial logistic regression (C = 4, balanced class weights), one softmax temperature (0.75).
- Artifact: `backend/claimvoice/nlu/artifacts/loss_type_v1.json.gz`, 332 KB, plain JSON (no pickle). Inference is
  plain Python over that file, checked against the scikit-learn pipeline it was exported from by a unit test.
- Speed: 0.06 ms per turn at the median and 0.22 ms at p95 for the classifier; about 1 ms p95 for the whole offline
  reader on every caller turn of every set (`make eval`, gate 5 ms).

## What it learned from

- 12,540 generated sentences from a seeded lexicon-and-template generator (docs/NLU_CORPUS.md), 1,100 per loss type
  in English and 550 in French, plus 1.6 times that for *not a description*.
- 290 turns of the 38 main scripted callers, labelled from where the engine placed them.
- Never the held-out caller sets; a test checks that none of their sentences is in the corpus.
- `make train-nlu` rebuilds everything in about five seconds; the same seed gives the same bytes.

## How it was tested

On 6,211 out-of-lexicon validation sentences, built only from word-list entries the training sentences never use:

| Measure | Value |
|---|---:|
| Accuracy (all seven labels) | 0.848 |
| Macro F1 | 0.857 |
| Accuracy, English / French | 0.846 / 0.853 |
| Expected calibration error, before / after temperature | 0.051 / 0.019 |
| Descriptions kept outright (at 0.84) | 57 % |
| Wrong when kept outright | 1.9 % (target at most 2 %) |
| Right when confirmed (0.30 to 0.84) | 80 % |
| *Not a description* read as a loss | 0 % |

These sentences are harsher than real calls on purpose (a held-back entry may be the only way a list names the loss),
so they set the thresholds, not the forecast.

On the scripted callers, through the whole engine (the reader with the classifier and the widened word lists, against
the rules the line shipped with):

| Caller set | Completed, before → now | Values right, before → now | Wrong values, before → now |
|---|---:|---:|---:|
| Main, 38 callers (tuned on) | 38 → 38 | 126/126 → 126/126 | 0 → 0 |
| Held out 1, 8 callers (used once to widen the rules) | 8 → 8 | 20/20 → 20/20 | 0 → 0 |
| Held out 2, 8 callers (used for development) | 1 → 8 | 0/22 → 22/22 | 0 → 0 |
| Held out 3, 12 callers (untouched, scored once) | 1 → 8 | 24/62 → 50/62 | 2 (3.2 %) → 1 (1.6 %) |

The widened word lists alone, without the classifier, take held out 3 to 2 of 12 and 30 of 62: most of the gain
comes from reading the opening statement.

## Limits

- **Small, scripted test sets.** Twelve untouched callers and 62 values; one call moves completion by 8 points. The
  scripted callers can't answer a question they weren't written for, so a confirmation the line asks costs them a
  turn that a real caller would simply answer.
- **The same team wrote the third set and the word lists.** The set was committed first and scored once, and list
  entries that would only echo its wording were left out, but some shared habits of phrasing are likely.
- **Held out 2 is no longer unseen.** Its misses shaped the lists; it shows the fixes hold.
- **Synthetic training text.** The generator's sentences are tidier than speech-to-text output; disfluent,
  run-on or code-switched turns are where it is weakest. The cloud reader (`LLM_FAKE=false`) remains the intended
  answer to fully open wording; this is the offline floor.
- **One label per call.** A storm that brings both wind and hail is filed under whichever the caller describes first.
