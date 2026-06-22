"""
Eval harness — measures Evaluator agent accuracy against a human-graded test set.
Produces the headline resume number: "grades within ±1 mark X% of the time".

Run: python -m scripts.eval_harness
"""
import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db
from app.models.db_models import Question
from app.agents.evaluator_agent import run_evaluator

EVAL_SET_PATH = os.path.join(os.path.dirname(__file__), "../../data/eval_set.json")


def run_eval():
    init_db()
    db = SessionLocal()
    try:
        with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
            eval_set = json.load(f)

        total = 0
        within_half = 0
        within_one = 0
        within_two = 0
        results_log = []

        for item in eval_set:
            q = db.query(Question).filter(Question.id == item["question_id"]).first()
            if not q:
                print(f"  ⚠️  Question {item['question_id']} not in DB — skipping")
                continue

            results = run_evaluator(
                db=db,
                question_ids=[item["question_id"]],
                answers={item["question_id"]: item["student_answer"]},
            )
            if not results:
                continue

            r = results[0]
            human_score = item["human_score"]
            diff = abs(r.score - human_score)
            total += 1

            if diff <= 0.5: within_half += 1
            if diff <= 1.0: within_one += 1
            if diff <= 2.0: within_two += 1

            results_log.append({
                "question_id": item["question_id"],
                "human_score": human_score,
                "agent_score": r.score,
                "diff": diff,
                "feedback": r.feedback,
            })
            print(f"  Q{item['question_id']}: human={human_score} agent={r.score} diff={diff:.1f}")

        print(f"\n{'='*50}")
        print(f"EVAL RESULTS  (n={total})")
        print(f"{'='*50}")
        if total > 0:
            print(f"Within ±0.5 marks : {within_half}/{total} = {within_half/total*100:.1f}%")
            print(f"Within ±1.0 marks : {within_one}/{total}  = {within_one/total*100:.1f}%  ← HEADLINE")
            print(f"Within ±2.0 marks : {within_two}/{total}  = {within_two/total*100:.1f}%")
        else:
            print("No results — check your eval_set.json and DB.")

        # Save log
        log_path = os.path.join(os.path.dirname(__file__), "../../data/eval_results.json")
        with open(log_path, "w") as f:
            json.dump(results_log, f, indent=2)
        print(f"\nDetailed log saved to {log_path}")

    finally:
        db.close()


if __name__ == "__main__":
    run_eval()
