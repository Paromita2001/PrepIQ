from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as c:
    rows = c.execute(text("""
        SELECT COALESCE(q.source, '(no source)'), COUNT(*) FROM question q
        JOIN topic t ON q.topic_id=t.id
        JOIN chapter ch ON t.chapter_id=ch.id
        WHERE ch.subject_id=(SELECT id FROM subject WHERE name='Sanskrit')
        GROUP BY q.source ORDER BY COUNT(*) DESC
    """)).fetchall()
    print("Sanskrit questions by source:")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")

    total = c.execute(text("""
        SELECT COUNT(*) FROM question q
        JOIN topic t ON q.topic_id=t.id
        JOIN chapter ch ON t.chapter_id=ch.id
        WHERE ch.subject_id=(SELECT id FROM subject WHERE name='Sanskrit')
    """)).scalar()
    print(f"  TOTAL: {total}")

    nc = c.execute(text("""
        SELECT COUNT(*) FROM ncert_chunk nc
        JOIN topic t ON nc.topic_id=t.id
        JOIN chapter ch ON t.chapter_id=ch.id
        WHERE ch.subject_id=(SELECT id FROM subject WHERE name='Sanskrit')
    """)).scalar()
    print(f"Sanskrit NCERT chunks in DB: {nc}")

    ch_rows = c.execute(text("""
        SELECT ch.name, COUNT(*) FROM question q
        JOIN topic t ON q.topic_id=t.id
        JOIN chapter ch ON t.chapter_id=ch.id
        WHERE ch.subject_id=(SELECT id FROM subject WHERE name='Sanskrit')
        GROUP BY ch.name ORDER BY ch.name
    """)).fetchall()
    print("Questions per chapter:")
    for r in ch_rows:
        print(f"  {r[0]}: {r[1]}")
