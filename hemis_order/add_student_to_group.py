import pandas as pd
import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import UnexpectedAlertPresentException, TimeoutException

from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "hemis_order/student_groups.xlsx"
SHEET_NAME = "talabalar"

COL_BUYRUK_ID = "buyruq_id"
COL_PIN = "passport_pin"
COL_GURUH = "guruh"
COL_FIO = "fio"

BASE_URL = "https://hemis.timeedu.uz"

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
        time.sleep(1.5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("✓ Kirish OK")
        return True
    except Exception as e:
        print("Login xato:", e)
        return False


# ==================== EXCEL ====================
def load_excel():
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    required = [COL_BUYRUK_ID, COL_PIN, COL_GURUH]
    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"'{col}' ustuni yo'q. Mavjud: {list(df.columns)}")

    df = df.dropna(subset=[COL_PIN])
    df[COL_PIN] = df[COL_PIN].astype(str).str.strip()
    df[COL_BUYRUK_ID] = df[COL_BUYRUK_ID].astype(str).str.strip()
    df[COL_GURUH] = df[COL_GURUH].astype(str).str.strip()
    df = df[df[COL_PIN] != ""]
    print(f"Excel: {len(df)} ta qator")
    return df


def _s(row, col, default=""):
    if col not in row.index or pd.isna(row.get(col)):
        return default
    return str(row[col]).strip()


# ==================== YORDAMCHI ====================
def decree_url(buyruq_id: str) -> str:
    return f"{BASE_URL}/decree/edu-decree-edit-students?id={buyruq_id}"


def clear_filters(buyruq_id: str):
    try:
        btn = driver.find_elements(
            By.XPATH,
            "//a[contains(@href,'clear-filter=1') or contains(.,'Tozalash')]"
        )
        if btn:
            driver.execute_script("arguments[0].click();", btn[0])
            time.sleep(0.8)
            return
    except Exception:
        pass
    driver.get(f"{decree_url(buyruq_id)}&clear-filter=1")
    time.sleep(0.8)


def search_student(pin: str) -> bool:
    try:
        inp = wait.until(EC.presence_of_element_located(
            (By.ID, "edecreeinfostudentmeta-search")))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", inp)
        time.sleep(0.15)

        driver.execute_script("""
            var el = document.getElementById('edecreeinfostudentmeta-search');
            if (!el) return;
            el.focus();
            el.value = '';
            el.dispatchEvent(new Event('input', {bubbles:true}));
        """)
        time.sleep(0.1)
        try:
            inp.clear()
        except Exception:
            pass
        inp.send_keys(pin)
        inp.send_keys(Keys.ENTER)
        time.sleep(1.0)
        return True
    except Exception as e:
        print(f"  ⚠ Qidiruv: {e}")
        return False


def select2_first_or_by_text(
    select_id: str,
    search_text: str = "",
    partial: bool = True,
    wait_opts: int = 20,
) -> bool:
    search_text = (search_text or "").strip()

    for _ in range(wait_opts):
        n = driver.execute_script(f"""
            var el = document.getElementById('{select_id}');
            if (!el) return 0;
            var c = 0;
            for (var i=0;i<el.options.length;i++) {{
                if ((el.options[i].value||'').trim()) c++;
            }}
            return c;
        """)
        if n and n > 0:
            break
        time.sleep(0.35)

    result = driver.execute_script("""
        var el = document.getElementById(arguments[0]);
        var needle = (arguments[1] || '').toLowerCase().trim();
        var partial = arguments[2];
        if (!el) return {ok:false, reason:'element_yoq'};

        var val = null, txt = null;
        for (var i = 0; i < el.options.length; i++) {
            var o = el.options[i];
            var v = (o.value || '').trim();
            var t = (o.textContent || o.innerText || '').trim();
            if (!v) continue;
            var tl = t.toLowerCase();
            if (tl.indexOf('tanlang') !== -1) continue;

            if (!needle) {
                val = v; txt = t; break;
            }
            if (partial) {
                if (tl.indexOf(needle) !== -1) { val = v; txt = t; break; }
            } else {
                if (tl === needle) { val = v; txt = t; break; }
            }
        }
        if (!val) return {ok:false, reason:'option_topilmadi', count: el.options.length};

        el.value = val;
        if (window.jQuery) {
            var $el = jQuery(el);
            $el.val(val).trigger('change');
            try { $el.trigger('select2:select'); } catch(e) {}
            try {
                var $s2 = $el.next('.select2-container').find('.select2-selection__rendered');
                if ($s2.length) {
                    $s2.text(txt).removeClass('select2-selection__placeholder').attr('title', txt);
                }
            } catch(e) {}
        }
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('input', {bubbles:true}));
        return {ok:true, value: val, text: txt};
    """, select_id, search_text, partial)

    if not result or not result.get("ok"):
        print(f"  ⚠ {select_id}: {result}")
        return False

    print(f"  ✓ {select_id}: {result.get('text')}")
    time.sleep(1)
    return True


def wait_group_options_loaded(guruh: str = "", max_wait: float = 20.0) -> bool:
    """
    O'quv rejadan keyin admission_group optionlari yuklanishini kutadi.
    Agar guruh berilgan bo'lsa — shu matn optionlarda paydo bo'lguncha kutadi.
    """
    end = time.time() + max_wait
    needle = (guruh or "").strip().lower()

    while time.time() < end:
        info = driver.execute_script("""
            var el = document.getElementById('edecreeinfostudentmeta-admission_group');
            if (!el) return {count: 0, hasText: false};
            var needle = (arguments[0] || '').toLowerCase();
            var c = 0, hasText = false;
            for (var i = 0; i < el.options.length; i++) {
                var v = (el.options[i].value || '').trim();
                var t = (el.options[i].textContent || el.options[i].innerText || '').trim().toLowerCase();
                if (!v) continue;
                c++;
                if (needle && t.indexOf(needle) !== -1) hasText = true;
            }
            return {count: c, hasText: hasText};
        """, needle)

        if info and info.get("count", 0) > 0:
            if not needle or info.get("hasText"):
                print(f"  ℹ Guruh optionlari yuklandi: {info.get('count')} ta")
                return True
            # optionlar bor lekin kerakli guruh hali yo'q — kutishda davom
        time.sleep(0.35)

    print("  ⚠ Guruh optionlari yuklanmadi / topilmadi")
    return False


def check_student_row() -> bool:
    for _ in range(20):
        ok = driver.execute_script("""
            var boxes = document.querySelectorAll(
                "table tbody tr input[type='checkbox'][name='selection[]']"
            );
            if (!boxes || !boxes.length) return {ok:false, count:0};

            var cb = boxes[0];
            if (!cb.checked) {
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {bubbles:true}));
                cb.dispatchEvent(new Event('click', {bubbles:true}));
            }
            return {ok: true, value: cb.value, checked: cb.checked};
        """)
        if ok and ok.get("ok") and ok.get("checked"):
            print(f"  ✓ Checkbox: {ok.get('value')}")
            return True
        time.sleep(0.3)

    print("  ⚠ Checkbox topilmadi")
    return False


def click_ok() -> bool:
    try:
        btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(@onclick,'confirmStudent') or "
            "(contains(.,'OK') and contains(@class,'btn-primary'))]"
        )))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
            btn,
        )
        print("  ✓ OK bosildi")
        return True
    except Exception as e:
        try:
            driver.execute_script("""
                if (typeof confirmStudent === 'function') {
                    confirmStudent();
                    return true;
                }
                var btns = document.querySelectorAll('button.btn-primary');
                for (var i=0;i<btns.length;i++) {
                    if ((btns[i].textContent||'').indexOf('OK') !== -1) {
                        btns[i].click();
                        return true;
                    }
                }
                return false;
            """)
            print("  ✓ OK (JS)")
            return True
        except Exception as e2:
            print(f"  ✗ OK: {e} / {e2}")
            return False


def accept_confirm_alert(timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            alert = driver.switch_to.alert
            txt = alert.text or ""
            print(f"  ℹ Alert: {txt[:80]}")
            alert.accept()
            time.sleep(0.5)
            return True
        except Exception:
            time.sleep(0.25)
    print("  ⚠ Alert chiqmadi")
    return False


def clear_toasts():
    driver.execute_script("""
        var c = document.getElementById('toast-container');
        if (c) c.innerHTML = '';
        document.querySelectorAll('.toast').forEach(function(t){ t.remove(); });
    """)


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
                '.toast-message, .toast-success, .toast-error'
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


def wait_success_toast(max_wait: float = 30.0) -> tuple[bool, str]:
    """
    'Hujjatga 1 nafar talaba muvaffaqiyatli qo'shildi' chiqmaguncha kutadi.
    """
    end = time.time() + max_wait
    error_msg = None
    any_toast = None

    while time.time() < end:
        for t in _collect_toasts_js():
            any_toast = any_toast or t
            low = t.lower()

            if (
                "muvaffaqiyatli" in low
                and (
                    "qo'shildi" in low
                    or "qo‘shildi" in low
                    or "qoshildi" in low
                )
            ) or (
                "hujjatga" in low and "muvaffaqiyatli" in low
            ):
                print(f"  ✅ Toast: {t[:120]}")
                return True, t

            if (
                "xato" in low or "error" in low or "hemis_error" in low
            ) and "himoya" not in low:
                if not error_msg:
                    error_msg = t

        if error_msg:
            print(f"  ❌ Toast xato: {error_msg[:120]}")
            return False, error_msg

        time.sleep(0.25)

    if error_msg:
        return False, error_msg
    if any_toast:
        return False, f"Kutilgan success toast emas: {any_toast[:120]}"
    return False, "Success toast chiqmadi"


# ==================== BITTA TALABA ====================
def process_student(row) -> tuple[bool, str]:
    buyruq_id = _s(row, COL_BUYRUK_ID)
    pin = _s(row, COL_PIN)
    guruh = _s(row, COL_GURUH)
    fio = _s(row, COL_FIO)

    print(
        f"\n--- {fio or pin} | JSHSHIR: {pin} | Guruh: {guruh} | Buyruq: {buyruq_id} ---")

    if not buyruq_id or not pin or not guruh:
        return False, "buyruq_id / pin / guruh bo'sh"

    try:
        driver.get(decree_url(buyruq_id))
        time.sleep(1.0)

        # 1) Qidiruv
        if not search_student(pin):
            return False, "Qidiruv ishlamadi"

        # 2) O'quv reja — birinchi valid option
        if not select2_first_or_by_text(
            "edecreeinfostudentmeta-admission_curriculum", "", wait_opts=20
        ):
            return False, "O'quv reja tanlanmadi"

        # 3) Guruh optionlari yuklanishini kutish (reja tanlangandan keyin)
        if not wait_group_options_loaded(guruh, max_wait=20.0):
            return False, f"Guruh optionlari yuklanmadi: {guruh}"

        # 4) Guruh tanlash
        if not select2_first_or_by_text(
            "edecreeinfostudentmeta-admission_group", guruh, partial=True, wait_opts=25
        ):
            return False, f"Guruh topilmadi: {guruh}"

        # 5) Checkbox
        if not check_student_row():
            return False, "Talaba checkbox topilmadi"

        # eski toast tozalash
        clear_toasts()

        # 6) OK
        if not click_ok():
            return False, "OK tugmasi bosilmadi"

        # 7) Alert OK
        if not accept_confirm_alert(timeout=6.0):
            print("  ℹ Alert yo'q — toast kutamiz")

        # 8) Success toast chiqmaguncha kutish
        ok, toast_msg = wait_success_toast(max_wait=30.0)
        if not ok:
            try:
                clear_filters(buyruq_id)
            except Exception:
                pass
            return False, toast_msg

        time.sleep(0.4)

        # 9) Tozalash
        clear_filters(buyruq_id)

        return True, "Muvaffaqiyatli"

    except UnexpectedAlertPresentException:
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass
        ok, toast_msg = wait_success_toast(max_wait=15.0)
        try:
            clear_filters(buyruq_id)
        except Exception:
            pass
        if ok:
            return True, "Muvaffaqiyatli (alert)"
        return False, toast_msg
    except Exception as e:
        err = str(e)[:140]
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass
        try:
            clear_filters(buyruq_id)
        except Exception:
            pass
        return False, f"Xato: {err}"


# ==================== MAIN ====================
def main():
    print("=" * 55)
    print("BUYRUQQA TALABA QO'SHISH (decree-edit-students)")
    print("=" * 55)

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
        print(f"[{idx + 1}/{total}]")
        success, msg = process_student(row)

        results.append({
            "buyruq_id": _s(row, COL_BUYRUK_ID),
            "fio": _s(row, COL_FIO),
            "pin": _s(row, COL_PIN),
            "guruh": _s(row, COL_GURUH),
            "status": "Muvaffaqiyatli" if success else "Xato",
            "xabar": msg,
        })
        if success:
            ok_count += 1
            print(f"  ✅ {msg}")
        else:
            fail_count += 1
            print(f"  ❌ {msg}")

        time.sleep(0.4)

    print("\n" + "=" * 55)
    print(f"Jami: {total} | ✅ {ok_count} | ❌ {fail_count}")
    print("=" * 55)

    out = "hemis_order/student_groups_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"📄 Natija: {out}")

    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()