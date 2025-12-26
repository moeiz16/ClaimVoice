# ClaimVoice frontend design: "On the line"

> Built to this document. The design was prototyped as static pages first (landing, live call, line desk, claim file, routing checks, sign-in); the web app in `app/` is the implementation. Screens the prototype didn't cover (quality review, settings, activity, the live demo line, the photo-upload page, and the empty, loading and error states) follow §5 here. Review flags in the app: `?theme=light|dark`, `?still` (reduced motion); the landing also takes `?t=<seconds>|end`, `?play` and `?read`; the claim file takes `?signs`. Screenshots are taken with the browser clock frozen at **Thu 8 Jan 2026 07:42 America/Edmonton**.

ClaimVoice is a voice line that takes the **first notice of loss** (FNOL) for auto and property claims at any hour, in English or French. It verifies the policy, asks the right follow-ups, sends a photo link, flags urgent safety and fraud signs for a person, hands off live, and produces a claim file where every value links to the words it came from. At hang-up a **routing check** sends the claim to fast-track, an adjuster or a closer look by special investigations, with reasons in plain words.

- **Seed insurer:** Larkspur Mutual (Calgary, Alberta and Denver, Colorado; EN/FR service including Québec).
- **Demo moment:** Thursday 8 January 2026, 7:42 a.m. Calgary time, the morning after an overnight Chinook windstorm (gusts over 100 km/h: roofs, siding, fences and skylights smashed by blown debris). Every displayed date sits in Dec 2025 to Jan 2026.
- **Stack:** Nuxt 3 (Vue 3) + TypeScript + Tailwind 4.1, Motion for Vue (`motion-v`), VueUse, Web Audio `AnalyserNode` + canvas for live audio, wavesurfer.js v7 for recordings.
- **Copy date:** written as of early January 2026; anything time-sensitive is computed at runtime from `CLAIMVOICE_DEMO_TODAY`.

---

## 1. Research: what we looked at and what we took

Each reference was opened during this design round. Where a vendor's docs were thin, the table says so.

| # | Reference | What it does | What ClaimVoice takes |
|---|---|---|---|
| 1 | Retell AI live call monitoring docs: https://docs.retellai.com/features/live-monitoring.md | A live list of in-progress calls; per call, a transcript with agent/caller turns, tool calls and a "Jump to latest" control; **Live Listen** (silent, "You're listening live" indicator), **Take Over** (confirmation, mic permission, the AI stops permanently, "You've taken over the call" banner), **End Call**. Losing the dashboard connection does not end the call. | The **Listen / Whisper / Take over** trio and the "You're listening" state on the strip and in the dock. Take over confirms in a sheet, then shows a third (cobalt) voice joining and ClaimVoice switching to "taking notes". The **error state** copy: "We lost the connection to the lines. Calls carry on; ClaimVoice keeps taking them." |
| 2 | Retell community roadmap: https://community.retellai.com/t/live-call-monitoring-and-supervisor-mode/2291.md | Whisper/coaching of the AI agent is *not* supported. | A gap we fill: **Whisper** means a note ClaimVoice acts on ("Ask if the garage skylight is damaged too") that the caller never hears. It appears in the transcript as a cobalt "Whisper, ClaimVoice only" row. |
| 3 | Talkdesk live monitoring and listen-in: https://support.talkdesk.com/hc/en-us/articles/10791422022171-Supervisor-Call-Monitoring-and-Listen-in-functionality | Supervisor is muted while listening; a typed **whisper box**. | Whisper is **typed**, not spoken, in a pill input under the transcript. |
| 4 | Five9 Agent Assist (Business Wire): https://www.businesswire.com/news/home/20200916005308/en/ | Five9 discourages putting live transcripts in an agent's line of sight: "one of the most distracting things." | The **switchboard never shows a scrolling transcript.** Each line strip shows only "ClaimVoice asked …", the script step and what was heard as short pills. The full transcript lives one click away. |
| 5 | Dialpad AI contact centre: https://www.dialpad.com/features/ai-call-center | Live sentiment; supervisors watch several calls and see which may escalate; listen / whisper / barge. | A single **plain mood word** per line ("Sounds shaken · speaking slower"), never a score or a red/green meter. |
| 6 | Aircall Live Monitoring: https://aircall.io/blog/features/introducing-live-monitoring/ | Tabs for Calls/Users/Numbers; colour-coded SLAs; one coach per call; emergency calls cannot be coached. | One person can take a call at a time (the strip locks with the person's initials). Counts appear as captions in the header ("3 on the line, 2 waiting for a person"), **not KPI tiles**. |
| 7 | Intercom Fin hand-off: https://developers.intercom.com/docs/references/preview/rest-api/api.intercom.io/fin-agent/escalatefinconversation and https://community.intercom.com/fin-tips-from-the-intercom-team-85/save-time-and-avoid-repetition-with-ai-summaries-10554 | Escalation arrives with a summary note so the teammate doesn't scroll the thread; Fin can pause and ask a teammate without handing off. | Every hand-off tray item carries a **two-line summary** and "Read the summary"; "nobody asks twice" is landing copy. Whisper is our "ask a teammate without handing off" in reverse. |
| 8 | Hi Marley claims: https://www.himarley.com/claims/ | Context carries over at every hand-off; one thread between carrier, customer and adjuster. | The claim file *is* the thread: the adjuster sees the same transcript and recording the supervisor heard. |
| 9 | Lemonade AI Jim (blog + reporting): https://www.lemonade.com/blog/?p=7867 and https://ktvz.com/lifestyle/technology/2021/05/27/this-5-billion-insurance-company-likes-to-talk-up-its-ai-now-its-in-a-mess-over-it/ | Claim as a conversation, an instant decision moment; the 2021 backlash over implying AI denies claims. | The **route reveal** as the call's last moment, and a hard rule in copy: "A sign is never a reason to deny a claim on its own, and nothing here was decided automatically." Lemonade's grey chat bubbles are what we avoided. |
| 10 | Decagon Watchtower: https://decagon.ai/blog/decagon-watchtower | Every conversation checked against plain-language criteria; flags in categories; drill straight into flagged conversations. | **Quality review**: rubric items written as sentences ("Asked for recording consent first"), and opening a flagged call **jumps the recording to the flagged moment**. |
| 11 | Sierra, "confidence in every conversation": https://sierra.ai/blog/confidence-in-every-conversation | Supervisory checks per turn and per conversation surface problems for human review. | The **safety watch** strip on the live call: "Listening for injury · gas · water near power · distress", always visible. |
| 12 | Pipecat Voice UI Kit / Pipecat UI: https://voiceuikit.pipecat.ai/components/overview and https://ui.pipecat.ai/docs | Transcript overlay with word-by-word captions; conversation view with speaker roles and function calls; audio-reactive bar visualisers. | The live caption treatment and the bar-style live waveform (thin rounded bars, not a glowing blob). Pipecat is the voice runtime, so its client events drive our UI states. |
| 13 | ElevenLabs UI and Orb: https://elevenlabs.io/blog/elevenlabs-ui and https://21st.dev/community/components/ElevenLabs/orb | Agent state (idle / listening / talking) as one animated object. | The **demo-line orb** on the landing (one object, three states), deliberately small in the product: in the app, state is the dock's live dot + waveform, not an orb. |
| 14 | Hume AI hero critique: https://ixd.prattsi.org/2025/09/design-critique-hume-ais-hero-page/ | Making the voice demo the hero lowers friction; state prerequisites early. | **Hear it in one click** (the play button sits on the waveform), and the demo line states its prerequisite before the mic prompt: "Uses your microphone in this browser only." |
| 15 | Sesame research essay: https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice | Audio as evidence inside an editorial page. | The landing reads like an essay you can **hear**: a call, then what the team gets, then safeguards. No feature grid. |
| 16 | Deepgram interim results + confidence: https://developers.deepgram.com/docs/interim-results and https://developers.deepgram.com/docs/confidence.mdx | Interim words get revised; confidence is lower at the audio boundary; show interim text for display only. | The **Settle** motion: interim words appear faint and blurred and settle into ink when final. Fields from interim words show "hearing now" and are not committed. |
| 17 | Descript playback: https://help.descript.com/descript-tour/playback-and-navigation.md and Avid transcript sync: https://mediacentral.avid.com/MCCUX/Content/Users_Guide/TranscriptTab_NavigatingTranscript.htm | The playhead highlights the current word; the transcript is linked to the media. | **Karaoke captions** and "What we heard" following the recording on the claim file. |
| 18 | Apple Music synced lyrics (TechRadar; design teardown): https://www.techradar.com/audio/spotify/i-didnt-know-you-could-do-this-hack-in-spotify-lyrics-until-now-and-im-truly-astonished-but-its-only-available-to-android-users-leaving-us-ios-minions-on-the-back-burner and https://blakecrosley.com/guides/design/apple-music | Lyrics as a full-screen experience; the active line is larger, past lines shrink, future lines are subdued. | The landing's **lyric sheet**: the current turn at 44 px, the two before it at 21 px and faded. We add a second axis: **ClaimVoice's lines hug the left, the caller's hug the right.** |
| 19 | Google Live Transcribe sound events: https://9to5google.com/2019/06/03/android-live-transcribe-update/ | Sound events ("dog barking", "knocking") shown, but in a strip far from the speech. | **Sound tags inline** in the transcript ("[dog barking]", "[wind gusting]"), in italic muted text, next to the words they interrupted. |
| 20 | Apple Live Captions (Pratt IxD): https://ixd.prattsi.org/2025/02/assistive-technology-live-captions-ios/ | Movable, resizable caption panel; text size and contrast settings. | **Captions / Read instead** on every audio surface, and a caption-size setting (S/M/L) in the account menu. |
| 21 | wavesurfer.js options and regions: https://wavesurfer.xyz/docs/types/wavesurfer.WaveSurferOptions and https://wavesurfer.xyz/docs/plugins/regions/ | `splitChannels`, `peaks`, `duration`, `barWidth/barGap/barRadius`, `cursorColor`, `progressColor`; regions with colour and content. | **Stereo recordings (caller left, ClaimVoice right) rendered as two lanes**, precomputed peaks, regions for turns, moments and the hush gap (§11). |
| 22 | Logic Pro mixer, mute/solo channel strips: https://help.apple.com/logicpro/mac/10.1/en.lproj/lgcpbc21a09d.html | Vertical channel strips with level meters and solo/mute buttons at the foot. | The switchboard as a **line desk**: each live call is a vertical strip with a segmented level meter down its edge and three buttons at its foot (Listen = solo, Whisper = talkback, Take over). |
| 23 | NAIC Model Bulletin on the Use of AI Systems by Insurers: https://content.naic.org/sites/default/files/call_materials/Model%20Bulletin%2010.23%20Clean.pdf | Insurers must govern AI used in claims, test for unfair discrimination and be able to explain decisions. | The **Routing checks** page is written as the questions a regulator asks, answered in frequencies ("96 in 100"), with fairness by region, language and age band and two sign-offs per version. |
| 24 | Awwwards "Sound-Audio" category: https://www.awwwards.com/websites/sound-audio/?page=1, AgentVoice nominee: https://www.awwwards.com/sites/agentvoice | Award sites lean on full-bleed sound objects and dark, glowing "AI" aesthetics. | We took the **full-bleed sound object** (the waveform horizon spans the page) and refused the dark-glow cliché. *Godly redirects to recent.design and Land-book returned 403 to automated fetches; voice-AI concepts on Contra (e.g. https://contra.com/p/oYWvQABg-capse-ai-voice-saa-s-landing-page) confirmed the common "dark premium + waveform preview + feature grid" pattern we avoided.* |

---

## 2. Concept: "On the line"

**Everything is a line, and every line has two voices.** A claim starts as someone telling us what happened. ClaimVoice's job is to listen, pick the facts out of the words, and keep a person within reach.

One picture runs through the whole product: **the conversation waveform**. A horizontal line; **Larkspur's side (ClaimVoice, or a person from Larkspur) speaks above it; the caller speaks below it.** You can see who is talking, for how long, where a card number was cut (a hatched gap), and where the facts were heard (moments pinned to the line). It is the landing hero, the dock's live meter, each strip on the switchboard and the recording on the claim file.

Mental models by role:

- **Policyholder:** "I'm telling someone what happened." They hear a calm voice, get a claim number and a time someone will call.
- **Intake supervisor (Renée Kowalchuk):** thinks in **lines**, like a sound desk: who is on now, what step each call is at, who needs a person, and is there a surge.
- **Adjuster (Lena Ortiz):** "What happened, can I trust it, where does it go?" Every fact links to the words and the moment in the recording.
- **SIU investigator (Dev Malhotra):** "Which details deserve a closer look, and where were they said?"
- **Compliance / model risk (Priya Sandhu):** "Can I show a regulator how routing works, that it's fair, and who signed it off?"
- **QA (Owen Fairweather):** "Which calls missed the rubric, and at what moment?"

The transcript is the **source of truth**; the claim file is a set of **pointers into it**. That is the product's one idea, and the UI never lets a value appear without its source chip ("▸ 1:52" or "from the policy").

---

## 3. Information architecture and navigation

**The dock is the only navigation.** A floating aubergine pill, 68 px tall, bottom-centre, 18 px off the bottom edge. It holds:

1. the mark (home), then
2. five destinations as text pills: **Lines · Claims · Quality · Routing checks · Settings** (counts as small orchid badges: lines waiting for a person, calls to review), then
3. **the line you are on**: a mini player with the line's live waveform, caller and elapsed time, and **Listening · Whisper · Take over**. It appears on any route as soon as you listen to a line and stays while you move around, like a music player's bar. It disappears when you stop listening.

There is no sidebar, no top tab bar and no command palette. The top of every page is a plain header: large page title in Bricolage, a one-line context caption (insurer, date, local time, counts as words), and at the right only page-level controls and the avatar.

Routes:

| Route | Who lands here | Notes |
|---|---|---|
| `/` | public | Landing with the recorded call |
| `/call` | public | "Ring the demo line": full-screen orb + captions; `?type` opens the typed call |
| `/sign-in` | public | |
| `/lines` | intake supervisor (default) | The switchboard (line desk) |
| `/lines/[lineId]` | supervisor, intake agent | Live call / intake view |
| `/claims`, `/claims/[claimId]` | adjuster (default), SIU | Claim list (a ledger of rounded rows, filter pills by route) and the claim file |
| `/quality`, `/quality/[callId]` | QA (default) | Review queue and the review view |
| `/routing`, `/routing/[check]` | compliance (default) | Routing checks and each check's fact sheet |
| `/settings/{scripts,consent,handoff,languages,retention,people}` | admin | Settings sections as pills under the header |
| `/activity` | compliance, admin | Audit log (reached from Settings and the account menu) |

**Phone (≤ 720 px):** the dock becomes a full-width bottom sheet: five icon+label tabs on the bottom row and, above them, the "line you are on" mini player (caller, tiny waveform, three round buttons). Two-pane screens (live call, claim file) get a segmented control (Conversation / Claim file). The hand-off tray moves **above** the strips on the switchboard, so an urgent call is first.

Keyboard: `G L` Lines, `G C` Claims, `G Q` Quality, `G R` Routing checks; on a line `L` listen, `W` whisper (focuses the input), `T` take over (opens the confirm sheet); on any recording `Space` play/pause, `←/→` 5 s, `[` / `]` previous/next turn, `J` / `K` previous/next moment.

---

## 4. Landing story, beat by beat (`/`)

No hero card, no stat strip, no "Explore the demo / Create an account". The page is a call you can hear.

| Beat | What the visitor sees and hears | Motion |
|---|---|---|
| 0 · Arrive | Top: logo, three anchor links (Ring the demo line · What your team gets · Safeguards), EN/FR, "Supervisors, sign in". Eyebrow: "A claim call to Larkspur Mutual, Calgary · Thursday 8 January, 2:14 a.m., during a Chinook windstorm" + "Sample call, voices are synthetic". The headline is **ClaimVoice's own first line**, left: "Tell me what happened. *I'll take it from there.*" (82 px, orchid second line). Right-aligned, in the caller's plum, a teaser: *Dana, policyholder* "The wind just smashed our skylight." Below: the **horizon**, the whole 1 min 16 s call drawn as one mirrored waveform across the page, with the 84 px orchid play button sitting at its start and "Play the call · 1 minute 16 · captions on". Moment labels under the line: Consent · Policy · Safe · When · Card stopped · Photos · Read-back · Claim no. | Play button halo **Breathes**. Nothing auto-plays. |
| 1 · Press play | The headline lifts away; the **lyric sheet** takes the stage: the current turn at 44 px, the two before it at 21 px, faded. ClaimVoice's lines hug the left, Dana's hug the right. Words arrive karaoke-style (spoken in ink, the rest faint). The play button shrinks to 60 px and rides the playhead along the horizon; the played part of the waveform is full colour, the rest at 32%. | **Ripple** from the button at each new turn. |
| 2 · Values are heard | When Dana reads her policy number, the words get an orchid wash and underline, then a copy **flies** down to the **claim slip** under the horizon and lands as a pill: "✓ Policy LM-AB-187342 · Dana Whitcombe ▸ 0:13". Pills update in place when a later sentence refines them ("Kitchen skylight smashed" → "Kitchen skylight smashed, now covered"). The address arrives as "from the policy", not heard. | **Pluck** (520 ms arc), landing pop. |
| 3 · The card number | Dana: "Do you need my card for the deductible? It's four-five …". The rest of the digits become a hatched **"■■■■ removed"** pill; on the horizon that stretch is a hatched gap with a dotted line, and a tag rides the playhead: "🔒 Recording paused · card number". ClaimVoice: "Please stop there. I never take card numbers on this line, and that part of the recording is removed." The slip gains a hatched pill "Card number not taken". | **Hush** (400 ms). |
| 4 · Read-back | ClaimVoice reads the claim back; Dana: "That's right." | |
| 5 · Route reveal | Last line: "Your claim number is CV-26-01842." The slip's last pill unfurls into the route: **✓ Fast-track** · 1 Damage limited to one area · 2 Nothing is open to the weather · 3 Nobody hurt. | **Route** (clip-path unfurl, 600 ms; reasons stagger 90 ms). |
| 6 · Ring the demo line | Full-bleed orchid-wash band: "Ring the demo line", a 176 px orb with a phone glyph, a suggestion in the caller's voice ("Try: 'Someone backed into my car in the Chinook Centre parking lot.'"), buttons **Ring the demo line** · **Type instead** · **Appeler en français**, and the prerequisite stated first: "Uses your microphone in this browser only. Nothing you say is kept after you close the page." | Orb Breathes; while live it reacts to mic level. |
| 7 · Said → filed | "What the caller hears, and what your team gets." Three rows (Policyholder · Intake team · Adjuster): a spoken line in display type, and what each gets as pills (the intake row shows the **Urgent safety** tag for a gas smell). | Rows fade up on scroll (opacity + 12 px). |
| 8 · Safeguards | Three tinted tiles: Recording consent comes first · Card numbers are never taken · A person can take over any call, each ending in the actual sentence the caller would hear. | |
| 9 · Compliance + footer | "Designed to support the NAIC model bulletin on insurers' use of AI, state call-recording consent rules, PCI DSS, GLBA, PIPEDA and Québec's Law 25. In English and French." Footer with "Supervisors, sign in", Français, Privacy. | |

Live demo call (`/call`) states: **idle** (orb breathing, "Ring the demo line"), **ringing** (two soft rings, 1.2 s), **asking consent** (captions show ClaimVoice's first line), **listening** (orb scales with mic level; your words appear faint and settle), **speaking** (orb pulses with ClaimVoice's speech output), **typed call** (a pill input replaces the mic; ClaimVoice's replies still speak unless muted), **mic blocked** ("Your browser didn't let us use the microphone. You can type instead." + Type instead), **speech recognition unavailable** (Web Speech missing: the typed call opens directly with a one-line note), **ended** (the claim slip and route appear as on the recorded call).

---

## 5. Screens

All app screens: header (72 px) + content + the floating dock. Page gutter 32 px (16 px on phone). Body bottom padding clears the dock (110 px desktop, 170 px phone).

### 5.1 Sign in (`signin.html`)
Logo top-left. Centre: "Pick up your lines." (44 px), "Sign in to Larkspur Mutual's claims lines.", pill inputs (52 px), **Sign in →**, "Forgot it?", EN/FR. A tinted demo row: "Demo: Renée Kowalchuk, intake supervisor · Sample data. Calgary Chinook windstorm, Thursday 8 January." Across the bottom edge, a quiet live waveform plays a faint conversation. Error: the input ring turns urgent red with "That email and password don't match. Try again or ask your admin." (icon + text).

### 5.2 Live call / intake view (`line.html`, `?line=3` for French)
- **Header:** "‹ Lines" · caller name (30 px) · "Line 1 · Saddle Ridge, Calgary · Wind · 3:12". Right: **Recording consent · 0:07** (green, shield icon; turns to "Waiting for consent" amber until given, and in two-party states nothing is kept before it), transcript language (English/Français, or Français/+ English for a French call), **Captions / Read instead**, avatar.
- **Script track:** a pill track of seven stops: Consent → Policy → Safety → What happened → Photos → Coverage → Read-back. Done stops show ✓; the current stop is a raised white pill with a live dot; future stops show their number. At the right, the **safety watch**: "⚠ Listening for injury · gas · water near power · distress".
- **Left, Conversation (55%):** rows with a time gutter (46 px), speaker dot + name, text at 15.5 px / 1.5. Heard spans carry the orchid wash + underline. Sound tags inline in italics. Removed card digits as the hatched "■■■■ removed" pill. A whisper appears as a cobalt row "Whisper, ClaimVoice only · Renée: Ask if the garage skylight is damaged too." **The current turn is large** (Bricolage 29 px) with interim words faint and settling. The top of the column fades out (mask). At the foot: the **whisper input** pill ("Whisper to ClaimVoice. Gord won't hear this." + Send).
- **Right, Claim file (45%):** tinted panel with white sections: Policy (Verified ✓), What happened, People and safety (Checked ✓), Damage, Photos, Card numbers, Coverage basics. Each field: muted label, then a **heard pill** with its source chip (▸ 1:52) or a "from the policy" source, or a dashed **pending** pill ("Not heard yet", "Cracked? Not confirmed yet"), or an orchid-outlined **"hearing now"** pill for interim values.
- **Linking:** hover or focus a field and its span lights orchid (and scrolls into view); click to play the 3-second clip. Hover a span to light its field. A linked value and its words light together on both sides.
- **French call:** the original French stays primary (`lang="fr"`), an English line sits under each turn for staff, and the claim file notes "kept in French (Law 25), English shown for staff".
- **Take over:** a bottom sheet: "You'll be speaking with Gord. ClaimVoice will stop talking and keep taking notes. Your microphone will turn on." · **Take the call** / Not now. After: a cobalt lane joins the waveform, the dock shows "You're on the call · ClaimVoice is taking notes", and the take-over is written to the audit log.
- **Hand off:** from the dock's overflow: choose a person or team, add a one-line reason; the call moves into the tray with its summary.
- **States:** *loading* (skeleton pills in the claim file and three faint bar rows in the conversation, animating left to right); *call ended* (the track completes, the route unfurls at the top of the claim file); *line lost* (banner: "We lost the connection to this line. The call carries on; ClaimVoice keeps taking it. Reconnecting…" + Reconnect); *consent refused* (the transcript stops recording, a muted row "Recording stopped at the caller's request. Notes only from here.").

### 5.3 Supervisor switchboard: the line desk (`desk.html`)
- **Header:** "Lines" · "Larkspur Mutual · Thursday 8 January · 7:42 a.m. Calgary time · 3 on the line, 2 waiting for a person". Region filter pills (All · Alberta · Colorado · Québec), night-line toggle, avatar.
- **Surge ribbon:** amber wash, rounded 28 px, wind icon: "**Chinook windstorm, Calgary** · Calls are 3.4× usual since 6 a.m. · ✓ Wind questions switched on · ◷ Wait for a person: about 1 min" + **Bring in the standby team (2)** + What's covered.
- **Strips (3 columns):** one per live line, natural height, white, radius 28. Left edge: a segmented **level meter** (4 px segments, caller plum at the bottom, orchid at the top). Head: Line n · language · elapsed. Name (23 px). Place · loss type with icon. A **live conversation waveform** (44 px). "ClaimVoice asked: '…'" in a tinted box (French lines show the French and an English line under it). The seven-segment **script progress** + "Step 4 of 7 · What happened" / "Photos next". What we heard as pills (a possible injury shows as an amber "Sore neck" tag). Mood word. Foot: **Listen · Whisper · Take over** as three 50 px tiles (Take over in ink; Listening in orchid when on). The strip you are listening to has a 2.5 px orchid inner ring and a "You're listening" tag.
- **Hand-off tray (372 px):** "Waiting for a person 2". An **Urgent safety** item with a 2 px red ring, wait time counting up in red: "Hal Petrenko · Line 4 · Smells gas after the wind tore the cover off his gas meter. Airdrie." + what ClaimVoice already did ("told him to leave the house and call 911; he is outside and still on the line") + **Take the call** / Listen first. Then "Asked for a person" items with **Take the call** / Read the summary. Foot: who is free ("Jamal, Sofía and Aurélie are free to take calls").
- **Finished this morning:** a row of rounded tickets (claim number · place, time, name, route tag).
- **Surge scale:** at more than 6 lines the strips narrow to a compact width (meter, name, step, mood, three icon buttons); at more than 12 they become rows of the same parts in a two-column list. The ribbon then shows the queue as words: "14 on the line, 5 waiting, longest wait 3 min".
- **States:** *empty* ("All quiet on the lines. The last call ended at 6:58 a.m." over a flat, faintly breathing horizon line), *loading* (three strip skeletons with waveform bars pulsing in sequence), *error* (ribbon in urgent red: "We lost the connection to the lines. Calls carry on; ClaimVoice keeps taking them. Reconnecting…").

### 5.4 Claim file, adjuster view (`claim.html`)
- **Header:** "‹ Claims" · "Tomás Reyes" · "CV-26-01856 · Rear-ended at a light, Denver · Wed 7 Jan, 5:52 p.m. · reported Thu 6:47 a.m." Right: assigned person tag, **Change route**, **Claim file PDF**.
- **Recording band (full width):** play (54 px), "3:12 / 6:24", speed pills; **moment pins** above the lanes (Consent · Policy · 🔒 Card number stopped (hatched) · 🔍 Other car changed (amber) · Photo link · Read-back); **two speaker lanes**: ClaimVoice bars rise from the lane floor, Tomás's hang from the lane ceiling, so together they read as one conversation; the hush gap is hatched; orchid cursor with its time; a minute scale.
- **Three columns:** **In short** (a written summary in Bricolage 19 px with heard phrases underlined, "checked by Tomás at 5:40"; then the fields grouped Policy · Collision · People, each with a source chip; a changed detail carries an amber "Changed at 3:12" tag), **What we heard** (the transcript following the recording, the current turn in an orchid wash, a closer-look phrase in amber), **Where it goes** (tinted): route tags (**Adjuster** and **Closer look**), one sentence on who does what, "Why an adjuster, not fast-track" as three numbered reasons each with its ▸ moment, **Likely size: Moderate** "claims like this usually settle at $4,000 to $9,000", "Signs worth a closer look · 3 of the 14 we check" (each with ▸ moment or its source: "from the policy", "claim history"), the shield note **"For a person to review. A sign is never a reason to deny a claim on its own, and nothing here was decided automatically."**, photos (three tiles from the text link) and **Accept route** / Change with a reason.
- **Change route:** a sheet with the three routes as large radio pills, a required reason (free text + common reasons as pills) and who is notified; the change is logged.
- **States:** *recording processing* ("The recording is being prepared. The transcript is ready now."), *no photos yet* (dashed tiles "Waiting for photos · link sent 7:02 a.m." + Resend link), *caller asked not to record* (the band shows "No recording at the caller's request" and the transcript is notes only).

### 5.5 Call quality review (`/quality`, not prototyped)
- **Left, the queue (420 px):** rounded rows, each with caller, line, time, reviewer, and the **rubric beads**: six small pills with icons and words, ✓ or ✕: Consent first · Identity checked · Required details (9/10) · Kind words · No card numbers · Right hand-off. Flagged calls first; filters as pills (Missed consent, Late hand-off, Card number, Low details).
- **Right, the review:** the recording band **opened at the flagged moment** ("Jumped to 4:10, where the hand-off came 40 seconds late"), with the rubric beads pinned on the waveform at the moments they were judged; the transcript around the moment; for each rubric item **Agree / Disagree** and an optional coaching note to the script owner. Done → next call.
- Empty: "Nothing to review. Every call this week met the rubric." Loading: bead skeletons.

### 5.6 Routing checks, for compliance (`models.html`)
- **Header:** "Routing checks" · "Two checks run when a call ends. A person can change any route. Reviewed monthly; last review Mon 5 Jan." + **Fact sheets** + **Pack for the regulator**.
- **The two checks** as wide cards: **Size check** ("How big is this claim likely to be?" decides fast-track or adjuster) and **Closer-look check** ("Should someone in special investigations look at it?" never denies). Each shows version, in-use date, signer and a status tag (Working as expected ✓ / Watch: storm week ◷ / Act ⚠).
- **Four questions** as cards, each a sentence answer with one chart under it:
  1. *How often is it right?* "Of 1,240 claims sent to fast-track in December, **1,191 closed without needing an adjuster**." Bars: Size check 96 in 100 vs Old rule of thumb 81 in 100; investigators agreed 7 in 10 vs random checks 4 in 10; days to pay 2 vs 9. Foot: "When it says 'likely 7 in 10', about 7 in 10 such claims turn out that way."
  2. *Is it fair to everyone?* Dot plot of the closer-look rate by region, call language and age band against the overall line (4.1%) and the allowed green band (±1.5 points). Foot: "Age, language and region are never used to route a claim. We use them only here, to check fairness."
  3. *Are this week's calls like the ones it learned from?* Eight weekly columns against Watch and Act lines; this week in amber: "Mostly. **More wind claims than usual**, which we expect during the storm." Foot: what happens at Act (fast-track pauses).
  4. *Should version 5 replace version 4?* A four-row comparison (fast-track right, investigators agreed, fair across groups, reasons stay the same) and the sign-off row: Claims ✓ signed 6 Jan · Model risk waiting · **Review and sign off**.
- "It never" pills: denies a claim · uses age, gender, language or postcode to route · stops a person changing the route · changes version without two sign-offs.
- **Fact sheet** (`/routing/[check]`): the model card in plain language: what it's for and not for, what it looks at (in words), how it was tested, known limits, fairness results, the sign-off history, and a "for the technical reviewer" fold with metrics tables (AUC, Brier, calibration) kept off the main page.

### 5.7 Settings (`/settings/*`, not prototyped)
- **Scripts per loss type:** pills for Auto collision · Hail · Wind · Water · Fire · Theft. A script is shown **as the conversation**: ClaimVoice's questions in order as editable lines in the left voice style, EN and FR side by side, each with ▸ "Hear it", required/optional, and the facts it fills. "Wind questions" (storm-only questions) can be switched on for a surge.
- **Consent rules:** a list by state/province (two-party states flagged with a ⚖ tag and "nothing is kept until the caller says yes"), the consent sentence per language, and what happens on "no".
- **Hand-off rules:** written as sentences with editable blanks: "If the caller mentions [gas, smoke, fire, someone hurt], **bring in a person now**." "If the caller asks for a person [once], **bring in a person**." "If ClaimVoice isn't sure what it heard [twice in a row], **offer a person**."
- **Languages:** English, French (Canada); voice and speed per language; French-first for Québec numbers.
- **Retention:** "Keep recordings for [7 years]", "Keep transcripts for [7 years]", "Remove card-number moments: always (cannot be turned off)", deletion requests queue.
- **People:** invite, roles (intake agent, supervisor, adjuster, SIU investigator, compliance/QA, admin).

### 5.8 Audit log (`/activity`, not prototyped)
A day-grouped list of sentences with initials avatars: "**Renée Kowalchuk took over** Line 1 (Gord Lindqvist) at 7:44 a.m." · "**Lena Ortiz changed the route** of CV-26-01856 from Closer look to Adjuster: 'Police report confirms the SUV.'" · "**Priya Sandhu signed off** Size check version 5." Filter pills by person, action and claim. A green "Record intact ✓ · checked 7:40 a.m." tag at the top (the hash chain verified). Export as CSV/PDF.

### 5.9 Phone (390 px)
Landing: headline 48 px, the horizon keeps its play button, the moment labels hide, the slip wraps. Switchboard: surge ribbon stacks (buttons full width), the tray first, strips full width with two heard pills, tickets as a list. Live call: name only in the header with a consent shield icon, the script track scrolls sideways with only the current stop labelled, Conversation / Claim file segmented control, the last five turns, the whisper input above the dock. No horizontal overflow on any page (checked in the shot script).

---

## 6. Typefaces (Google Fonts)

```
https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&family=Figtree:ital,wght@0,300..900;1,400..600&display=swap
```

| Role | Face | Settings |
|---|---|---|
| Display: page titles, the headline, lyric captions, the current turn, names, question headings | **Bricolage Grotesque** (variable: opsz 12–96, wdth 75–100, wght 200–800) | Use **500, 600, 650, 700, 750**. `opsz` 72–96 for ≥ 24 px, 48 for the wordmark. Tracking −0.02 to −0.045 em, tighter as size grows. Headline 82/0.98 (750); lyric 44/1.12 (700); current turn 29/1.2 (650); page title 30 (750); card questions 23–24 (650–700). |
| UI, transcript, labels, tables | **Figtree** (variable 300–900) | Use **400, 500, 550, 600, 650, 700, 750**; body 15/1.5, transcript 15.5/1.5, labels 12.5–13 (700–750), never uppercase-tracked. Italic 400 for sound tags only. |
| Numbers (times, claim numbers, policy numbers, money) | Figtree with `font-variant-numeric: tabular-nums` | **No monospace anywhere.** |

The wordmark is "Claim**Voice**" in Bricolage Grotesque 750, opsz 48, wdth 92, tracking −0.035 em, with "Voice" in orchid.

---

## 7. Palette (tokens), contrast checked

Light **"Day line"** is the deliberate default: ClaimVoice is used through the working day and the warmth matters to callers. Dark **"Night line"** is an aubergine night (never blue-black) offered by a toggle, remembered per person.

| Token | Day line (default) | Night line | Use |
|---|---|---|---|
| `--cv-bg` | `#FBF7F9` porcelain blush | `#170E16` | page |
| `--cv-surface` | `#FFFFFF` | `#211520` | cards, strips |
| `--cv-sunk` | `#F3ECF0` | `#2B1C29` | tinted fills (separation without borders) |
| `--cv-sunk-2` | `#ECE2E8` | `#352434` | hover, tracks, hush hatch |
| `--cv-ink` | `#24131F` aubergine ink | `#F7ECF2` | text |
| `--cv-muted` | `#6B5664` | `#C4B0BD` | secondary text |
| `--cv-faint` | `#8F7C89` | `#8E7A88` | decoration, unplayed waveform, large text only |
| `--cv-orchid` | `#C8337A` | `#F27BB4` | ClaimVoice's voice, primary buttons, focus, playhead |
| `--cv-orchid-ink` | `#A3195C` | `#F27BB4` | orchid text on tinted fills, links |
| `--cv-orchid-wash` | `#FBE4EF` | `#3A1B2E` | heard spans, demo band |
| `--cv-on-orchid` | `#FFFFFF` | `#170E16` | text on orchid fills |
| `--cv-dock` | `#2A1530` | `#34202F` | the dock |
| `--cv-on-dock` / `--cv-dock-muted` / `--cv-dock-orchid` | `#F8EEF4` / `#C9B3C3` / `#F07AB0` | `#F8EEF4` / `#C4B0BD` / `#F27BB4` | dock text, idle nav, active control |
| `--cv-caller` (+ wash) | `#5B4A68` (`#ECE6F1`) | `#B9A6CC` (`#2E2236`) | the caller's voice |
| `--cv-person` (+ wash) | `#2F5BD3` (`#E6ECFB`) | `#8FAEFF` (`#1F2747`) | a person from Larkspur (whisper, take over, adjuster) |
| `--cv-fast` (+ wash) | `#1E7350` (`#E2F3EA`) | `#6FD1A3` (`#15302A`) | ✓ Fast-track, consent given, checked |
| `--cv-adj` (+ wash) | `#2F5BD3` (`#E6ECFB`) | `#8FAEFF` (`#1F2747`) | 👤 Adjuster, "asked for a person" |
| `--cv-siu` (+ wash) | `#875700` (`#FBF0DA`) | `#E8B65C` (`#33270F`) | 🔍 Closer look, surge, Watch |
| `--cv-urgent` (+ wash) | `#BE2A20` (`#FCE6E3`) | `#FF8070` (`#3B1A18`) | ⚠ Urgent safety, errors, Act |

**WCAG ratios (computed, WCAG 2.x relative luminance):**

| Pair | Day line | Night line |
|---|---|---|
| ink on bg / surface / sunk | 16.65 / 17.68 / 15.21 | 16.42 / 15.29 / 14.02 |
| muted on bg / surface / sunk | 6.30 / 6.69 / 5.75 | 9.27 / 8.63 / 7.91 |
| faint on bg (large text and decoration only) | 3.65 | 4.76 |
| orchid on bg / surface | 4.70 / 4.99 | 7.44 / 6.93 |
| orchid on sunk (fails 4.5 for small text → use orchid-ink) | 4.29 | 6.36 |
| orchid-ink on bg / surface / wash | 6.94 / 7.37 / 6.12 | 7.44 / 6.93 / 6.01 |
| on-orchid on orchid (button text) | 4.99 (white) | 7.44 (`#170E16`) |
| caller on bg / surface | 7.54 / 8.00 | 8.45 / 7.87 |
| person on bg / its wash | 5.56 / 4.99 | 8.70 / — |
| fast on bg / its wash | 5.46 / 5.03 | 10.20 / — |
| siu on bg / its wash | 5.83 / 5.47 | 10.15 / — |
| urgent on bg / its wash | 5.58 / 4.96 | 7.72 / — |
| on-dock on dock / dock-muted on dock / dock-orchid on dock | 14.84 / 8.59 / 6.50 | 13.29 / 7.38 / 5.93 |
| muted on orchid wash | 5.56 | — |
| focus ring (orchid) vs surface (non-text, ≥ 3:1) | 4.99 | 6.93 |

**Speaker colours and colour vision:** orchid vs caller plum separate well for normal vision (ΔE 20.8) but only ΔE 5.2 (protan) for colour-blind readers, measured with the dataviz validator. That is acceptable **only because speaker identity is position-first**: Larkspur above the line, caller below; lanes are labelled; transcript rows name the speaker. Never use these two colours as the only cue (e.g. in a legend-less chart). Status always ships with an icon and a word (✓ Fast-track, 👤 Adjuster, 🔍 Closer look, ⚠ Urgent safety, ◷ Watch).

Charts (Routing checks) are single-series: "ours" in orchid, comparison in faint grey with a direct label; text never takes the series colour.

---

## 8. Component shape language

- **Radius ladder:** pills 999 px (buttons, tags, heard values, inputs, the dock), 28 px (strips, cards, ribbons, the recording band), 20 px (inner boxes, tickets, ctrl tiles), 14 px (rows, reasons), 10–12 px (small). Nothing is square.
- **Fills over borders.** No hairlines. Separation comes from tinted surfaces (`sunk`) and white cards on porcelain. Borders appear only as meaning: the 1.5 px orchid-wash ring on a heard pill, the 1.5 px **dashed** ring on a pending pill, the 2 px red ring on an urgent tray item, the 2.5 px orchid ring on the strip you're listening to, focus rings.
- **Shadows:** only on things that float: the dock (`0 18px 40px -18px`), a pluck in flight, sheets.
- **Density:** low to medium. Touch targets ≥ 44 px (dock items 44, buttons 48/38, ctrl tiles 50). Transcript line height 1.5.
- **Data idioms:** the **conversation waveform** (mirrored, two voices), **heard pills with source chips**, **lyric captions**, **channel strips**, **script track**, **sentence answers with one chart**. No KPI tiles, no data grids on primary screens, no graphs/maps/canvases.
- **Hatching** means "deliberately not kept" (card number gaps, removed digits, a recording the caller declined). Dashed means "not heard yet".
- **Logo:** a rounded speech tile in orchid with a tail at the lower left; inside, five white bars that rise left to right like a waveform resolving into a tick (voice → claim filed). Favicon: the tile alone. Wordmark: §6.

---

## 9. Motion language: "Voice"

Library: **Motion for Vue (`motion-v`)** for layout/presence/shared elements, the **Web Animations API** for Pluck flights, canvas `requestAnimationFrame` for waveforms. Everything animates transform, opacity, filter or clip-path only.

| Motion | What it means | Spec | Reduced motion |
|---|---|---|---|
| **Breathe** | "The line is open; I'm listening." Play halo, demo orb, empty-state horizon. | scale 1 → 1.04 → 1, 3200 ms, `cubic-bezier(.45,0,.55,1)`, infinite. When live, scale = 1 + level × 0.12 via spring (stiffness 300, damping 30). | Static ring; live level shown as a numeric-free 5-step meter updated at 4 fps. |
| **Settle** | "We're sure we heard this." Interim → final words. | Per word: opacity .35 → 1, blur 2 px → 0, 240 ms `cubic-bezier(.2,.8,.2,1)`, 30 ms stagger. Interim words use `--cv-faint`. | Words swap to final instantly. |
| **Pluck** | "This value came from these words." | Span wash reveals (clip-path inset, 180 ms), a ghost pill flies on an arc (midpoint 60 px above the line) to its field, 520 ms `cubic-bezier(.2,.8,.2,1)`, scale 1 → .8; the field pops 1 → 1.06 → 1 in 220 ms. | Span and field both get a 1.6 s orchid highlight; nothing travels. |
| **Ripple** | "Someone new is speaking." | One 2 px orchid ring from the play button / dock dot: scale .7 → 1.9, opacity .55 → 0, 700 ms ease-out, per turn. | Off. |
| **Hush** | "We deliberately didn't keep this." | The digits blur (4 px) and collapse into "■■■■ removed" (width tween 400 ms); the waveform segment flattens to a dotted line over a hatched band; the "Recording paused" tag drops 8 px with fade. | Instant swap. |
| **Hand** | "A person is needed." | The strip lifts (−8 px, shadow) and its summary card slides into the tray (`layoutId` shared element), spring stiffness 260, damping 26, ≈ 480 ms; urgent items enter from the left 40 px. | Crossfade 150 ms. |
| **Route** | "Here's where the claim goes, and why." | The final slip pill unfurls with `clip-path: inset(0 100% 0 0 round 999px)` → `inset(0)` over 600 ms; reasons stagger 90 ms (opacity + 6 px). | Appears complete. |
| **Ride** | "You are here in the call." | The play button rides the playhead (left tween 120 ms linear while playing); shrinks 84 → 60 px when started (200 ms). | Button stays at the start; a static cursor marks the position. |
| Page change | Moving between dock destinations. | Content fades and rises 8 px (180 ms); the dock never moves. View Transitions where supported. | Instant. |

Rules: one moving thing per region at a time; live waveforms pause when off-screen (`useIntersectionObserver`) or when the tab is hidden (`useDocumentVisibility`); `prefers-reduced-motion` and an in-app "Reduce motion" setting both apply (`useReducedMotion` from motion-v or VueUse `usePreferredReducedMotion`).

---

## 10. Signature interactions

1. **Where did we hear that?** Click any claim-file value and the transcript scrolls to its words, lights them, and plays the 3-second clip; click any underlined phrase and its field lights. Every value without a heard source says where it came from ("from the policy", "claim history").
2. **The line desk: Listen · Whisper · Take over.** Listen puts the line in the dock and keeps playing as you move around the app. Whisper sends ClaimVoice a typed note it acts on next turn; the caller never hears it. Take over confirms in a sheet, then a cobalt voice joins the waveform and ClaimVoice switches to "taking notes".
3. **Card numbers are never taken (Hush).** The moment a caller starts reading digits, ClaimVoice interrupts, the digits become "■■■■ removed", and the stored recording has a hatched silent gap. The same visual appears on the landing, the live call, the claim file and the QA rubric.
4. **Route reveal with reasons.** At hang-up the last pill unfurls into the route and three plain reasons, each linked to a moment; **Change with a reason** is always next to **Accept route**.
5. **Ring the demo line.** A live browser call from the landing, with captions, a typed fallback and French.

---

## 11. Waveforms and audio

**One grammar everywhere:** a horizontal centre line; **ClaimVoice and Larkspur people above, the caller below**; bars 3 px wide, 2 px gap, fully rounded; played portion full colour, unplayed 32%; hush = hatched band + dotted line.

**Live audio (Web Audio + canvas), component `<LiveLine>`:**
- Caller side: `getUserMedia` → `AudioContext` → `MediaStreamAudioSourceNode` → `AnalyserNode` (`fftSize` 1024, `smoothingTimeConstant` 0.6). ClaimVoice side: the TTS output element or Pipecat's remote audio track → `MediaElementAudioSourceNode` / `MediaStreamAudioSourceNode` → its own analyser (and on to `destination`).
- Each frame, compute RMS from `getFloatTimeDomainData`; every 90 ms push one bar `{who, level}` into a ring buffer sized to the canvas width; draw right-to-left so the newest bar is at the right edge, older bars fading to 35%.
- Canvas sized with `devicePixelRatio`; redraw only when a bar is added; pause with `useIntersectionObserver` + `useDocumentVisibility`.
- **Switchboard lines** don't stream audio to supervisors unless they Listen: the server sends level frames over SSE (10 Hz per line: `{line, cv: 0..1, caller: 0..1, speaking: "cv"|"caller"|null}`) and the same component draws them.
- Web Speech fallback (demo line): `SpeechRecognition` `interimResults: true` drives Settle; `speechSynthesis` voices `en-CA`/`fr-CA` speak ClaimVoice's turns; the analyser still reads the mic for the orb. Where `SpeechRecognition` is missing, open the typed call.

**Recorded calls (wavesurfer.js v7), component `<CallRecording>`:**
- Store each call as **stereo: caller on the left channel, ClaimVoice/people on the right**, so lanes come for free. Generate **peaks JSON** server-side at upload (2 channels × ~800 points) and pass `peaks`, `duration`, `splitChannels` (two channel option objects: `waveColor` faint/`progressColor` caller for channel 0, faint/orchid for channel 1, `height` 58 each), `barWidth: 3`, `barGap: 2`, `barRadius: 1.5`, `cursorColor: var(--cv-orchid)`, `cursorWidth: 2`, `normalize: true`, `interact: true`.
- Draw the lanes mirrored with a `renderFunction` (ClaimVoice bars from the lane floor up, caller bars from the lane ceiling down) so the recording reads like the live line.
- **Regions plugin:** one region per turn (no fill; used for `[`/`]` navigation and transcript sync), one per **hush** (hatched content element, not draggable), one per **moment** (pin above the lanes: consent, policy found, safety, closer-look sign in amber, photos, read-back). **Timeline plugin** for minute ticks. **Hover plugin** for a time tooltip.
- Transcript sync: on `timeupdate`, find the turn containing `currentTime` and mark it current (orchid wash); clicking a turn or a source chip calls `setTime(start)` and plays 3 s for chips.
- PCI: the hushed span is silence in the stored file (cut before storage) and the region is metadata; there is nothing to "unhide".

---

## 12. How this differs

What voice-AI and contact-centre products usually do, and what ClaimVoice does instead.

| | The usual pattern | **ClaimVoice** |
|---|---|---|
| **Layout** | Sidebar + dashboard cards | **Rounded cards on porcelain; vertical channel strips; transcript ↔ claim file split; a full-width recording band** |
| **Navigation** | Left sidebar with grouped menus | **A floating aubergine pill dock at the bottom centre, which also carries the line you're on** |
| **Landing** | Dark "premium AI" hero, a glowing orb or waveform preview, then a feature grid | **A call you can hear: lyric captions in two alignments over a full-bleed mirrored waveform; values pluck into a slip; the route unfurls. Nothing auto-plays.** |
| **Home** | Greeting + KPI tiles | **The line desk: strips per live call, hand-off tray, surge ribbon, finished tickets** |
| **Transcript** | Chat bubbles, or a scrolling live transcript on the supervisor's screen | **A lyric sheet on the landing, time-gutter rows in the app, and no live transcript on the desk** |
| **Type** | One system sans | **Bricolage Grotesque (opsz) + Figtree; no serif, no mono** |
| **Colour** | Dark with a neon accent, or grey + blue | **Porcelain blush + aubergine ink + orchid magenta; caller plum, person cobalt; light default, aubergine night** |
| **Shape** | Default radii, borders | **Pills and 28 px cards, fills not borders, hatching = not kept** |
| **Motion** | Fades and a pulsing orb | **Breathe, Settle, Pluck, Ripple, Hush, Hand, Route, Ride (audio-reactive)** |
| **Density** | Medium to high, tables | **Low: 44–50 px targets, 1.5 line height, a few big things per screen** |
| **Data idiom** | Scores, gauges and sentiment meters | **Conversation waveform, heard pills with source chips, lyric captions, sentence answers, rates as "96 in 100"** |
| **Logo** | A soundwave or a microphone | **Orchid speech tile with bars rising into a tick + Bricolage "ClaimVoice"** |

The claim file's three-column body is the most conventional screen; its recording band and source chips are what make
it ClaimVoice's.

---

## 13. Implementation notes (Nuxt 3 + Tailwind 4.1)

**Packages** (pinned exact versions, built on Node 21.7): `nuxt` 3.x, `@tailwindcss/vite` 4.1.x (Tailwind via the Vite plugin in `nuxt.config.ts` → `vite.plugins`), `motion-v` (Motion for Vue), `@vueuse/core` (+ `@vueuse/nuxt`), `wavesurfer.js` 7.x (Regions, Timeline, Hover plugins ship in the package), `@nuxt/fonts` or a plain `<link>` for the Google Fonts URL in §6. No UI kit; components below are ours.

**Tokens:** the CSS variables (`:root`/`[data-theme="light"]` and `[data-theme="dark"]` blocks, plus motion tokens) live in `assets/css/tokens.css`, then map them into Tailwind:

```css
/* assets/css/main.css */
@import "tailwindcss";
@import "./tokens.css";
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme inline {
  --color-bg: var(--cv-bg);           --color-surface: var(--cv-surface);
  --color-sunk: var(--cv-sunk);       --color-sunk-2: var(--cv-sunk-2);
  --color-ink: var(--cv-ink);         --color-muted: var(--cv-muted);   --color-faint: var(--cv-faint);
  --color-orchid: var(--cv-orchid);   --color-orchid-ink: var(--cv-orchid-ink);
  --color-orchid-wash: var(--cv-orchid-wash); --color-on-orchid: var(--cv-on-orchid);
  --color-dock: var(--cv-dock);       --color-on-dock: var(--cv-on-dock);
  --color-dock-muted: var(--cv-dock-muted); --color-dock-orchid: var(--cv-dock-orchid);
  --color-caller: var(--cv-caller);   --color-caller-wash: var(--cv-caller-wash);
  --color-person: var(--cv-person);   --color-person-wash: var(--cv-person-wash);
  --color-fast: var(--cv-fast);       --color-fast-wash: var(--cv-fast-wash);
  --color-adj: var(--cv-adj);         --color-adj-wash: var(--cv-adj-wash);
  --color-siu: var(--cv-siu);         --color-siu-wash: var(--cv-siu-wash);
  --color-urgent: var(--cv-urgent);   --color-urgent-wash: var(--cv-urgent-wash);
  --font-display: "Bricolage Grotesque", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Figtree", ui-sans-serif, system-ui, sans-serif;
  --radius-pill: 999px; --radius-xl: 28px; --radius-lg: 20px; --radius-md: 14px; --radius-sm: 10px;
  --ease-voice: cubic-bezier(.2,.8,.2,1); --ease-breath: cubic-bezier(.45,0,.55,1); --ease-lift: cubic-bezier(.3,1.3,.5,1);
  --animate-breathe: breathe 3200ms var(--ease-breath) infinite;
}
```

Theme: `data-theme` on `<html>`, default `light`, stored per user (`useLocalStorage` for signed-out visitors); never follow the OS automatically on first visit (light is the deliberate default), but offer "Night line" in the account menu and on the switchboard header.

**Components:**
- Shell: `AppDock` (nav + `DockNowPlaying`), `PageHeader`, `ThemeToggle`, `LangToggle`, `CaptionsToggle`.
- Voice: `LiveLine` (canvas, analyser or SSE levels), `CallRecording` (wavesurfer wrapper), `Horizon` (landing waveform + ride button + moment labels), `LyricSheet`, `TranscriptTurn` (with `HeardSpan`, `SoundTag`, `HushPill`, `WhisperRow`), `SettleWords`, `DemoOrb`, `TypedCall`.
- Claim: `HeardPill` (value + `SourceChip`), `PendingPill`, `ClaimSection`, `ClaimSlip`, `RouteUnfurl`, `ReasonList`, `SignsList` (with the never-deny note), `PhotoTiles`, `ChangeRouteSheet`.
- Lines: `LineStrip` (`LevelMeter`, `ScriptProgress`, `AskingBox`, `StripControls`), `HandoffTray` (`WaitItem`), `SurgeRibbon`, `TakeOverSheet`, `WhisperInput`, `FinishedTickets`.
- Quality: `RubricBeads`, `ReviewPlayer`.
- Routing checks: `CheckCard`, `QuestionCard`, `BarCompare`, `FairnessDots`, `DriftColumns`, `VersionCompare`, `SignOffRow`.
- Shared: `Tag` (fast/adj/siu/urgent/orchid/plain, always icon + word), `Btn` (primary/soft/ink/quiet; sm/md), `Seg`, `Sheet`, `EmptyState`, `Skeleton`, `ErrorBanner`, an inline SVG `Icon` set (stroke 1.8, round caps; `components/CvIcon.ts`).

**Composables:** `useLiveLevels(line)` (SSE → ring buffer), `useMicLevel()` (getUserMedia + analyser), `useCallPlayback(claimId)` (wavesurfer instance, `currentTurn`, `seek`, `playClip`), `useHeardLinks()` (field ↔ span highlighting), `useDemoClock()` (reads `CLAIMVOICE_DEMO_TODAY`; every displayed date goes through it), `useReducedMotionPref()`.

**Accessibility:** captions on by default; captions region `aria-live="polite"` announcing **final** turns only (not interim words); "Read instead" renders the full transcript as an ordered list; every waveform has a text equivalent (`aria-label` with duration and moments) and the moments are real buttons; status is never colour alone; focus ring 3 px orchid, 3 px offset; the dock is a `nav` landmark; Take over and Change route are dialogs with focus traps; the French content carries `lang="fr"`.

**Copy rules (rendered text):** plain, warm, second person for callers, short declaratives for staff. Say "what we heard", "why this route", "signs worth a closer look", "routing checks", "fact sheet", "likely size". Never: LLM, model scores, SHAP, slots, prompt, pipeline, latency, fallback, confidence decimals. Express rates as "96 in 100". The forbidden-word scan run with the screenshots must stay clean.

### Changes from the first concept
1. **No chat bubbles.** The transcript is a lyric sheet on the landing (two alignments) and time-gutter rows in the app; bubbles read as every chat widget (Lemonade, Retell).
2. **One dock, not a top route bar + a bottom call dock.** Navigation and the line you're on share one floating pill, so there is one thing at the bottom of the screen, not two.
3. **The landing hero is a waveform horizon, not a centred orb.** The play button rides the call; the headline is ClaimVoice's own first line; the route is the last slip pill unfurling (no card flip, no card on the right). The orb moved to the demo-line band.
4. **Switchboard rows became vertical channel strips** (sound desk) with level meters, "ClaimVoice asked", script progress and pills, and **no live transcript** on the desk (Five9 finding).
5. **Palette tuned:** blush `#FBF6F3` → porcelain `#FBF7F9` (the beige read as old paper); added aubergine ink and dock; caller plum and person cobalt as voice colours; the chat-bubble tokens are gone; an aubergine Night line replaces a generic dark.
6. **New motions:** Settle (interim → final), Hush (card numbers), Hand (hand-off), Ride (playhead); Route is an unfurl instead of a flip.
7. **Whisper redefined** for an AI agent: a typed note ClaimVoice acts on, shown in the transcript.
8. **Routing checks** written as a regulator's questions with frequencies, not a metrics page.
9. **Logo:** the first sketch, a flower curl, is replaced by a speech tile whose bars rise into a tick.
