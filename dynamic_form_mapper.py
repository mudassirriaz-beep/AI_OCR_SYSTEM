import json
import re

def find_entry_ids_and_labels(obj, path=""):
    """
    Recursively walk through the parsed JSON data.
    When we find a string that looks like 'entry.123456789',
    we try to find a corresponding label (question text) nearby.
    """
    results = []
    
    if isinstance(obj, dict):
        # Check if this dict has an entry ID
        for key, value in obj.items():
            if isinstance(value, str) and re.match(r'entry\.\d+', value):
                # Found an entry ID
                # Look for a 'label' or 'question' in same dict or nearby
                label = None
                # Try to get from sibling keys
                if "label" in obj:
                    label = obj["label"]
                elif "question" in obj:
                    label = obj["question"]
                elif "title" in obj:
                    label = obj["title"]
                # If not, we'll search in the parent structure later
                results.append((value, label))
            else:
                results.extend(find_entry_ids_and_labels(value, path + f"/{key}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            results.extend(find_entry_ids_and_labels(item, path + f"[{idx}]"))
    return results

def extract_form_mapping(raw_json_path):
    with open(raw_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # First, collect all entry IDs with possible labels
    entries = find_entry_ids_and_labels(data)
    
    # Build mapping: entry_id -> label (clean)
    mapping = {}
    for entry_id, maybe_label in entries:
        # If we already have this entry, skip (keep first)
        if entry_id in mapping:
            continue
        # Try to find a better label by scanning the JSON again (simple heuristic)
        # For Google Forms, the label is usually in the same array element as the entry ID.
        # We'll use a second pass: locate the entry ID in the structure and get the question text from index [1] of the parent list.
        # But for simplicity, we rely on the recursive search.
        if maybe_label:
            # Clean label: remove asterisk, extra spaces
            label = re.sub(r'\s*\*$', '', maybe_label).strip()
            mapping[entry_id] = label
        else:
            # No label found yet; we'll assign a temporary name
            mapping[entry_id] = f"Field_{len(mapping)+1}"
    
    # If we didn't get any labels, try a more targeted parse:
    if not any(mapping.values()):
        # Known structure: data[1][1] is list of pages; each page[1] is list of questions
        # Each question is a list where index 1 is label, index 4[0][0] is entry ID.
        try:
            pages = data[1][1]
            for page in pages:
                for question in page[1]:
                    label = question[1]
                    entry_id = question[4][0][0]
                    label = re.sub(r'\s*\*$', '', label).strip()
                    mapping[entry_id] = label
        except (IndexError, TypeError, KeyError):
            pass
    
    # Invert to {label: entry_id} for easier use in form submission
    label_to_entry = {v: k for k, v in mapping.items() if v}
    return label_to_entry

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = "raw_form_data.json"
    mapping = extract_form_mapping(json_file)
    if mapping:
        print("✅ Extracted mapping (label -> entry_id):")
        for label, entry_id in mapping.items():
            print(f"  {label} → {entry_id}")
        with open("form_fields_dynamic.json", "w") as f:
            json.dump(mapping, f, indent=2)
        print("\n💾 Saved to 'form_fields_dynamic.json'")
    else:
        print("❌ No fields found. Check the JSON structure.")