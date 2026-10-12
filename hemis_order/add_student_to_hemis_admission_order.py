import pandas as pd
import time
from datetime import date

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import UnexpectedAlertPresentException

from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "hemis_order/admission_students.xlsx"
SHEET_NAME = "talabalar"

COL_BUYRUK_ID = "buyruq_id"
COL_HEMIS_ID = "hemis_id"
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
    required = [COL_BUYRUK_ID, COL_HEMIS_ID]
    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"'{col}' ustuni yo'q. Mavjud: {list(df.columns)}")

    df = df.dropna(subset=[COL_HEMIS_ID])
    df[COL_HEMIS_ID] = df[COL_HEMIS_ID].astype(str).str.strip()
    df[COL_BUYRUK_ID] = df[COL_BUYRUK_ID].astype(str).str.strip()
    df = df[df[COL_HEMIS_ID] != ""]
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


def search_student(hemis_id: str) -> bool:
    """hemis_id bilan qidirish"""
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
        inp.send_keys(hemis_id)
        inp.send_keys(Keys.ENTER)
        time.sleep(1.0)
        print(f"  ✓ Qidiruv: {hemis_id}")
        return True
    except Exception as e:
        print(f"  ⚠ Qidiruv: {e}")
        return False


def fill_enroll_date() -> bool:
    """Bugungi sanani YYYY-MM-DD formatida yozadi"""
    today = date.today().strftime("%Y-%m-%d")
    try:
        inp = wait.until(EC.presence_of_element_located(
            (By.ID, "edecreeinfostudentmeta-enroll_date")))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", inp)
        time.sleep(0.15)

        driver.execute_script("""
            var el = document.getElementById('edecreeinfostudentmeta-enroll_date');
            if (!el) return false;
            var val = arguments[0];
            el.focus();
            el.value = val;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new Event('blur', {bubbles:true}));
            if (window.jQuery) {
                try {
                    var $el = jQuery(el);
                    $el.val(val).trigger('change').trigger('blur');
                    if ($el.data('kvDatepicker')) {
                        $el.kvDatepicker('update', val);
                    }
                } catch(e) {}
            }
            return true;
        """, today)

        time.sleep(0.3)
        cur = driver.execute_script(
            "return (document.getElementById('edecreeinfostudentmeta-enroll_date').value || '');"
        )
        if today in (cur or ""):
            print(f"  ✓ Sana: {cur}")
            return True

        # Fallback
        try:
            inp.click()
            time.sleep(0.1)
            inp.send_keys(Keys.CONTROL, "a")
            inp.send_keys(Keys.DELETE)
            time.sleep(0.1)
            inp.send_keys(today)
            inp.send_keys(Keys.ENTER)
            time.sleep(0.3)
        except Exception:
            pass

        cur = driver.execute_script(
            "return (document.getElementById('edecreeinfostudentmeta-enroll_date').value || '');"
        )
        print(f"  ✓ Sana: {cur or today}")
        return True

    except Exception as e:
        print(f"  ⚠ Sana yozilmadi: {e}")
        return False


def check_student_row() -> bool:
    """
    Qidiruvdan keyin jadvaldagi birinchi talabani belgilaydi.
    Bir necha usul: JS checked, native click, label/td click.
    """
    # 1) Jadval va checkbox paydo bo'lishini kutish
    end = time.time() + 12
    found = False
    while time.time() < end:
        count = driver.execute_script("""
            var boxes = document.querySelectorAll(
                "table tbody tr input[type='checkbox'][name='selection[]'], " +
                "table tbody tr input[type='checkbox'][name*='selection'], " +
                "table.kv-grid-table tbody tr input[type='checkbox']"
            );
            return boxes ? boxes.length : 0;
        """)
        if count and count > 0:
            found = True
            break
        time.sleep(0.3)

    if not found:
        print("  ⚠ Jadvalda checkbox topilmadi")
        return False

    time.sleep(0.3)

    # 2) Birinchi qatorni belgilash — bir necha usul
    result = driver.execute_script("""
        function isVisible(el) {
            if (!el) return false;
            var s = window.getComputedStyle(el);
            return s && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
        }

        var selectors = [
            "table tbody tr input[type='checkbox'][name='selection[]']",
            "table tbody tr input[type='checkbox'][name*='selection']",
            "table.kv-grid-table tbody tr input[type='checkbox']",
            "table tbody tr td input[type='checkbox']"
        ];

        var cb = null;
        for (var s = 0; s < selectors.length; s++) {
            var list = document.querySelectorAll(selectors[s]);
            if (list && list.length) {
                // header dagi "select all" ni o'tkazib yuboramiz
                for (var i = 0; i < list.length; i++) {
                    var row = list[i].closest('tr');
                    if (!row) continue;
                    // thead ichidagi checkbox emas
                    if (row.closest('thead')) continue;
                    // bo'sh qator emas
                    if ((row.innerText || '').trim().length < 3) continue;
                    cb = list[i];
                    break;
                }
            }
            if (cb) break;
        }

        if (!cb) return {ok: false, reason: 'checkbox_yoq'};

        // allaqachon belgilangan bo'lsa
        if (cb.checked) {
            return {ok: true, value: cb.value || '', method: 'already'};
        }

        // Usul 1: to'g'ridan-to'g'ri click
        try {
            cb.scrollIntoView({block: 'center'});
            cb.click();
            if (cb.checked) return {ok: true, value: cb.value || '', method: 'click'};
        } catch(e) {}

        // Usul 2: JS checked + event
        try {
            cb.checked = true;
            cb.dispatchEvent(new Event('click', {bubbles: true}));
            cb.dispatchEvent(new Event('change', {bubbles: true}));
            if (cb.checked) return {ok: true, value: cb.value || '', method: 'js'};
        } catch(e) {}

        // Usul 3: parent label
        try {
            var label = cb.closest('label');
            if (label) {
                label.click();
                if (cb.checked) return {ok: true, value: cb.value || '', method: 'label'};
            }
        } catch(e) {}

        // Usul 4: td ga click
        try {
            var td = cb.closest('td');
            if (td) {
                td.click();
                if (cb.checked) return {ok: true, value: cb.value || '', method: 'td'};
            }
        } catch(e) {}

        // Usul 5: tr ga click
        try {
            var tr = cb.closest('tr');
            if (tr) {
                tr.click();
                if (cb.checked) return {ok: true, value: cb.value || '', method: 'tr'};
            }
        } catch(e) {}

        // Usul 6: jQuery trigger
        try {
            if (window.jQuery) {
                jQuery(cb).prop('checked', true).trigger('click').trigger('change');
                if (cb.checked) return {ok: true, value: cb.value || '', method: 'jquery'};
            }
        } catch(e) {}

        return {
            ok: !!cb.checked,
            value: cb.value || '',
            method: 'final',
            checked: cb.checked
        };
    """)

    if result and result.get("ok") and result.get("checked", True):
        print(f"  ✓ Checkbox: {result.get('value')} [{result.get('method')}]")
        return True

    # 3) Selenium native click — oxirgi urinish
    try:
        boxes = driver.find_elements(
            By.CSS_SELECTOR,
            "table tbody tr input[type='checkbox'][name='selection[]'], "
            "table tbody tr input[type='checkbox']"
        )
        for box in boxes:
            # thead dagi emas
            try:
                row = box.find_element(By.XPATH, "./ancestor::tr[1]")
                if row.find_elements(By.XPATH, "./ancestor::thead"):
                    continue
            except Exception:
                pass

            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", box)
            time.sleep(0.2)
            try:
                box.click()
            except Exception:
                driver.execute_script("arguments[0].click();", box)
            time.sleep(0.3)

            checked = driver.execute_script(
                "return arguments[0].checked;", box)
            if checked:
                val = box.get_attribute("value") or ""
                print(f"  ✓ Checkbox (selenium): {val}")
                return True
    except Exception as e:
        print(f"  ⚠ Selenium click: {e}")

    print("  ⚠ Checkbox belgilanmadi")
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
    hemis_id = _s(row, COL_HEMIS_ID)
    fio = _s(row, COL_FIO)

    print(
        f"\n--- {fio or hemis_id} | HEMIS ID: {hemis_id} | Buyruq: {buyruq_id} ---")

    if not buyruq_id or not hemis_id:
        return False, "buyruq_id / hemis_id bo'sh"

    try:
        driver.get(decree_url(buyruq_id))
        time.sleep(1.0)

        # 1) Qidiruv (hemis_id)
        if not search_student(hemis_id):
            return False, "Qidiruv ishlamadi"

        # 2) Ro'yxatga olish sanasi (bugun)
        if not fill_enroll_date():
            return False, "Sana yozilmadi"

        # 3) Checkbox
        if not check_student_row():
            return False, "Talaba checkbox topilmadi"

        clear_toasts()

        # 4) OK
        if not click_ok():
            return False, "OK tugmasi bosilmadi"

        # 5) Alert OK
        if not accept_confirm_alert(timeout=6.0):
            print("  ℹ Alert yo'q — toast kutamiz")

        # 6) Success toast
        ok, toast_msg = wait_success_toast(max_wait=30.0)
        if not ok:
            try:
                clear_filters(buyruq_id)
            except Exception:
                pass
            return False, toast_msg

        time.sleep(0.4)

        # 7) Tozalash
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
            "hemis_id": _s(row, COL_HEMIS_ID),
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

    out = "hemis_order/admission_order_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"📄 Natija: {out}")

    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()
