"""
Agent 1 — Form Inspector
Accepts any form source: http/https URL, local HTML file path, or PDF path.
Returns a structured JSON schema describing every interactive field.
"""
import json
import os
import re
import time

# ── PDF inspection ─────────────────────────────────────────────────────────────

def _inspect_pdf(pdf_path: str) -> dict:
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    fields = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for widget in page.widgets():
            ftype = (widget.field_type_string or "text").lower()
            options = []
            if ftype in ("listbox", "combobox") and hasattr(widget, "choice_values"):
                options = [{"value": v, "text": v} for v in (widget.choice_values or [])]

            fields.append({
                "tag":          "input",
                "type":         ftype,
                "id":           widget.field_name or "",
                "name":         widget.field_name or "",
                "label":        widget.field_label or widget.field_name or "",
                "placeholder":  "",
                "required":     False,
                "options":      options,
                "radio_options":[],
                "min": "", "max": "", "pattern": "",
                "page":         page_num + 1,
                "rect":         list(widget.rect),
                "xpath":        "",
            })
    doc.close()
    return {"source": pdf_path, "type": "pdf", "fields": fields, "field_count": len(fields)}


# ── HTML / web inspection (Selenium) ──────────────────────────────────────────

def _get_xpath(driver, element) -> str:
    try:
        return driver.execute_script(
            """
            function xp(el) {
                if (el.id) return '//*[@id="' + el.id + '"]';
                if (el === document.body) return '/html/body';
                var ix = 0, sibs = el.parentNode.childNodes;
                for (var i = 0; i < sibs.length; i++) {
                    var s = sibs[i];
                    if (s === el) return xp(el.parentNode) + '/' + el.tagName.toLowerCase() + '[' + (ix+1) + ']';
                    if (s.nodeType === 1 && s.tagName === el.tagName) ix++;
                }
            }
            return xp(arguments[0]);
            """,
            element,
        )
    except Exception:
        return ""


def _inspect_web(url: str, driver_path: str = None) -> dict:
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    opts = EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--log-level=3")

    if driver_path and os.path.exists(driver_path):
        driver = webdriver.Edge(service=EdgeService(driver_path), options=opts)
    else:
        driver = webdriver.Edge(options=opts)

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(1.5)  # let JS-rendered content settle

        fields = []
        seen_radio_names = set()

        for elem in driver.find_elements(By.CSS_SELECTOR, "input, select, textarea"):
            tag       = elem.tag_name.lower()
            ftype     = (elem.get_attribute("type") or tag).lower()

            # skip non-interactive types
            if ftype in ("submit", "reset", "button", "file", "hidden", "image"):
                continue
            field_id   = elem.get_attribute("id")   or ""
            field_name = elem.get_attribute("name") or ""
            if not field_id and not field_name:
                continue

            # deduplicate radio groups — only emit once per name
            if ftype == "radio":
                if field_name in seen_radio_names:
                    continue
                seen_radio_names.add(field_name)

            placeholder = elem.get_attribute("placeholder") or ""
            required    = elem.get_attribute("required") is not None
            min_val     = elem.get_attribute("min")     or ""
            max_val     = elem.get_attribute("max")     or ""
            pattern     = elem.get_attribute("pattern") or ""

            # label text — cascade through multiple sources
            label_text = ""
            if field_id:
                try:
                    lbl = driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                    label_text = lbl.text.strip()
                except Exception:
                    pass
            if not label_text:
                label_text = (elem.get_attribute("aria-label") or
                              elem.get_attribute("title") or "")
            if not label_text:
                aria_lb = elem.get_attribute("aria-labelledby")
                if aria_lb:
                    try:
                        ref = driver.find_element(By.ID, aria_lb)
                        label_text = ref.text.strip()
                    except Exception:
                        pass

            # nearby_text — text visible near the input (preceding sibling / parent)
            nearby_text = driver.execute_script("""
                var el = arguments[0];
                // 1. preceding sibling text
                var prev = el.previousSibling;
                while (prev) {
                    if (prev.nodeType === 3 && prev.textContent.trim())
                        return prev.textContent.trim();
                    if (prev.nodeType === 1) {
                        var t = prev.innerText || prev.textContent || '';
                        if (t.trim()) return t.trim();
                    }
                    prev = prev.previousSibling;
                }
                // 2. parent element text (exclude child inputs)
                var par = el.parentElement;
                if (par) {
                    var clone = par.cloneNode(true);
                    var inputs = clone.querySelectorAll('input,select,textarea');
                    inputs.forEach(function(i){ i.remove(); });
                    var pt = clone.innerText || clone.textContent || '';
                    if (pt.trim()) return pt.trim();
                }
                return '';
            """, elem)
            nearby_text = (nearby_text or "").strip()

            # select options
            options_list = []
            if tag == "select":
                for opt in elem.find_elements(By.TAG_NAME, "option"):
                    val  = opt.get_attribute("value") or ""
                    txt  = opt.text.strip()
                    if val or txt:
                        options_list.append({"value": val, "text": txt})

            # radio group options
            radio_options = []
            if ftype == "radio" and field_name:
                for r in driver.find_elements(
                    By.CSS_SELECTOR, f"input[type='radio'][name='{field_name}']"
                ):
                    r_val   = r.get_attribute("value") or ""
                    r_id    = r.get_attribute("id") or ""
                    r_label = ""
                    if r_id:
                        try:
                            rl = driver.find_element(By.CSS_SELECTOR, f"label[for='{r_id}']")
                            r_label = rl.text.strip()
                        except Exception:
                            pass
                    radio_options.append({"value": r_val, "label": r_label or r_val})

            fields.append({
                "tag":          tag,
                "type":         ftype,
                "id":           field_id,
                "name":         field_name,
                "label":        label_text,
                "placeholder":  placeholder,
                "nearby_text":  nearby_text,
                "required":     required,
                "options":      options_list,
                "radio_options": radio_options,
                "min":          min_val,
                "max":          max_val,
                "pattern":      pattern,
                "xpath":        _get_xpath(driver, elem),
            })

        return {"source": url, "type": "web", "fields": fields, "field_count": len(fields)}

    finally:
        driver.quit()


# ── Public entry point ─────────────────────────────────────────────────────────

def inspect_form(source: str, driver_path: str = None) -> dict:
    """
    Detect source type and dispatch to the right inspector.
    source can be:
      - http:// or https:// URL
      - file:// URL
      - local path ending in .pdf
      - local path to an HTML file
    """
    if source.lower().endswith(".pdf") and not source.startswith("http"):
        return _inspect_pdf(source)

    # Normalise local paths to file:// URLs
    if not source.startswith(("http://", "https://", "file://")):
        abs_path = os.path.abspath(source)
        source   = "file:///" + abs_path.replace("\\", "/")

    return _inspect_web(source, driver_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python agent_form_inspector.py <url_or_path>")
        sys.exit(1)
    result = inspect_form(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
