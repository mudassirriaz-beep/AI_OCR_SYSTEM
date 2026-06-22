"""
Agent 3 — Form Filler
Drives a Selenium Edge browser to fill every field type correctly:
  text, email, tel, textarea  → clear + send_keys
  date, datetime-local        → JS value injection + event dispatch + fallback key send
  number                      → JS injection + input event
  select (dropdown)           → Select API with value/text/fuzzy fallback
  radio                       → click best-matching radio option
  checkbox                    → toggle to desired state
Saves a screenshot and returns the filled page source for audit.
"""
import json
import os
import re
import time
from typing import List, Dict

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_driver(driver_path: str = None, headless: bool = False):
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions

    opts = EdgeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    if driver_path and os.path.exists(driver_path):
        return webdriver.Edge(service=EdgeService(driver_path), options=opts)
    return webdriver.Edge(options=opts)


def _find_element(driver, field_id: str, field_name: str, field_type: str, timeout: int = 5):
    """Try multiple locators to find a form element."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    locators = []
    if field_id:
        locators += [
            (By.ID, field_id),
            (By.CSS_SELECTOR, f"[id='{field_id}']"),
        ]
    if field_name:
        locators += [
            (By.NAME, field_name),
            (By.CSS_SELECTOR, f"[name='{field_name}']"),
        ]
    # For radio: grab the group by name
    if field_type == "radio" and field_name:
        locators.append((By.CSS_SELECTOR, f"input[type='radio'][name='{field_name}']"))

    for locator in locators:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            return el
        except Exception:
            continue
    return None


def _js_set(driver, element, value: str, event: str = "change"):
    """Set value via JS and dispatch an event so frameworks notice the change."""
    driver.execute_script(
        "arguments[0].value = arguments[1]; "
        f"arguments[0].dispatchEvent(new Event('{event}', {{bubbles:true}}));",
        element, value,
    )


def _fill_date(driver, element, value: str) -> bool:
    """
    Robust date filling.
    value must be YYYY-MM-DD (Agent 2 guarantees this).
    Strategy 1: JS assignment (works for native date pickers).
    Strategy 2: send_keys after clearing (works for text-type date fields).
    Strategy 3: Tab-separated day/month/year for composite pickers.
    """
    from selenium.webdriver.common.keys import Keys

    # Strategy 1 — JS direct set
    try:
        _js_set(driver, element, value, "change")
        actual = element.get_attribute("value")
        if actual == value:
            return True
    except Exception:
        pass

    # Strategy 2 — clear + type (some date inputs accept text)
    try:
        element.clear()
        element.send_keys(value)
        time.sleep(0.2)
        actual = element.get_attribute("value")
        if actual:
            return True
    except Exception:
        pass

    # Strategy 3 — send numeric parts via Keys (MM/DD/YYYY or DD/MM/YYYY pickers)
    try:
        parts = value.split("-")  # YYYY-MM-DD
        if len(parts) == 3:
            yyyy, mm, dd = parts
            element.clear()
            element.send_keys(mm + dd + yyyy)
            time.sleep(0.2)
            return True
    except Exception:
        pass

    return False


def _fill_select(driver, element, value: str) -> bool:
    """Try exact value → exact text → fuzzy text match."""
    from selenium.webdriver.support.ui import Select
    from selenium.webdriver.common.by import By

    try:
        sel = Select(element)

        # exact value
        try:
            sel.select_by_value(value)
            return True
        except Exception:
            pass

        # exact visible text
        try:
            sel.select_by_visible_text(value)
            return True
        except Exception:
            pass

        # fuzzy — pick the option whose text is closest to value
        try:
            from rapidfuzz import fuzz
            opts = element.find_elements(By.TAG_NAME, "option")
            best_opt = max(
                opts,
                key=lambda o: fuzz.ratio(
                    (o.text or "").strip().lower(), value.lower()
                ),
                default=None,
            )
            if best_opt:
                v = best_opt.get_attribute("value")
                sel.select_by_value(v)
                return True
        except Exception:
            pass

    except Exception:
        pass
    return False


def _fill_radio(driver, field_name: str, value: str) -> bool:
    """Click the radio button whose value or label best matches `value`."""
    from selenium.webdriver.common.by import By
    try:
        from rapidfuzz import fuzz
        radios = driver.find_elements(
            By.CSS_SELECTOR, f"input[type='radio'][name='{field_name}']"
        )
        if not radios:
            return False

        def score(r):
            rv = (r.get_attribute("value") or "").strip()
            # also try to read sibling label text
            rid = r.get_attribute("id") or ""
            rl  = ""
            if rid:
                try:
                    rl = driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text.strip()
                except Exception:
                    pass
            return max(fuzz.ratio(rv.lower(), value.lower()),
                       fuzz.ratio(rl.lower(), value.lower()))

        best = max(radios, key=score, default=None)
        if best:
            driver.execute_script("arguments[0].click();", best)
            return True
    except Exception:
        pass
    return False


# ── Main filler ────────────────────────────────────────────────────────────────

def fill_web_form(
    url: str,
    actions: List[Dict],
    driver_path: str = None,
    headless: bool = False,
    screenshot_path: str = "form_filled_screenshot.png",
) -> dict:
    """
    Open `url` in Edge and execute each fill action.
    Returns {filled, failed, skipped, screenshot, page_source}.
    """
    from selenium.webdriver.common.by import By

    driver  = _build_driver(driver_path, headless)
    results = {"url": url, "filled": [], "failed": [], "skipped": []}

    try:
        driver.get(url)

        # Wait for at least one input to appear
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input,select,textarea"))
            )
        except Exception:
            pass
        time.sleep(1.5)

        for action in actions:
            field_id   = action.get("field_id", "")
            field_name = action.get("field_name", "")
            field_type = action.get("field_type", "text").lower()
            value      = str(action.get("value", "")).strip()
            act        = action.get("action", "type_text")
            tag_label  = field_id or field_name or "?"

            if not value:
                results["skipped"].append(f"{tag_label}: empty value")
                continue

            # Special case: radio handled by group, not single element
            if act == "click_radio":
                ok = _fill_radio(driver, field_name, value)
                (results["filled"] if ok else results["failed"]).append(
                    f"{tag_label} (radio) = {value}"
                )
                continue

            elem = _find_element(driver, field_id, field_name, field_type)
            if elem is None:
                results["failed"].append(f"{tag_label}: element not found")
                continue

            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                time.sleep(0.2)
                ok = False

                if act in ("type_text", "type_textarea"):
                    try:
                        elem.clear()
                    except Exception:
                        pass
                    elem.send_keys(value)
                    ok = True

                elif act == "set_date":
                    ok = _fill_date(driver, elem, value)

                elif act == "set_number":
                    try:
                        _js_set(driver, elem, value, "input")
                        ok = True
                    except Exception:
                        try:
                            elem.clear()
                            elem.send_keys(value)
                            ok = True
                        except Exception:
                            pass

                elif act == "select_option":
                    ok = _fill_select(driver, elem, value)

                elif act == "check_checkbox":
                    should_check = value.lower() in ("true", "yes", "1", "checked", "on")
                    is_checked   = elem.is_selected()
                    if should_check != is_checked:
                        driver.execute_script("arguments[0].click();", elem)
                    ok = True

                (results["filled"] if ok else results["failed"]).append(
                    f"{tag_label} = {value}" + ("" if ok else " [FAILED]")
                )

            except Exception as e:
                results["failed"].append(f"{tag_label}: {e}")

        # Screenshot for audit
        try:
            driver.save_screenshot(screenshot_path)
            results["screenshot"] = screenshot_path
        except Exception:
            pass

        results["page_source"] = driver.page_source

    finally:
        time.sleep(2)   # brief pause so user can see the result before headless closes
        driver.quit()

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python agent_form_filler.py <url> <actions_json_file>")
        sys.exit(1)
    with open(sys.argv[2], encoding="utf-8") as fh:
        acts = json.load(fh)
    res = fill_web_form(sys.argv[1], acts, headless=False)
    print(json.dumps({k: v for k, v in res.items() if k != "page_source"}, indent=2))
