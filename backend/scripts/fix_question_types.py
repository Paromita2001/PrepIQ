"""
Fix incorrectly-typed questions in the DB without loading the embedding model.
Uses raw SQLAlchemy against the Neon DB directly.
"""
import sys, os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    rows = conn.execute(text('SELECT id, type, marks, text FROM "question"')).fetchall()
    print(f"Total questions: {len(rows)}")

    mcq_fix_ids = []
    figure_delete_ids = []

    for row in rows:
        qid, qtype, marks, qtext = row
        if not qtext:
            continue

        tl = qtext.lower()
        # Figure/image-dependent questions — cannot be answered in text UI
        if ("(a)" in tl or "(A)" in qtext) and (
            ("as shown" in tl and "figure" in tl) or
            ("shown in figure" in tl) or
            ("refer to figure" in tl) or
            ("given in figure" in tl)
        ):
            print(f"[DELETE] id={qid} type={qtype}: {qtext[:100]}")
            figure_delete_ids.append(qid)
            continue

        # MCQ-format options in text but wrong type label
        has_opts = ("(A)" in qtext and "(B)" in qtext and "(C)" in qtext and "(D)" in qtext)
        if has_opts and qtype != "mcq":
            print(f"[FIX] id={qid} {qtype}->mcq marks={marks}->1: {qtext[:80]}")
            mcq_fix_ids.append(qid)

    # Apply fixes
    if mcq_fix_ids:
        conn.execute(
            text('UPDATE question SET type=\'mcq\', marks=1 WHERE id = ANY(:ids)'),
            {"ids": mcq_fix_ids}
        )
        print(f"\nFixed {len(mcq_fix_ids)} questions: type set to mcq, marks=1")

    if figure_delete_ids:
        # Remove responses first (FK constraint)
        conn.execute(text('DELETE FROM response WHERE question_id = ANY(:ids)'), {"ids": figure_delete_ids})
        conn.execute(text('DELETE FROM question WHERE id = ANY(:ids)'), {"ids": figure_delete_ids})
        print(f"Deleted {len(figure_delete_ids)} figure-reference questions")

    conn.commit()
    remaining = conn.execute(text('SELECT COUNT(*) FROM "question"')).scalar()
    print(f"Questions remaining: {remaining}")
