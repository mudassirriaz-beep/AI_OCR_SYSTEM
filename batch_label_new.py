"""
Batch OCR labeling for New_data folder.
Runs OCR on every image and saves preliminary labels.
Then opens review_labels.py automatically.
"""
import os, sys, json

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
NEW_DATA_ROOT = os.path.join(BASE_DIR, "New_data", "New_data")

SUBFOLDERS = [
    ("cnic_images",    "CNIC"),
    ("driving_license","DL"),
]
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def run():
    total = done = skipped = failed = 0

    for subfolder, doc_type in SUBFOLDERS:
        folder     = os.path.join(NEW_DATA_ROOT, subfolder)
        labels_dir = os.path.join(folder, "labels")
        os.makedirs(labels_dir, exist_ok=True)

        images = sorted(
            f for f in os.listdir(folder)
            if os.path.splitext(f.lower())[1] in IMG_EXTS
        )
        total += len(images)
        print(f"\n[{doc_type}] {len(images)} images found in {subfolder}/")

        for i, fname in enumerate(images, 1):
            stem       = os.path.splitext(fname)[0]
            label_path = os.path.join(labels_dir, stem + ".json")

            if os.path.exists(label_path):
                try:
                    d = json.load(open(label_path, encoding="utf-8"))
                    if d.get("gt_parse"):
                        skipped += 1
                        continue
                except Exception:
                    pass

            img_path = os.path.join(folder, fname)
            print(f"  [{i:3d}/{len(images)}] {fname}", end=" ... ", flush=True)

            try:
                if doc_type == "CNIC":
                    import brain_format_cnic
                    result = brain_format_cnic.extract_cnic_info(img_path)
                else:
                    import brain_format_dl
                    result = brain_format_dl.extract_dl_info(img_path)

                gt = {k: str(v).strip() for k, v in result.items()
                      if not k.startswith("_") and k not in ("Photo_Path", "Photo_Base64")}
                gt["doc_type"]  = doc_type
                gt["_reviewed"] = False

                with open(label_path, "w", encoding="utf-8") as f:
                    json.dump({"gt_parse": gt}, f, ensure_ascii=False, indent=2)

                conf = result.get("_confidence", 0)
                print(f"OK  conf={conf:.0%}")
                done += 1

            except Exception as e:
                print(f"FAILED: {e}")
                failed += 1

    print(f"\n{'='*55}")
    print(f"Labeled : {done}")
    print(f"Skipped (already labeled): {skipped}")
    print(f"Failed  : {failed}")
    print(f"Total   : {total}")
    print(f"{'='*55}")
    print("\nDone! Now opening review tool...")


if __name__ == "__main__":
    run()
