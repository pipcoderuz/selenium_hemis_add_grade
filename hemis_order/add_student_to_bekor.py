import pandas as pd
import time
from datetime import date

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.keys import Keys

from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "hemis_order/kk_order_students.xlsx"
SHEET_NAME = "orders"

COL_BUYRUK_ID = "buyruq_id"
COL_HEMIS_ID = "hemis_id"
COL_FIO = "talaba_fio"

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
    for col in [COL_BUYRUK_ID, COL_HEMIS_ID]:
        if col not in df.columns:
            raise ValueError(
                f"'{col}' ustuni yo'q. Mavjud: {list(df.columns)}")
    df = df.dropna(subset=[COL_HEMIS_ID, COL_BUYRUK_ID])
    print(f"Excel: {len(df)} ta qator")
    return df


def _s(row, col, default=""):
    if col not in row.index or pd.isna(row.get(col)):
        return default
    return str(row[col]).strip()


def decree_url(buyruq_id: str) -> str:
    return f"{BASE_URL}/decree/edu-decree-edit-students?id={buyruq_id}"


def clear_filters(buyruq_id: str):
    try:
        btns = driver.find_elements(
            By.XPATH,
            "//a[contains(@href,'clear-filter=1') or contains(.,'Tozalash')]"
        )
        if btns:
            driver.execute_script("arguments[0].click();", btns[0])
            time.sleep(0.8)
            return
    except Exception:
        pass
    driver.get(f"{decree_url(buyruq_id)}&clear-filter=1")
    time.sleep(0.8)


# ==================== QIDIRUV ====================
def search_student(hemis_id: str) -> bool:
    try:
        inp = wait.until(EC.presence_of_element_located(
            (By.ID, "edecreeinfostudentmeta-search")
        ))
        driver.execute_script("""
            var el = document.getElementById('edecreeinfostudentmeta-search');
            if (!el) return;
            el.focus();
            el.value = '';
            el.dispatchEvent(new Event('input', {bubbles:true}));
        """)
        time.sleep(0.15)
        try:
            inp.clear()
        except Exception:
            pass
        inp.send_keys(str(hemis_id))
        inp.send_keys(Keys.ENTER)
        print(f"  ✓ Qidiruv: {hemis_id}")
        time.sleep(1.2)
        return True
    except Exception as e:
        print(f"  ✗ Qidiruv: {e}")
        return False


# ==================== SANA ====================
def set_today_date() -> bool:
    today = date.today().strftime("%Y-%m-%d")
    try:
        result = driver.execute_script("""
            var el = document.getElementById('edecreeinfostudentmeta-remove_date');
            if (!el) return {ok:false, reason:'element_yoq'};
            var val = arguments[0];
            el.focus();
            el.value = val;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new Event('blur', {bubbles:true}));
            if (window.jQuery) {
                try { jQuery(el).val(val).trigger('change').trigger('blur'); } catch(e) {}
            }
            el.setAttribute('aria-invalid', 'false');
            var fg = el.closest('.form-group');
            if (fg) {
                fg.classList.remove('has-error');
                var hb = fg.querySelector('.help-block');
                if (hb) hb.innerHTML = '';
            }
            return {ok:true, value: el.value};
        """, today)

        if result and result.get("ok"):
            print(f"  ✓ Sana: {result.get('value')}")
            time.sleep(0.3)
            return True

        el = wait.until(EC.presence_of_element_located(
            (By.ID, "edecreeinfostudentmeta-remove_date")
        ))
        el.clear()
        el.send_keys(today)
        el.send_keys(Keys.TAB)
        print(f"  ✓ Sana (Selenium): {today}")
        return True
    except Exception as e:
        print(f"  ✗ Sana: {e}")
        return False


# ==================== CHECKBOX (sizning ishlaydigan versiya) ====================
def checkboxni_belgilash():
    try:
        found_checkbox = False

        for attempt in range(3):
            try:
                ok = driver.execute_script("""
                    var boxes = document.querySelectorAll(
                        "input[type='checkbox'][name='selection[]']"
                    );
                    if (!boxes.length) return {found:false};
                    var cb = boxes[0];
                    cb.scrollIntoView({block:'center'});
                    if (!cb.checked) {
                        cb.checked = true;
                        cb.dispatchEvent(new Event('click', {bubbles:true}));
                        cb.dispatchEvent(new Event('change', {bubbles:true}));
                    }
                    return {found:true, checked: !!cb.checked, value: cb.value};
                """)
                if not ok or not ok.get("found"):
                    print(f"  ✗ Checkbox topilmadi (urinish {attempt+1})")
                    time.sleep(0.4)
                    continue

                found_checkbox = True
                if ok.get("checked"):
                    print(f"  ✓ Checkbox belgilandi ({ok.get('value')})")
                    return True, None

                print(
                    f"  ⚠ Checkbox topildi, belgilanmadi (urinish {attempt+1})")
                time.sleep(0.4)
            except Exception as e:
                print(f"  ⚠ Urinish {attempt+1}: {e}")
                time.sleep(0.4)

        if not found_checkbox:
            return False, "Checkbox topilmadi"
        return False, "Checkbox belgilanmadi"

    except Exception as e:
        return False, f"Checkbox xatoligi: {str(e)}"


# ==================== OK / ALERT / TOAST ====================
def click_ok() -> bool:
    try:
        btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[@onclick='return confirmStudent()' or "
            "(contains(@class,'btn-primary') and contains(.,'OK'))]"
        )))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
            btn,
        )
        print("  ✓ OK bosildi")
        return True
    except Exception:
        try:
            driver.execute_script("""
                if (typeof confirmStudent === 'function') {
                    confirmStudent();
                    return true;
                }
                var btns = document.querySelectorAll('button.btn-primary');
                for (var i=0;i<btns.length;i++) {
                    if ((btns[i].textContent||'').indexOf('OK') !== -1) {
                        btns[i].click(); return true;
                    }
                }
                return false;
            """)
            print("  ✓ OK (JS)")
            return True
        except Exception as e:
            print(f"  ✗ OK: {e}")
            return False


def accept_alert(timeout: float = 6.0) -> tuple[bool, str]:
    end = time.time() + timeout
    while time.time() < end:
        try:
            alert = driver.switch_to.alert
            txt = (alert.text or "").strip()
            print(f"  ℹ Alert: {txt[:120]}")
            alert.accept()
            print("  ✓ Alert OK")
            time.sleep(0.4)
            return True, txt
        except UnexpectedAlertPresentException:
            try:
                a = driver.switch_to.alert
                txt = (a.text or "").strip()
                a.accept()
                return True, txt
            except Exception:
                time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    print("  ⚠ Alert chiqmadi")
    return False, ""


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
    start = time.time()
    error_msg = any_toast = None

    while True:
        for t in _collect_toasts_js():
            any_toast = any_toast or t
            low = t.lower()
            if (
                "muvaffaqiyatli" in low
                and ("qo'shildi" in low or "qo‘shildi" in low or "qoshildi" in low)
            ) or ("hujjatga" in low and "muvaffaqiyatli" in low):
                print(f"  ✅ Toast: {t[:120]}")
                return True, t
            if ("xato" in low or "error" in low or "hemis_error" in low) and "himoya" not in low:
                if not error_msg:
                    error_msg = t

        if error_msg:
            print(f"  ❌ Toast: {error_msg[:120]}")
            return False, error_msg

        if time.time() - start > max_wait:
            if any_toast:
                return False, f"Kutilgan toast emas: {any_toast[:120]}"
            return False, f"Success toast {int(max_wait)}s ichida chiqmadi"

        time.sleep(0.25)


# ==================== BITTA TALABA ====================
def process_student(buyruq_id: str, hemis_id: str, fio: str = "") -> tuple[bool, str]:
    print(
        f"\n--- {fio or hemis_id} | HEMIS: {hemis_id} | Buyruq: {buyruq_id} ---")

    try:
        driver.get(decree_url(buyruq_id))
        time.sleep(0.9)

        clear_filters(buyruq_id)

        # 1) Qidiruv
        if not search_student(hemis_id):
            return False, "Qidiruv ishlamadi"

        # 2) Sana
        if not set_today_date():
            return False, "Sana yozilmadi"

        # 3) Checkbox — OK dan oldin (sizning ishlaydigan funksiya)
        ok_cb, err_cb = checkboxni_belgilash()
        if not ok_cb:
            return False, err_cb or "Checkbox belgilanmadi"

        clear_toasts()

        # 4) OK
        if not click_ok():
            return False, "OK bosilmadi"

        # 5) Alert
        ok_alert, alert_txt = accept_alert(timeout=6.0)
        if ok_alert:
            low = (alert_txt or "").lower()
            if "tanlash zarur" in low or "talabalarni tanlash" in low:
                return False, f"Checkbox tanlanmadi (alert): {alert_txt}"

        # 6) Toast
        ok, msg = wait_success_toast(max_wait=30.0)
        if not ok:
            try:
                clear_filters(buyruq_id)
            except Exception:
                pass
            return False, msg

        time.sleep(0.3)
        clear_filters(buyruq_id)
        return True, "Muvaffaqiyatli"

    except UnexpectedAlertPresentException:
        try:
            a = driver.switch_to.alert
            txt = (a.text or "")
            a.accept()
            if "tanlash zarur" in txt.lower():
                return False, f"Checkbox tanlanmadi (alert): {txt}"
        except Exception:
            pass
        ok, msg = wait_success_toast(max_wait=15.0)
        try:
            clear_filters(buyruq_id)
        except Exception:
            pass
        if ok:
            return True, "Muvaffaqiyatli"
        return False, msg
    except Exception as e:
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass
        return False, f"Xato: {str(e)[:120]}"


# ==================== MAIN ====================
def main():
    print("=" * 55)
    print("BUYRUQQA TALABA QO'SHISH (sana + checkbox)")
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
        buyruq_id = _s(row, COL_BUYRUK_ID)
        hemis_id = _s(row, COL_HEMIS_ID)
        fio = _s(row, COL_FIO)

        try:
            if buyruq_id:
                buyruq_id = str(int(float(buyruq_id)))
            if hemis_id and hemis_id.replace(".", "", 1).isdigit():
                hemis_id = str(int(float(hemis_id)))
        except Exception:
            pass

        print(f"[{idx + 1}/{total}]")
        success, msg = process_student(buyruq_id, hemis_id, fio)

        results.append({
            "buyruq_id": buyruq_id,
            "hemis_id": hemis_id,
            "fio": fio,
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

    print("\n" + "=" * 55)
    print(f"Jami: {total} | ✅ {ok_count} | ❌ {fail_count}")
    print("=" * 55)

    out = "hemis_order/buyruq_qoshish_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"📄 Natija: {out}")

    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()
