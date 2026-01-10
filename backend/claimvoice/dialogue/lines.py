"""Every fixed line ClaimVoice speaks, in English and Canadian French. The engine never improvises: a spoken turn is a
line from here, a question from the loss type's script, or a read-back built from values the caller gave."""

from __future__ import annotations

LINES: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "{org} claims, this is ClaimVoice, an automated assistant. {announcement} Is that okay?",
        "fr": "Sinistres {org}, ici ClaimVoice, un assistant automatisé. {announcement} Êtes-vous d'accord?",
    },
    "greeting_asked": {
        "en": "{org} claims, this is ClaimVoice, an automated assistant. {announcement}",
        "fr": "Sinistres {org}, ici ClaimVoice, un assistant automatisé. {announcement}",
    },
    "bilingual_hint": {
        "en": "Pour le français, répondez simplement en français.",
        "fr": "For English, just answer in English.",
    },
    "consent_reask": {
        "en": "Before we go on, is it okay that this call is recorded?",
        "fr": "Avant de continuer, êtes-vous d'accord pour que cet appel soit enregistré?",
    },
    "sorry_loss": {"en": "I'm sorry to hear that.", "fr": "Je suis désolée d'apprendre ça."},
    "thanks": {"en": "Thank you.", "fr": "Merci."},
    "consent_refused": {
        "en": "Understood. I've stopped recording, and I'll only keep notes for your claim. Would you like to speak "
        "with a person instead, or shall we carry on together?",
        "fr": "Je comprends. J'ai arrêté l'enregistrement et je ne garderai que des notes pour votre réclamation. "
        "Voulez-vous parler à une personne, ou on continue ensemble?",
    },
    "carry_on": {"en": "Okay, let's carry on.", "fr": "D'accord, on continue."},
    "ask_policy": {
        "en": "What's your policy number, or the phone number on your policy?",
        "fr": "Quel est votre numéro de police, ou le numéro de téléphone inscrit à votre police?",
    },
    "policy_not_found": {
        "en": "I couldn't find that policy. Could you read the policy number again, slowly?",
        "fr": "Je n'ai pas trouvé cette police. Pouvez-vous me redonner le numéro de police, lentement?",
    },
    "lookup_slow": {
        "en": "One moment while I pull up your policy.",
        "fr": "Un instant, je retrouve votre police.",
    },
    "lookup_failed": {
        "en": "I'm having trouble reaching our records. Could you give me the policy number once more?",
        "fr": "J'ai de la difficulté à joindre nos dossiers. Pouvez-vous me redonner le numéro de police?",
    },
    "ask_identity": {
        "en": "Thanks, {first}. To confirm it's you, what's your date of birth, or the {postal} on the policy?",
        "fr": "Merci, {first}. Pour confirmer votre identité, quelle est votre date de naissance, ou le code "
        "postal inscrit à votre police?",
    },
    "identity_mismatch": {
        "en": "That doesn't match what I have. Could you try your date of birth, or the {postal}?",
        "fr": "Ça ne correspond pas à ce que j'ai. Pouvez-vous essayer votre date de naissance, ou le code postal?",
    },
    "identity_ok": {"en": "Thank you, that matches.", "fr": "Merci, ça correspond."},
    "ask_safety": {
        "en": "Before anything else: is everyone safe, and is anything dangerous right now, like a smell of gas, "
        "smoke, or water near the electrical panel?",
        "fr": "Avant toute chose : est-ce que tout le monde est en sécurité, et y a-t-il un danger en ce moment, "
        "comme une odeur de gaz, de la fumée ou de l'eau près du panneau électrique?",
    },
    "safety_clarify": {
        "en": "Just to be sure: is anyone hurt?",
        "fr": "Juste pour être certaine : quelqu'un est-il blessé?",
    },
    "injury_care": {
        "en": "I'm sorry you're hurt. If you need medical care, please don't wait: call 911 or see a doctor.",
        "fr": "Je suis désolée que vous soyez blessé. Si vous avez besoin de soins, n'attendez pas : appelez le 911 "
        "ou consultez un médecin.",
    },
    "glad_safe": {"en": "I'm glad everyone's okay.", "fr": "Je suis contente que tout le monde aille bien."},
    "ask_loss": {"en": "Tell me what happened.", "fr": "Racontez-moi ce qui s'est passé."},
    "ask_loss_confirm": {
        "en": "Just so I have it right: is this about {loss}?",
        "fr": "Pour être certaine de bien comprendre : est-ce que c'est {loss}?",
    },
    "ask_loss_choices": {
        "en": "I want to get this right. Was it a collision, wind or hail, water, a fire, or a theft?",
        "fr": "Je veux bien comprendre. Est-ce une collision, du vent ou de la grêle, un dégât d'eau, un incendie "
        "ou un vol?",
    },
    "storm_confirmed": {
        "en": "I can see the {event} on our weather records.",
        "fr": "Je vois l'événement météo dans nos dossiers : {event}.",
    },
    "not_caught": {"en": "Sorry, I didn't catch that.", "fr": "Désolée, je n'ai pas bien compris."},
    "noted": {"en": "Thanks, I've noted that.", "fr": "Merci, c'est noté."},
    "changed": {"en": "Thanks, I've changed that to {value}.", "fr": "Merci, j'ai corrigé : {value}."},
    "card_number": {
        "en": "Please stop there. I never take card numbers on this line, and that part of the recording is "
        "removed. You won't need to pay anything on this call.",
        "fr": "Arrêtez-vous là, s'il vous plaît. Je ne prends jamais de numéros de carte sur cette ligne, et cette "
        "partie de l'enregistrement est retirée. Vous n'avez rien à payer pendant cet appel.",
    },
    "ask_photos": {
        "en": "I can text you a link to upload photos of the damage when it's light and safe. Should I send it to "
        "the number ending in {last4}?",
        "fr": "Je peux vous texter un lien pour téléverser des photos des dommages quand il fera clair et que ce "
        "sera sécuritaire. Est-ce que je l'envoie au numéro qui se termine par {last4}?",
    },
    "ask_photos_number": {
        "en": "I can text you a link to upload photos of the damage. What number should I send it to?",
        "fr": "Je peux vous texter un lien pour téléverser des photos des dommages. À quel numéro dois-je l'envoyer?",
    },
    "photos_other_number": {
        "en": "Would you like it at another number, or no photos for now?",
        "fr": "Voulez-vous le recevoir à un autre numéro, ou pas de photos pour l'instant?",
    },
    "photos_sent": {"en": "Done, the link is on its way.", "fr": "C'est fait, le lien est envoyé."},
    "photos_failed": {
        "en": "I couldn't send the text just now. Your adjuster will send the link instead.",
        "fr": "Je n'ai pas pu envoyer le texto. Votre expert en sinistres vous enverra le lien.",
    },
    "photos_declined": {"en": "No problem.", "fr": "Pas de problème."},
    "coverage_check": {"en": "Does that make sense so far?", "fr": "Est-ce que ça va jusqu'ici?"},
    "coverage_fallback": {
        "en": "Your adjuster will go through your coverage with you. I can't make a decision on the claim.",
        "fr": "Votre expert en sinistres passera votre couverture en revue avec vous. Je ne peux pas prendre de "
        "décision sur la réclamation.",
    },
    "read_back": {
        "en": "Here's what I have: {summary}. Is that right?",
        "fr": "Voici ce que j'ai noté : {summary}. Est-ce exact?",
    },
    "read_back_fix": {"en": "What should I change?", "fr": "Qu'est-ce que je dois corriger?"},
    "read_back_rest": {"en": "Is everything else right?", "fr": "Le reste est-il exact?"},
    "claim_number": {
        "en": "Your claim number is {number}. {next_steps} Is there anything else I can help with?",
        "fr": "Votre numéro de réclamation est le {number}. {next_steps} Puis-je vous aider avec autre chose?",
    },
    "next_property": {
        "en": "An adjuster will call you within one business day.",
        "fr": "Un expert en sinistres vous appellera d'ici un jour ouvrable.",
    },
    "next_property_surge": {
        "en": "Because of the storm, an adjuster will call you within two business days.",
        "fr": "En raison de la tempête, un expert en sinistres vous appellera d'ici deux jours ouvrables.",
    },
    "next_auto": {
        "en": "An adjuster will call you within one business day about repairs and a rental if you need one.",
        "fr": "Un expert en sinistres vous appellera d'ici un jour ouvrable pour les réparations et, au besoin, "
        "un véhicule de location.",
    },
    "goodbye": {
        "en": "Thank you for calling {org}, {first}. Take care.",
        "fr": "Merci d'avoir appelé {org}, {first}. Prenez soin de vous.",
    },
    "goodbye_noted": {
        "en": "I've noted that for your adjuster. Thank you for calling {org}, {first}. Take care.",
        "fr": "Je l'ai noté pour votre expert en sinistres. Merci d'avoir appelé {org}, {first}. Prenez soin de vous.",
    },
    # hand-offs
    "handoff_asked": {
        "en": "Of course. I'm connecting you with a person now. I'll pass on what you've told me, so you won't "
        "have to repeat it.",
        "fr": "Bien sûr. Je vous mets en contact avec une personne. Je lui transmets ce que vous m'avez dit pour "
        "que vous n'ayez pas à le répéter.",
    },
    "handoff_urgent_gas": {
        "en": "I'm sorry, that sounds frightening. Please leave the house now, don't use light switches, and call 911 "
        "from outside. I'm bringing in a "
        "person from Larkspur right away. Please stay on the line.",
        "fr": "Je suis désolée, ça doit être inquiétant. Sortez de la maison maintenant, ne touchez pas aux "
        "interrupteurs et appelez le 911 de l'extérieur. "
        "Je fais venir une personne de Larkspur tout de suite. Restez en ligne.",
    },
    "handoff_urgent": {
        "en": "I'm sorry, that sounds frightening. Please get to safety now and call 911. I'm bringing in a person "
        "from Larkspur right away. Please stay "
        "on the line.",
        "fr": "Je suis désolée, ça doit être inquiétant. Mettez-vous en sécurité maintenant et appelez le 911. "
        "Je fais venir une personne de Larkspur tout "
        "de suite. Restez en ligne.",
    },
    "handoff_distress": {
        "en": "That sounds like a lot to deal with. I'm bringing in a person from Larkspur to help you. You don't "
        "have to repeat anything.",
        "fr": "Ça fait beaucoup à gérer. Je fais venir une personne de Larkspur pour vous aider. Vous n'aurez rien "
        "à répéter.",
    },
    "handoff_low_confidence": {
        "en": "I'm sorry, I'm having trouble understanding. Let me bring in a person who can help.",
        "fr": "Je suis désolée, j'ai de la difficulté à comprendre. Je fais venir une personne qui pourra vous aider.",
    },
    "handoff_identity": {
        "en": "I wasn't able to confirm the policy, so I'm bringing in a person who can help.",
        "fr": "Je n'ai pas pu confirmer la police, alors je fais venir une personne qui pourra vous aider.",
    },
    "handoff_tool": {
        "en": "I can't reach our records right now, so I'm bringing in a person to help.",
        "fr": "Je n'arrive pas à joindre nos dossiers, alors je fais venir une personne pour vous aider.",
    },
    "handoff_consent": {
        "en": "Of course. I'm connecting you with a person now, without recording.",
        "fr": "Bien sûr. Je vous mets en contact avec une personne, sans enregistrement.",
    },
    "waiting": {
        "en": "A person from Larkspur will be with you shortly. You don't need to repeat anything.",
        "fr": "Une personne de Larkspur sera avec vous sous peu. Vous n'avez rien à répéter.",
    },
    "callback_offer": {
        "en": "Everyone is busy right now. Would you like a call back within the hour, or shall I finish your claim "
        "with you now?",
        "fr": "Tout le monde est occupé en ce moment. Voulez-vous qu'on vous rappelle d'ici une heure, ou je "
        "termine votre réclamation avec vous maintenant?",
    },
    "callback_booked": {
        "en": "Okay, someone from Larkspur will call you back within the hour. Take care.",
        "fr": "D'accord, une personne de Larkspur vous rappellera d'ici une heure. Prenez soin de vous.",
    },
    "back_with_line": {"en": "Thanks for waiting. Let's carry on.", "fr": "Merci d'avoir patienté. On continue."},
    "silence": {"en": "Are you still there?", "fr": "Êtes-vous toujours là?"},
    "silence_end": {
        "en": "I haven't heard anything, so I'll end the call. Please call back any time.",
        "fr": "Je n'entends plus rien, alors je vais mettre fin à l'appel. Rappelez-nous en tout temps.",
    },
    "language_switched": {"en": "Sure, let's continue in English.", "fr": "Bien sûr, on continue en français."},
    "whisper_question": {"en": "One more question: {question}", "fr": "Une autre question : {question}"},
    # off-script answers (fixed; then the pending question again)
    "faq_robot": {
        "en": "Yes, I'm ClaimVoice, Larkspur Mutual's automated assistant. You can ask for a person at any time.",
        "fr": "Oui, je suis ClaimVoice, l'assistant automatisé de Larkspur Mutual. Vous pouvez demander à parler à "
        "une personne en tout temps.",
    },
    "faq_premium": {
        "en": "I can't say how a claim affects your premium. Your adjuster can talk that through with you.",
        "fr": "Je ne peux pas dire comment une réclamation touche votre prime. Votre expert en sinistres pourra en "
        "parler avec vous.",
    },
    "faq_covered": {
        "en": "I can't decide coverage on this call. I'll go over the basics shortly, and your adjuster confirms it.",
        "fr": "Je ne peux pas décider de la couverture pendant cet appel. Je vais vous expliquer l'essentiel, et "
        "votre expert en sinistres confirmera.",
    },
    "faq_deductible": {
        "en": "I'll mention the deductible your policy shows in a moment, and your adjuster confirms it.",
        "fr": "Je vais vous indiquer la franchise prévue à votre police dans un instant; votre expert en sinistres "
        "la confirmera.",
    },
    "faq_rental": {
        "en": "If your policy includes a rental car, your adjuster will set it up.",
        "fr": "Si votre police comprend un véhicule de location, votre expert en sinistres s'en occupera.",
    },
    "faq_contractor": {
        "en": "You can choose your own contractor. Please keep receipts for any emergency repairs.",
        "fr": "Vous pouvez choisir votre propre entrepreneur. Gardez les reçus de toute réparation d'urgence.",
    },
    "faq_timeline": {
        "en": "Most claims like this get a call back within one business day.",
        "fr": "La plupart des réclamations comme la vôtre reçoivent un rappel d'ici un jour ouvrable.",
    },
    "faq_next": {
        "en": "I'll finish a few questions, give you a claim number, and an adjuster will call you.",
        "fr": "Je termine quelques questions, je vous donne un numéro de réclamation, et un expert en sinistres "
        "vous appellera.",
    },
    "faq_other": {
        "en": "That's a good question for your adjuster. I'll note it so they can follow up.",
        "fr": "C'est une bonne question pour votre expert en sinistres. Je la note pour qu'il fasse le suivi.",
    },
}

EMPATHY_MARKERS: tuple[str, ...] = (
    "i'm sorry",
    "i'm glad",
    "that sounds",
    "thanks for waiting",
    "take care",
    "je suis désolée",
    "je suis contente",
    "ça fait beaucoup",
    "prenez soin",
    "merci d'avoir patienté",
)


def line(key: str, language: str, **values: str) -> str:
    text = LINES[key]["fr" if language == "fr" else "en"]
    if not values:
        return text
    out = text.format(**values)
    return out.replace("..", ".").replace(".?", "?").replace(" ,", ",")


def both(key: str, **values: str) -> tuple[str, str]:
    """(English, French) for a line; the English goes in `text_en` under French turns."""
    return line(key, "en", **values), line(key, "fr", **values)
