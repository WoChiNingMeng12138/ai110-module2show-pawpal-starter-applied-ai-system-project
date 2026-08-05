# Model Card: PawPal+ AI Care Advisor
---

## Limitations and Bias

- **The knowledge base is narrow, and it hasn't been reviewed by an actual expert.** `knowledge_base/sample_care_guide.txt` is a single file I put together myself. It only covers dogs and cats, and it's based on general, common-knowledge care advice — not something written or checked by a veterinarian. Anyone treating this as "professional advice" is trusting the knowledge base for more than it actually is.

- **There's no real content for "other" species at all.** The pet-species dropdown in the app lets you pick "other," but the knowledge base has nothing about birds, reptiles, or anything besides dogs and cats. In that case, the retriever still returns whatever dog or cat passage is closest by embedding distance — it doesn't say "no answer available," it gives an answer that *looks* reasonable but is for the wrong species. That's arguably worse than an outright error, because the user has no obvious way to notice it.

- **Retrieval works on chunk-level similarity, not full understanding.** If a pet's specific situation — say, "on medication" and "has allergies" — is split across different paragraphs in the knowledge base, the retriever only pulls the top 3-4 most similar chunks each time. It might catch one part of that situation and miss the other, so the generated care plan can end up incomplete.

- **The age field is ambiguous.** `Pet.age` is just an integer, and the UI lets you enter 0 to mean "under 1 year old" — but that's a convention I made up for the README examples, not something the code actually enforces. The retrieval query just concatenates that integer into a string, so a 3-month-old puppy and an 11-month-old puppy get treated identically.

---

## Potential Misuse & Mitigations

**The most realistic misuse risk here isn't someone attacking the system — it's someone trusting it too much.** Specifically:

1. **Cost abuse from unlimited clicking.** The "Generate AI care plan" button has no rate limiting right now — a user could click it repeatedly in a short time and burn through API quota. That's not an urgent problem at the current scale (a local, single-user app), but a multi-user deployment would need a per-user rate limit before going live.

---

## What Surprised Me While Testing Reliability

- **The biggest surprise was how much harder it was to mock Anthropic's exceptions than I expected.** I assumed I could just throw together a fake `anthropic.APIStatusError` with `unittest.mock` and be done with it. It turned out the constructor actually requires a real `httpx.Response` object (and, underneath that, a real `httpx.Request`) — you can't just pass it a plain string message. Lesson: the more "self-explanatory" an exception class looks, the more likely it is carrying real HTTP context that can't be faked casually. Checking `inspect.signature()` before writing the test would have saved a round of trial and error.

- **ChromaDB's default embedding function downloads an ~80MB ONNX model the first time it runs.** I hadn't expected that — "local vector database" sounded like it should mean fully offline, but the default setup still needs a network connection the first time it's used, just to fetch the model weights. This is the concrete thing behind the "a bit of extra startup overhead" line in the Design Decisions section of the README.

---

## AI Collaboration Reflection

### A helpful suggestion

**Using `output_config.format`'s JSON schema for structured output, instead of "let the model write free text, then parse it by hand."** The obvious first instinct is to have the model write a paragraph of advice, then separately describe a task list, and pull out each field with a regex or some basic string splitting. Structured output (adopted after checking the Claude API documentation) sidesteps that whole category of problem — the model might phrase a duration or frequency slightly differently each time, and none of that matters, because the API guarantees the response is valid JSON matching the schema.

### A flawed or incorrect suggestion

**When I first designed the JSON schema for the `preferred_time` field, I wrote `"type": ["string", "null"]`** — a type array meaning "this can be a string, or it can be null." That's a completely normal, common pattern in general JSON Schema usage, and it looked fine at a glance. But Anthropic's structured output feature doesn't actually support union types written as a type array — the only supported way to express that is `anyOf: [{"type": "string"}, {"type": "null"}]`. If I hadn't gone back and re-checked the Claude API documentation's "JSON Schema Limitations" section before writing the code, this schema would have caused the request to fail validation the moment it was actually called. This is a good example of a suggestion that's reasonable in general, but wrong for this specific API — a reminder that even my own suggestions need to be checked against the actual documentation when they touch API-specific behavior, rather than trusting general experience with "how JSON Schema usually works."
