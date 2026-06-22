"""Quick debug: verify rfind extraction on a few reviewed images."""
import json, re, torch
from pathlib import Path
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel

BASE_DIR  = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models" / "donut_finetuned"
TASK_START = "<s_parse>"
TASK_END   = "</s_parse>"

processor = DonutProcessor.from_pretrained(str(MODEL_DIR))
model     = VisionEncoderDecoderModel.from_pretrained(str(MODEL_DIR))
device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device).eval()

start_id = processor.tokenizer.convert_tokens_to_ids([TASK_START])[0]
print(f"TASK_START id={start_id}  TASK_END id={processor.tokenizer.convert_tokens_to_ids([TASK_END])[0]}")

DATASET_ROOT = BASE_DIR / "Dataset_Images" / "Dataset_Images"
samples = []
for subfolder in DATASET_ROOT.iterdir():
    ldir = subfolder / "labels"
    if not ldir.exists():
        continue
    for lf in ldir.glob("*.json"):
        try:
            data = json.load(open(lf))
        except Exception:
            continue
        if not data.get("gt_parse", {}).get("_reviewed"):
            continue
        for ext in [".jpg",".jpeg",".png",".bmp"]:
            img_p = subfolder / (lf.stem + ext)
            if img_p.exists():
                samples.append({"img": img_p, "gt": data["gt_parse"]})
                break
    if len(samples) >= 5:
        break

correct = total = 0
for i, s in enumerate(samples[:5]):
    print(f"\n=== Sample {i+1}: {s['img'].name} ===")
    gt_clean = {k:v for k,v in s['gt'].items() if not k.startswith('_')}
    print(f"GT: {json.dumps(gt_clean, ensure_ascii=False)[:250]}")

    img = Image.open(s["img"]).convert("RGB")
    pv  = processor(img, return_tensors="pt").pixel_values.to(device)
    dec = torch.tensor([[start_id]], device=device)

    with torch.no_grad():
        out = model.generate(
            pv,
            decoder_input_ids=dec,
            max_length=512,
            num_beams=4,
            early_stopping=True,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
        )

    pred = processor.tokenizer.decode(out[0], skip_special_tokens=False)

    # rfind extraction
    last_start = pred.rfind(TASK_START)
    parsed = {}
    if last_start >= 0:
        after     = pred[last_start + len(TASK_START):].strip()
        end_idx   = after.find(TASK_END)
        candidate = after[:end_idx].strip() if end_idx >= 0 else after.strip()
        try:
            parsed = json.loads(candidate)
            print(f"PRED: {json.dumps(parsed, ensure_ascii=False)[:250]}")
        except Exception as e:
            print(f"JSON error: {e}")
            print(f"Candidate: {candidate[:150]}")
    else:
        print(f"No TASK_START found. Raw: {pred[:200]}")

    # Compare
    for key, expected in gt_clean.items():
        if key.startswith("_") or not expected or expected == "None":
            continue
        total += 1
        got = str(parsed.get(key, "")).strip().lower()
        exp = str(expected).strip().lower()
        if got == exp:
            correct += 1
        else:
            print(f"  MISMATCH {key}: expected={expected!r} got={parsed.get(key,'')!r}")

print(f"\nField accuracy on {len(samples)} samples: {correct}/{total} = {correct/total:.1%}" if total else "No data")
