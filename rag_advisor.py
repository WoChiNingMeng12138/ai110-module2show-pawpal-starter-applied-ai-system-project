"""RAG-powered pet care advisor.

Loads text care guides from knowledge_base/, indexes them in a local
persistent ChromaDB collection, retrieves the passages most relevant to a
given pet, and asks Claude to turn that context into natural-language advice
plus a structured list of tasks that can be instantiated as pawpal_system.Task
objects.
"""

import os
import glob
import json
import logging

import anthropic
import chromadb
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma_store")
COLLECTION_NAME = "pawpal_care_guides"
CLAUDE_MODEL = "claude-opus-5"

TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "advice": {
            "type": "string",
            "description": "A natural-language care summary/recommendation for this specific pet.",
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                    "priority": {"type": "integer", "enum": [1, 2, 3]},
                    "frequency": {"type": "string", "enum": ["daily", "weekly", "once"]},
                    "required": {"type": "boolean"},
                    "preferred_time": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ],
                        "description": "Optional fixed 'HH:MM' time, or null if flexible.",
                    },
                },
                "required": [
                    "description",
                    "duration_minutes",
                    "priority",
                    "frequency",
                    "required",
                    "preferred_time",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["advice", "tasks"],
    "additionalProperties": False,
}


class RAGAdvisorError(Exception):
    """Raised when the advisor cannot produce a care plan (retrieval or API failure)."""


class RAGAdvisor:
    """Retrieval-augmented advisor that turns a Pet's profile into a care plan."""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("RAGAdvisor init failed: ANTHROPIC_API_KEY is not set.")
            raise RAGAdvisorError(
                "ANTHROPIC_API_KEY is not set. Add it to a .env file or your environment "
                "before using the AI care advisor."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._collection = self._load_or_build_collection()

    def _load_or_build_collection(self):
        chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        existing = {c.name for c in chroma_client.list_collections()}

        source_files = sorted(glob.glob(os.path.join(KNOWLEDGE_BASE_DIR, "*.txt")))
        if not source_files:
            logger.error("No knowledge base .txt files found in %s.", KNOWLEDGE_BASE_DIR)
            raise RAGAdvisorError(
                f"No knowledge base files found in {KNOWLEDGE_BASE_DIR}. "
                "Add at least one .txt care guide."
            )

        if COLLECTION_NAME in existing:
            collection = chroma_client.get_collection(COLLECTION_NAME)
            if collection.count() > 0:
                return collection
            chroma_client.delete_collection(COLLECTION_NAME)

        collection = chroma_client.create_collection(COLLECTION_NAME)
        documents, ids, metadatas = [], [], []
        for file_path in source_files:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                ids.append(f"{os.path.basename(file_path)}::{i}")
                metadatas.append({"source": os.path.basename(file_path)})

        if documents:
            collection.add(documents=documents, ids=ids, metadatas=metadatas)
        return collection

    def _retrieve_context(self, query: str, n_results: int = 4) -> str:
        results = self._collection.query(query_texts=[query], n_results=n_results)
        chunks = results.get("documents", [[]])[0]
        return "\n\n---\n\n".join(chunks)

    def generate_smart_care_plan(self, pet) -> tuple:
        """Generate natural-language advice and a structured task list for a Pet.

        Returns (advice_text, task_dicts) where each task_dict has the keys
        needed to instantiate a pawpal_system.Task (minus task_id, which the
        caller assigns).

        Raises RAGAdvisorError on retrieval or API failure.
        """
        query = f"{pet.species} age {pet.age} care {pet.notes or ''}".strip()
        logger.info("Retrieving care context for pet=%s query=%r", pet.name, query)
        context = self._retrieve_context(query)
        if not context:
            logger.warning("No retrieval hits for query=%r (pet=%s).", query, pet.name)
            raise RAGAdvisorError("No relevant care guidance found in the knowledge base.")

        user_prompt = (
            f"Pet profile:\n"
            f"- Name: {pet.name}\n"
            f"- Species: {pet.species}\n"
            f"- Age: {pet.age}\n"
            f"- Notes: {pet.notes or '(none)'}\n\n"
            f"Relevant care guide excerpts:\n{context}\n\n"
            "Using only the guidance above, write a short natural-language care "
            "recommendation for this specific pet, and propose a structured list "
            "of 2-4 recurring care tasks appropriate for its species, age, and notes."
        )

        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=(
                    "You are a veterinary care planning assistant embedded in a pet "
                    "scheduling app. Base your recommendations strictly on the provided "
                    "care guide excerpts; do not invent medical advice beyond them."
                ),
                output_config={"format": {"type": "json_schema", "schema": TASK_SCHEMA}},
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIStatusError as e:
            logger.error("Claude API error for pet=%s: status=%s message=%s", pet.name, e.status_code, e.message)
            raise RAGAdvisorError(f"Claude API error ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            logger.error("Claude API connection error for pet=%s: %s", pet.name, e)
            raise RAGAdvisorError(f"Could not reach the Claude API: {e}") from e

        if response.stop_reason == "refusal":
            logger.warning("Claude refused the request for pet=%s (stop_reason=refusal).", pet.name)
            raise RAGAdvisorError("The AI advisor declined to generate a plan for this request.")

        text_block = next((b.text for b in response.content if b.type == "text"), None)
        if not text_block:
            logger.error("Claude returned no text content block for pet=%s.", pet.name)
            raise RAGAdvisorError("The AI advisor returned no usable content.")

        try:
            payload = json.loads(text_block)
        except json.JSONDecodeError as e:
            logger.error("Claude returned malformed JSON for pet=%s: %s", pet.name, e)
            raise RAGAdvisorError("The AI advisor returned malformed output.") from e

        logger.info(
            "Generated care plan for pet=%s: %d task(s) proposed.", pet.name, len(payload["tasks"])
        )
        return payload["advice"], payload["tasks"]
