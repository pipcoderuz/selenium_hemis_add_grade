import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, UnexpectedAlertPresentException
)
from selenium.webdriver.common.keys import Keys
import time
from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== O'ZGARUVCHILAR ====================
EXCEL_FILE = "hemis_order/kk_order_students.xlsx"
SHEET_NAME = "orders"
BUYRUK_ID_COLUMN = "buyruq_id"
HEMIS_ID_COLUMN = "hemis_id"
TALABA_FIO_COLUMN = "talaba_fio"
GURUH_COLUMN = "guruh"
KURS_COLUMN = "kurs"
SEMESTR_COLUMN = "semestr"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

muvaffaqiyatsiz_talabalar = []
checkbox_belgilanmaganlar = []


# ==================== LOGIN ====================
print("Login sahifasiga o'tyapman...")
driver.get("https://hemis.timeedu.uz/")

try:
    oneid_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,
             "//a[contains(@href, '/auth/edu-id') or contains(text(), 'OneID')]")
        )
    )
    oneid_button.click()
    print("OneID tugmasi bosildi")
except Exception as e:
    print("OneID tugmasi topilmadi:", e)
    driver.quit()
    exit()

try:
    wait.until(EC.presence_of_element_located((By.NAME, "login")))
    print("OneID forma yuklandi")
except Exception:
    print("OneID login maydoni topilmadi")
    driver.quit()
    exit()

driver.find_element(By.NAME, "login").clear()
driver.find_element(By.NAME, "login").send_keys(LOGIN_VALUE)
driver.find_element(By.NAME, "password").clear()
driver.find_element(By.NAME, "password").send_keys(PASSWORD_VALUE)

try:
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[contains(text(), 'Kirish') or @type='submit']")
    )).click()
    print("Kirish bosildi")
except Exception as e:
    print("Kirish tugmasi muammosi:", e)

time.sleep(1.5)

try:
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    print("Dashboard yuklandi")
except Exception:
    print("Kirishdan keyin sahifa yuklanmadi")
    driver.quit()
    exit()


# ==================== Excel ====================
try:
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    print(f"Excel fayldan {len(df)} ta qator o'qildi")

    required_columns = [
        BUYRUK_ID_COLUMN, HEMIS_ID_COLUMN, TALABA_FIO_COLUMN,
        GURUH_COLUMN, KURS_COLUMN, SEMESTR_COLUMN
    ]
    for col in required_columns:
        if col not in df.columns:
            print(f"Xatolik: Excelda '{col}' ustuni topilmadi!")
            print(f"Mavjud ustunlar: {list(df.columns)}")
            driver.quit()
            exit()
except Exception as e:
    print(f"Excel faylni o'qishda xatolik: {e}")
    driver.quit()
    exit()


# ==================== TOZALASH ====================
def tozalash_tugmasini_bosish():
    try:
        clear_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 "//a[contains(@href, 'clear-filter=1') and contains(., 'Tozalash')]")
            )
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", clear_btn)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", clear_btn)
        print("  ✓ Tozalash tugmasi bosildi")
        time.sleep(0.8)
        return True
    except Exception as e:
        print(f"  ⚠ Tozalash: {e}")
        return False


# ==================== SELECT2 ====================
def selectni_tanlash(select_id, qiymat, select_nomi, wait_opts: int = 20):
    qiymat = str(qiymat).strip()
    if not qiymat:
        return False, f"{select_nomi} qiymati bo'sh"

    for _ in range(wait_opts):
        n = driver.execute_script("""
            var el = document.getElementById(arguments[0]);
            if (!el) return 0;
            var c = 0;
            for (var i = 0; i < el.options.length; i++) {
                if ((el.options[i].value || '').trim()) c++;
            }
            return c;
        """, select_id)
        if n and n > 0:
            break
        time.sleep(0.3)

    result = driver.execute_script("""
        var el = document.getElementById(arguments[0]);
        var needleRaw = (arguments[1] || '').trim();
        if (!el) return {ok:false, reason:'element_yoq'};

        function norm(s) {
            s = (s || '').toLowerCase().trim();
            s = s.replace(/[‘’`]/g, "'");
            s = s.replace(/[–—]/g, '-');
            s = s.replace(/\\s+/g, ' ');
            return s;
        }
        var needle = norm(needleRaw);
        var val = null, txt = null;

        for (var i = 0; i < el.options.length; i++) {
            var o = el.options[i];
            var v = (o.value || '').trim();
            var t = (o.textContent || o.innerText || '').trim();
            if (!v) continue;
            if (norm(t) === needle) { val = v; txt = t; break; }
        }
        if (!val) {
            for (var i = 0; i < el.options.length; i++) {
                var o = el.options[i];
                var v = (o.value || '').trim();
                var t = (o.textContent || o.innerText || '').trim();
                if (!v) continue;
                var nt = norm(t);
                if (nt.indexOf(needle) !== -1 || needle.indexOf(nt) !== -1) {
                    val = v; txt = t; break;
                }
            }
        }
        if (!val && needle.indexOf('kurs') !== -1) {
            var parts = needle.split('/');
            var p0 = (parts[0] || '').trim();
            var p1 = (parts[1] || '').trim();
            for (var i = 0; i < el.options.length; i++) {
                var o = el.options[i];
                var v = (o.value || '').trim();
                var t = (o.textContent || o.innerText || '').trim();
                if (!v) continue;
                var nt = norm(t);
                if (p0 && p1 && nt.indexOf(p0) !== -1 && nt.indexOf(p1) !== -1) {
                    val = v; txt = t; break;
                }
            }
        }

        if (!val) {
            var opts = [];
            for (var i = 0; i < el.options.length; i++) {
                var t = (el.options[i].textContent || '').trim();
                var v = (el.options[i].value || '').trim();
                if (v) opts.push(t);
            }
            return {ok:false, reason:'option_topilmadi', options: opts.slice(0, 8)};
        }

        el.value = val;
        if (window.jQuery) {
            var $el = jQuery(el);
            $el.val(val).trigger('change');
            try { $el.trigger('select2:select'); } catch(e) {}
            try {
                var $s2 = $el.next('.select2-container')
                    .find('.select2-selection__rendered');
                if ($s2.length) {
                    $s2.text(txt)
                       .removeClass('select2-selection__placeholder')
                       .attr('title', txt);
                }
            } catch(e) {}
        }
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('input', {bubbles:true}));
        return {ok:true, value: val, text: txt};
    """, select_id, qiymat)

    if result and result.get("ok"):
        print(f"  ✓ {select_nomi} tanlandi: {result.get('text')}")
        time.sleep(0.6)
        return True, None

    print(f"  ✗ {select_nomi}: '{qiymat}' topilmadi → {result}")
    return False, f"{select_nomi} '{qiymat}' tanlanmadi"


# ==================== CHECKBOX ====================
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
                '.toast-message, .toast-success, .toast-error, .toast-info'
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


def clear_toasts():
    driver.execute_script("""
        var c = document.getElementById('toast-container');
        if (c) c.innerHTML = '';
        document.querySelectorAll('.toast').forEach(function(t){ t.remove(); });
    """)


def wait_success_toast(max_wait: float = 30.0) -> tuple[bool, str]:
    """
    Toast chiqmaguncha kutadi (vaqtga bog'liq emas — polling).
    max_wait — faqat himoya: umuman chiqmasa to'xtatish.
    """
    start = time.time()
    error_msg = None
    any_toast = None

    while True:
        for t in _collect_toasts_js():
            any_toast = any_toast or t
            low = t.lower()

            # muvaffaqiyat
            if (
                "muvaffaqiyatli" in low
                and ("qo'shildi" in low or "qo‘shildi" in low or "qoshildi" in low)
            ) or (
                "hujjatga" in low and "muvaffaqiyatli" in low
            ):
                print(f"  ✅ Toast: {t[:120]}")
                return True, t

            # xato toast
            if (
                "xato" in low or "error" in low or "hemis_error" in low
            ) and "himoya" not in low:
                if not error_msg:
                    error_msg = t

        if error_msg:
            print(f"  ❌ Toast xato: {error_msg[:120]}")
            return False, error_msg

        # Himoya: juda uzoq kutib qolmasin
        if time.time() - start > max_wait:
            if any_toast:
                return False, f"Kutilgan success toast emas: {any_toast[:120]}"
            return False, f"Success toast {int(max_wait)}s ichida chiqmadi"

        time.sleep(0.25)  # faqat CPU yukini kamaytirish uchun

# ==================== TALABANI BUYRUQQA QO'SHISH ====================
def talabani_buyruqqa_qoshish(
    buyruq_id, hemis_id, talaba_fio, guruh, kurs, semestr, row_index, total_count
):
    try:
        print(f"\n--- {row_index+1}/{total_count} ---")
        print(f"Talaba: {talaba_fio}")
        print(f"HEMIS ID: {hemis_id}, Buyruq ID: {buyruq_id}")
        print(f"Guruh: {guruh}, Kurs: {kurs}, Semestr: {semestr}")

        url = f"https://hemis.timeedu.uz/decree/edu-decree-edit-students?id={buyruq_id}"
        driver.get(url)
        time.sleep(0.8)

        print("  🔄 Filtrlarni tozalash...")
        tozalash_tugmasini_bosish()

        # Qidiruv
        try:
            search_input = wait.until(
                EC.presence_of_element_located(
                    (By.ID, "edecreeinfostudentmeta-search"))
            )
            driver.execute_script("""
                var el = arguments[0];
                el.value = '';
                el.dispatchEvent(new Event('input', {bubbles:true}));
            """, search_input)
            try:
                search_input.clear()
            except Exception:
                pass
            search_input.send_keys(str(hemis_id))
            search_input.send_keys(Keys.ENTER)
            print(f"  ✓ HEMIS ID qidiruvga yozildi: {hemis_id}")
            time.sleep(0.7)
        except Exception as e:
            print(f"  ✗ Qidiruv xatoligi: {e}")
            return False, "Qidiruv xatoligi"

        # Guruh
        guruh_ok, guruh_err = selectni_tanlash(
            "edecreeinfostudentmeta-_group", guruh, "Guruh")
        if not guruh_ok:
            return False, guruh_err

        # Semestr
        semestr_ok, semestr_err = selectni_tanlash(
            "edecreeinfostudentmeta-_semestr", semestr, "Semestr")
        if not semestr_ok:
            return False, semestr_err

        # Kurs
        time.sleep(0.8)
        kurs_ok, kurs_err = selectni_tanlash(
            "edecreeinfostudentmeta-next_semester", kurs, "Kurs", wait_opts=25)
        if not kurs_ok:
            return False, kurs_err

        # Checkbox
        checkbox_ok, checkbox_err = checkboxni_belgilash()
        if not checkbox_ok:
            checkbox_belgilanmaganlar.append({
                "buyruq_id": buyruq_id,
                "hemis_id": hemis_id,
                "talaba_fio": talaba_fio,
                "guruh": guruh,
                "kurs": kurs,
                "semestr": semestr,
                "xatolik_sababi": checkbox_err,
            })
            return False, checkbox_err

        # Eski toast tozalash (oldingi talabadan)
        clear_toasts()

        # OK
        try:
            ok_button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@onclick='return confirmStudent()']")
                )
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
                ok_button,
            )
            print("  ✓ OK tugmasi bosildi")
            time.sleep(0.4)
        except Exception as e:
            print(f"  ✗ OK tugmasi: {e}")
            return False, f"OK tugmasi topilmadi: {str(e)}"

        # Alert OK
        try:
            alert = WebDriverWait(driver, 6).until(EC.alert_is_present())
            alert_text = alert.text
            print(f"  Alert: {alert_text}")
            alert.accept()
            print("  ✓ Alert qabul qilindi")
        except TimeoutException:
            return False, "Alert topilmadi"
        except UnexpectedAlertPresentException:
            try:
                driver.switch_to.alert.accept()
                print("  ✓ Alert qabul qilindi")
            except Exception:
                return False, "Alert xatoligi"
        except Exception as e:
            return False, f"Alert xatoligi: {str(e)}"

        # Toast: "Hujjatga 1 nafar talaba muvaffaqiyatli qo'shildi"
        ok, toast_msg = wait_success_toast(max_wait=30.0)
        if not ok:
            return False, toast_msg

        time.sleep(0.4)
        return True, "Muvaffaqiyatli"

    except Exception as e:
        print(f"  ✗ Umumiy xatolik: {e}")
        return False, f"Umumiy xatolik: {str(e)}"


# ==================== ASOSIY ====================
print("\n" + "=" * 60)
print("TALABALARNI BUYRUQQA QO'SHISH JARAYONI BOSHLANDI")
print("=" * 60)

muvaffaqiyatli = 0
muvaffaqiyatsiz = 0
total_count = len(df)

for index, row in df.iterrows():
    try:
        buyruq_id = row[BUYRUK_ID_COLUMN]
        hemis_id = row[HEMIS_ID_COLUMN]
        talaba_fio = row[TALABA_FIO_COLUMN]
        guruh = str(row[GURUH_COLUMN]).strip()
        kurs = str(row[KURS_COLUMN]).strip()
        semestr = str(row[SEMESTR_COLUMN]).strip()

        if pd.isna(buyruq_id) or pd.isna(hemis_id) or pd.isna(guruh) or pd.isna(kurs) or pd.isna(semestr):
            print(f"\n--- {index+1}/{total_count} ---")
            print("  ⚠ Ma'lumotlar to'liq emas")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                "buyruq_id": buyruq_id,
                "hemis_id": hemis_id,
                "talaba_fio": talaba_fio,
                "guruh": guruh,
                "kurs": kurs,
                "semestr": semestr,
                "xatolik_sababi": "Ma'lumotlar to'liq emas (NaN)",
            })
            continue

        try:
            buyruq_id = int(float(buyruq_id)) if isinstance(
                buyruq_id, (int, float)) else int(buyruq_id)
            hemis_id = str(int(float(hemis_id))) if isinstance(
                hemis_id, (int, float)) else str(hemis_id)
        except Exception:
            print(f"\n--- {index+1}/{total_count} ---")
            print("  ⚠ Format xatoligi")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                "buyruq_id": buyruq_id,
                "hemis_id": hemis_id,
                "talaba_fio": talaba_fio,
                "guruh": guruh,
                "kurs": kurs,
                "semestr": semestr,
                "xatolik_sababi": "Format xatoligi",
            })
            continue

        natija, sabab = talabani_buyruqqa_qoshish(
            buyruq_id, hemis_id, talaba_fio, guruh, kurs, semestr,
            index, total_count
        )

        if natija:
            muvaffaqiyatli += 1
            print(f"  ✅ {sabab}")
        else:
            muvaffaqiyatsiz += 1
            print(f"  ❌ {sabab}")
            if sabab not in ["Checkbox belgilanmadi"]:
                muvaffaqiyatsiz_talabalar.append({
                    "buyruq_id": buyruq_id,
                    "hemis_id": hemis_id,
                    "talaba_fio": talaba_fio,
                    "guruh": guruh,
                    "kurs": kurs,
                    "semestr": semestr,
                    "xatolik_sababi": sabab,
                })

        time.sleep(0.4)

    except Exception as e:
        print(f"\n--- {index+1}/{total_count} ---")
        print(f"  ✗ Xatolik: {e}")
        muvaffaqiyatsiz += 1
        muvaffaqiyatsiz_talabalar.append({
            "buyruq_id": row.get(BUYRUK_ID_COLUMN, "Noma'lum"),
            "hemis_id": row.get(HEMIS_ID_COLUMN, "Noma'lum"),
            "talaba_fio": row.get(TALABA_FIO_COLUMN, "Noma'lum"),
            "guruh": row.get(GURUH_COLUMN, "Noma'lum"),
            "kurs": row.get(KURS_COLUMN, "Noma'lum"),
            "semestr": row.get(SEMESTR_COLUMN, "Noma'lum"),
            "xatolik_sababi": f"Umumiy xatolik: {str(e)}",
        })


print("\n" + "=" * 60)
print("JARAYON YAKUNLANDI!")
print("=" * 60)
print(f"Jami talabalar: {total_count}")
print(f"✅ Muvaffaqiyatli: {muvaffaqiyatli}")
print(f"❌ Muvaffaqiyatsiz: {muvaffaqiyatsiz}")
if checkbox_belgilanmaganlar:
    print(f"⚠ Checkbox belgilanmaganlar: {len(checkbox_belgilanmaganlar)}")
print("=" * 60)

if muvaffaqiyatsiz_talabalar:
    pd.DataFrame(muvaffaqiyatsiz_talabalar).to_excel(
        "hemis_order/qoshilmagan_talabalar.xlsx",
        index=False,
        sheet_name="Muvaffaqiyatsizlar",
    )
    print(f"\n📄 Muvaffaqiyatsizlar: {len(muvaffaqiyatsiz_talabalar)} ta")

if checkbox_belgilanmaganlar:
    pd.DataFrame(checkbox_belgilanmaganlar).to_excel(
        "hemis_order/checkbox_belgilanmaganlar.xlsx",
        index=False,
        sheet_name="Checkbox belgilanmaganlar",
    )
    print(f"📄 Checkbox belgilanmaganlar: {len(checkbox_belgilanmaganlar)} ta")

if not muvaffaqiyatsiz_talabalar and not checkbox_belgilanmaganlar:
    print("\n✅ Barcha talabalar muvaffaqiyatli qo'shildi!")

time.sleep(2)
driver.quit()
print("\nDastur tugadi!")
