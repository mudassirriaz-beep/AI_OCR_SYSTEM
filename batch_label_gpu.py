"""
GPU-accelerated batch labeling using the fine-tuned DONUT model.
Much faster than CPU OCR — processes each image in ~3-5 seconds on GPU.

Usage:  python batch_label_gpu.py
"""
import json, re, os, sys
from pathlib import Path

import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel

BASE_DIR   = Path(__file__).parent
MODEL_DIR  = BASE_DIR / "models" / "donut_finetuned"
TASK_START = "<s_parse>"
TASK_END   = "</s_parse>"
MAX_LENGTH = 512
IMG_EXTS   = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

# Folders to label — add more here as needed
SOURCES = [
    (BASE_DIR / "New_data" / "New_data" / "cnic_images",    "CNIC"),
    (BASE_DIR / "New_data" / "New_data" / "driving_license", "DL"),
    (BASE_DIR / "Final_images" / "Cnic_images",    "CNIC"),
    (BASE_DIR / "Final_images" / "Driving_license", "DL"),
]

CNIC_FIELDS = ["Full_Name","Father_Name","Gender","Identity_Number",
               "DOB","Date_of_Issue","Date_of_Expiry","Country"]
DL_FIELDS   = ["Full_Name","Father_Name","Gender","License_Number",
               "DOB","Date_of_Issue","Date_of_Expiry","Country","Category","Province"]


def load_model():
    if not MODEL_DIR.exists():
        print(f"[ERROR] Model not found at {MODEL_DIR}")
        print("        Run finetune_donut.py first.")
        sys.exit(1)
    print(f"[DONUT] Loading model from {MODEL_DIR} ...")
    processor = DonutProcessor.from_pretrained(str(MODEL_DIR))
    model     = VisionEncoderDecoderModel.from_pretrained(str(MODEL_DIR))
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    print(f"[DONUT] Loaded on {device} ({torch.cuda.get_device_name(0) if device.type=='cuda' else 'CPU'})")
    return processor, model, device


def infer(img_path, processor, model, device) -> dict:
    img       = Image.open(img_path).convert("RGB")
    pv        = processor(img, return_tensors="pt").pixel_values.to(device)
    start_id  = processor.tokenizer.convert_tokens_to_ids([TASK_START])[0]
    dec_input = torch.tensor([[start_id]], device=device)

    with torch.no_grad():
        out = model.generate(
            pv,
            decoder_input_ids=dec_input,
            max_length=MAX_LENGTH,
            num_beams=4,
            early_stopping=True,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
        )

    pred = processor.tokenizer.decode(out[0], skip_special_tokens=False)

    last = pred.rfind(TASK_START)
    if last >= 0:
        after     = pred[last + len(TASK_START):].strip()
        end_idx   = after.find(TASK_END)
        candidate = after[:end_idx].strip() if end_idx >= 0 else after.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return {}


def run():
    processor, model, device = load_model()

    total = done = skipped = failed = 0

    for folder, doc_type in SOURCES:
        if not folder.exists():
            print(f"[SKIP] Folder not found: {folder}")
            continue

        images = sorted(
            f for f in folder.iterdir()
            if f.suffix.lower() in IMG_EXTS
        )
        labels_dir = folder / "labels"
        labels_dir.mkdir(exist_ok=True)

        print(f"\n[{doc_type}] {len(images)} images in {folder.name}/")
        total += len(images)
        fields = CNIC_FIELDS if doc_type == "CNIC" else DL_FIELDS

        for i, img_path in enumerate(images, 1):
            label_path = labels_dir / (img_path.stem + ".json")

            # Skip already reviewed labels
            if label_path.exists():
                try:
                    d = json.load(open(label_path, encoding="utf-8"))
                    if d.get("gt_parse", {}).get("_reviewed"):
                        skipped += 1
                        continue
                except Exception:
                    pass

            print(f"  [{i:3d}/{len(images)}] {img_path.name}", end=" ... ", flush=True)

            try:
                raw = infer(img_path, processor, model, device)

                gt = {"doc_type": doc_type, "_reviewed": False}
                for field in fields:
                    gt[field] = str(raw.get(field, "")).strip()

                # Rough confidence: fraction of non-empty fields
                filled = sum(1 for f in fields if gt.get(f, "").strip())
                conf   = filled / len(fields)
                gt["_confidence"] = round(conf, 2)

                with open(label_path, "w", encoding="utf-8") as f:
                    json.dump({"gt_parse": gt}, f, ensure_ascii=False, indent=2)

                print(f"OK  conf={conf:.0%}  [{filled}/{len(fields)} fields]")
                done += 1

            except Exception as e:
                print(f"FAILED: {e}")
                failed += 1

    print(f"\n{'='*55}")
    print(f"Labeled : {done}")
    print(f"Skipped (already reviewed): {skipped}")
    print(f"Failed  : {failed}")
    print(f"Total   : {total}")
    print(f"{'='*55}")
    print("\nDone! Now run:  python review_labels.py")


if __name__ == "__main__":
    run()
