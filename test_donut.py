"""
Test the fine-tuned DONUT model on a sample of reviewed images.
Loads the BEST saved checkpoint and measures real field-level accuracy.

Usage:
    python test_donut.py
    python test_donut.py path/to/image.jpg
"""
import json
import re
import sys
from pathlib import Path

import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel

BASE_DIR   = Path(__file__).parent
MODEL_DIR  = BASE_DIR / "models" / "donut_finetuned"
DATASET_ROOT = BASE_DIR / "Dataset_Images" / "Dataset_Images"
IMG_EXTS   = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
TASK_START = "<s_parse>"
TASK_END   = "</s_parse>"
MAX_LENGTH = 512


def load_model():
    print(f"[DONUT] Loading model from {MODEL_DIR} …")
    processor = DonutProcessor.from_pretrained(str(MODEL_DIR))
    model     = VisionEncoderDecoderModel.from_pretrained(str(MODEL_DIR))
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    print(f"[DONUT] Loaded on {device}")
    return processor, model, device


def extract(image_path: str, processor, model, device) -> dict:
    img = Image.open(image_path).convert("RGB")
    pv  = processor(img, return_tensors="pt").pixel_values.to(device)

    start_id      = processor.tokenizer.convert_tokens_to_ids([TASK_START])[0]
    decoder_input = torch.tensor([[start_id]], device=device)

    with torch.no_grad():
        out = model.generate(
            pv,
            decoder_input_ids=decoder_input,
            max_length=MAX_LENGTH,
            num_beams=4,
            early_stopping=True,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
        )

    pred = processor.tokenizer.decode(out[0], skip_special_tokens=False)

    # Find the LAST task-start token and extract JSON up to task-end
    last_start = pred.rfind(TASK_START)
    if last_start >= 0:
        after     = pred[last_start + len(TASK_START):].strip()
        end       = after.find(TASK_END)
        candidate = after[:end].strip() if end >= 0 else after.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # Fallback: first balanced JSON object
    m2 = re.search(r'\{.*?\}', pred, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group())
        except json.JSONDecodeError:
            pass
    return {}


def evaluate(processor, model, device, n: int = 50):
    """Measure field-level accuracy on reviewed val samples."""
    samples = []
    for subfolder in DATASET_ROOT.iterdir():
        if not subfolder.is_dir():
            continue
        ldir = subfolder / "labels"
        if not ldir.exists():
            continue
        for lf in ldir.glob("*.json"):
            try:
                data = json.load(open(lf, encoding="utf-8"))
            except Exception:
                continue
            gt = data.get("gt_parse", {})
            if not gt.get("_reviewed"):
                continue
            for ext in IMG_EXTS:
                img_p = subfolder / (lf.stem + ext)
                if img_p.exists():
                    samples.append({"img_path": img_p, "gt": gt})
                    break

    import random
    random.seed(42)
    random.shuffle(samples)
    subset = samples[:n]

    correct = total = 0
    field_stats: dict[str, list] = {}

    for item in subset:
        pred = extract(str(item["img_path"]), processor, model, device)
        gt   = item["gt"]

        for key, expected in gt.items():
            if key.startswith("_") or not expected:
                continue
            total += 1
            match  = str(pred.get(key, "")).strip().lower() == str(expected).strip().lower()
            correct += int(match)
            field_stats.setdefault(key, []).append(int(match))

    print(f"\n{'='*55}")
    print(f"  Overall field accuracy: {correct}/{total}  =  {correct/total:.1%}")
    print(f"{'='*55}")
    print(f"  Per-field breakdown:")
    for field, results in sorted(field_stats.items()):
        pct = sum(results) / len(results)
        bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
        print(f"  {field:<22} [{bar}]  {pct:.0%}  ({sum(results)}/{len(results)})")
    print(f"{'='*55}\n")
    return correct / total if total else 0


def main():
    if not MODEL_DIR.exists():
        print(f"[ERROR] Model not found at {MODEL_DIR}")
        print("        Run finetune_donut.py first.")
        return

    processor, model, device = load_model()

    if len(sys.argv) > 1:
        # Single image test
        img_path = sys.argv[1]
        print(f"\n[TEST] Extracting from: {img_path}")
        result = extract(img_path, processor, model, device)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Full accuracy evaluation
        print("\n[EVAL] Running accuracy test on 50 reviewed samples…")
        evaluate(processor, model, device, n=50)


if __name__ == "__main__":
    main()
