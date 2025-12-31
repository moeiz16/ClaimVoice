# Problem statement

## The first call after a loss

The first notice of loss (FNOL) is the call a policyholder makes right after something goes wrong: a car hit at a
red light, a basement full of water, a roof opened up by a windstorm at two in the morning. It is the moment an
insurer is judged on, and it is also the moment its claims operation is least ready for:

- **Calls arrive in waves.** A Chinook windstorm over Calgary, a hailstorm over Denver or a cold snap that bursts
  pipes across Montréal turns a normal hour of four calls into an hour of fourteen. Callers wait on hold while they
  stand in a damaged house; some hang up and call back, some give up and call a broker or a lawyer.
- **Nights and weekends are thin.** Most regional insurers and managing general agents staff intake during business
  hours and rely on an answering service overnight. The answering service takes a name and a number, so the real
  intake happens the next morning, and the caller tells the story twice.
- **The first call decides the rest.** An intake that misses a safety question, a police report number, whether
  water is still coming in or whether the house is still open to the weather sends the claim to the wrong person,
  delays mitigation and costs money. Adjusters spend the first part of every claim re-asking what intake missed.
- **Fraud and soft fraud hide in ordinary calls**, and the signs (a policy that started days before the loss, a
  report weeks late, a story that changes) are scattered across the call, the policy and the claim history.
- **Quality is checked on a tiny sample.** Supervisors listen to a few calls a week; most consent misses, card
  numbers read aloud and late hand-offs are never seen.

## What ClaimVoice does

ClaimVoice is a voice line that answers the first call at any hour, in English or French:

1. Asks for **recording consent first**, following the caller's state or province rule.
2. **Verifies the caller and the policy**, asks whether **everyone is safe**, then asks the right follow-up questions
   for the loss type (collision, hail, wind, water, fire, theft), allowing interruptions and corrections.
3. **Texts a photo link**, explains coverage basics in plain words (never a decision), reads the summary back and
   gives a claim number and next steps.
4. **Hands off live to a person** whenever the caller asks, safety is at risk, the caller is distressed or the line
   is not sure what it heard; supervisors can follow the call live, whisper a note the line acts on, or take the call.
5. Produces a **structured claim file** where every value links to the words it came from, plus the transcript,
   the recording and a summary.
6. At hang-up, two **routing checks** send the claim to fast-track or an adjuster and ask special investigations to
   take a closer look when several signs line up, always with reasons in plain words, and never deny a claim.
7. Scores **every call** against a quality rubric and puts the ones that need attention in front of a reviewer.

## Who uses it

| Person | What they need |
|---|---|
| **Policyholder** (calling in) | A calm voice, at 2 a.m., in their language; a claim number and a time someone will call back |
| **Intake supervisor** | Every live line at a glance: which step each call is at, who needs a person now, whether a surge is building |
| **Intake agent** | Hand-offs that arrive with a summary, so nobody asks the caller twice |
| **Adjuster** | A claim file they can trust: each fact linked to the moment it was said, photos, and why it was routed to them |
| **Special investigator** | The signs worth a closer look and where they were said, without a verdict pre-written for them |
| **Compliance, model risk and quality** | Evidence for a regulator: consent, card-number handling, fairness of routing, sign-offs, a tamper-evident log |

## Compliance and constraints

ClaimVoice is designed to support these obligations; it does not claim certification against any of them.

- **NAIC Model Bulletin on the Use of AI Systems by Insurers** (December 2023, adopted by a growing number of US
  states): insurers need a written AI program with governance, risk management and testing for unfair
  discrimination for AI used in claims. ClaimVoice keeps both routing checks explainable, tests fairness by region,
  language and age band on every version, requires two sign-offs before a version goes into use, keeps a fact sheet
  per check and never lets a model deny a claim.
- **Call-recording consent.** Some US states require every party's consent (California Penal Code §632, Washington
  RCW 9.73.030, Florida, Illinois and others); Colorado is one-party. In Canada, privacy law (PIPEDA, Alberta PIPA,
  Québec's private-sector act) requires notice and consent for recording a business call. The line asks first, keeps
  nothing in all-party regions before a yes, and on a no stops recording and keeps notes only.
- **GLBA** (US) privacy and safeguards for customer financial information: personal data is masked in every
  response, the date of birth is used only to verify identity and is never shown, sessions are short-lived and every
  sensitive action is audited.
- **PCI DSS: no card numbers by voice.** The line never asks for payment details. If a caller reads a card number
  out anyway, the digits are removed before anything is stored, the recording is paused for that moment, and the
  caller is told not to share card numbers on this line.
- **Canada: PIPEDA and Québec Law 25.** Consent, purpose limits and retention limits; Law 25 also requires a
  designated person responsible for personal information (the privacy officer in Settings), privacy impact
  assessments, and telling people when a decision about them is made by automated processing alone. ClaimVoice makes
  no such decision: routing decides who looks at a claim first, and a person can always change it. Québec's Charter
  of the French language means French first for Québec callers.
- **Accessibility:** captions for every spoken line, a "read instead" typed call, keyboard access, and status never
  shown by colour alone.

## Non-functional requirements

- **Response time:** under 800 ms at the 95th percentile from the end of the caller's speech to the start of the
  line's reply, measured with the offline fakes and budgeted per step for the cloud services (docs/ARCHITECTURE.md).
- **Graceful failover to a person:** any failure of a speech or language service, or of a required lookup, leads to a
  person or a call-back, never to a dead line.
- **No autonomous claim denial, and every decision explainable** in plain words, with the moment in the call that
  supports it.
- **Runs offline** for development and demos: deterministic fakes for speech, language understanding, text messages
  and weather; no accounts or keys.

## What is out of scope

Real telephone numbers (the demo line is a browser call; a SIP or phone-network transport is a later addition),
payments, claim settlement, adjuster scheduling and any decision on coverage or liability.
