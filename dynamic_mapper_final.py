import json
import re

def extract_fields_from_fb_data(data):
    """Extract { label: "entry.xxx" } mapping from FB_PUBLIC_LOAD_DATA_"""
    mapping = {}
    try:
        questions = data[1][1]   # Standard location
    except (IndexError, TypeError):
        # Fallback: recursively search for pattern
        return fallback_extract(data)
    
    for q in questions:
        label = q[1]                       # question text
        # Get the entry ID (inside the 4th element: [ [ entryId, null, flag ] ])
        entry_id = q[4][0][0] if len(q) > 4 and q[4] else None
        if label and entry_id:
            # Clean label: remove trailing *, extra spaces
            label = re.sub(r'\s*\*$', '', label).strip()
            mapping[f"entry.{entry_id}"] = label   # store as entry_id -> label
    return mapping

def fallback_extract(obj, results=None):
    """Recursive fallback to find any string matching 'entry.digits'"""
    if results is None:
        results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.match(r'entry\.\d+', v):
                # Look for a 'label' key in same dict
                label = obj.get('label', 'Unknown')
                results.append((v, label))
            else:
                fallback_extract(v, results)
    elif isinstance(obj, list):
        for item in obj:
            fallback_extract(item, results)
    return dict(results)

def main():
    import sys
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = "raw_form_data.json"
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    mapping = extract_fields_from_fb_data(data)
    if not mapping:
        print("Standard extraction failed, trying fallback...")
        fallback = fallback_extract(data)
        if fallback:
            mapping = {k: v for k, v in fallback.items()}
    
    if mapping:
        # Invert to label -> entry_id for easier use
        label_to_entry = {label: entry_id for entry_id, label in mapping.items()}
        with open("form_fields_final.json", "w") as f:
            json.dump(label_to_entry, f, indent=2)
        print(f"✅ Extracted {len(label_to_entry)} fields:")
        for label, entry_id in label_to_entry.items():
            print(f"  {label} → {entry_id}")
        print("\n💾 Saved to 'form_fields_final.json'")
    else:
        print("❌ No fields found. Please share your raw_form_data.json content.")

if __name__ == "__main__":
    main()