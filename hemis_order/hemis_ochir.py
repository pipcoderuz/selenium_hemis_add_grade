import pandas as pd
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException

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
        "muvaffaqiyatli", "o'chirildi", "o‘chirildi", "ochirildi",
        "saqlandi", "o'zgartirildi", "o‘zgartirildi",
        "yaratildi", "qo'shildi", "qo‘shildi"
    ]):
        return "success"
    if "error" in low or "xato" in low:
        return "error"
    return "other"


def wait_delete_result(timeout: float = 12.0) -> tuple[bool, str]:
    end = time.time() + timeout
    success_msg = error_msg = any_toast = None
    time.sleep(0.4)

    while time.time() < end:
        # alert qolib ketgan bo'lsa
        try:
            alert = driver.switch_to.alert
            print(f"  ℹ Qolgan alert: {(alert.text or '')[:80]}")
            alert.accept()
            time.sleep(0.3)
        except Exception:
            pass

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
        time.sleep(0.25)

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


def accept_any_alert(timeout: float = 6.0) -> bool:
    """Confirm: Talabani o'chirishni istaysizmi? → OK"""
    end = time.time() + timeout
    while time.time() < end:
        try:
            alert = driver.switch_to.alert
            txt = (alert.text or "").strip()
            print(f"  ℹ Alert: {txt[:120]}")
            alert.accept()
            print("  ✓ Alert OK")
            time.sleep(0.5)
            return True
        except UnexpectedAlertPresentException:
            try:
                driver.switch_to.alert.accept()
                print("  ✓ Alert OK (unexpected)")
                time.sleep(0.5)
                return True
            except Exception:
                time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    return False


def click_delete() -> bool:
    """
    O‘chirish bosiladi. deleteItem() darhol alert ochadi —
    shuning uchun exception ham muvaffaqiyat deb hisoblanadi.
    """
    try:
        found = driver.execute_script("""
            var a = document.querySelector(
                "a.btn-danger[href*='delete=1'], " +
                "a[href*='delete=1'][onclick*='deleteItem'], " +
                "a[onclick*='deleteItem']"
            );
            if (!a) {
                var links = document.querySelectorAll('a.btn-danger, a.btn');
                for (var i = 0; i < links.length; i++) {
                    var t = (links[i].textContent || '').toLowerCase();
                    if (t.indexOf('chirish') !== -1 || t.indexOf('delete') !== -1) {
                        a = links[i];
                        break;
                    }
                }
            }
            if (!a) return false;
            a.scrollIntoView({block:'center'});
            return true;
        """)
        if not found:
            # Selenium bilan topish
            btns = driver.find_elements(
                By.XPATH,
                "//a[contains(@href,'delete=1') or contains(@onclick,'deleteItem') "
                "or contains(.,'O‘chirish') or contains(.,\"O'chirish\") "
                "or contains(.,'Ochirish')]"
            )
            if not btns:
                print("  ✗ O‘chirish tugmasi topilmadi")
                return False
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btns[0])
                btns[0].click()
            except UnexpectedAlertPresentException:
                pass
            print("  ✓ O‘chirish bosildi")
            return True

        # JS click — alert ochilishi mumkin
        try:
            driver.execute_script("""
                var a = document.querySelector(
                    "a.btn-danger[href*='delete=1'], " +
                    "a[href*='delete=1'][onclick*='deleteItem'], " +
                    "a[onclick*='deleteItem']"
                );
                if (!a) {
                    var links = document.querySelectorAll('a.btn-danger, a.btn');
                    for (var i = 0; i < links.length; i++) {
                        var t = (links[i].textContent || '').toLowerCase();
                        if (t.indexOf('chirish') !== -1 || t.indexOf('delete') !== -1) {
                            a = links[i]; break;
                        }
                    }
                }
                if (a) a.click();
            """)
            print("  ✓ O‘chirish bosildi")
            return True
        except UnexpectedAlertPresentException:
            # Alert ochildi — bu muvaffaqiyat
            print("  ✓ O‘chirish bosildi (alert ochildi)")
            return True

    except UnexpectedAlertPresentException:
        print("  ✓ O‘chirish bosildi (alert)")
        return True
    except Exception as e:
        # Ba'zan alert tufayli boshqa xato matni keladi
        err = str(e)
        if "alert" in err.lower() or "unexpected alert" in err.lower():
            print("  ✓ O‘chirish bosildi (alert exception)")
            return True
        print(f"  ✗ O‘chirish: {err[:150]}")
        return False


def search_url(pin: str) -> str:
    q = quote(str(pin).strip(), safe="")
    return f"{STUDENT_LIST_URL}?EStudent%5Bsearch%5D={q}"


def find_student_edit_url(timeout: float = 8.0) -> tuple:
    end = time.time() + timeout
    while time.time() < end:
        info = driver.execute_script("""
            var links = document.querySelectorAll(
                "table.toggle_table a[href*='student-edit?id='], " +
                "table a[href*='student-edit?id=']"
            );
            if (!links.length) {
                links = document.querySelectorAll("a[href*='student-edit?id=']");
            }
            if (!links.length) return {count: 0};

            for (var i = 0; i < links.length; i++) {
                var href = links[i].getAttribute('href') || '';
                if (href.indexOf('resume=') !== -1) continue;
                if (href.indexOf('document=') !== -1) continue;
                if (href.indexOf('delete=') !== -1) continue;
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
        driver.get(search_url(pin))
        time.sleep(0.8)

        try:
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "table.toggle_table, table tbody tr"
            )))
        except Exception:
            pass

        url, name_or_err = find_student_edit_url(timeout=8.0)
        if not url:
            return False, name_or_err

        print(f"  ✓ Topildi: {name_or_err or pin}")

        driver.get(url)
        time.sleep(0.7)

        try:
            wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//a[contains(@href,'delete=1') or contains(@onclick,'deleteItem') "
                "or contains(.,'O‘chirish') or contains(.,\"O'chirish\") "
                "or contains(.,'Ochirish')]"
            )))
        except Exception:
            return False, "O‘chirish tugmasi yuklanmadi"

        driver.execute_script("""
            var c = document.getElementById('toast-container');
            if (c) c.innerHTML = '';
            document.querySelectorAll('.toast').forEach(function(t){ t.remove(); });
        """)

        # 1) O‘chirish
        if not click_delete():
            # alert ochiq qolgan bo'lishi mumkin
            if not accept_any_alert(timeout=2.0):
                return False, "O‘chirish tugmasi topilmadi"

        # 2) Confirm alert → OK
        if not accept_any_alert(timeout=6.0):
            print("  ⚠ Confirm alert topilmadi — toast kutamiz")

        # 3) Toast
        ok, msg = wait_delete_result(timeout=12.0)
        if ok:
            return True, "O‘chirildi"
        return False, msg

    except UnexpectedAlertPresentException:
        try:
            driver.switch_to.alert.accept()
            print("  ✓ Alert OK (catch)")
        except Exception:
            pass
        ok, msg = wait_delete_result(timeout=10.0)
        if ok:
            return True, "O‘chirildi"
        return False, msg
    except Exception as e:
        err = str(e)
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass
        if "alert" in err.lower():
            ok, msg = wait_delete_result(timeout=10.0)
            if ok:
                return True, "O‘chirildi"
            return False, msg or err[:120]
        if "stale" in err.lower():
            return False, "Stale (kutilmagan)"
        return False, f"Xato: {err[:120]}"


# ==================== MAIN ====================
def main():
    print("=" * 50)
    print("JSHSHIR → TALABANI O‘CHIRISH")
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
            "status": "O‘chirildi" if success else "Xato",
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

    out = "hemis_order/talaba_ochirish_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"\n📄 Natija: {out}")
    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()
