"""
Batch OCR labeling — runs OCR on every image in Dataset_Images and saves
preliminary labels. Run this once; then use review_labels.py to review.
"""
import os, sys, json

DATASET_ROOT = os.path.join(os.path.dirname(__file__),
                            "Dataset_Images", "Dataset_Images")
SUBFOLDERS = [
    ("CNIC_Images",            "CNIC"),
    ("Driving_License_images", "DL"),
]
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def run():
    total = done = skipped = failed = 0

    for subfolder, doc_type in SUBFOLDERS:
        folder     = os.path.join(DATASET_ROOT, subfolder)
        labels_dir = os.path.join(folder, "labels")
        os.makedirs(labels_dir, exist_ok=True)

        images = sorted(
            f for f in os.listdir(folder)
            if os.path.splitext(f.lower())[1] in IMG_EXTS
        )
        total += len(images)

        for i, fname in enumerate(images, 1):
            stem       = os.path.splitext(fname)[0]
            label_path = os.path.join(labels_dir, stem + ".json")

            if os.path.exists(label_path):
                skipped += 1
                continue

            img_path = os.path.join(folder, fname)
            print(f"[{doc_type}] {i}/{len(images)} — {fname}", end=" ... ", flush=True)

            try:
                if doc_type == "CNIC":
                    import brain_format_cnic
                    result = brain_format_cnic.extract_cnic_info(img_path)
                else:
                    import brain_format_dl
                    result = brain_format_dl.extract_dl_info(img_path)

                # Strip internal keys
                gt = {k: str(v).strip() for k, v in result.items()
                      if not k.startswith("_") and k not in ("Photo_Path", "Photo_Base64")}
                gt["doc_type"]  = doc_type
                gt["_reviewed"] = False   # marks as not yet confirmed by user

                with open(label_path, "w", encoding="utf-8") as f:
                    json.dump({"gt_parse": gt}, f, ensure_ascii=False, indent=2)

                conf = result.get("_confidence", 0)
                print(f"OK  conf={conf:.0%}")
                done += 1

            except Exception as e:
                print(f"FAILED: {e}")
                failed += 1

    print(f"\n{'='*50}")
    print(f"Done.  Labeled: {done}  |  Skipped (existing): {skipped}  |  Failed: {failed}")
    print(f"Now run:  python review_labels.py")


if __name__ == "__main__":
    run()
