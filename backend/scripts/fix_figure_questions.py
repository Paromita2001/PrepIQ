"""
Fix figure-reference questions: strip the leading phrase where possible,
delete only if the question body itself depends on a figure.
"""
import re, sys, os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])

FIGURE_PREFIX_RE = re.compile(
    r"^(in (the |this |a )?(given |above |below |following )?figure[^,\.]*[,\.]\s*"
    r"|from (the |this )?figure[^,\.]*[,\.]\s*"
    r"|refer(ring)? to (the )?figure[^,\.]*[,\.]\s*"
    r"|as shown (in|by) (the )?figure[^,\.]*[,\.]\s*"
    r"|the (given |following )?figure (shows?|depicts?|illustrates?)[^\.]*\.\s*)",
    re.IGNORECASE,
)
FIGURE_BODY_RE = re.compile(
    r"\b(figure|diagram|shown below|given below|attached figure|above figure|the image)\b",
    re.IGNORECASE,
)

with engine.connect() as c:
    rows = c.execute(text("""
        SELECT id, text FROM question
        WHERE text ILIKE '%in the given figure%'
           OR text ILIKE '%given figure%'
           OR text ILIKE '%from the figure%'
           OR text ILIKE '%refer to the figure%'
           OR text ILIKE '%shown in the figure%'
           OR text ILIKE '%shown below%'
           OR text ILIKE '%the figure shows%'
           OR text ILIKE '%the figure depicts%'
    """)).fetchall()

    print(f"Found {len(rows)} questions with figure references")

    fix_ids = []
    del_ids = []
    for qid, qtext in rows:
        stripped = FIGURE_PREFIX_RE.sub("", qtext).strip()
        if stripped and stripped[0].islower():
            stripped = stripped[0].upper() + stripped[1:]
        if not stripped or FIGURE_BODY_RE.search(stripped):
            del_ids.append(qid)
        else:
            fix_ids.append((qid, stripped))

    for qid, new_text in fix_ids:
        c.execute(text("UPDATE question SET text=:t WHERE id=:id"), {"t": new_text, "id": qid})
        print(f"  FIXED id={qid}: {new_text[:80]}")

    if del_ids:
        c.execute(text("DELETE FROM response WHERE question_id = ANY(:ids)"), {"ids": del_ids})
        c.execute(text("DELETE FROM question WHERE id = ANY(:ids)"), {"ids": del_ids})
        print(f"  DELETED {len(del_ids)} unrepairable questions: {del_ids}")

    c.commit()
    remaining = c.execute(text("SELECT COUNT(*) FROM question")).scalar()
    print(f"\nFixed: {len(fix_ids)}  Deleted: {len(del_ids)}  Remaining: {remaining}")
