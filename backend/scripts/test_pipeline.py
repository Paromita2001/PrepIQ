"""
Full pipeline smoke-test.
Tests every API endpoint and agent node end-to-end against a live backend.

Run from backend/ with venv active:
    python -m scripts.test_pipeline

Requires backend running on localhost:8000.
Creates a temporary test user.
"""

import sys
import time
import uuid
import requests

BASE = "http://localhost:8000"
_results = []


def check(label, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    _results.append((label, ok))
    return ok


def section(title):
    print(f"\n{'-'*60}")
    print(f"  {title}")
    print(f"{'-'*60}")


def get(path, token=None, **kw):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{BASE}{path}", headers=h, **kw)


def post(path, token=None, **kw):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    if "json" in kw:
        h["Content-Type"] = "application/json"
    return requests.post(f"{BASE}{path}", headers=h, **kw)


# -------------------------------------------------------------------------
# 1. HEALTH
# -------------------------------------------------------------------------

section("1. Health checks")

try:
    r = get("/health", timeout=5)
    check("GET /health returns 200", r.status_code == 200)
    check("/health body status=ok", r.json().get("status") == "ok")
except Exception as e:
    check("GET /health reachable", False, str(e))
    print(f"\n  Backend not running on {BASE} -- aborting.")
    sys.exit(1)

try:
    print("  [INFO] Running /health/full (may take ~15s for Groq ping)...")
    r = get("/health/full", timeout=90)
    d = r.json()
    checks = d.get("checks", {})
    check("GET /health/full returns 200", r.status_code == 200)
    check("DB check passes",
          checks.get("db", {}).get("ok") is True,
          "subjects: " + str(checks.get("db", {}).get("subjects", "?")))
    check("Embedding check passes",
          checks.get("embedding", {}).get("ok") is True,
          "dim=" + str(checks.get("embedding", {}).get("dim", "?")))
    check("Groq API check passes",
          checks.get("groq", {}).get("ok") is True)
    q_count = checks.get("db", {}).get("question_count", 0)
    chunk_count = checks.get("db", {}).get("ncert_chunk_count", 0)
    check("DB has questions", q_count > 0, str(q_count) + " questions")
    check("DB has NCERT chunks", chunk_count > 0, str(chunk_count) + " chunks")
except Exception as e:
    check("GET /health/full", False, str(e))


# -------------------------------------------------------------------------
# 2. SUBJECTS (no auth required)
# -------------------------------------------------------------------------

section("2. Subjects list")

r = get("/student/subjects", timeout=10)
check("GET /student/subjects returns 200", r.status_code == 200)
subjects = r.json() if r.status_code == 200 else []
subject_names = [s["name"] for s in subjects]
check("Mathematics present", "Mathematics" in subject_names)
check("Science present", "Science" in subject_names)
check("English present", "English" in subject_names)
check("Hindi present", "Hindi" in subject_names)
check("Social Science present", "Social Science" in subject_names)
check("At least 6 subjects seeded", len(subject_names) >= 6, str(len(subject_names)) + " subjects")
# Note: Physics/Chemistry/Biology stay in the DB; the frontend subject picker
# hides them since Science covers all three at Class 10 level.
print("  [INFO] Subjects in DB: " + str(subject_names))


# -------------------------------------------------------------------------
# 3. AUTH
# -------------------------------------------------------------------------

section("3. Auth -- register / login / me")

uid = uuid.uuid4().hex[:8]
TEST_EMAIL = f"pipeline{uid}@mailtest.io"
TEST_PASS  = "Test@1234"
TOKEN      = None

r = post("/auth/register", json={
    "name": "Pipeline Test User",
    "email": TEST_EMAIL,
    "password": TEST_PASS,
})
check("POST /auth/register returns 201", r.status_code == 201, r.text[:80])

r = post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
check("POST /auth/login returns 200", r.status_code == 200, r.text[:80])
if r.status_code == 200:
    TOKEN = r.json().get("access_token")
    check("Login returns access_token", bool(TOKEN))

r2 = post("/auth/login", json={"email": TEST_EMAIL, "password": "wrongpass"})
check("Wrong password returns 401", r2.status_code == 401)

r3 = get("/auth/me", token=TOKEN, timeout=5)
check("GET /auth/me returns 200", r3.status_code == 200)
me = r3.json() if r3.status_code == 200 else {}
check("GET /auth/me returns correct email", me.get("email") == TEST_EMAIL)

r4 = get("/auth/me", timeout=5)
check("GET /auth/me without token returns 401/403", r4.status_code in (401, 403))

if not TOKEN:
    print("\n  No token -- skipping all auth-dependent tests.")
    sys.exit(1)


# -------------------------------------------------------------------------
# 4. TEST GENERATION -- Mathematics practice with prompt
# -------------------------------------------------------------------------

section("4. Test generation -- Mathematics practice (with prompt)")

GEN_MATHS = {}
print("  [INFO] Calling /test/generate (first LLM call may take 20-40s)...")
t0 = time.time()
r = post("/test/generate", token=TOKEN, json={
    "subject": "Mathematics",
    "mode": "practice",
    "raw_prompt": "test me on real numbers and polynomials",
}, timeout=120)
elapsed = time.time() - t0
ok = check("POST /test/generate Math returns 200", r.status_code == 200,
           f"({elapsed:.0f}s)" if r.status_code == 200
           else f"({elapsed:.0f}s) {r.text[:120]}")

if ok:
    GEN_MATHS = r.json()
    questions = GEN_MATHS.get("questions", [])
    plan      = GEN_MATHS.get("plan", {})
    session_id = GEN_MATHS.get("session_id")

    check("Response has session_id", bool(session_id))
    check("Response has questions", len(questions) > 0, str(len(questions)) + " questions")
    check("Response has plan", bool(plan))
    check("Response has events list", isinstance(GEN_MATHS.get("events"), list))

    if questions:
        q = questions[0]
        check("Questions have required fields",
              all(k in q for k in ["id", "text", "marks", "type", "topic_name"]))
        check("Question marks are positive", all(qq["marks"] > 0 for qq in questions))
        check("Question difficulty 1-5",
              all(1 <= qq.get("difficulty", 3) <= 5 for qq in questions))
        print("  [INFO] Types: " + str({qq["type"] for qq in questions}))
        print("  [INFO] Chapters: " + str({qq.get("chapter_name","") for qq in questions}))

    mcq_qs = [q for q in questions if q["type"] == "mcq"]
    if mcq_qs:
        check("MCQ questions embed options (A)",
              all("(A)" in q["text"] for q in mcq_qs),
              str(len(mcq_qs)) + " MCQs checked")


# -------------------------------------------------------------------------
# 5. TEST GENERATION -- Science practice (no prompt)
# -------------------------------------------------------------------------

section("5. Test generation -- Science practice (no prompt)")

GEN_SCI = {}
print("  [INFO] Calling /test/generate Science...")
t0 = time.time()
r = post("/test/generate", token=TOKEN, json={
    "subject": "Science",
    "mode": "practice",
}, timeout=120)
elapsed = time.time() - t0
ok = check("POST /test/generate Science returns 200", r.status_code == 200,
           f"({elapsed:.0f}s)" if r.status_code == 200
           else f"({elapsed:.0f}s) {r.text[:120]}")
if ok:
    GEN_SCI = r.json()
    check("Science test has questions",
          len(GEN_SCI.get("questions", [])) > 0,
          str(len(GEN_SCI.get("questions", []))) + " questions")


# -------------------------------------------------------------------------
# 6. ANSWER SUBMISSION -- Mathematics
# -------------------------------------------------------------------------

section("6. Answer submission + evaluation")

SUB_RESULT = {}
if not GEN_MATHS:
    print("  SKIP -- no Mathematics test generated")
else:
    session_id = GEN_MATHS["session_id"]
    questions  = GEN_MATHS["questions"]

    answers = {}
    for q in questions:
        if q["type"] == "mcq":
            answers[str(q["id"])] = "(A)"
        elif q["type"] == "short":
            answers[str(q["id"])] = (
                "The key concept here involves the fundamental definition and its application. "
                "Step 1: identify the given values. Step 2: apply the relevant formula. "
                "Step 3: calculate the result. Therefore the answer follows from the above steps."
            )
        else:
            answers[str(q["id"])] = (
                "A comprehensive answer covering all aspects of the question. "
                "The concept is defined as the principle underlying the topic. "
                "The mathematical formulation gives us the key relationship. "
                "A worked example demonstrates the practical application. "
                "Real-world significance includes industrial and scientific uses."
            )

    print(f"  [INFO] Submitting {len(answers)} answers for session {session_id}...")
    t0 = time.time()
    r = post(f"/test/submit/{session_id}", token=TOKEN, json=answers, timeout=300)
    elapsed = time.time() - t0
    ok = check("POST /test/submit returns 200", r.status_code == 200,
               f"({elapsed:.0f}s)" if r.status_code == 200
               else f"({elapsed:.0f}s) {r.text[:150]}")

    if ok:
        SUB_RESULT = r.json()
        evals = SUB_RESULT.get("eval_results", [])
        check("eval_results present", len(evals) > 0, str(len(evals)) + " results")
        check("eval_results count matches questions", len(evals) == len(questions))
        check("All results have score", all("score" in e for e in evals))
        check("All results have feedback", all(bool(e.get("feedback")) for e in evals))
        check("Scores are non-negative", all(e["score"] >= 0 for e in evals))
        check("Scores don't exceed max_score",
              all(e["score"] <= e["max_score"] for e in evals))
        check("total_score present", "total_score" in SUB_RESULT)
        check("percentage present", "percentage" in SUB_RESULT)
        check("mentor_advice present", bool(SUB_RESULT.get("mentor_advice")))

        ma = SUB_RESULT.get("mentor_advice") or {}
        check("Mentor has recommendations", len(ma.get("recommendations", [])) > 0)
        check("Mentor has study_plan_summary", bool(ma.get("study_plan_summary")))
        print(f"  [INFO] Score: {SUB_RESULT.get('total_score')}/{SUB_RESULT.get('total_marks')} "
              f"({SUB_RESULT.get('percentage')}%)")

        r_bad = post("/test/submit/99999999", token=TOKEN, json={"1": "test"}, timeout=10)
        check("Submit to invalid session returns 404", r_bad.status_code == 404)


# -------------------------------------------------------------------------
# 7. MCQ EXACT MATCH
# -------------------------------------------------------------------------

section("7. MCQ exact-match scoring")

if GEN_MATHS and SUB_RESULT:
    mcq_ids = {q["id"] for q in GEN_MATHS["questions"] if q["type"] == "mcq"}
    mcq_res = [e for e in SUB_RESULT.get("eval_results", [])
               if e["question_id"] in mcq_ids]
    if not mcq_res:
        print("  [WARN] No MCQ questions in this test -- skipping")
    else:
        check("MCQ results returned", len(mcq_res) > 0, str(len(mcq_res)) + " MCQs")
        check("MCQ scores are binary (0 or full marks)",
              all(e["score"] in (0.0, float(e["max_score"])) for e in mcq_res),
              str([(e["score"], e["max_score"]) for e in mcq_res[:3]]))
else:
    print("  SKIP -- no submission result")


# -------------------------------------------------------------------------
# 8. MASTERY TRACKING
# -------------------------------------------------------------------------

section("8. Mastery tracking")

r = get("/student/mastery/Mathematics", token=TOKEN, timeout=10)
check("GET /student/mastery/Mathematics returns 200", r.status_code == 200)
mastery_rows = r.json() if r.status_code == 200 else []

if SUB_RESULT:
    check("Mastery rows created after submission",
          len(mastery_rows) > 0, str(len(mastery_rows)) + " rows")
    if mastery_rows:
        row = mastery_rows[0]
        check("Mastery row has required fields",
              all(k in row for k in ["topic_name", "chapter_name", "mastery", "attempts"]))
        check("Mastery value in [0,1]",
              all(0.0 <= rr["mastery"] <= 1.0 for rr in mastery_rows))
        check("Attempts > 0 after submission",
              all(rr["attempts"] > 0 for rr in mastery_rows))
else:
    print("  [INFO] Mastery rows (no submission yet): " + str(len(mastery_rows)))

r2 = get("/student/mastery/Nonexistent", token=TOKEN, timeout=5)
check("Mastery for unknown subject returns 200 empty list",
      r2.status_code == 200 and r2.json() == [])


# -------------------------------------------------------------------------
# 9. STUDENT SESSIONS
# -------------------------------------------------------------------------

section("9. Student sessions history")

r = get("/student/sessions", token=TOKEN, timeout=10)
check("GET /student/sessions returns 200", r.status_code == 200)
sessions = r.json() if r.status_code == 200 else []
check("At least 2 sessions exist", len(sessions) >= 2,
      str(len(sessions)) + " sessions")
if sessions:
    s = sessions[0]
    check("Session has required fields",
          all(k in s for k in ["id", "subject_name", "mode", "started_at"]))
    check("Session subject_name non-empty", bool(s.get("subject_name")))


# -------------------------------------------------------------------------
# 10. SSE STREAM
# -------------------------------------------------------------------------

section("10. SSE event stream")

if GEN_MATHS:
    sid = GEN_MATHS["session_id"]
    r = get(f"/test/stream/{sid}", token=TOKEN, timeout=10)
    check("GET /test/stream/{id} returns 200", r.status_code == 200)
    check("Content-Type is text/event-stream",
          "text/event-stream" in r.headers.get("content-type", ""))
    lines = [l for l in r.text.splitlines() if l.startswith("data:")]
    check("Stream has at least 1 event", len(lines) >= 1, str(len(lines)) + " events")
    check("Stream ends with done", "done" in r.text)
else:
    print("  SKIP -- no session")


# -------------------------------------------------------------------------
# 11. PROMPT-TO-TOPIC ROUTING
# -------------------------------------------------------------------------

section("11. Prompt-to-topic routing accuracy")

ROUTING_CASES = [
    ("test me on quadratic equations", "Mathematics", "quadratic"),
    ("test me on carbon and its compounds", "Science", "carbon"),
    ("test me on heredity and evolution", "Science", "heredit"),
]

for prompt, subject, kw in ROUTING_CASES:
    print(f"  [INFO] Routing: \"{prompt}\" -> {subject}")
    try:
        r = post("/test/generate", token=TOKEN, json={
            "subject": subject, "mode": "practice", "raw_prompt": prompt,
        }, timeout=120)
        if r.status_code != 200:
            check(f"Generate '{prompt[:35]}'", False, r.text[:100])
            continue
        data = r.json()
        questions = data.get("questions", [])
        if not questions:
            check(f"'{prompt[:35]}' -> has questions", False, "0 questions")
            continue
        relevant = any(
            kw.lower() in q.get("chapter_name", "").lower() or
            kw.lower() in q.get("topic_name", "").lower() or
            kw.lower() in q.get("text", "").lower()
            for q in questions
        )
        check(f"'{prompt[:35]}' -> relevant questions",
              relevant,
              "topics: " + str([q["topic_name"] for q in questions[:3]]))
    except Exception as e:
        check(f"Routing '{prompt[:35]}'", False, str(e)[:80])


# -------------------------------------------------------------------------
# 12. EDGE CASES
# -------------------------------------------------------------------------

section("12. Edge cases")

# Invalid subject -- should return 500 with a detail (Subject not found)
r = post("/test/generate", token=TOKEN,
         json={"subject": "Astrology", "mode": "practice"}, timeout=30)
check("Invalid subject returns 4xx or 500",
      r.status_code in (400, 422, 500),
      f"status={r.status_code}")

# Invalid mode -- Pydantic validator should reject with 422
r = post("/test/generate", token=TOKEN,
         json={"subject": "Mathematics", "mode": "cheat"}, timeout=10)
check("Invalid mode returns 422", r.status_code == 422)

# Empty prompt -- should still work (falls back to generic test for subject)
print("  [INFO] Testing empty prompt fallback...")
r = post("/test/generate", token=TOKEN,
         json={"subject": "English", "mode": "practice", "raw_prompt": ""},
         timeout=120)
check("Empty prompt still generates test", r.status_code == 200,
      f"status={r.status_code}" + (f" {r.text[:80]}" if r.status_code != 200 else ""))

# No auth
r = post("/test/generate",
         json={"subject": "Mathematics", "mode": "practice"}, timeout=5)
check("Unauthenticated generate returns 401/403", r.status_code in (401, 403))


# -------------------------------------------------------------------------
# SUMMARY
# -------------------------------------------------------------------------

section("SUMMARY")

passed = sum(1 for _, ok in _results if ok)
failed = sum(1 for _, ok in _results if not ok)
total  = len(_results)

print(f"\n  Total : {total}")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")

if failed:
    print("\n  Failed tests:")
    for label, ok in _results:
        if not ok:
            print(f"    x {label}")

print()
if failed == 0:
    print("  [OK] All tests passed -- pipeline is healthy.")
elif failed <= 3:
    print("  [!!] Minor issues -- review FAIL lines above.")
else:
    print("  [XX] Multiple failures -- check backend logs.")
print()

sys.exit(0 if failed == 0 else 1)
