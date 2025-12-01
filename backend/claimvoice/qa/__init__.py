"""Call quality: every call is scored against the rubric (rules first, plus a language check through the LLM
adapter, fake by default); low scores and disagreements go to the supervisor review queue."""
