"""
End-to-end integration test for Meeting Scribe agent.

Requirements:
    - docker compose up -d (postgres + ollama must be running)
    - ollama pull mistral:7b (or OLLAMA_MODEL env override)
    - pip install -r requirements.txt
    - .env file with DATABASE_URL

Run:
    pytest tests/test_meeting_scribe.py -v
"""

import json
import os
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TRANSCRIPT_PATH = FIXTURES_DIR / "demo_transcript.txt"


def _db_conn():
    db_url = os.getenv("DATABASE_URL", "postgresql://gfs:gfs@localhost:5432/gfsdb")
    return psycopg2.connect(db_url)


def _postgres_available() -> bool:
    try:
        conn = _db_conn()
        conn.close()
        return True
    except Exception:
        return False


def _ollama_available() -> bool:
    try:
        import ollama
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        client = ollama.Client(host=host)
        client.list()
        return True
    except Exception:
        return False


requires_stack = pytest.mark.skipif(
    not (_postgres_available() and _ollama_available()),
    reason="Requires running Docker stack (postgres + ollama). Run `docker compose up -d` first.",
)


@requires_stack
def test_meeting_scribe_end_to_end():
    """
    Full pipeline: transcript file → Ollama → Pydantic validation → PostgreSQL.
    Verifies output structure and DB persistence.
    """
    from agents.meeting_scribe.agent import run_agent
    from agents.meeting_scribe.schemas import MeetingOutput

    assert TRANSCRIPT_PATH.exists(), f"Demo transcript not found: {TRANSCRIPT_PATH}"

    output, meeting_id = run_agent(str(TRANSCRIPT_PATH), contact_id=None)

    # --- Validate output structure ---
    assert isinstance(output, MeetingOutput), "run_agent must return a MeetingOutput instance"
    assert output.summary, "summary must not be empty"
    assert output.next_step, "next_step must not be empty"
    assert output.sentiment in ("positive", "neutral", "negative"), \
        f"Invalid sentiment: {output.sentiment}"
    assert isinstance(output.action_items, list), "action_items must be a list"

    for item in output.action_items:
        assert item.owner, "Each action_item must have an owner"
        assert item.task, "Each action_item must have a task"

    # --- Validate DB persistence ---
    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            # meetings table
            cur.execute(
                "SELECT summary, sentiment, next_step, action_items FROM meetings WHERE id = %s",
                (meeting_id,),
            )
            row = cur.fetchone()
            assert row is not None, f"Meeting id={meeting_id} not found in DB"
            db_summary, db_sentiment, db_next_step, db_action_items = row
            assert db_summary == output.summary
            assert db_sentiment == output.sentiment
            assert db_next_step == output.next_step
            assert isinstance(db_action_items, list)

            # agent_actions audit log
            cur.execute(
                "SELECT agent_name, model_used, cost_usd FROM agent_actions "
                "WHERE output_summary LIKE %s ORDER BY created_at DESC LIMIT 1",
                (f"%meeting_id={meeting_id}%",),
            )
            audit_row = cur.fetchone()
            assert audit_row is not None, "No audit log entry found for this run"
            assert audit_row[0] == "sales_meeting_scribe"
            assert float(audit_row[2]) == 0.0, "Stage 0: cost_usd must be 0"
    finally:
        conn.close()

    print(f"\n[PASS] meeting_id={meeting_id}, sentiment={output.sentiment}, "
          f"action_items={len(output.action_items)}")
