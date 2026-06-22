from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as c:
    sub = c.execute(text("SELECT id, name FROM subject WHERE LOWER(name)='sanskrit'")).fetchone()
    print("Sanskrit subject:", sub)
    if not sub:
        print("No Sanskrit subject found")
    else:
        sid = sub[0]
        count = c.execute(text("""
            SELECT COUNT(*) FROM question q
            JOIN topic t ON q.topic_id=t.id
            JOIN chapter ch ON t.chapter_id=ch.id
            WHERE ch.subject_id=:sid
        """), {"sid": sid}).scalar()
        print(f"Sanskrit questions in DB: {count}")

        rows = c.execute(text("""
            SELECT q.id, q.type, q.source, LEFT(q.text, 120)
            FROM question q
            JOIN topic t ON q.topic_id=t.id
            JOIN chapter ch ON t.chapter_id=ch.id
            WHERE ch.subject_id=:sid LIMIT 10
        """), {"sid": sid}).fetchall()
        for r in rows:
            print(f"  id={r[0]} {r[1]} [{r[2]}]: {r[3]}")

        # Delete all Sanskrit questions so they get regenerated in Hindi
        resp_del = c.execute(text("""
            DELETE FROM response WHERE question_id IN (
                SELECT q.id FROM question q
                JOIN topic t ON q.topic_id=t.id
                JOIN chapter ch ON t.chapter_id=ch.id
                WHERE ch.subject_id=:sid
            )
        """), {"sid": sid})
        q_del = c.execute(text("""
            DELETE FROM question WHERE id IN (
                SELECT q.id FROM question q
                JOIN topic t ON q.topic_id=t.id
                JOIN chapter ch ON t.chapter_id=ch.id
                WHERE ch.subject_id=:sid
            )
        """), {"sid": sid})
        c.commit()
        print(f"Deleted {q_del.rowcount} Sanskrit questions (will be regenerated in Hindi/Devanagari)")
