"""Reproducible, offline demo of the RAG care advisor.

Real knowledge-base retrieval runs unmodified (it needs no network access and
no API key). The Claude API call itself is replaced with a fixed, canned
response so this script produces the exact same output every time it runs --
no ANTHROPIC_API_KEY required. This makes it possible to see real input ->
real output for the RAG pipeline, and to see the failure-handling path fire,
without depending on a live model call.

Run with: python demo_ai_advisor.py
"""

import json
import os
from unittest.mock import MagicMock
from types import SimpleNamespace

# RAGAdvisor's constructor requires a truthy ANTHROPIC_API_KEY before it will
# build the Chroma index (see rag_advisor.py). This placeholder is never
# actually sent anywhere -- the client is replaced with a mock below before
# any network call would happen.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-placeholder-not-a-real-key")

from pawpal_system import Pet
from rag_advisor import RAGAdvisor, RAGAdvisorError


def make_advisor_with_mocked_client():
    advisor = RAGAdvisor()  # builds the real ChromaDB index from knowledge_base/
    advisor._client = MagicMock()
    return advisor


def print_header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def demo_success_case(advisor):
    print_header("DEMO 1: senior dog on medication (success path)")

    pet = Pet(
        name="Bruno",
        species="dog",
        age=10,
        notes="on daily thyroid medication, senior, needs monitoring",
    )
    print(f"Input pet -> name={pet.name!r}, species={pet.species!r}, age={pet.age}, notes={pet.notes!r}")

    context = advisor._retrieve_context(f"{pet.species} age {pet.age} care {pet.notes}")
    print(f"\nRetrieved context (first 200 chars):\n{context[:200]}...")

    # Canned response standing in for the real Claude call -- this is the
    # exact JSON shape output_config.format guarantees Claude will return.
    canned_payload = {
        "advice": (
            "Bruno is a senior dog on daily thyroid medication. Keep his medication "
            "at a fixed time every day for consistent blood levels, and keep walks "
            "shorter and gentler given his age, while still going out daily for mobility."
        ),
        "tasks": [
            {
                "description": "Give thyroid medication",
                "duration_minutes": 5,
                "priority": 1,
                "frequency": "daily",
                "required": True,
                "preferred_time": "08:00",
            },
            {
                "description": "Short gentle walk",
                "duration_minutes": 15,
                "priority": 1,
                "frequency": "daily",
                "required": True,
                "preferred_time": None,
            },
        ],
    }
    advisor._client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(canned_payload))],
        stop_reason="end_turn",
    )

    advice, tasks = advisor.generate_smart_care_plan(pet)

    print(f"\nAI advice:\n{advice}")
    print("\nAI proposed tasks:")
    for t in tasks:
        print(f"  - {t}")

    med_task = tasks[0]
    assert med_task["priority"] == 1
    assert med_task["preferred_time"] is not None
    print("\nGuardrail check: medication task has priority=1 and a non-null preferred_time -- PASSED")


def demo_refusal_guardrail(advisor):
    print_header("DEMO 2: Claude refusal -> handled as a clean error, not a crash")

    pet = Pet(name="Mochi", species="dog", age=3)
    print(f"Input pet -> name={pet.name!r}, species={pet.species!r}, age={pet.age}")

    advisor._client.messages.create.return_value = SimpleNamespace(
        content=[],
        stop_reason="refusal",
    )

    try:
        advisor.generate_smart_care_plan(pet)
        print("ERROR: expected RAGAdvisorError to be raised, but it was not.")
    except RAGAdvisorError as e:
        print(f"Caught RAGAdvisorError as expected (this is what st.error() shows the user):\n  {e}")


def demo_malformed_output_guardrail(advisor):
    print_header("DEMO 3: malformed model output -> handled as a clean error, not a crash")

    pet = Pet(name="Luna", species="cat", age=1)
    print(f"Input pet -> name={pet.name!r}, species={pet.species!r}, age={pet.age}")

    advisor._client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="not valid json {{{")],
        stop_reason="end_turn",
    )

    try:
        advisor.generate_smart_care_plan(pet)
        print("ERROR: expected RAGAdvisorError to be raised, but it was not.")
    except RAGAdvisorError as e:
        print(f"Caught RAGAdvisorError as expected (this is what st.error() shows the user):\n  {e}")


if __name__ == "__main__":
    advisor = make_advisor_with_mocked_client()
    demo_success_case(advisor)
    demo_refusal_guardrail(advisor)
    demo_malformed_output_guardrail(advisor)
    print("\nAll demo scenarios completed without an unhandled exception.\n")
