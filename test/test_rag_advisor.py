"""Automated tests for the RAG care advisor (rag_advisor.py).

These tests exercise real retrieval against the bundled knowledge base (no
network calls, no API key needed for that part) and mock the Anthropic
client for every code path that talks to Claude, so each failure mode
(refusal, malformed output, HTTP error, connection error) can be verified
without a live API key.
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-placeholder-for-unit-tests")

from pawpal_system import Pet
from rag_advisor import RAGAdvisor, RAGAdvisorError


@pytest.fixture(scope="module")
def advisor():
    """A real RAGAdvisor (real retrieval, real ChromaDB) with the Claude client mocked out."""
    instance = RAGAdvisor()
    instance._client = MagicMock()
    return instance


def _text_response(payload: dict, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        stop_reason=stop_reason,
    )


# ---------------------------------------------------------------------------
# Construction / configuration
# ---------------------------------------------------------------------------

def test_missing_api_key_raises_ragadvisor_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RAGAdvisorError, match="ANTHROPIC_API_KEY is not set"):
        RAGAdvisor()


# ---------------------------------------------------------------------------
# Retrieval correctness (real ChromaDB, no mocking)
# ---------------------------------------------------------------------------

def test_retrieval_returns_dog_relevant_context(advisor):
    context = advisor._retrieve_context("dog age 3 care needs daily walk")
    assert "walk" in context.lower()


def test_retrieval_returns_cat_relevant_context(advisor):
    context = advisor._retrieve_context("indoor cat kitten litter box play")
    assert "litter" in context.lower() or "play" in context.lower()


def test_retrieval_is_non_empty_for_generic_query(advisor):
    context = advisor._retrieve_context("general pet care notes")
    assert len(context) > 0


# ---------------------------------------------------------------------------
# generate_smart_care_plan: success path
# ---------------------------------------------------------------------------

def test_generate_smart_care_plan_success_returns_advice_and_tasks(advisor):
    pet = Pet(name="Mochi", species="dog", age=3, notes="")
    payload = {
        "advice": "Walk Mochi twice daily and brush weekly.",
        "tasks": [
            {
                "description": "Morning walk",
                "duration_minutes": 25,
                "priority": 1,
                "frequency": "daily",
                "required": True,
                "preferred_time": None,
            }
        ],
    }
    advisor._client.messages.create.return_value = _text_response(payload)

    advice, tasks = advisor.generate_smart_care_plan(pet)

    assert advice == payload["advice"]
    assert tasks == payload["tasks"]


def test_generate_smart_care_plan_sends_pet_context_in_prompt(advisor):
    pet = Pet(name="Bruno", species="dog", age=10, notes="on daily thyroid medication, senior")
    advisor._client.messages.create.return_value = _text_response(
        {"advice": "ok", "tasks": []}
    )

    advisor.generate_smart_care_plan(pet)

    _, kwargs = advisor._client.messages.create.call_args
    sent_prompt = kwargs["messages"][0]["content"]
    assert "Bruno" in sent_prompt
    assert "on daily thyroid medication" in sent_prompt


# ---------------------------------------------------------------------------
# generate_smart_care_plan: failure paths
# ---------------------------------------------------------------------------

def test_generate_smart_care_plan_raises_on_refusal(advisor):
    pet = Pet(name="Mochi", species="dog", age=3)
    advisor._client.messages.create.return_value = _text_response(
        {"advice": "", "tasks": []}, stop_reason="refusal"
    )

    with pytest.raises(RAGAdvisorError, match="declined"):
        advisor.generate_smart_care_plan(pet)


def test_generate_smart_care_plan_raises_on_malformed_json(advisor):
    pet = Pet(name="Mochi", species="dog", age=3)
    advisor._client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="not valid json {{{")],
        stop_reason="end_turn",
    )

    with pytest.raises(RAGAdvisorError, match="malformed"):
        advisor.generate_smart_care_plan(pet)


def test_generate_smart_care_plan_raises_on_no_text_block(advisor):
    pet = Pet(name="Mochi", species="dog", age=3)
    advisor._client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking="")],
        stop_reason="end_turn",
    )

    with pytest.raises(RAGAdvisorError, match="no usable content"):
        advisor.generate_smart_care_plan(pet)


def test_generate_smart_care_plan_raises_on_api_status_error(advisor):
    pet = Pet(name="Mochi", species="dog", age=3)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=529, request=request)
    advisor._client.messages.create.side_effect = anthropic.APIStatusError(
        message="Overloaded", response=response, body=None
    )

    with pytest.raises(RAGAdvisorError, match="Claude API error"):
        advisor.generate_smart_care_plan(pet)


def test_generate_smart_care_plan_raises_on_connection_error(advisor):
    pet = Pet(name="Mochi", species="dog", age=3)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    advisor._client.messages.create.side_effect = anthropic.APIConnectionError(request=request)

    with pytest.raises(RAGAdvisorError, match="Could not reach the Claude API"):
        advisor.generate_smart_care_plan(pet)
