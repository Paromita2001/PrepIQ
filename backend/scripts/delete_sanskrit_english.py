"""Delete Sanskrit questions written in English (Roman script) so they regenerate in Hindi/Devanagari."""
from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as c:
    sub = c.execute(text("SELECT id FROM subject WHERE LOWER(name)='sanskrit'")).fetchone()
    if not sub:
        print("No Sanskrit subject")
        exit()
    sid = sub[0]

    # Only delete questions whose text is predominantly ASCII (English/transliteration)
    # Questions already in Devanagari have non-ASCII chars and should be kept
    rows = c.execute(text("""
        SELECT q.id, q.text FROM question q
        JOIN topic t ON q.topic_id=t.id
        JOIN chapter ch ON t.chapter_id=ch.id
        WHERE ch.subject_id=:sid
    """), {"sid": sid}).fetchall()

    english_ids = []
    for qid, qtext in rows:
        if not qtext:
            continue
        ascii_chars = sum(1 for ch in qtext if ord(ch) < 128)
        total = len(qtext)
        # If >80% ASCII → written in English/transliteration → delete
        if total > 0 and ascii_chars / total > 0.80:
            english_ids.append(qid)

    print(f"Sanskrit questions total: {len(rows)}")
    print(f"English/transliteration questions to delete: {len(english_ids)}")

    if english_ids:
        c.execute(text("DELETE FROM response WHERE question_id = ANY(:ids)"), {"ids": english_ids})
        r = c.execute(text("DELETE FROM question WHERE id = ANY(:ids)"), {"ids": english_ids})
        c.commit()
        print(f"Deleted: {r.rowcount}")

    remaining = c.execute(text("""
        SELECT COUNT(*) FROM question q
        JOIN topic t ON q.topic_id=t.id
        JOIN chapter ch ON t.chapter_id=ch.id
        WHERE ch.subject_id=:sid
    """), {"sid": sid}).scalar()
    print(f"Remaining Sanskrit questions (Devanagari): {remaining}")
