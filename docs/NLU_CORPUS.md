# Training sentences for the loss-type reader

The offline reader's classifier (`backend/claimvoice/nlu/model.py`, card in
[model-cards/loss-type-reader.md](model-cards/loss-type-reader.md)) learns from two sources. `make train-nlu`
rebuilds both and the model from scratch in a few seconds; the same seed gives the same sentences and the same
artifact bytes.

## 1. Generated paraphrases (`nlu/corpus.py`, word lists in `nlu/lexicon.py`)

Each sentence is `opener + hedge + clause [+ second clause] + tail`, in English or Canadian French, labelled with one
of seven classes: `collision`, `hail`, `wind`, `water`, `fire`, `theft`, or `none` (a turn that does not describe a
loss).

| Part | Examples | Why |
|---|---|---|
| Opener | "Hi, I need to report a claim.", "Yeah hi,", "Allô, bonjour." | First turns rarely start with the loss |
| Hedge | "I think", "so basically", "I'm pretty sure", "je pense que", "fait que" | Callers soften what they say |
| Clause | built per loss type from the word lists below | The description itself |
| Second clause | "and the tailgate won't close", "et des voleurs ont pris mon portefeuille" | Multi-fact first sentences |
| Tail | "last night", "about an hour ago", ", it's pretty bad", " pendant la fin de semaine" | Times and feelings |

Clause templates per loss type:

- **Collision**: *other vehicle + verb + object + place* ("a delivery van sideswiped my parked car in the Costco
  lot"), single-vehicle events ("I slid into a pole"), passives ("I got t-boned"), "my Outback got plowed into by a
  cab", plain words ("I had a fender bender"), with an optional damaged part ("and the bumper is caved in").
  French: "un camion a accroché ma voiture sur la 40", "je me suis fait emboutir", "j'ai glissé dans le fossé".
- **Water**: "there's water seeping under the baseboards", "the hot water tank let go", "my rec room is under
  water", "water is dripping through the ceiling from the dishwasher", stains, bubbling paint and warped floors.
  French: "il y a de l'eau qui s'infiltre par la fondation", "le chauffe-eau a fui", "mon sous-sol est inondé".
- **Wind**: *cause + verb + target* ("a gust of wind toppled the shed over"), falls ("a tree fell on the house"),
  "wind damage to the soffit". French: "les rafales ont arraché la gouttière".
- **Hail**: *hail + verb + target* ("golf-ball-sized hail pitted the hood"), passives, "it hailed like crazy".
- **Fire**: events ("the dryer caught fire in the laundry room") with what came after ("it's out now", "everything
  smells like smoke").
- **Theft**: *someone + verb + item + place*, entries ("thieves pried open the shed and took the snowblower"),
  passives ("my car isn't where I parked it"). French: "on s'est fait cambrioler", "on m'a volé mon vélo".

The `none` class covers the other turns of a call: consent answers, policy numbers, dates of birth, postal codes,
safety answers ("No one was hurt, no gas, no smoke"), times and dates, places, generic openings ("I need to report
some damage", "Something happened to my car"), questions, requests for a person and read-back replies. It is what lets
the line tell an opening statement from everything else and keeps "Everyone's fine, nothing dangerous" from being
read as a fire.

Volumes: 1,100 sentences per loss type in English and 550 in French, and 1.6 times that for `none` (12,540 in all).

### Out-of-lexicon validation

Every word list is split by a stable hash of each entry: one entry in five goes to validation. Training sentences are
built only from the training share and validation sentences only from the validation share, so the validation verbs,
objects, causes, places and openers are words the model has never seen in that role. The temperature and both
thresholds are fitted on these sentences. This is deliberately harsher than real calls (a held-back entry might be the
only way a list says "wind"), so the accuracy it reports is a floor, not a forecast.

## 2. The main scripted callers' turns

`scripted_turns()` plays the 38 callers in `eval/callers/*.yml` through the engine with the rules-only reader and
labels each caller turn from the call itself: the opening takes the caller's expected loss type; turns the engine
placed in consent, identity, safety, photos, coverage, read-back or wrap-up are `none` (unless the rules hear a loss
type in them); turns about the loss details are left out. That adds 290 real-shaped turns.

## What is never in it

- The held-out caller sets (`eval/callers/held_out*/`): `load_callers` only reads the top folder, and a test checks
  that no held-out turn of four words or more appears in the generated sentences.
- Anything from a real call. Every sentence is synthetic or comes from the scripted callers.

## How the lists were written, and an honest note

The lists come from claims-intake practice: first-notice-of-loss forms, adjuster checklists and the common causes of
loss in Alberta, Québec and Colorado. The second held-out set (`held_out_2`) was used for development: its misses
(open wording such as "a pickup clipped my car" or "mon lave-vaisselle a débordé") showed which kinds of wording were
missing, so it is reported as a development set. The third set (`held_out_3`) was written and committed before any of
this, by the same team; to keep its number honest, entries that would only echo its wording were left out of the lists
on purpose, and it was scored once, at the end.
