# PawPal+: AI Smart Pet Care Scheduler

## Original Project

This project builds on the course starter project, **PawPal+ (Module 2 Project)**. The starter's goal was to design and build a Streamlit app that helps pet owners plan daily care tasks for their pets. Its core features include sorting tasks by priority or fixed time, generating a daily schedule based on available time, automatically renewing recurring tasks (daily/weekly), and detecting and explaining schedule conflicts. The original object-oriented design (`Owner`, `Pet`, `Task`, `Scheduler`, `DailyPlan`, and other classes) lives in `pawpal_system.py` and connects to the Streamlit frontend through `app.py`.

On top of that, this project adds a **stretch feature**: a **RAG (Retrieval-Augmented Generation) "smart pet care advisor."** With one click, it generates personalized care advice and a structured task list based on a pet's species, age, and notes, which the user can accept as real, schedulable `Task` objects.

---

## Title and Summary

**PawPal+ AI Care Advisor: turning a static care guide into a schedule you can actually act on.**

Here's why this matters. Most pet owners already know the basics — "dogs need walks," "cats need a clean litter box" — but they usually don't know the right frequency, duration, or priority to assign, and they don't have time to read through a care guide and turn it into individual tasks by hand. PawPal+'s core scheduler already turns tasks into a conflict-free, explainable daily plan. What the new RAG advisor adds is a solution to the step *before* that: where do the tasks come from in the first place? It takes unstructured care knowledge (plain-text care guides) and turns it into structured, schedulable task suggestions, while still keeping a plain-language explanation so the user understands *why* something was suggested — instead of treating the AI as an opaque black box.

---

## Architecture Overview

The system diagram is in [`diagrams/rag_architecture.mmd`](diagrams/rag_architecture.mmd). Here's the short version:

```
User clicks "Generate AI care plan"
        ↓
[Retriever]
knowledge_base/*.txt care guides
   → split into chunks by paragraph
   → stored in a local, persistent ChromaDB vector store
   → queried using "species + age + notes" to pull the most relevant passages
        ↓
[Agent: rag_advisor.py]
   → assembles the prompt (system instructions + retrieved context + pet info)
   → calls Claude (claude-opus-5, with structured JSON-schema output)
   → raises an exception if the API call fails or is refused
        ↓
[Output]
   → plain-language care advice
   → a structured task list (description / duration / priority / frequency / required / preferred_time)
        ↓
[Integration back into pawpal_system.py]
   → each task dictionary is mapped to a real Task instance
        ↓
[Human / reviewer checkpoint]
   → the user sees the advice and the proposed task table in the UI first
   → tasks are only written to Pet.tasks after the user clicks "Add these tasks to the schedule"
   → any API error shows up as a clean st.error message instead of crashing or silently adding bad data
```

Why split it into these three pieces:
- **Retriever** — handles "where does the knowledge come from." Keeping it separate from the model call means the knowledge base can be swapped out or expanded later without touching the calling logic.
- **Agent (`rag_advisor.py`)** — handles "how to ask, and how to constrain the output format." It's the only module that talks to the Claude API directly.
- **Human checkpoint** — this is a deliberate gate. AI-generated content is always shown before it's saved. Nothing the AI generates gets written into the real schedule without the user explicitly confirming it first.

---

## Setup Instructions

1. **Clone or open the project folder**, then create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Besides the original `streamlit` and `pytest`, `requirements.txt` now also includes `anthropic` (the Claude API SDK), `chromadb` (a local vector database), and `python-dotenv` (for reading the API key from a `.env` file).

2. **Set your Claude API key** (needed for the RAG advisor):

   Create a `.env` file in the project root (this file should never be committed to version control) and add:

   ```
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

   If the key isn't set, the AI advisor will show a clean `st.error` message ("ANTHROPIC_API_KEY is not set") when you click the generate button — but this **won't affect anything else in the app**. The original manual scheduling, task management, and conflict detection all work completely independently of the RAG feature.

3. **(Optional) Check the knowledge base**: `knowledge_base/sample_care_guide.txt` is a built-in example care guide covering feeding, walking/play, grooming, and medication basics for dogs and cats. The first time you run the app, `rag_advisor.py` automatically reads every `.txt` file in that folder, splits them into chunks, and builds a local, persistent Chroma vector store (saved under `.chroma_store/`, built only once). You can drop more `.txt` care guides into that folder to expand the knowledge base.

4. **Run the app**:

   ```bash
   streamlit run app.py
   ```

   Once it's open in your browser: add a pet under "Adding a Pet" first, then go to the new "**AI Smart Care Plan**" section, pick that pet, and click "Generate AI care plan."

5. **Run the tests**:

   ```bash
   python -m pytest
   ```

   (These tests cover the core scheduler logic only — they don't need a network connection or an API key. See the "Testing Summary" section below.)

---

## Interaction Examples

> A note on these examples: they show the expected **structure** and **typical content** the system should produce for a given input, based on the prompt design and the JSON schema enforced through `output_config.format`. The machine used for development doesn't have a real `ANTHROPIC_API_KEY` configured, so these aren't captured from an actual API call. Once you have a key set up, run it yourself and consider swapping in the real output here as final evidence that the system works end to end.

### Example 1: a healthy 3-year-old dog, no special notes

**Input (a `Pet` object):**
```
name = "Mochi"
species = "dog"
age = 3
notes = ""
```

**Retrieved context (excerpt):** matches the "Dog Care Basics" section of `sample_care_guide.txt`, specifically the parts about daily walk length, feeding frequency, and grooming schedule.

**AI output (structured JSON, mapped to 3 Task objects):**
```json
{
  "advice": "Mochi is a healthy adult dog. Focus on two walks a day (morning and evening, 20-30 minutes each) for weight and mental stimulation, twice-daily feeding roughly 12 hours apart, and weekly brushing since no long-haired grooming needs were noted.",
  "tasks": [
    {"description": "Morning + evening walk", "duration_minutes": 25, "priority": 1, "frequency": "daily", "required": true, "preferred_time": null},
    {"description": "Feed breakfast and dinner", "duration_minutes": 10, "priority": 1, "frequency": "daily", "required": true, "preferred_time": null},
    {"description": "Brush coat", "duration_minutes": 10, "priority": 2, "frequency": "weekly", "required": false, "preferred_time": null}
  ]
}
```

### Example 2: an 8-month-old indoor kitten

**Input:**
```
name = "Luna"
species = "cat"
age = 0  (under 1 year — the example uses 0 to represent "less than a year old")
notes = "indoor only"
```

**Retrieved context (excerpt):** matches the "Cat Care Basics" section, specifically the parts about smaller, more frequent meals for kittens and daily interactive play for indoor-only cats.

**AI output (example):**
```json
{
  "advice": "As a kitten under 1 year that is indoor-only, Luna needs more frequent, smaller meals and daily interactive play to prevent boredom-driven behavior since she has no outdoor stimulation.",
  "tasks": [
    {"description": "Small meals (3-4x/day)", "duration_minutes": 10, "priority": 1, "frequency": "daily", "required": true, "preferred_time": null},
    {"description": "Scoop litter box", "duration_minutes": 5, "priority": 1, "frequency": "daily", "required": true, "preferred_time": null},
    {"description": "Interactive wand-toy play session", "duration_minutes": 15, "priority": 2, "frequency": "daily", "required": true, "preferred_time": null}
  ]
}
```

### Example 3: a senior dog on medication (an edge case)

**Input:**
```
name = "Bruno"
species = "dog"
age = 10
notes = "on daily thyroid medication, senior, needs monitoring"
```

**Expected behavior:** because the notes mention "on medication," the retriever should pull up the guide's note that "medication should be given at the same time every day." The prompt instructs the model to give higher priority — and a fixed `preferred_time` where relevant — to any pet whose notes mention medication or monitoring. So the medication task should come back marked `priority: 1`, `required: true`, and with a real `preferred_time` (like `"08:00"`) instead of `null`. This is the key test case for checking whether the prompt's constraints actually shape the output, not just its format.

**If the API key is missing or the request fails:** the UI shows `st.error("Could not generate an AI care plan: ANTHROPIC_API_KEY is not set...")`. Nothing crashes, and no task gets added to the schedule by mistake.

---

## Design Decisions

1. **Why use ChromaDB for local retrieval instead of just stuffing the whole care guide into the prompt?**
   The care guide could eventually grow to cover dozens of species and hundreds of pages. Sending all of that in every request wastes tokens, slows things down, and pulls the model's attention toward content that isn't relevant to the pet in question. Retrieving just the 3-4 most relevant passages keeps costs down and keeps Claude's advice focused. The tradeoff: it adds another moving part (Chroma plus a local ONNX embedding model), and the first run needs to download that embedding model and build an index, which adds a bit of startup time and one more dependency to manage.

2. **Why use structured output (`output_config.format`) instead of letting the model write free text and parsing it afterward?**
   The first version had the model write advice, then describe the task list separately, with a regex or basic string parsing pulling out the task fields. That turned out to be fragile — the model would occasionally phrase durations or frequencies differently, and the parsing would break. Switching to a single call with a JSON schema that locks down the shape of "advice + tasks" means the output is guaranteed to be valid JSON every time, with no need for fallback parsing or retries. The tradeoff: this only works with a model that supports structured output (like `claude-opus-5`), and the schema itself needs more care — for example, `preferred_time` needed `anyOf: [string, null]` instead of a simple optional field.

3. **Why require a human confirmation step instead of adding the tasks to the schedule right away?**
   This is probably the most important design decision in the whole project. The AI's advice is based on a limited knowledge base and a short pet description — it's not a substitute for real veterinary judgment. Users should get to see what the AI suggested and which tasks it wants to add *before* any of it actually affects their schedule. That's why the UI splits "generate" and "add to schedule" into two separate buttons: the generated result is held in `st.session_state` and shown to the user first, and `Pet.add_task()` is only called once the user explicitly clicks the second button. The tradeoff is one extra click, but that friction is intentional — it stops AI output from being accepted without a second look.

4. **Why keep all the RAG code in its own `rag_advisor.py` instead of folding it into `pawpal_system.py`?**
   `pawpal_system.py` is a pure, network-free scheduling layer, and its correctness is fully backed by the existing 18 pytest cases. Keeping the AI/network calls in a separate module means the core scheduler doesn't get harder to test just because it now has to deal with API keys and network failures. Any failure in `rag_advisor.py` bubbles up to the UI as one controlled `RAGAdvisorError`, without touching the scheduler's own error handling.

5. **Why `claude-opus-5` instead of a cheaper model?**
   The care advice directly shapes real decisions about a pet's care — especially in cases involving medication or monitoring an older pet — so a wrong suggestion is genuinely costly. That's why this feature defaults to the strongest model available rather than downgrading to save money. It's a "correctness over cost" tradeoff, and it fits how the feature is actually used: on demand, when the user clicks a button, not in some high-volume batch process.

---

## Testing Summary

**How reliability is actually checked here:** two things, both real and both run — automated tests (`test/test_rag_advisor.py`, 11 cases) and logging/error handling (every failure path in `rag_advisor.py` writes a `logger.error`/`logger.warning` line before raising, verified by capturing the log output directly, shown below). No live Claude API key was available in this environment, so the Anthropic client is mocked in these tests; the mocking targets the actual failure modes the code has to handle (a refusal, malformed JSON, an HTTP error, a dropped connection), not just the happy path.

**Result: 29 out of 29 tests pass** — the original 18 pytest cases for the scheduler, plus 11 new ones for the RAG advisor. Full breakdown of the new 11:

- **3 tests hit the real ChromaDB retriever** (no mocking) — a dog-focused query returns the walk-related passage, a cat/indoor query returns the litter-or-play passage, and a generic query still returns something non-empty. All 3 passed, confirming the retriever is actually pulling species-relevant content, not just returning whatever chunk happens to be first.
- **1 test checks the missing-API-key path** — confirms `RAGAdvisor()` raises `RAGAdvisorError` with a clear message when `ANTHROPIC_API_KEY` isn't set, instead of crashing with a raw exception. Passed.
- **2 tests check the success path** — a mocked Claude response with valid JSON is correctly unpacked into `(advice, tasks)`, and the pet's name/notes are confirmed to actually appear in the prompt sent to the model (so the "personalization" claim isn't just asserted, it's checked). Both passed.
- **5 tests check failure handling** — a `stop_reason: "refusal"` response, a text block that isn't valid JSON, a response with no text block at all, a real `anthropic.APIStatusError` (HTTP 529), and a real `anthropic.APIConnectionError`. All 5 raised the expected `RAGAdvisorError` with no unhandled exception and no silent failure.

**Logging, verified with real output:** running the missing-API-key path with logging turned on to `INFO` produces:
```
ERROR:rag_advisor:RAGAdvisor init failed: ANTHROPIC_API_KEY is not set.
Caught: ANTHROPIC_API_KEY is not set. Add it to a .env file or your environment before using the AI care advisor.
```
Every other failure branch (retrieval miss, API status error, connection error, refusal, malformed JSON, empty text block) logs a similar line with the pet's name and the underlying cause before the `RAGAdvisorError` is raised, so a failure in production leaves a trace instead of just an `st.error` popup that disappears.

**What worked well:** locking down the output format with a JSON schema (`output_config.format`) meant the "malformed JSON" test only had to check that a bad response is *caught*, not that the model rarely produces one — the schema does that work. Mocking the Anthropic client also made it possible to actually test every error branch (refusal, HTTP error, connection error) without needing to somehow trigger those conditions from a real, unpredictable API call.

**What's still a known limitation:**
- All 11 RAG tests use a mocked Claude client. They prove the code handles a refusal, a bad response, or an API error correctly — they don't prove the *real* Claude Opus 5 model reliably follows the prompt's instructions (like giving a fixed `preferred_time` for medication tasks). That still needs a real end-to-end run once `ANTHROPIC_API_KEY` is set — see the note under "Interaction Examples" above.
- The knowledge base currently has just one example care guide, so its topic coverage is limited. There's no test yet for what happens with a species or situation the guide doesn't cover at all (e.g. `species = "other"`) — right now that would just retrieve whatever chunks are closest by embedding distance, which may not be relevant.
- There's no confidence score attached to the AI's output — the system either returns a plan or raises an error, with nothing in between to flag "this advice might be shaky." Adding one (e.g. checking how much retrieved context vs. training-prior the model actually used) is a reasonable next step.

**What I learned:** testing an AI-integrated feature doesn't mean testing the AI's *judgment* — it means testing that your code doesn't fall over no matter what the AI hands back. Every one of those 5 failure-path tests exists because "the API call didn't work the way I expected" is the default case to plan for, not the exception.

```
============================================================================ test session starts ============================================================================
platform win32 -- Python 3.14.0, pytest-9.0.3, pluggy-1.6.0
rootdir: F:\UniversityDocument\US_TAMU\2026_Summer\Interview\ai110-module2show-pawpal-starter-applied-ai-system-project
plugins: anyio-4.13.0
collected 29 items

test\test_pawpal.py ..................                                                                                                                    [ 62%]
test\test_rag_advisor.py ...........                                                                                                                      [100%]

============================================================================= 29 passed, 1 warning in 3.38s =============================================================================
```

---

## Reproducible Execution Evidence

Everything in this section is a real terminal transcript, captured by actually running the commands shown — nothing here is hand-written or made up. You can run every one of these commands yourself and get the same result.

### 1. Command: run the full automated test suite

```bash
python -m pytest test/ -v
```

**Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.3, pluggy-1.6.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: F:\UniversityDocument\US_TAMU\2026_Summer\Interview\ai110-module2show-pawpal-starter-applied-ai-system-project
plugins: anyio-4.13.0
collecting ... collected 29 items

test/test_pawpal.py::test_task_completion PASSED                         [  3%]
test/test_pawpal.py::test_task_addition PASSED                           [  6%]
test/test_pawpal.py::test_sort_tasks_orders_by_priority_normal_case PASSED [ 10%]
test/test_pawpal.py::test_sort_tasks_required_tasks_come_before_optional_regardless_of_priority PASSED [ 13%]
test/test_pawpal.py::test_sort_tasks_empty_list_returns_empty_list PASSED [ 17%]
test/test_pawpal.py::test_sort_by_time_orders_chronologically PASSED     [ 20%]
test/test_pawpal.py::test_sort_by_time_missing_preferred_time_sorts_last PASSED [ 24%]
test/test_pawpal.py::test_daily_task_completion_creates_next_day_occurrence PASSED [ 27%]
test/test_pawpal.py::test_weekly_task_completion_creates_occurrence_seven_days_later PASSED [ 31%]
test/test_pawpal.py::test_once_task_completion_creates_no_next_occurrence PASSED [ 34%]
test/test_pawpal.py::test_mark_task_complete_on_pet_adds_recurring_task_to_pet_list PASSED [ 37%]
test/test_pawpal.py::test_mark_task_complete_on_pet_does_not_add_task_for_one_off PASSED [ 41%]
test/test_pawpal.py::test_generate_plan_pet_with_no_tasks_produces_empty_plan PASSED [ 44%]
test/test_pawpal.py::test_detect_conflicts_returns_no_warnings_for_non_overlapping_items PASSED [ 48%]
test/test_pawpal.py::test_generate_plan_staggers_two_fixed_tasks_requested_at_the_same_time PASSED [ 51%]
test/test_pawpal.py::test_has_conflict_detects_true_overlap_directly PASSED [ 55%]
test/test_pawpal.py::test_detect_conflicts_flags_manually_overlapping_items_from_different_pets PASSED [ 58%]
test/test_pawpal.py::test_detect_conflicts_back_to_back_items_are_not_conflicts PASSED [ 62%]
test/test_rag_advisor.py::test_missing_api_key_raises_ragadvisor_error PASSED [ 65%]
test/test_rag_advisor.py::test_retrieval_returns_dog_relevant_context PASSED [ 68%]
test/test_rag_advisor.py::test_retrieval_returns_cat_relevant_context PASSED [ 72%]
test/test_rag_advisor.py::test_retrieval_is_non_empty_for_generic_query PASSED [ 75%]
test/test_rag_advisor.py::test_generate_smart_care_plan_success_returns_advice_and_tasks PASSED [ 79%]
test/test_rag_advisor.py::test_generate_smart_care_plan_sends_pet_context_in_prompt PASSED [ 82%]
test/test_rag_advisor.py::test_generate_smart_care_plan_raises_on_refusal PASSED [ 86%]
test/test_rag_advisor.py::test_generate_smart_care_plan_raises_on_malformed_json PASSED [ 89%]
test/test_rag_advisor.py::test_generate_smart_care_plan_raises_on_no_text_block PASSED [ 93%]
test/test_rag_advisor.py::test_generate_smart_care_plan_raises_on_api_status_error PASSED [ 96%]
test/test_rag_advisor.py::test_generate_smart_care_plan_raises_on_connection_error PASSED [100%]

============================== warnings summary ===============================
C:\Users\HAO\AppData\Roaming\Python\Python314\site-packages\chromadb\telemetry\opentelemetry\__init__.py:128
  C:\Users\HAO\AppData\Roaming\Python\Python314\site-packages\chromadb\telemetry\opentelemetry\__init__.py:128: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(f):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 29 passed, 1 warning in 3.53s ========================
```

### 2. Command: run the offline, reproducible AI advisor demo

`demo_ai_advisor.py` runs the real retrieval pipeline against the real knowledge base (no mocking there), and only replaces the network call to Claude with a fixed, canned response — so this script produces the exact same output every time, without needing a live `ANTHROPIC_API_KEY`. It shows one successful input → output case, plus two guardrail cases (a refusal and a malformed response), so a grader can see input/output *and* reliability behavior without owning an API key.

```bash
python demo_ai_advisor.py
```

**Output:**
```
======================================================================
DEMO 1: senior dog on medication (success path)
======================================================================
Input pet -> name='Bruno', species='dog', age=10, notes='on daily thyroid medication, senior, needs monitoring'

Retrieved context (first 200 chars):
Medication for dogs with chronic conditions (e.g., thyroid, arthritis) should be given at the same time every day to maintain consistent blood levels. Missing doses can reduce effectiveness.

---

Any...

AI advice:
Bruno is a senior dog on daily thyroid medication. Keep his medication at a fixed time every day for consistent blood levels, and keep walks shorter and gentler given his age, while still going out daily for mobility.

AI proposed tasks:
  - {'description': 'Give thyroid medication', 'duration_minutes': 5, 'priority': 1, 'frequency': 'daily', 'required': True, 'preferred_time': '08:00'}
  - {'description': 'Short gentle walk', 'duration_minutes': 15, 'priority': 1, 'frequency': 'daily', 'required': True, 'preferred_time': None}

Guardrail check: medication task has priority=1 and a non-null preferred_time -- PASSED

======================================================================
DEMO 2: Claude refusal -> handled as a clean error, not a crash
======================================================================
Input pet -> name='Mochi', species='dog', age=3
Caught RAGAdvisorError as expected (this is what st.error() shows the user):
  The AI advisor declined to generate a plan for this request.

======================================================================
DEMO 3: malformed model output -> handled as a clean error, not a crash
======================================================================
Input pet -> name='Luna', species='cat', age=1
Caught RAGAdvisorError as expected (this is what st.error() shows the user):
  The AI advisor returned malformed output.

All demo scenarios completed without an unhandled exception.
```

*(The two `logger.error(...)` lines from the refusal and malformed-JSON guardrail checks are also written to stderr during this run — see the "Testing Summary" section above for what that logging output looks like on its own.)*

### 3. Reliability / guardrail results, summarized

| Scenario | Input | Guardrail behavior | Result |
|---|---|---|---|
| Missing API key | No `ANTHROPIC_API_KEY` set | Raises `RAGAdvisorError` before any network call | PASSED (test + demo) |
| Real Claude refusal | Any pet, `stop_reason: "refusal"` | Caught, raises `RAGAdvisorError`, no crash | PASSED (test + demo) |
| Malformed JSON from the model | Any pet, non-JSON text response | Caught, raises `RAGAdvisorError`, no crash | PASSED (test + demo) |
| No text block in the response | Any pet, only non-text content blocks | Caught, raises `RAGAdvisorError`, no crash | PASSED (test only) |
| Real `anthropic.APIStatusError` (HTTP 529) | Any pet | Caught, raises `RAGAdvisorError` with the status code | PASSED (test only) |
| Real `anthropic.APIConnectionError` | Any pet | Caught, raises `RAGAdvisorError` | PASSED (test only) |
| Medication-related notes (senior dog on medication) | `notes="on daily thyroid medication..."` | Retrieval correctly returns the medication-timing passage; canned response demonstrates `priority=1` + non-null `preferred_time` | PASSED (demo) — **not yet verified against the real model**, see the limitation noted in Testing Summary |

**Full test suite: 29/29 passing** (18 original scheduler tests + 11 RAG advisor tests). See the "Testing Summary" section above for the breakdown of what each RAG test actually checks.

---

## Reflection

This project made it clearer to me that in a RAG system, "retrieval" and "generation" are really two separate things that can each fail on their own — and each deserves its own check. When something goes wrong, it's usually faster to first confirm whether the retrieved context actually makes sense, rather than jumping straight to "maybe the model didn't understand the prompt." I also found that letting the API's structured-output feature guarantee "is this valid JSON" — instead of writing more defensive parsing code in the app — is a cleaner, more reliable engineering choice. That's really the same idea as "push constraints as early as possible, and fix problems at the source," applied to a specific case.

> A more detailed, responsible-AI-focused reflection (how I collaborated with the AI, one AI suggestion that helped, one that was flawed, and the system's limitations) lives in [`model_card.md`](model_card.md) instead of here, per the assignment instructions.
