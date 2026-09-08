import pandas as pd
import re
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "hemis_order/specialty_update.xlsx"
SHEET_NAME = "talabalar"

COL_PIN = "passport_pin"           # JSHSHIR
COL_FIO = "fio"                    # ixtiyoriy
COL_SPECIALTY_CODE = "specialty_code"   # 60410100
COL_SPECIALTY_NAME = "specialty_name"   # Iqtisod

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
    for col in [COL_PIN, COL_SPECIALTY_CODE]:
        if col not in df.columns:
            raise ValueError(
                f"'{col}' ustuni yo'q. Mavjud: {list(df.columns)}")
    df = df.dropna(subset=[COL_PIN])
    df[COL_PIN] = df[COL_PIN].astype(str).str.strip()
    df = df[df[COL_PIN] != ""]
    print(f"Excel: {len(df)} ta qator")
    return df


def _s(row, col, default=""):
    if col not in row.index or pd.isna(row.get(col)):
        return default
    return str(row[col]).strip()


# ==================== QIDIRUV ====================
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


# ==================== MUTAXASSISLIK ====================
def select_specialty_by_code(code: str, name: str = "", wait_opts: int = 40) -> bool:
    """
    Kod bir xil bo'lsa — specialty_name bilan aniq tanlaydi.
    code=60410100, name=Iqtisod → '60410100 - Iqtisodiyot'
    """
    code = re.sub(r"\D", "", str(code or ""))
    name = (name or "").strip()
    if not code:
        print("  ⚠ specialty_code bo'sh")
        return False

    # optionlar yuklanishini kutish
    loaded = False
    for i in range(wait_opts):
        info = driver.execute_script("""
            var el = document.getElementById('_specialty');
            if (!el) return {count: 0, hasCode: false};
            var code = arguments[0];
            var c = 0, hasCode = false;
            for (var i = 0; i < el.options.length; i++) {
                var v = (el.options[i].value || '').trim();
                var t = (el.options[i].textContent || el.options[i].innerText || '');
                if (!v) continue;
                c++;
                if (t.indexOf(code) !== -1) hasCode = true;
            }
            return {count: c, hasCode: hasCode};
        """, code)
        if info and info.get("count", 0) > 0 and info.get("hasCode"):
            loaded = True
            print(f"  ℹ Mutaxassisliklar: {info.get('count')} ta")
            break
        if info and info.get("count", 0) > 1 and i > 8:
            loaded = True
            break
        time.sleep(0.3)

    if not loaded:
        # edit sahifada optionlar oldindan yuklangan bo'lishi mumkin
        n = driver.execute_script("""
            var el = document.getElementById('_specialty');
            if (!el) return 0;
            var c = 0;
            for (var i=0;i<el.options.length;i++) {
                if ((el.options[i].value||'').trim()) c++;
            }
            return c;
        """)
        if not n:
            print("  ⚠ _specialty optionlari yo'q")
            return False

    result = driver.execute_script("""
        var el = document.getElementById('_specialty');
        var code = (arguments[0] || '').trim();
        var name = (arguments[1] || '').trim();
        if (!el) return {ok:false, reason:'element_yoq'};

        function norm(s) {
            s = (s || '').toLowerCase().trim();
            s = s.replace(/[‘’ʻʼ`´]/g, "'");
            s = s.replace(/[–—−]/g, '-');
            s = s.replace(/\\s+/g, ' ');
            return s;
        }
        var nameN = norm(name);

        var items = [];
        for (var i = 0; i < el.options.length; i++) {
            var o = el.options[i];
            var v = (o.value || '').trim();
            var t = (o.textContent || o.innerText || '').trim();
            if (!v) continue;
            items.push({v: v, t: t, tn: norm(t)});
        }

        var val = null, txt = null, how = '';

        // 1) KOD + NOM
        if (code && nameN) {
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (it.t.indexOf(code) === -1) continue;
                if (it.tn.indexOf(nameN) !== -1) {
                    val = it.v; txt = it.t; how = 'code+name'; break;
                }
            }
            if (!val) {
                for (var i = 0; i < items.length; i++) {
                    var it = items[i];
                    if (it.t.indexOf(code) === -1) continue;
                    var after = it.tn;
                    var dash = it.tn.indexOf(' - ');
                    if (dash !== -1) after = it.tn.substring(dash + 3);
                    if (after.indexOf(nameN) !== -1 || nameN.indexOf(after) !== -1) {
                        val = it.v; txt = it.t; how = 'code+name_after'; break;
                    }
                }
            }
        }

        // 2) Faqat NOM
        if (!val && nameN) {
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                var after = it.tn;
                var dash = it.tn.indexOf(' - ');
                if (dash !== -1) after = it.tn.substring(dash + 3);
                if (after.indexOf(nameN) !== -1 || it.tn.indexOf(nameN) !== -1) {
                    val = it.v; txt = it.t; how = 'name_only'; break;
                }
            }
        }

        // 3) Faqat KOD
        if (!val && code) {
            var codeHits = [];
            for (var i = 0; i < items.length; i++) {
                if (items[i].t.indexOf(code) !== -1) codeHits.push(items[i]);
            }
            if (codeHits.length === 1) {
                val = codeHits[0].v; txt = codeHits[0].t; how = 'code_single';
            } else if (codeHits.length > 1 && !nameN) {
                val = codeHits[0].v; txt = codeHits[0].t; how = 'code_first_no_name';
            } else if (codeHits.length > 1 && nameN) {
                return {
                    ok: false,
                    reason: 'code_ambiguous_name_not_matched',
                    count: codeHits.length,
                    name: name,
                    sample: codeHits.map(function(x){ return x.t; })
                };
            }
        }

        if (!val) {
            return {
                ok: false,
                reason: 'option_topilmadi',
                count: items.length,
                sample: items.slice(0, 6).map(function(x){ return x.t; })
            };
        }

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
        el.setAttribute('aria-invalid', 'false');
        var fg = el.closest('.form-group');
        if (fg) {
            fg.classList.remove('has-error');
            var hb = fg.querySelector('.help-block');
            if (hb) hb.innerHTML = '';
        }
        return {ok:true, value: val, text: txt, how: how};
    """, code, name)

    if not result or not result.get("ok"):
        print(
            f"  ⚠ Specialty tanlanmadi: code={code!r} name={name!r} → {result}")
        return False

    print(f"  ✓ Specialty: {result.get('text')}  [{result.get('how')}]")
    time.sleep(0.4)
    return True


# ==================== SAQLASH / TOAST ====================
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
        wait.until(EC.presence_of_element_located((By.ID, "submitButton")))
        driver.execute_script("""
            var b = document.getElementById('submitButton');
            if (b) { b.scrollIntoView({block:'center'}); b.click(); }
        """)
        print("  ✓ Saqlash bosildi")
        return True
    except Exception as e:
        print(f"  ✗ Saqlash: {e}")
        return False


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


def wait_save_result(timeout: float = 8.0) -> tuple[bool, str]:
    end = time.time() + timeout
    success_msg = error_msg = any_toast = None
    time.sleep(0.3)

    while time.time() < end:
        for t in _collect_toasts_js():
            any_toast = any_toast or t
            low = t.lower()
            if (
                "hemis_error" in low
                or ("xato" in low and "himoya" not in low)
                or "error" in low
            ):
                if "himoya" not in low and "captcha" not in low:
                    if not error_msg:
                        error_msg = t
            elif any(w in low for w in [
                "muvaffaqiyatli", "saqlandi", "o'zgartirildi", "o‘zgartirildi"
            ]):
                if not success_msg:
                    success_msg = t

        if error_msg:
            return False, error_msg
        if success_msg:
            return True, success_msg
        time.sleep(0.2)

    if error_msg:
        return False, error_msg
    if success_msg:
        return True, success_msg
    if any_toast:
        return False, any_toast
    return True, "Saqlash bosildi (toast yo'q)"


# ==================== BITTA TALABA ====================
def process_student(pin: str, spec_code: str, spec_name: str = "", fio: str = "") -> tuple[bool, str]:
    print(f"\n--- {fio or pin} | JSHSHIR: {pin} ---")
    print(f"  → Specialty: {spec_code} / {spec_name}")

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
        time.sleep(0.9)

        try:
            wait.until(EC.presence_of_element_located((By.ID, "_specialty")))
        except Exception:
            return False, "_specialty select topilmadi"

        if not select_specialty_by_code(spec_code, spec_name):
            return False, f"Mutaxassislik topilmadi: {spec_code} / {spec_name}"

        # eski toast tozalash
        driver.execute_script("""
            var c = document.getElementById('toast-container');
            if (c) c.innerHTML = '';
            document.querySelectorAll('.toast').forEach(function(t){ t.remove(); });
        """)

        if not click_save():
            return False, "Saqlash tugmasi topilmadi"

        ok, msg = wait_save_result(timeout=8.0)
        if ok:
            return True, "Muvaffaqiyatli"
        return False, msg

    except Exception as e:
        return False, f"Xato: {str(e)[:120]}"


# ==================== MAIN ====================
def main():
    print("=" * 55)
    print("TALABA → FAQAT MUTAXASSISLIK O'ZGARTIRISH")
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
        pin = _s(row, COL_PIN)
        fio = _s(row, COL_FIO)
        code = _s(row, COL_SPECIALTY_CODE)
        name = _s(row, COL_SPECIALTY_NAME)
        print(f"[{idx + 1}/{total}]")

        success, msg = process_student(pin, code, name, fio)

        results.append({
            "fio": fio,
            "pin": pin,
            "specialty_code": code,
            "specialty_name": name,
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

    out = "hemis_order/specialty_update_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"📄 Natija: {out}")

    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()
