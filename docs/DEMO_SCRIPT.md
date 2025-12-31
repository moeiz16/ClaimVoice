# Demo script: three minutes on the line

A walkthrough for showing ClaimVoice to a claims leader, an engineering manager or a reviewer. It follows one
morning at Larkspur Mutual: **Thursday 8 January 2026, 7:42 a.m. Calgary time**, after an overnight Chinook
windstorm. Everything on screen is sample data.

## Before you start

```bash
make setup     # once
make reset     # fresh seed: 79 calls, 63 claims, 3 live lines, 2 callers waiting for a person
make dev       # API on :8040, web app on :3040
```

Open http://localhost:3040 in Chrome with the sound on. Use a second tab for the app so the landing page stays
ready. If you plan to ring the demo line, allow the microphone once beforehand, or use **Type instead**.

## The script

| Time | Where | Do | Say |
|---|---|---|---|
| 0:00 | Landing `/` | Press play on the waveform. Let it run to the policy number, then drag the playhead to the card-number moment | "This is a real claim call shape: 2:14 a.m., a skylight smashed by debris in a windstorm. Watch the values leave the words and land in the claim file, each with the second it was said." |
| 0:20 | Landing | Pause on the hatched gap | "The caller starts reading a card number. The digits are removed before anything is stored and the recording is silenced for that moment. The line never takes payment details." |
| 0:30 | Landing | Jump to the end | "Read-back, claim number, and the route: fast-track, with three reasons in plain words. Nothing here denies a claim." |
| 0:40 | Sign-in `/sign-in` | Use the demo sign-in as **Claims supervisor** (Renée Kowalchuk) | "Six roles. I'm the supervisor running the line desk." |
| 0:45 | Lines `/lines` | Point at the amber ribbon, then the strips, then the tray | "A Chinook surge: calls are 3.4 times usual since 6 a.m. Three callers are on the line with ClaimVoice, each at a step of the seven-step script. Two are waiting for a person, and the urgent one is first: Hal smells gas in Airdrie. The line already told him to get out and call 911." |
| 1:05 | Line 1, Gord Lindqvist | Press **Listen**, then **Whisper**: "Ask if the garage skylight is damaged too" | "I can follow the call by live captions, whisper a note the caller never hears, or take the call. The whisper becomes one question in ClaimVoice's own words. The script, not a language model, decides what happens next." |
| 1:30 | Claims `/claims` → **CV-26-01856** (Tomás Reyes, Denver) | Press play on the recording band; click a source chip in **In short** | "The adjuster's view. Every fact links to the moment it was said. Two speaker lanes, and the card-number gap is hatched." |
| 1:50 | Same claim, **Where it goes** | Point at the route tags, the likely size and the signs | "The routing checks run at hang-up. XGBoost, calibrated, with reasons from SHAP turned into sentences. This one asked for a closer look: 3 of the 14 signs it checks, including a policy that started 19 days before the loss. Lena, the adjuster, moved it to Adjuster with a reason, and the referral stays open for the investigator. Both are in the audit log." |
| 2:10 | Quality `/quality` | Open a call flagged **Right hand-off** (the labelled set includes a gas call where a person came 40 seconds late) | "Every call is scored against a rubric: consent first, identity, required details, kind words, no card numbers, the right hand-off. Twelve calls are waiting for review. This one opens at the moment that failed." |
| 2:30 | Routing checks `/routing` | Scroll the four questions; stop on fairness and sign-off | "For compliance, the checks answer a regulator's four questions: how often it's right, whether it's fair by region, language and age band, which are never inputs, whether this week looks like the training data, and who signed this version. Two different people must sign." |
| 2:50 | Activity `/activity` | Point at **Record intact** | "Every sensitive action is in a hash-chained log, and one click checks nothing was changed. That's the call from 2 a.m. to the regulator's file." |

## If you have another minute

- **Ring the demo line** (`/call`, or **Appeler en français**): say "Someone backed into my car" and answer the
  questions. The line asks for recording consent first. Read out a test card number such as 4111 1111 1111 1111
  to see the line stop you. This uses the browser's own speech recognition and voices; nothing is kept after the
  page closes.
- **Take over** on Line 2 (Kiara Booker): type what to say and the line speaks it in its own voice, while ClaimVoice
  stops asking questions and keeps taking notes.
- **French:** open Line 3 (Martine Gagnon, Montréal). The French stays primary, with an English line under each turn
  for staff.
- **Night line:** the theme toggle in the account menu.

## Questions people ask

- **"Does the AI decide the claim?"** No. Routing decides who looks at a claim first. A closer-look referral is a
  request for review. No endpoint approves or denies a claim, and a test checks that.
- **"What if the speech service is slow or down?"** The language reader has a 600 ms limit and falls back to rules;
  two turns not understood bring in a person. Measured end of speech to first audio with the offline services is
  about 200 ms at p95, and most of that is the voice-activity detector's 200 ms stop setting.
- **"Are the model numbers real?"** The claim costs come from freMTPL2, real French motor claims. The fraud labels
  are synthetic, with documented injected patterns, so the closer-look numbers describe the method, not the world.
  See [model-cards/](model-cards/) and [eval/RESULTS.md](../eval/RESULTS.md).
- **"How well does it understand callers it hasn't heard before?"** With the offline rules, not well yet. On eight
  held-out callers never used for tuning, 1 call completes as expected, and the rest hand off to a person after two
  turns it can't place, rather than filing a wrong value. Open wording is what the optional cloud reader is for; the
  rules are the offline floor.
