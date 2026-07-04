"""
Meeting Scribe — Stage 0 agent.
Reads a .txt transcript, calls local Ollama, validates with Pydantic,
writes to meetings + agent_actions tables.

Usage:
    python agents/meeting_scribe/agent.py --transcript path/to/transcript.txt
    python agents/meeting_scribe/agent.py --transcript path/to/transcript.txt --contact-id 2
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import ollama
import psycopg2
from dotenv import load_dotenv
from pydantic import ValidationError

from agents.meeting_scribe.schemas import MeetingOutput

load_dotenv()

AGENT_NAME = "sales_meeting_scribe"
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
PROMPT_FILE = PROMPTS_DIR / "PROMPT-MEETING-SCRIBE-v1.0.md"


def _load_prompt() -> str:
    """Load system prompt from versioned file, stripping the YAML header."""
    text = PROMPT_FILE.read_text(encoding="utf-8")
    # Drop the top comment block (lines starting with #) that holds metadata
    lines = text.splitlines()
    content_lines = []
    in_header = True
    for line in lines:
        if in_header and (line.startswith("#") or line.strip() == "" or line.startswith("---")):
            continue
        in_header = False
        content_lines.append(line)
    return "\n".join(content_lines).strip()


def _extract_json(text: str) -> str:
    """
    Extract a JSON object from LLM output that may contain markdown wrappers.
    mistral:7b often returns ```json ... ``` blocks or prose before the JSON.
    """
    # Try markdown code block first: ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)

    # Try to find the outermost { ... } in the response
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    return text  # return as-is and let json.loads raise a clear error


def _call_ollama(system_prompt: str, transcript: str, extra_instruction: str = "") -> str:
    """Call local Ollama and return the raw response text."""
    model = os.getenv("OLLAMA_MODEL", "mistral:7b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    client = ollama.Client(host=host)

    user_content = f"TRANSCRIPT:\n\n{transcript}"
    if extra_instruction:
        user_content = f"{extra_instruction}\n\n{user_content}"

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response["message"]["content"]


def _parse_output(raw: str) -> MeetingOutput:
    """Extract JSON from raw LLM output and validate with Pydantic."""
    json_str = _extract_json(raw)
    data = json.loads(json_str)
    return MeetingOutput(**data)


def _save_to_db(output: MeetingOutput, transcript: str, contact_id, model: str) -> int:
    """Write meeting result and audit log to PostgreSQL. Returns meeting id."""
    db_url = os.getenv("DATABASE_URL", "postgresql://gfs:gfs@localhost:5432/gfsdb")
    conn = psycopg2.connect(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meetings
                        (contact_id, transcript_raw, summary, action_items, sentiment, next_step)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        contact_id,
                        transcript,
                        output.summary,
                        json.dumps([ai.model_dump() for ai in output.action_items]),
                        output.sentiment,
                        output.next_step,
                    ),
                )
                meeting_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO agent_actions
                        (agent_name, model_used, input_summary, output_summary, cost_usd)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        AGENT_NAME,
                        model,
                        f"transcript: {len(transcript)} chars",
                        f"meeting_id={meeting_id}, sentiment={output.sentiment}, "
                        f"action_items={len(output.action_items)}",
                        0,
                    ),
                )
    finally:
        conn.close()
    return meeting_id


def run_agent(transcript_path: str, contact_id=None) -> MeetingOutput:
    """
    Main entry point — also called directly from tests.
    Returns the validated MeetingOutput and writes to DB.
    """
    transcript = Path(transcript_path).read_text(encoding="utf-8").strip()
    if not transcript:
        raise ValueError(f"Transcript file is empty: {transcript_path}")

    system_prompt = _load_prompt()
    model = os.getenv("OLLAMA_MODEL", "mistral:7b")

    # First attempt
    raw = _call_ollama(system_prompt, transcript)
    try:
        output = _parse_output(raw)
    except (json.JSONDecodeError, ValidationError, KeyError) as first_error:
        print(f"[Meeting Scribe] First attempt failed: {first_error}", file=sys.stderr)
        print("[Meeting Scribe] Retrying with explicit JSON instruction...", file=sys.stderr)

        # Retry: tell the model exactly what went wrong
        extra = (
            f"IMPORTANT: Your previous response could not be parsed as JSON. "
            f"Error: {first_error}. "
            f"Return ONLY a raw JSON object starting with {{ and ending with }}. "
            f"No markdown, no explanation, no code blocks."
        )
        raw = _call_ollama(system_prompt, transcript, extra_instruction=extra)
        try:
            output = _parse_output(raw)
        except (json.JSONDecodeError, ValidationError, KeyError) as second_error:
            print(
                f"[Meeting Scribe] ERROR: Could not parse valid JSON after retry.\n"
                f"Final error: {second_error}\n"
                f"Raw LLM output:\n{raw}",
                file=sys.stderr,
            )
            sys.exit(1)

    meeting_id = _save_to_db(output, transcript, contact_id, model)
    return output, meeting_id


def main():
    parser = argparse.ArgumentParser(description="GFS Meeting Scribe — Stage 0 agent")
    parser.add_argument("--transcript", required=True, help="Path to .txt transcript file")
    parser.add_argument(
        "--contact-id", type=int, default=None, help="CRM contact ID to link this meeting to"
    )
    args = parser.parse_args()

    print(f"[Meeting Scribe] Processing: {args.transcript}")
    print(f"[Meeting Scribe] Model: {os.getenv('OLLAMA_MODEL', 'mistral:7b')}")

    output, meeting_id = run_agent(args.transcript, contact_id=args.contact_id)

    print("\n--- Result ---")
    print(json.dumps(output.model_dump(), indent=2, ensure_ascii=False))
    print(f"\n✓ Saved to meetings table (id={meeting_id})")


if __name__ == "__main__":
    main()
