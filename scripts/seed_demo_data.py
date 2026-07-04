"""
Seed script — creates 3 demo contacts in the CRM.
Run once after `docker compose up -d`:
    python scripts/seed_demo_data.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

CONTACTS = [
    {
        "name": "Ahmad Al-Rashidi",
        "email": "a.alrashidi@eno-uae.ae",
        "company": "Emirates National Oil Co",
    },
    {
        "name": "Chukwuemeka Obi",
        "email": "c.obi@lagospetroleum.ng",
        "company": "Lagos Petroleum Ltd",
    },
    {
        "name": "Arjun Sharma",
        "email": "arjun.sharma@iocl.com",
        "company": "Indian Oil Corporation",
    },
]


def seed():
    db_url = os.getenv("DATABASE_URL", "postgresql://gfs:gfs@localhost:5432/gfsdb")
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as e:
        print(f"ERROR: Cannot connect to database.\n{e}", file=sys.stderr)
        print("Make sure `docker compose up -d` is running.", file=sys.stderr)
        sys.exit(1)

    created = 0
    with conn:
        with conn.cursor() as cur:
            for contact in CONTACTS:
                cur.execute(
                    "SELECT id FROM contacts WHERE email = %s", (contact["email"],)
                )
                if cur.fetchone():
                    print(f"  skip  {contact['name']} (already exists)")
                    continue
                cur.execute(
                    "INSERT INTO contacts (name, email, company) VALUES (%s, %s, %s) RETURNING id",
                    (contact["name"], contact["email"], contact["company"]),
                )
                new_id = cur.fetchone()[0]
                print(f"  created  {contact['name']} — {contact['company']} (id={new_id})")
                created += 1
    conn.close()
    print(f"\n{created} contact(s) created.")


if __name__ == "__main__":
    seed()
