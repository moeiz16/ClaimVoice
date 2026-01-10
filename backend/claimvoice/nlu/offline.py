"""The offline reader (LLM_FAKE=true, the default): the rules, with a learned loss-type classifier for open wording.

The rules (`nlu.fake`, `nlu.extract`) answer first: intents, safety and distress, and every value with its span. When
the stage is still waiting to learn what happened and the rules heard no loss type, the classifier (`nlu.model`)
reads the turn:

- at or above its `accept` threshold the loss type is taken, with the span of the word that decided it;
- between `confirm` and `accept` it is offered as a candidate: the line asks "is this about water damage?" and only
  a yes keeps it;
- below `confirm`, or when the model says the turn isn't a description at all, nothing is added and the line asks
  which kind of loss it was.

Both thresholds were fitted on out-of-lexicon validation sentences (docs/model-cards/loss-type-reader.md). The model
never sees or decides the stage; it only proposes a value inside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from claimvoice.dialogue.slots import display
from claimvoice.nlu.base import Intent, NluRequest, NluResult, SlotValue
from claimvoice.nlu.fake import FakeUnderstanding
from claimvoice.nlu.lexicon import NONE
from claimvoice.nlu.model import LossTypeModel, loaded

# Stages where "what happened" can still be unknown: the opening (during consent), identity, safety and the question.
OPEN_STAGES = frozenset({"consent", "identity", "safety", "loss_type"})
_SKIP_INTENTS = frozenset({Intent.HANDOFF_REQUEST, Intent.REPEAT, Intent.GOODBYE})
MIN_WORDS = 3


@dataclass
class OfflineUnderstanding:
    """Rules first, the learned loss-type classifier for what they miss. `use_model=False` is the rules alone."""

    extra_urgent_keywords: tuple[str, ...] = ()
    use_model: bool = True
    model: LossTypeModel | None = None
    rules: FakeUnderstanding = field(init=False)

    def __post_init__(self) -> None:
        self.rules = FakeUnderstanding(self.extra_urgent_keywords)
        if self.use_model and self.model is None:
            self.model = loaded()

    async def understand(self, request: NluRequest) -> NluResult:
        return self.understand_sync(request)

    def understand_sync(self, request: NluRequest) -> NluResult:
        base = self.rules.understand_sync(request)
        if self.model is None or not self._wants_loss_type(request, base):
            return base
        text = request.utterance
        pred = self.model.predict(text)
        if pred.label == NONE:
            return base
        span = pred.cue or (0, len(text.rstrip()))
        value = SlotValue(
            "loss_type",
            pred.label,
            display("loss_type", pred.label, request.language),
            round(pred.probability, 3),
            span,
        )
        if pred.probability >= self.model.thresholds["accept"]:
            intent = Intent.ANSWER if base.intent is Intent.UNKNOWN else base.intent
            return replace(base, intent=intent, slots=(*base.slots, value), source="model")
        if pred.probability >= self.model.thresholds["confirm"]:
            return replace(base, candidates=(value,))
        return base

    @staticmethod
    def _wants_loss_type(request: NluRequest, base: NluResult) -> bool:
        if request.loss_type or request.stage not in OPEN_STAGES:
            return False
        if not any(s.key == "loss_type" for s in request.expecting):
            return False
        if any(v.key == "loss_type" for v in base.slots) or base.intent in _SKIP_INTENTS or base.urgent_safety:
            return False
        return len(request.utterance.split()) >= MIN_WORDS
