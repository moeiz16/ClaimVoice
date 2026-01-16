# ClaimVoice frontend design, v3: "Ask and answer"

> The current design. It replaces the switchboard (v2: key bank, slate, tape and loss notice; orchid on porcelain,
> Commissioner and Inclusive Sans) and the first round before it (the floating dock and the line desk). Features,
> routes, roles, data flows, the live call and its offline speech path, the demo clock and EN/FR are unchanged; the
> colours, the shell, every page skeleton, the type, the components' shape and the motion are new.
>
> Review flags in the app: `?theme=light|dark`, `?still` (reduced motion); the landing takes `?t=<seconds>|end`,
> `?play` and `?read`; the claim file takes `?signs` and `?read`. Screenshots are taken with the browser's `Date`
> frozen at **Thu 8 Jan 2026 07:42 America/Edmonton** and the API's clock at `CLAIMVOICE_DEMO_TODAY=2026-01-08`.

ClaimVoice answers an insurer's claims line at any hour, in English or French, takes the first notice of loss for
auto and property claims, keeps a person within reach, and hands the team a claim file where every value links to
the words it came from. At hang-up a routing check sends the claim to fast-track, an adjuster or a closer look, with
reasons in plain words. Seed insurer: Larkspur Mutual (Calgary and Denver, EN/FR including Québec), the morning
after an overnight Chinook windstorm.

---

## 1. What we looked at

The brief for this round: the owner saw the old product in every screen (the pink, the porcelain, the aubergine
column, waveforms on every page, "Tell me what happened." in the same treatment) and a portfolio whose headings all
looked alike. So we started again from what the line *does*, not from the last layout.

| # | Reference | What it does | What we took (or refused) |
|---|---|---|---|
| 1 | iPhone Phone app, in-call and incoming-call screens; Google Phone's 2024–25 move to two answer/decline buttons (https://9to5google.com/2025/03/13/google-phone-app-incoming-call-new-ui/, https://www.androidauthority.com/google-phone-incoming-call-ui-test-teardown-3485981/) | A caller as one big round face, the name, a timer and a grid of round buttons; answering is one big round green button | **The in-call stage** of the live call and the demo line (a centred caller pebble, round call buttons), and the landing's hero: **an incoming claim call you answer** |
| 2 | Apple HIG pull-down buttons and SwiftUI toolbar title menus (https://developer.apple.com/design/human-interface-guidelines/pull-down-buttons, https://useyourloaf.com/blog/swiftui-toolbar-title-menus) | A menu drops from the navigation title to switch context | **The question heading is the navigation**: press it and every other place drops down |
| 3 | Contact-centre wallboards (https://www.callcentrehelper.com/top-10-things-to-include-on-your-contact-centre-screens-2081.htm, https://help.8x8.com/docs/wallboards-overview.md, https://docs.natterbox.com/docs/wallboard-best-practices-and-scenarios) | Calls waiting and the longest wait lead; agents' states sit beneath; few numbers | The Lines page **answers in one sentence** ("2 callers are waiting for a person, the longest for 1:48") and groups callers by who they need, waiting first. No tiles, no stat strip |
| 4 | Hi Marley claims threads (https://www.himarley.com/claims/) and Lemonade's claim chat (https://www.lemonade.com/blog/secret-behind-lemonades-instant-insurance/) | The claim *is* a conversation: one thread, bubbles, photos in line | **The conversation is shown as speech bubbles** (ClaimVoice left, the caller right), and **the claim file is written as answers to the questions ClaimVoice asked**. Lemonade's lesson stays in the copy: a sign is never a reason to deny a claim |
| 5 | iOS Settings "inset grouped" lists | Settings as rounded groups of rows with a value and a chevron | **Settings** pages |
| 6 | Apple Wallet passes | A rounded card whose primary field is huge, with a strip of secondary fields | **The claim card** at the top of a claim file |
| 7 | Netflix and Disney+ profile pickers | "Who's watching?": round faces, a name under each | **Sign-in**: "Who's picking up today?", the demo people as round faces |
| 8 | Duolingo's chunky pressable buttons and rounded display type (https://www.shadcn.io/design/duolingo, https://madegooddesigns.com/duolingo-font/) | Thick bottom "lip" on every control, heavy rounded type | The **pressable lip** on buttons and round call buttons. We kept the colour, the voice and the density our own: no mascot, no caps, no game chrome |
| 9 | Retell, Talkdesk and Dialpad live monitoring (https://docs.retellai.com/features/live-monitoring.md, https://support.talkdesk.com/hc/en-us/articles/10791422022171) | Listen, whisper (typed), take over; one person per call | Kept as features; now **round call buttons** on the stage and **the Bell** for the line you're on |
| 10 | Five9 Agent Assist on live transcripts (https://www.businesswire.com/news/home/20200916005308/en/) | Scrolling transcripts in the line of sight distract | The Lines page shows **one question and the heard answers per call**, never a scrolling transcript |
| 11 | Awwwards and Land-book "soft / friendly" service sites (DesignRush write-ups of WeCircle and Kaleidoscope Counseling: https://www.designrush.com/best-designs/websites/wecircle-website-design, https://www.designrush.com/best-designs/websites/kaleidoscope-counseling-web-design) | Seafoam and muted teal, rounded heavy type at large sizes, open space | The **sea-glass** palette, big soft headings, generous air. Godly and Land-book block automated fetching; we read write-ups instead |
| 12 | NAIC model bulletin on insurers' use of AI (https://content.naic.org/sites/default/files/call_materials/Model%20Bulletin%2010.23%20Clean.pdf) | Govern, test for unfair discrimination, explain | Routing checks answer **a regulator's questions** in frequencies with a 100-dot picture |

What we refused: a waveform as decoration (waveforms stay only where they carry sound: the recording player, the live
level on a call), a dark "AI glow", chat-app greys, a stat strip, card grids of identical tiles, and anything from
another project's row in `DESIGN_DIRECTIONS.md`.

---

## 2. Concept: "Ask and answer"

ClaimVoice works by asking a caller plain questions and writing down the answers. **Every screen works the same way.**
Its heading is the question a person on the team is asking ("Who's on the line?", "Where does Dana's claim go?"), the
first line under it answers in one sentence, and the page beneath is the evidence. On a call the evidence is the
conversation itself, as speech bubbles; in a claim file it is ClaimVoice's questions with the caller's answers, each
answer linked to the moment it was said.

Mental models by role:
- **Intake supervisor (Renée):** "Who's on the line, and who needs me?" Waiting callers come first, in big bubbles.
- **Adjuster (Lena):** "Which claims came in, and where does this one go?" A claim card, a verdict, the answers.
- **Special investigations (Dev):** "Which details deserve a closer look, and where were they said?"
- **Compliance (Priya) and QA (Owen):** "Is routing working and fair?" "Which calls missed the mark?"
- **Policyholder:** "Someone picked up, and they were kind."

---

## 3. Shell: the question heading and the Bell

No top bar, no sidebar, no dock, no right-hand column, no tabs.

- **The question heading** (top-left of every signed-in page). The mark (a sea-glass pebble with a speech tail) and
  the page's question in Nunito Black, 60–64 px, with a round chevron button joined to it. The heading *is* a button
  (`aria-haspopup="dialog"`): pressing it, or `M`, `/` or ⌘K, drops **the Questions sheet**.
- **The Questions sheet** (Nuxt UI Modal, anchored to the top, 32 px radius). Every place the person can open, as big
  rounded questions with the short name and a count: *Who's on the line?* Lines · 2 waiting; *Which claims came in?*
  Claims; *Which calls missed the mark?* Quality · 6 to review; *Is routing working, and fair?* Routing checks; *How
  should the line behave?* Settings; *Who did what, and when?* Activity. Above them a **Find** field (lines, this
  morning's claims, a claim search); below them the person: name and role, Night line, caption size, Reduce motion,
  Sign out. Arrow keys move, Enter opens; `G` + letter shortcuts stay (G L, G C, G Q, G R, G S).
- **The Bell** (top-right, for people who watch the lines). A round button with the number of callers waiting for a
  person inside a ring; it nudges once when someone new starts waiting. Its popover lists who is waiting (urgent first,
  with Take the call) and, when you are listening to a call, **the line you're on**: the caller, a live level, Whisper,
  Take over or Hand back, Hand off, Stop listening, Open the call. Its accessible name says it in words ("2 callers
  waiting for a person; you're listening to Gord Lindqvist").
- **Record pages** (a call, a claim, a review, a fact sheet, a settings section) put a small **crumb pebble** above the
  record's own name ("‹ Lines", with its own chevron that opens the same sheet). The record's name is the heading.
- **Phone (≤ 720 px):** the same shell. The question drops to 34–38 px and wraps; the Bell stays top-right; the sheet
  fills the screen; round call buttons wrap into a 3 × 2 grid.

### Page skeletons by screen type
| Screen | Skeleton |
|---|---|
| Lines (home) | Question + answer sentence → **weather note** (the surge, a sand note with its two levers) → **pools**: *Waiting for a person* (wide speech-bubble cards, urgent first, a wait ring around the caller's initials, Take the call) → *Talking with ClaimVoice* (call bubbles in a flowing wrap: a step ring around the initials, ClaimVoice's last question in a jade bubble, heard answers as pebbles, round Listen · Whisper · Take over) → *With a person* → *Finished this morning* as pebble rows |
| Live call | Crumb → **in-call stage**, centred: caller pebble with step ring and live level, name, place, timer, consent; round call buttons (Listen, Whisper, Take over / Hand back, Hand off, Captions / Read instead) → the **conversation** as speech bubbles (Captions: the latest exchange large; Read instead: the whole call) with the whisper / say composer under it like a message field → **the answer sheet** filling below (question bubbles → answer bubbles) → at hang-up, Where it goes |
| Claim file | Crumb → **claim card** (wallet pass: claim number, holder, what, where, when, reported, route chip, assigned person; Change route, PDF) → **Where it goes**: the verdict as a big bubble, its three reasons as numbered pebbles with ▸ times, likely size, signs folded with the never-deny line, Accept / Change → **the recording** (play button + waveform; the one place a waveform stays) → **In short** → **the answer sheet** with photos under *Any photos?* → *What we heard* opens the conversation bubbles in a slide-over |
| Claims register | Question + answer → filter pebbles (route, assigned to me) and Find → **pebble rows** (initials, claim no., caller, what happened, where, reported, where it goes, assigned) |
| Quality | Queue: question + answer → filter pebbles → pebble rows with rubric dots. Review: crumb → name → player opened at the flagged moment → the rubric as a **checklist of round ticks** with Agree / Disagree and a coaching note → Done, next call |
| Routing checks | Question + answer → **answer cards**, one per regulator question: the question as a heading, the answer as a huge sentence ("96 in 100"), a 100-dot picture or a dot plot, the sign-offs |
| Settings | Question → **inset groups** of rows (iOS Settings) → section pages with grouped rows and switches |
| Activity | Question → day groups, each entry a round node on a soft line, with the chain check as a sentence |
| Landing | **An incoming claim call** (see §6) |
| Sign-in | "Who's picking up today?" with the demo people as round faces, then the email form |
| Demo line | Incoming call → in-call stage + bubbles + the answer sheet, the same as the live call |
| Photo link | Phone-first: one question per step, a big round camera button |

---

## 4. Type

- **Nunito** (Vernon Adams; variable, 800–900) for headings, questions, names and big numbers. Rounded terminals,
  heavy and soft. Headings are sentence case, set tight (−0.025 em at display sizes, −0.015 em at 30 px), and carry a
  **cushion**: a soft offset shadow in sea glass (`0 0.055em 0` in `--cv-cushion`), so the letters sit on the page like
  pressed pebbles. Never tracked caps, never italic, never two-tone.
- **Lexend** (Bonnie Shaver-Troup, Thomas Jockin; variable) for the UI, body, labels, values and tables: wide,
  hyper-legible, made for reading proficiency. Numbers, times and money use Lexend with `tnum`.
- Scale (desktop / phone): display 92/56 · question 62/36 · record name 52/34 · h2 30/24 · h3 21/19 · body 15/15 ·
  small 13 · label 13 (500, sentence case). Line height 0.98 for display and questions, 1.1 for h2, 1.55 for body.
- Self-hosted from `@fontsource-variable/nunito` 5.2.7 and `@fontsource-variable/lexend` 5.2.11. Commissioner,
  Inclusive Sans, Bricolage Grotesque and Figtree are retired.

---

## 5. Palette: sea glass

Hue family jade / sea glass, 164–172°. Light ("Day line") is the default; dark is the "Night line", a deep-sea green
night, not a black. Contrast is WCAG AA for all text; status is never colour alone (always an icon and a word).

| Token | Day line | Night line | Use |
|---|---|---|---|
| `--cv-bg` | `#EEF4F1` sea mist | `#0A1715` | page |
| `--cv-surface` | `#FFFFFF` | `#11221F` | bubbles, sheets, rows |
| `--cv-sunk` | `#E2ECE7` | `#172C28` | wells, tracks, pressed |
| `--cv-rule` | `#C9DCD4` | `#264540` | 2 px control borders |
| `--cv-ink` | `#0D2925` deep sea (15.4 : 1 on white) | `#E4F2EE` | text |
| `--cv-muted` | `#466560` (6.4 : 1) | `#9DBAB3` (7.9 : 1) | secondary text |
| `--cv-faint` | `#6E8A84` (non-text only) | `#6F8C86` | dots, tracks |
| `--cv-jade` | `#0B7D66` (white on it 5.1 : 1) | `#4CD3AF` (8.8 : 1) | ClaimVoice's voice, primary buttons, rings, focus |
| `--cv-jade-ink` | `#06654F` (7.0 : 1) | `#6FE0C1` | jade text |
| `--cv-jade-wash` | `#D2EFE5` (jade ink 5.8 : 1) | `#123A31` | ClaimVoice's bubbles, soft fills |
| `--cv-seaglass` / `--cv-cushion` | `#A9DDCB` / `#BFE6D8` | `#1D4A40` / `#16443A` | rings, heading cushion |
| `--cv-caller` / `--cv-sand` | `#7A5530` / `#F5ECDD` (5.7 : 1) | `#E6C9A2` / `#2A2620` | the caller's voice and bubbles; the weather note |
| `--cv-person` / wash | `#2454C2` / `#E2EAFB` (5.6 : 1) | `#93B3FF` / `#1B2A4A` | a person from Larkspur; adjuster route; whispers |
| `--cv-fast` / wash | jade ink / jade wash | | ✓ Fast-track, complete |
| `--cv-siu` / wash | `#8A5600` / `#FBEFD3` (5.4 : 1) | `#F0C066` / `#36290F` | closer look, the surge |
| `--cv-urgent` / wash | `#B8321A` / `#FCE4DC` (4.9 : 1) | `#FF8F73` / `#3D1C14` | urgent safety, errors |

Porcelain, orchid, magenta, pink, plum and aubergine are retired from ClaimVoice.

---

## 6. Landing: an incoming claim call (`/`)

1. **Arrive.** A light top row (mark and name; Hear a call · What your team gets · Safeguards; EN/FR; Sign in). The
   headline, centred, in Nunito Black at 92 px with its cushion: **"The claims line that always picks up."** One
   plain sentence under it. Then **an incoming call**, centred, as a phone would show it: "Incoming claim call · 2:14
   a.m. · Calgary", Dana's initials in a big sea-glass pebble, "Dana Whitcombe, policyholder · Chinook windstorm",
   and two round buttons: **Answer** (jade, "Play the call · 1 min 16") and **Read instead**. "Sample call, shortened;
   voices are synthetic."
2. **Answer.** The incoming card becomes an in-call card (timer, a live level ring around the pebble, Pause), and
   under it the conversation arrives as **speech bubbles** that inflate from their tails, ClaimVoice's on the left in
   jade wash, Dana's on the right in sand, the spoken word darkening as it is said (captions on by default).
3. **Answers are filed.** Beside the bubbles a **claim card** fills: each heard value pops in as a pebble ("Policy
   LM-AB-187342 ▸ 0:13"); the card number becomes a hatched "Card number not taken" pebble when Dana starts reading it
   and ClaimVoice stops her.
4. **Where it goes.** The last bubble gives the claim number; the card turns over to the route: ✓ Fast-track, with
   three numbered reasons.
5. **Call the demo line.** A sea-glass band with a big round phone button: Call the demo line · Type instead · Appeler
   en français, the microphone prerequisite stated first.
6. **What your team gets.** Three answers, by role (policyholder, intake team, adjuster), each a question and a reply.
7. **Safeguards.** Three promises as bubbles in the words the caller would hear. Compliance line and footer.

CTAs: **Answer** / **Call the demo line** / **Sign in**. No headline-left + card-right, no stat strip, no "Explore the
demo", no waveform horizon.

---

## 7. Components: Nuxt UI 3, re-shaped

`@nuxt/ui` 3.3.7 (Reka UI, Tailwind 4.1) stays, re-themed so it doesn't read as Nuxt UI:
- **Shape:** radius 16 px on buttons and inputs, 24 px on bubbles, groups and cards, 32 px on sheets and modals,
  full round for chips, avatars and call buttons. Containers are borderless and separated by tone; controls carry a
  2 px border.
- **Press:** solid buttons have a 3 px lip (a darker inset bottom edge) and travel 2 px down when pressed.
- **Focus:** a 3 px jade ring 3 px outside the shape, following its radius; on jade fills the ring is ink.
- **Density:** 48 px controls by default, 40 px small, 60–64 px round call buttons; rows 64 px.
- Used: UApp, UButton, UBadge (inside `CvTag`/`RouteTag`: icon + word), UModal (Questions sheet, take over, hand off,
  change route, sign-off, invite, photo viewer), USlideover (What we heard; Read the summary), UPopover (the Bell,
  What's covered), UTooltip, UToast, UTable (pebble rows), UPagination, UInput, UTextarea, USelect, USelectMenu,
  URadioGroup, USwitch, USlider, UFormField, UAccordion, UAlert, USkeleton, UKbd, UAvatar, UProgress.
- Ours, because no kit has them: the speech bubble, heard pebbles and their ▸ chips, the hatched Hush pebble, step and
  wait rings, the round call buttons, the 100-dot picture, the recording player.

---

## 8. Motion: "Tide"

Soft, springy and short (motion-v springs, CSS transitions, WAAPI):
- **Drop**: the Questions sheet falls from the heading (translate −16 px + scale .98 → 1, spring 420/32).
- **Inflate**: a new speech bubble grows from its tail corner (scale .6 → 1, transform-origin at the tail, 260 ms).
- **Pop**: a filed answer pebble arrives (scale .85 → 1 with a jade halo that fades, 320 ms).
- **Ring**: step and wait rings draw their arcs (stroke-dashoffset, 600 ms).
- **Nudge**: the Bell tilts ±10° twice when a new caller starts waiting.
- **Rise**: pages rise 10 px and fade in; pool members stagger 40 ms.
- **Turn**: on the landing the claim card turns over to its route (rotateY, 500 ms).
`prefers-reduced-motion` and the in-app Reduce motion switch turn all of it into instant changes or 120 ms fades; the
Bell never moves, and the rings are drawn at once.

---

## 9. Signature interactions

1. **Ask the heading** — the page question opens every other question; Find lives in the same sheet.
2. **Where did we hear that?** — every answer pebble carries ▸ time; pressing it plays the 3-second clip (claim file)
   or lights its words in the conversation (live call).
3. **Answer the call** — the landing's incoming call, and the in-call stage with round Listen / Whisper / Take over.
4. **The Bell** — who is waiting for a person, and the line you're on, from any page.
5. **The verdict** — where a claim goes, three numbered reasons, never a denial on a sign alone.

---

## 10. How this differs

| | v2 (switchboard) | v3 (ask and answer) |
|---|---|---|
| Shell | 96 px aubergine key bank on the right, numbered line keys with lamps, slate titles | No chrome bar or column: the **question heading is the menu**, the **Bell** top-right, crumb pebbles on records |
| Home | NEXT-order ruled rows with a Take-the-next key | **Pools** of speech-bubble call cards by who the caller needs |
| Call | Two-voice tape with words above and below a line, boxed loss notice | **In-call stage** with round buttons, the conversation as **bubbles**, the claim as **answers to questions** |
| Claim file | Slate, tape, section 8, boxed notice with margin notes | **Claim card** (pass), verdict bubble, player, answer sheet |
| Type | Commissioner (flared) + Inclusive Sans | **Nunito Black** (rounded, cushioned) + **Lexend** |
| Colour | Porcelain + orchid magenta + aubergine | **Sea mist + jade sea glass + deep sea ink**; sand for the caller |
| Shape | 6 px controls, hairline boxes | 16/24/32 px, 2 px borders, pressable lips, round call buttons |
| Motion | Voice: Settle, Pluck, Hush, Lamp, Fill | **Tide**: Drop, Inflate, Pop, Ring, Nudge, Rise, Turn |
| Landing | The tape as hero, "Tell me what happened." | **An incoming claim call you answer**, "The claims line that always picks up." |

Against other projects: no left sidebar (Necessa), no icon spine and board (Kinroot), no console, axis or status line
(Nightjar), no query strip (Tariff Compass), no title block (Groundwork AR), no devtools dock (Legible), no notebook
(Covenant), no spreadsheet (Thirdline), no masthead tabs over a map (Plotline). Nunito and Lexend are reserved for
ClaimVoice in the type registry; jade 164–172° sits between Thirdline's ledger green (148°) and Groundwork's non-photo
blue (195°), and is used as a soft fill and a voice, not as a ledger rule or a construction line.

---

## 11. Implementation notes

- Tokens: `app/assets/css/tokens.css` (both themes, motion); Tailwind and Nuxt UI mapping in `app/assets/css/main.css`;
  component shape in `app/app.config.ts`.
- Shell: `layouts/default.vue` → `shell/QuestionHead.vue` (heading and crumb), `shell/QuestionsSheet.vue` (places,
  Find, the person), `shell/CallBell.vue` (waiting callers and the line you're on).
- Shared: `voice/Bubble.vue`, `voice/Conversation.vue`, `notice/AnswerSheet.vue` (the claim file as answers; built
  from `utils/notice.ts`), `lines/CallCard.vue`, `lines/StepRing.vue`, `ui/PageHead.vue`.
- Waveforms remain only in `voice/CallRecording.vue` (recordings) and `voice/LiveWave.vue` (the live level on a call
  and in the Bell).
