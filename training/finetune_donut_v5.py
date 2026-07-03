"""
Fine-tune DONUT Round 5 — starting from V4 checkpoint.

- Loads from models/donut_finetuned/ (V4 — never modified)
- Saves best checkpoint to models/donut_round5/ (new folder)
- LR = 3e-6 (lower than V4's 1e-5 to reduce overfitting)
- Early stopping patience = 6
"""

import json
import os
import random
import re
from pathlib import Path

import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import DataLoader, Dataset
from torch.optim import AdamW
from transformers import (
    DonutProcessor,
    VisionEncoderDecoderModel,
    get_scheduler,
)
from tqdm import tqdm

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
V4_DIR      = BASE_DIR / "models" / "donut_finetuned"   # source — never written
OUTPUT_DIR  = BASE_DIR / "models" / "donut_round5"      # V5 destination
IMG_EXTS    = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

DATASET_ROOTS = [
    BASE_DIR / "Dataset_Images" / "Dataset_Images",
    BASE_DIR / "New_data" / "New_data",
    BASE_DIR / "Final_images",
]

# ── Hyperparameters ───────────────────────────────────────────────────────────
IMAGE_SIZE   = [960, 960]
MAX_LENGTH   = 512
BATCH_SIZE   = 1
GRAD_ACCUM   = 8
EPOCHS       = 20
LR           = 3e-6        # lower than V4 (1e-5) to avoid overfitting
WARMUP_RATIO = 0.05
VAL_SPLIT    = 0.15
EARLY_STOP   = 6
SEED         = 42
TASK_START   = "<s_parse>"
TASK_END     = "</s_parse>"


# ── Data loading ──────────────────────────────────────────────────────────────

def _find_image(folder: Path, stem: str) -> Path | None:
    for ext in IMG_EXTS:
        p = folder / (stem + ext)
        if p.exists():
            return p
    return None


def load_reviewed_samples() -> list[dict]:
    samples = []
    for dataset_root in DATASET_ROOTS:
        if not dataset_root.exists():
            continue
        for subfolder in dataset_root.iterdir():
            if not subfolder.is_dir():
                continue
            labels_dir = subfolder / "labels"
            if not labels_dir.exists():
                continue
            for lf in sorted(labels_dir.glob("*.json")):
                try:
                    with open(lf, encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue
                gt = data.get("gt_parse", {})
                if not gt.get("_reviewed", False):
                    continue
                img_path = _find_image(subfolder, lf.stem)
                if img_path is None:
                    continue
                output = {k: v for k, v in gt.items()
                          if not k.startswith("_") and v not in (None, "", [])}
                if not output:
                    continue
                target_str = TASK_START + json.dumps(output, ensure_ascii=False) + TASK_END
                samples.append({"img_path": img_path, "target_str": target_str})

    random.seed(SEED)
    random.shuffle(samples)
    print(f"[DATA]  {len(samples)} reviewed samples found")
    return samples


# ── Dataset ───────────────────────────────────────────────────────────────────

class IDCardDataset(Dataset):
    def __init__(self, samples, processor):
        self.samples   = samples
        self.processor = processor

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        try:
            img = Image.open(item["img_path"]).convert("RGB")
        except Exception:
            img = Image.new("RGB", (IMAGE_SIZE[1], IMAGE_SIZE[0]), color=255)

        pixel_values = self.processor(
            img, return_tensors="pt"
        ).pixel_values.squeeze(0)

        labels = self.processor.tokenizer(
            item["target_str"],
            add_special_tokens=False,
            max_length=MAX_LENGTH,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).input_ids.squeeze(0)

        labels[labels == self.processor.tokenizer.pad_token_id] = -100
        return {"pixel_values": pixel_values, "labels": labels}


# ── Evaluation ────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    last_start = text.rfind(TASK_START)
    if last_start >= 0:
        after     = text[last_start + len(TASK_START):].strip()
        end       = after.find(TASK_END)
        candidate = after[:end].strip() if end >= 0 else after.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


def evaluate_accuracy(model, processor, samples, device, n=30) -> float:
    model.eval()
    subset  = random.sample(samples, min(n, len(samples)))
    correct = total = 0

    for item in subset:
        try:
            img = Image.open(item["img_path"]).convert("RGB")
        except Exception:
            continue

        pv            = processor(img, return_tensors="pt").pixel_values.to(device)
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

        pred_str = processor.tokenizer.decode(out[0], skip_special_tokens=False)
        pred = _extract_json(pred_str)
        gt   = _extract_json(item["target_str"])

        for key, expected in gt.items():
            if not expected or key.startswith("_"):
                continue
            total   += 1
            correct += int(str(pred.get(key, "")).strip().lower() ==
                           str(expected).strip().lower())

    return (correct / total) if total > 0 else 0.0


# ── Training ──────────────────────────────────────────────────────────────────

def train():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[SETUP] Device : {device}")
    if device.type == "cuda":
        print(f"[SETUP] GPU    : {torch.cuda.get_device_name(0)}")

    # Load from V4 — never write back to V4_DIR
    if not (V4_DIR / "config.json").exists():
        print(f"[ERROR] V4 checkpoint not found at {V4_DIR}")
        return
    print(f"[MODEL] Loading V4 checkpoint from: {V4_DIR}")
    print(f"[MODEL] Will save V5 to           : {OUTPUT_DIR}")
    processor = DonutProcessor.from_pretrained(str(V4_DIR))
    model     = VisionEncoderDecoderModel.from_pretrained(str(V4_DIR))
    processor.feature_extractor.size      = IMAGE_SIZE
    processor.feature_extractor.do_resize = True
    model.config.encoder.image_size       = IMAGE_SIZE
    model.config.decoder.max_length       = MAX_LENGTH
    model.config.pad_token_id             = processor.tokenizer.pad_token_id
    model.config.decoder_start_token_id   = processor.tokenizer.convert_tokens_to_ids(
        [TASK_START]
    )[0]
    model.to(device)

    # Data
    samples = load_reviewed_samples()
    if not samples:
        print("[ERROR] No reviewed samples found.")
        return

    n_val      = max(1, int(len(samples) * VAL_SPLIT))
    val_data   = samples[:n_val]
    train_data = samples[n_val:]
    print(f"[DATA]  Train={len(train_data)}  Val={len(val_data)}")

    train_loader = DataLoader(
        IDCardDataset(train_data, processor),
        batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True
    )
    val_loader = DataLoader(
        IDCardDataset(val_data, processor),
        batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True
    )

    optimizer    = AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    total_steps  = (len(train_loader) // GRAD_ACCUM) * EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)
    scheduler    = get_scheduler(
        "cosine", optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    best_val_loss = float("inf")
    patience      = 0
    log_path      = OUTPUT_DIR / "training_log.txt"

    print(f"\n{'='*60}")
    print(f"Round 5 fine-tuning  |  LR={LR}  |  max {EPOCHS} epochs  |  patience={EARLY_STOP}")
    print(f"V4 accuracy baseline : 90.5%")
    print(f"{'='*60}\n")

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(
                tqdm(train_loader, desc=f"Epoch {epoch:02d}/{EPOCHS} [train]")):
            pv     = batch["pixel_values"].to(device)
            labels = batch["labels"].to(device)
            loss   = model(pixel_values=pv, labels=labels).loss / GRAD_ACCUM
            loss.backward()
            train_loss += loss.item() * GRAD_ACCUM
            if (step + 1) % GRAD_ACCUM == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_train = train_loss / len(train_loader)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in tqdm(val_loader, desc=f"Epoch {epoch:02d}/{EPOCHS} [val]  "):
                pv     = batch["pixel_values"].to(device)
                labels = batch["labels"].to(device)
                val_loss += model(pixel_values=pv, labels=labels).loss.item()
        avg_val = val_loss / len(val_loader)

        log_line = (f"Epoch {epoch:02d}  train={avg_train:.4f}  "
                    f"val={avg_val:.4f}  best={best_val_loss:.4f}")
        print(log_line)
        with open(log_path, "a") as f:
            f.write(log_line + "\n")

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            patience      = 0
            model.save_pretrained(str(OUTPUT_DIR))
            processor.save_pretrained(str(OUTPUT_DIR))
            print(f"  ✓ Best V5 checkpoint saved  (val_loss={avg_val:.4f})")
        else:
            patience += 1
            print(f"  · No improvement ({patience}/{EARLY_STOP})")
            if patience >= EARLY_STOP:
                print(f"\n[TRAIN] Early stop at epoch {epoch}")
                break

    # Evaluate best V5 checkpoint
    print("\n[EVAL] Reloading best V5 checkpoint for accuracy evaluation…")
    best_processor = DonutProcessor.from_pretrained(str(OUTPUT_DIR))
    best_model     = VisionEncoderDecoderModel.from_pretrained(str(OUTPUT_DIR))
    best_model.to(device).eval()

    acc = evaluate_accuracy(best_model, best_processor, val_data, device,
                            n=min(50, len(val_data)))
    print(f"[EVAL] V5 field accuracy: {acc:.1%}  (V4 baseline: 90.5%)")
    with open(log_path, "a") as f:
        f.write(f"\nFinal field accuracy (val): {acc:.1%}\n")
        f.write(f"V4 baseline: 90.5%\n")

    print(f"\n{'='*60}")
    print(f"Done.  V5 model saved → {OUTPUT_DIR}")
    print(f"V4 model intact       → {V4_DIR}")
    print(f"Best val loss : {best_val_loss:.4f}")
    print(f"V5 accuracy   : {acc:.1%}")
    print(f"{'='*60}")


if __name__ == "__main__":
    train()
