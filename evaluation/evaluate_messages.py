import os
import sys
import json
import asyncio
from typing import List, Tuple
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score

# Ensure backend can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.services.message_service import analyze_message

def load_uci_dataset(file_path: str, max_samples: int = 150) -> List[Tuple[str, int]]:
    """Load stratified subset from UCI SMSSpamCollection (label: ham=0, spam=1)."""
    dataset = []
    spam_count = 0
    ham_count = 0
    half = max_samples // 2

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                label_str, text = parts
                if label_str == "spam" and spam_count < half:
                    dataset.append((text, 1))
                    spam_count += 1
                elif label_str == "ham" and ham_count < half:
                    dataset.append((text, 0))
                    ham_count += 1
            if spam_count >= half and ham_count >= half:
                break
    return dataset

async def run_evaluation():
    dataset_path = os.path.join(os.path.dirname(__file__), "SMSSpamCollection")
    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}")
        return

    print("Loading UCI SMS Spam Collection...")
    samples = load_uci_dataset(dataset_path, max_samples=100)
    print(f"Loaded {len(samples)} stratified test samples (50 ham, 50 spam).")

    print("Evaluating SafeLens Message Analysis Pipeline...")
    sem = asyncio.Semaphore(10)

    async def eval_sample(text: str, label: int, idx: int):
        async with sem:
            res = await analyze_message(text)
            risk = res.get("risk_category", "Low Risk")
            pred = 1 if risk in ["High Risk", "Caution"] else 0
            if (idx + 1) % 20 == 0 or (idx + 1) == len(samples):
                print(f"Processed {idx + 1}/{len(samples)} samples...")
            return label, pred

    results = await asyncio.gather(*[eval_sample(text, label, idx) for idx, (text, label) in enumerate(samples)])
    y_true = [r[0] for r in results]
    y_pred = [r[1] for r in results]

    # Compute metrics
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()

    report = {
        "dataset": "UCI SMS Spam Collection (Held-Out Benchmark)",
        "sample_size": len(samples),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "scope_limitations": [
            "Dataset is historical English SMS and does not cover modern UPI payment scams or Indian multilingual threats.",
            "Text heuristics prioritize conservative caution: some promotional ham messages may be flagged for review."
        ]
    }

    report_path = os.path.join(os.path.dirname(__file__), "evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "="*50)
    print("SAFELENS MODEL EVALUATION RESULTS (UCI BENCHMARK)")
    print("="*50)
    print(f"Total Samples Evaluated: {len(samples)}")
    print(f"True Positives (Threats Caught): {tp}")
    print(f"True Negatives (Benign Allowed): {tn}")
    print(f"False Positives (Benign Flagged): {fp}")
    print(f"False Negatives (Threats Missed): {fn}")
    print(f"Precision: {prec:.2%}")
    print(f"Recall:    {rec:.2%}")
    print(f"F1-Score:  {f1:.2%}")
    print("="*50)
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
