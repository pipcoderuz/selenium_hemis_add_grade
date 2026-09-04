import pandas as pd
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "hemis_order/abiturients.xlsx"
SHEET_NAME = "talabalar"

COL_PIN = "passport_pin"
COL_FIO = "fio"

BASE_URL = "https://hemis.timeedu.uz"
STUDENT_LIST_URL = f"{BASE_URL}/student/student"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

results = []


# ==================== LOGIN ====================
def login() -> bool:
    print("Login...")
    driver.get(BASE_URL)
    try:
        wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//a[contains(@href, '/auth/edu-id') or contains(text(), 'OneID')]"
        ))).click()
        wait.until(EC.presence_of_element_located((By.NAME, "login")))
        driver.find_element(By.NAME, "login").send_keys(LOGIN_VALUE)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD_VALUE)
        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(), 'Kirish') or @type='submit']"
        ))).click()
        time.sleep(1.2)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("✓ Kirish OK")
        return True
    except Exception as e:
        print("Login xato:", e)
        return False


# ==================== EXCEL ====================
def load_excel():
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    if COL_PIN not in df.columns:
        raise ValueError(
            f"'{COL_PIN}' ustuni yo'q. Mavjud: {list(df.columns)}")
    df = df.dropna(subset=[COL_PIN])
    df[COL_PIN] = df[COL_PIN].astype(str).str.strip()
    df = df[df[COL_PIN] != ""]
    print(f"Excel: {len(df)} ta JSHSHIR")
    return df


def _s(row, col, default=""):
    if col not in row.index or pd.isna(row.get(col)):
        return default
    return str(row[col]).strip()


# ==================== TOAST ====================
def _collect_toasts_js() -> list:
    try:
        texts = driver.execute_script("""
            var out = [], seen = {};
            function add(t) {
                t = (t || '').replace(/\\s+/g, ' ').trim();
                if (!t || t.length < 3 || seen[t]) return;
                seen[t] = true;
                out.push(t);
            }
            document.querySelectorAll(
                '#toast-container .toast-message, #toast-container .toast, ' +
                '.toast-message, .toast-success, .toast-error, .toast-info, [class*="toast"]'
            ).forEach(function(el) {
                add(el.innerText || el.textContent);
            });
            var c = document.getElementById('toast-container');
            if (c) add(c.innerText || c.textContent);
            return out;
        """) or []
        return [t for t in texts if t]
    except Exception:
        return []


def _classify_toast(text: str) -> str:
    low = text.lower()
    if (
        "hemis_error" in low
        or "o'qiydi" in low or "o‘qiydi" in low
        or "o'qimoqda" in low or "o‘qimoqda" in low
    ):
        return "error"
    if "himoya" in low or "captcha" in low:
        return "other"
    if any(w in low for w in [
        "muvaffaqiyatli", "saqlandi", "o'zgartirildi", "o‘zgartirildi",
        "yaratildi", "qo'shildi", "qo‘shildi"
    ]):
        return "success"
    if "error" in low or "xato" in low:
        return "error"
    return "other"


def wait_save_result(timeout: float = 8.0) -> tuple[bool, str]:
    end = time.time() + timeout
    success_msg = error_msg = any_toast = None
    time.sleep(0.5)

    while time.time() < end:
        for t in _collect_toasts_js():
            any_toast = any_toast or t
            kind = _classify_toast(t)
            if kind == "error" and not error_msg:
                error_msg = t
            elif kind == "success" and not success_msg:
                success_msg = t

        if error_msg:
            print(f"  ❌ {error_msg[:130]}")
            return False, error_msg
        if success_msg:
            print(f"  ✅ {success_msg[:130]}")
            return True, success_msg
        time.sleep(0.2)

    for t in _collect_toasts_js():
        kind = _classify_toast(t)
        if kind == "error":
            return False, t
        if kind == "success":
            return True, t
        any_toast = any_toast or t

    if any_toast:
        return False, any_toast
    return False, "Toast chiqmadi"


def click_save() -> bool:
    try:
        ok = driver.execute_script("""
            var btn = document.getElementById('submitButton');
            if (!btn) return false;
            btn.scrollIntoView({block: 'center'});
            btn.click();
            return true;
        """)
        if ok:
            print("  ✓ Saqlash bosildi")
            return True
        # kutib qayta
        wait.until(EC.presence_of_element_located((By.ID, "submitButton")))
        driver.execute_script(
            "var b=document.getElementById('submitButton');"
            "if(b){b.scrollIntoView({block:'center'}); b.click();}"
        )
        print("  ✓ Saqlash bosildi")
        return True
    except Exception as e:
        print(f"  ✗ Saqlash: {e}")
        return False


def search_url(pin: str) -> str:
    """Inputga tegmasdan — to'g'ridan-to'g'ri qidiruv URL."""
    q = quote(str(pin).strip(), safe="")
    return f"{STUDENT_LIST_URL}?EStudent%5Bsearch%5D={q}"


def find_student_edit_url(timeout: float = 8.0) -> tuple:
    """
    table.toggle_table ichidan
    a[href*='student-edit?id='] — faqat JS, element saqlanmaydi.
    """
    end = time.time() + timeout
    while time.time() < end:
        info = driver.execute_script("""
            // Avvalo aniq student-edit?id=
            var links = document.querySelectorAll(
                "table.toggle_table a[href*='student-edit?id='], " +
                "table a[href*='student-edit?id=']"
            );
            if (!links.length) {
                links = document.querySelectorAll("a[href*='student-edit?id=']");
            }
            if (!links.length) return {count: 0};

            // resume/document emas — oddiy edit
            for (var i = 0; i < links.length; i++) {
                var href = links[i].getAttribute('href') || '';
                if (href.indexOf('resume=') !== -1) continue;
                if (href.indexOf('document=') !== -1) continue;
                if (href.indexOf('student-edit') === -1) continue;
                var name = (links[i].textContent || '').trim().split('\\n')[0];
                return {count: 1, href: href, name: name};
            }
            return {count: 0};
        """)
        if info and info.get("count") and info.get("href"):
            href = info["href"]
            if href.startswith("/"):
                href = BASE_URL + href
            elif not href.startswith("http"):
                href = BASE_URL + "/" + href.lstrip("/")
            return href, (info.get("name") or "").strip()
        time.sleep(0.3)

    return None, "Talaba topilmadi"


# ==================== BITTA TALABA ====================
def process_student(pin: str, fio: str = "") -> tuple[bool, str]:
    print(f"\n--- {fio or pin} | JSHSHIR: {pin} ---")

    try:
        # 1) Qidiruv — input YO'Q, faqat URL (stale yo'q)
        driver.get(search_url(pin))
        time.sleep(0.8)

        # jadval paydo bo'lishini kutish
        try:
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "table.toggle_table, table tbody tr"
            )))
        except Exception:
            pass

        # 2) Edit URL
        url, name_or_err = find_student_edit_url(timeout=8.0)
        if not url:
            return False, name_or_err

        print(f"  ✓ Topildi: {name_or_err or pin}")

        # 3) Talaba sahifasi
        driver.get(url)
        time.sleep(0.7)

        try:
            wait.until(EC.presence_of_element_located((By.ID, "submitButton")))
        except Exception:
            return False, "Saqlash tugmasi yuklanmadi"

        # eski toast
        driver.execute_script("""
            var c = document.getElementById('toast-container');
            if (c) c.innerHTML = '';
            document.querySelectorAll('.toast').forEach(function(t){ t.remove(); });
        """)

        # 4) Saqlash — faqat JS click
        if not click_save():
            return False, "Saqlash tugmasi topilmadi"

        ok, msg = wait_save_result(timeout=8.0)
        if ok:
            return True, "Muvaffaqiyatli"
        return False, msg

    except Exception as e:
        # stale endi deyarli chiqmasligi kerak; chiqsa ham aniq matn
        err = str(e)
        if "stale" in err.lower():
            return False, "Stale (kutilmagan)"
        if "not interactable" in err.lower():
            return False, "Interactable emas (kutilmagan)"
        return False, f"Xato: {err[:120]}"


# ==================== MAIN ====================
def main():
    print("=" * 50)
    print("JSHSHIR → SAQLASH → HEMIS_ERROR (URL qidiruv)")
    print("=" * 50)

    if not login():
        driver.quit()
        return

    try:
        df = load_excel()
    except Exception as e:
        print(e)
        driver.quit()
        return

    total = len(df)
    ok_count = fail_count = 0

    for idx, row in df.iterrows():
        pin = _s(row, COL_PIN)
        fio = _s(row, COL_FIO)
        print(f"[{idx + 1}/{total}]")

        success, msg = process_student(pin, fio)

        results.append({
            "fio": fio,
            "pin": pin,
            "status": "Muvaffaqiyatli" if success else "Xato",
            "xabar": msg,
        })
        if success:
            ok_count += 1
            print(f"  ✅ {msg}")
        else:
            fail_count += 1
            print(f"  ❌ {msg}")

        time.sleep(0.3)

    print("\n" + "=" * 50)
    print(f"Jami: {total} | ✅ {ok_count} | ❌ {fail_count}")
    print("=" * 50)

    hemis_errs = [
        r for r in results
        if r["status"] == "Xato"
        and (
            "HEMIS_ERROR" in str(r.get("xabar", "")).upper()
            or "o'qiydi" in str(r.get("xabar", "")).lower()
            or "o‘qiydi" in str(r.get("xabar", "")).lower()
        )
    ]
    if hemis_errs:
        print(f"\n⚠ HEMIS_ERROR ({len(hemis_errs)} ta):")
        for r in hemis_errs:
            print(
                f"  - {r.get('fio') or r.get('pin')}: {r.get('xabar')[:140]}")

    out = "hemis_order/jshshir_saqlash_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"\n📄 Natija: {out}")
    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()
