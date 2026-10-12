import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time
import re
from datetime import datetime, timedelta
from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== O'ZGARUVCHILAR ====================
EXCEL_FILE = "personal_sheet/personal_sheets.xlsx"
SHEET_NAME = "talabalar"

HEMIS_ID_COLUMN = "hemis_id"
TALABA_FIO_COLUMN = "talaba_fio"
BUYRUK_NOMI_COLUMN = "buyruq_nomi"
BUYRUK_SANASI_COLUMN = "buyruq_sanasi"
FAN_COLUMN = "fan"
SEMESTR_COLUMN = "semestr"

MASUL_SHAXS = "SHARIPOV KAMRONBEK KONGRATBAYEVICH"

OQITUVCHI_QIDIRUV = "SHOKIR"
OQITUVCHI_TOLIQ = "SHARIPOV SHOKIR XOLBOY O‘G‘LI"

SEMESTR = "10-semestr"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

muvaffaqiyatsiz_talabalar = []


def clean_id(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value).strip()
    s = str(value).strip()
    if re.fullmatch(r"\d+\.0+", s):
        return s.split(".")[0]
    return s


def norm_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("‘", "'").replace(
        "’", "'").replace("ʻ", "'").replace("ʼ", "'")
    s = s.replace("`", "'").replace("´", "'")
    s = re.sub(r"\s+", " ", s)
    return s


# ==================== LOGIN ====================
def login():
    print("Login sahifasiga o'tyapman...")
    driver.get("https://hemis.timeedu.uz/")

    try:
        oneid_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 "//a[contains(@href, '/auth/edu-id') or contains(text(), 'OneID')]")
            )
        )
        oneid_button.click()
        print("OneID tugmasi bosildi")
    except Exception as e:
        print("OneID tugmasi topilmadi:", e)
        return False

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "login")))
        print("OneID forma yuklandi")
    except Exception:
        print("OneID login maydoni topilmadi")
        return False

    driver.find_element(By.NAME, "login").clear()
    driver.find_element(By.NAME, "login").send_keys(LOGIN_VALUE)
    driver.find_element(By.NAME, "password").clear()
    driver.find_element(By.NAME, "password").send_keys(PASSWORD_VALUE)

    try:
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 "//button[contains(text(), 'Kirish') or @type='submit']")
            )
        )
        submit_button.click()
        print("Kirish bosildi")
    except Exception as e:
        print("Kirish tugmasi muammosi:", e)
        return False

    time.sleep(1)
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Dashboard yuklandi")
        return True
    except Exception:
        print("Kirishdan keyin sahifa yuklanmadi")
        return False


# ==================== EXCEL ====================
def excel_oquvchi_va_guruhla():
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
        print(f"Excel fayldan {len(df)} ta qator o'qildi")

        required = [HEMIS_ID_COLUMN, BUYRUK_NOMI_COLUMN,
                    BUYRUK_SANASI_COLUMN, FAN_COLUMN]
        for col in required:
            if col not in df.columns:
                print(
                    f"Xatolik: '{col}' ustuni yo'q. Mavjud: {list(df.columns)}")
                return None

        has_semestr = SEMESTR_COLUMN in df.columns
        df = df.dropna(subset=[HEMIS_ID_COLUMN, BUYRUK_NOMI_COLUMN,
                               BUYRUK_SANASI_COLUMN, FAN_COLUMN])
        df[HEMIS_ID_COLUMN] = df[HEMIS_ID_COLUMN].apply(clean_id)
        df[BUYRUK_NOMI_COLUMN] = df[BUYRUK_NOMI_COLUMN].astype(str).str.strip()
        df[BUYRUK_SANASI_COLUMN] = df[BUYRUK_SANASI_COLUMN].astype(
            str).str.strip()
        df[FAN_COLUMN] = df[FAN_COLUMN].astype(str).str.strip()

        if has_semestr:
            df[SEMESTR_COLUMN] = df[SEMESTR_COLUMN].apply(
                lambda x: "" if pd.isna(x) else str(x).strip())
        else:
            df[SEMESTR_COLUMN] = ""

        def collect_fans(group):
            items, seen = [], set()
            for _, r in group.iterrows():
                fan = str(r[FAN_COLUMN]).strip()
                sem = str(r[SEMESTR_COLUMN]).strip() if has_semestr else ""
                key = (fan, sem)
                if key not in seen:
                    seen.add(key)
                    items.append({"fan": fan, "semestr": sem})
            return items

        group_cols = [HEMIS_ID_COLUMN,
                      BUYRUK_NOMI_COLUMN, BUYRUK_SANASI_COLUMN]
        records = []
        for keys, grp in df.groupby(group_cols, as_index=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            rec = {
                HEMIS_ID_COLUMN: keys[0],
                BUYRUK_NOMI_COLUMN: keys[1],
                BUYRUK_SANASI_COLUMN: keys[2],
                FAN_COLUMN: collect_fans(grp),
            }
            if TALABA_FIO_COLUMN in df.columns:
                fio_val = grp[TALABA_FIO_COLUMN].dropna()
                rec[TALABA_FIO_COLUMN] = (
                    str(fio_val.iloc[0]).strip() if len(fio_val) else "")
            records.append(rec)

        grouped = pd.DataFrame(records)
        print(f"Guruhlash: {len(grouped)} ta")
        return grouped
    except Exception as e:
        print(f"Excel xato: {e}")
        return None


# ==================== O'QITUVCHI (selectize: data-selectable + span.item-option) ====================
def get_selectize_options():
    """
    Haqiqiy HTML:
      div.selectize-dropdown-content
        > div[data-selectable][data-value="..."]
          > span.item-option  TEXT
    """
    return driver.execute_script("""
        var out = [];
        var nodes = document.querySelectorAll(
            'div.selectize-dropdown-content div[data-selectable], ' +
            'div.selectize-dropdown div[data-selectable]'
        );
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            // display:none parent bo'lsa ham text olamiz; keyin click qilamiz
            var span = el.querySelector('span.item-option');
            var txt = (span ? span.textContent : el.textContent) || '';
            txt = txt.replace(/\\s+/g, ' ').trim();
            if (!txt) continue;
            out.push({
                value: el.getAttribute('data-value') || '',
                text: txt,
                index: i
            });
        }
        return out;
    """) or []


def click_selectize_option_by_value_or_text(value: str = "", text: str = "") -> bool:
    """Optionni data-value yoki text bo'yicha JS click"""
    return bool(driver.execute_script("""
        var wantVal = (arguments[0] || '').toString();
        var wantTxt = (arguments[1] || '').toLowerCase().trim();
        function norm(s) {
            return (s || '').toLowerCase()
                .replace(/[‘’ʻʼ`´]/g, "'")
                .replace(/\\s+/g, ' ').trim();
        }
        wantTxt = norm(wantTxt);
        var nodes = document.querySelectorAll(
            'div.selectize-dropdown-content div[data-selectable], ' +
            'div.selectize-dropdown div[data-selectable]'
        );
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            var v = el.getAttribute('data-value') || '';
            var span = el.querySelector('span.item-option');
            var t = norm(span ? span.textContent : el.textContent);
            if (wantVal && v === wantVal) {
                el.click();
                return true;
            }
            if (wantTxt && (t === wantTxt || t.indexOf(wantTxt) !== -1 || wantTxt.indexOf(t) !== -1)) {
                // sharipov+shokir bo'lsa aniqroq
                el.click();
                return true;
            }
        }
        return false;
    """, value, text))


def oqituvchi_qidirish_va_tanlash():
    try:
        selectize_inputs = driver.find_elements(
            By.CSS_SELECTOR, "div.selectize-input input[type='text']"
        )
        if not selectize_inputs:
            print("  ✗ Selectize input topilmadi")
            return False

        print(f"  O'qituvchi maydonlari: {len(selectize_inputs)} ta")
        toliq_n = norm_text(OQITUVCHI_TOLIQ)
        kerak = ["sharipov", "shokir"]  # xolboy ixtiyoriy

        for i, inp in enumerate(selectize_inputs):
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", inp)
                time.sleep(0.2)

                parent = inp.find_element(
                    By.XPATH, "./ancestor::div[contains(@class,'selectize-input')]")

                # Allaqachon to'g'ri?
                existing = parent.find_elements(By.CSS_SELECTOR, "div.item")
                if existing:
                    cur = existing[0].text.strip()
                    cn = norm_text(cur)
                    if all(p in cn for p in kerak):
                        print(f"  → #{i+1} allaqachon: {cur}")
                        continue
                    try:
                        parent.find_element(
                            By.CSS_SELECTOR, "a.remove").click()
                        time.sleep(0.3)
                    except Exception:
                        driver.execute_script("""
                            arguments[0].querySelectorAll('div.item').forEach(function(it){ it.remove(); });
                        """, parent)
                        time.sleep(0.2)

                # Fokus + tozalash
                driver.execute_script("arguments[0].click();", inp)
                time.sleep(0.15)
                try:
                    inp.send_keys(Keys.CONTROL, "a")
                    inp.send_keys(Keys.BACKSPACE)
                except Exception:
                    pass

                # Qidiruv matnini yozish
                for ch in OQITUVCHI_QIDIRUV:
                    inp.send_keys(ch)
                    time.sleep(0.03)
                time.sleep(1.6)

                # Dropdown ochiqligini ta'minlash
                driver.execute_script("""
                    var dd = document.querySelector('div.selectize-dropdown');
                    if (dd) {
                        dd.style.display = 'block';
                        dd.style.visibility = 'visible';
                    }
                """)
                time.sleep(0.3)

                # Optionlarni o'qish
                opts = []
                for _ in range(12):
                    opts = get_selectize_options()
                    if opts:
                        break
                    time.sleep(0.3)

                if not opts:
                    print(f"  ⚠ #{i+1} optionlar yo'q")
                    continue

                print(f"  ℹ #{i+1} {len(opts)} ta option (namuna):")
                for o in opts[:6]:
                    print(f"      [{o.get('value')}] {o.get('text', '')[:70]}")

                # Mos optionni topish
                best_val, best_txt = None, None

                for o in opts:
                    tn = norm_text(o.get("text", ""))
                    if all(p in tn for p in ["sharipov", "shokir", "xolboy"]):
                        best_val, best_txt = o.get("value"), o.get("text")
                        break
                if not best_val:
                    for o in opts:
                        tn = norm_text(o.get("text", ""))
                        if all(p in tn for p in kerak):
                            best_val, best_txt = o.get("value"), o.get("text")
                            break
                if not best_val:
                    for o in opts:
                        tn = norm_text(o.get("text", ""))
                        if toliq_n in tn or tn in toliq_n:
                            best_val, best_txt = o.get("value"), o.get("text")
                            break

                if not best_val:
                    print(f"  ✗ #{i+1} SHARIPOV SHOKIR topilmadi")
                    # Dropdown yopish
                    try:
                        inp.send_keys(Keys.ESCAPE)
                    except Exception:
                        pass
                    continue

                # Click — data-value yoki text
                ok = click_selectize_option_by_value_or_text(
                    best_val, best_txt)
                if not ok:
                    # Selenium fallback
                    try:
                        el = driver.find_element(
                            By.CSS_SELECTOR,
                            f'div.selectize-dropdown-content div[data-selectable][data-value="{best_val}"]'
                        )
                        driver.execute_script("arguments[0].click();", el)
                        ok = True
                    except Exception:
                        try:
                            spans = driver.find_elements(
                                By.CSS_SELECTOR,
                                "div.selectize-dropdown-content span.item-option"
                            )
                            for sp in spans:
                                if norm_text(sp.text) == norm_text(best_txt) or \
                                   all(p in norm_text(sp.text) for p in kerak):
                                    driver.execute_script(
                                        "arguments[0].closest('div[data-selectable]').click();", sp)
                                    ok = True
                                    break
                        except Exception as e2:
                            print(f"  ⚠ click fallback: {e2}")

                time.sleep(0.45)

                # Tekshirish
                items = parent.find_elements(By.CSS_SELECTOR, "div.item")
                if items:
                    final = items[0].text.strip()
                    print(f"  ✓ #{i+1} tanlandi: {final}")
                elif ok:
                    print(f"  ✓ #{i+1} tanlandi: {best_txt}")
                else:
                    print(f"  ✗ #{i+1} tanlanmadi")

            except Exception as e:
                print(f"  ⚠ #{i+1} xato: {e}")
                continue

        return True
    except Exception as e:
        print(f"  ✗ O'qituvchi umumiy xato: {e}")
        return False


# ==================== MUDDAT ====================
def nazorat_sanasi_yozish():
    try:
        date_inputs = driver.find_elements(
            By.CSS_SELECTOR,
            "input.form-control.krajee-datepicker[name*='control_date']"
        )
        if not date_inputs:
            date_inputs = driver.find_elements(
                By.XPATH,
                "//input[contains(@name, 'EStudentPtt[ar][control_date]')]"
            )
        if not date_inputs:
            print("  ✗ Muddat topilmadi")
            return False

        future = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        print(f"  Muddat: {len(date_inputs)} ta → {future}")
        for i, di in enumerate(date_inputs):
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", di)
                time.sleep(0.2)
                driver.execute_script(
                    """
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
                    arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
                    """, di, future)
                di.clear()
                di.send_keys(future)
                di.send_keys(Keys.TAB)
                print(f"  ✓ Muddat #{i+1}: {future}")
            except Exception as e:
                print(f"  ⚠ Muddat #{i+1}: {e}")
        return True
    except Exception as e:
        print(f"  ✗ Muddat: {e}")
        return False


def norm_semestr(s: str) -> str:
    s = (s or "").lower().strip().replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s)


def fan_mos_keladimi(fan_nomi, qator_sem, kerak_fan, kerak_sem) -> bool:
    if fan_nomi.strip() != kerak_fan.strip():
        if kerak_fan.strip() not in fan_nomi.strip() and fan_nomi.strip() not in kerak_fan.strip():
            return False
    if not kerak_sem:
        return True
    return norm_semestr(kerak_sem) in norm_semestr(qator_sem) or \
        norm_semestr(qator_sem) in norm_semestr(kerak_sem)


# ==================== PTT ====================
def ptt_talaba_qoshish(row):
    global SEMESTR
    try:
        hemis_id = clean_id(row[HEMIS_ID_COLUMN])
        buyruq_nomi = f"№ {str(row[BUYRUK_NOMI_COLUMN]).strip()}"
        buyruq_sanasi = str(row[BUYRUK_SANASI_COLUMN]).strip()
        fanlar = row[FAN_COLUMN]
        if fanlar and isinstance(fanlar[0], str):
            fanlar = [{"fan": f, "semestr": ""} for f in fanlar]

        talaba_fio = ""
        if TALABA_FIO_COLUMN in row and pd.notna(row.get(TALABA_FIO_COLUMN)):
            talaba_fio = str(row[TALABA_FIO_COLUMN]).strip()

        print(f"\n--- HEMIS={hemis_id} {talaba_fio} ---")
        print(f"  Buyruq: {buyruq_nomi} / {buyruq_sanasi}")

        driver.get("https://hemis.timeedu.uz/performance/ptt-edit")
        time.sleep(2)

        try:
            si = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "estudentpttmeta-search")))
            si.clear()
            si.send_keys(hemis_id)
            si.send_keys(Keys.ENTER)
            print(f"  ✓ Qidiruv: {hemis_id}")
            time.sleep(2)
        except Exception as e:
            return False, f"Qidiruv: {e}"

        try:
            rows = driver.find_elements(By.XPATH, "//table//tbody/tr")
            found = False
            for tr in rows:
                try:
                    cells = tr.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 7:
                        continue
                    guruh = cells[5].text.strip()
                    if buyruq_nomi in guruh and buyruq_sanasi in guruh:
                        talim = cells[3].text.strip()
                        if "Sirtqi" in talim:
                            SEMESTR = "10-semestr"
                        elif "Magistr" in talim:
                            SEMESTR = "4-semestr"
                        else:
                            SEMESTR = "8-semestr"
                        print(f"  ✓ Semestr: {SEMESTR}")
                        links = cells[6].find_elements(
                            By.XPATH, ".//a[contains(text(), \"Qo'shish\")]")
                        if not links:
                            return False, "Shaxsiy qaydnoma allaqachon yaratilgan"
                        driver.execute_script(
                            "arguments[0].scrollIntoView(true);", links[0])
                        time.sleep(0.4)
                        links[0].click()
                        print("  ✓ Qo'shish")
                        found = True
                        break
                except Exception:
                    continue
            if not found:
                return False, "Buyruq topilmadi"
        except Exception as e:
            return False, f"Buyruq: {e}"

        time.sleep(2)
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.ID, "estudentptt-date")))
        except TimeoutException:
            return False, "Forma ochilmadi"

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            driver.find_element(By.ID, "estudentptt-date").clear()
            driver.find_element(By.ID, "estudentptt-date").send_keys(today)
            ts = str(int(time.time()))
            driver.find_element(By.ID, "estudentptt-number").clear()
            driver.find_element(By.ID, "estudentptt-number").send_keys(ts)
            print(f"  ✓ Sana/raqam: {today} / {ts}")
        except Exception as e:
            return False, f"Sana: {e}"

        try:
            Select(WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "estudentptt-_admin"))
            )).select_by_visible_text(MASUL_SHAXS)
            print(f"  ✓ Mas'ul: {MASUL_SHAXS}")
            time.sleep(0.4)
        except Exception as e:
            return False, f"Mas'ul: {e}"

        try:
            Select(WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "estudentptt-_semester"))
            )).select_by_visible_text(SEMESTR)
            print(f"  ✓ Semestr: {SEMESTR}")
            time.sleep(2)
        except Exception as e:
            return False, f"Semestr: {e}"

        # Fanlar
        try:
            cbs = driver.find_elements(
                By.XPATH,
                "//table//tbody/tr/td[2]//input[@type='checkbox' and @class='ptt-items']")
            jadval, belgilangan, topilmagan = [], [], []
            for cb in cbs:
                try:
                    tr = cb.find_element(By.XPATH, "./ancestor::tr")
                    tds = tr.find_elements(By.TAG_NAME, "td")
                    jadval.append({
                        "cb": cb,
                        "fan": tds[2].text.strip() if len(tds) > 2 else "",
                        "sem": tds[-1].text.strip() if len(tds) > 3 else "",
                        "dis": cb.get_attribute("disabled") is not None,
                    })
                except Exception:
                    continue

            for item in fanlar:
                kf, ks = item["fan"], item.get("semestr", "") or ""
                okf = False
                for j in jadval:
                    if fan_mos_keladimi(j["fan"], j["sem"], kf, ks):
                        if j["dis"]:
                            topilmagan.append(f"{kf} (o'chirilgan)")
                        else:
                            driver.execute_script(
                                "arguments[0].scrollIntoView(true);", j["cb"])
                            time.sleep(0.2)
                            driver.execute_script(
                                "arguments[0].click();", j["cb"])
                            belgilangan.append(j["fan"])
                            print(f"  ✓ Fan: {j['fan']} [{j['sem']}]")
                        okf = True
                        break
                if not okf:
                    topilmagan.append(kf)
            if topilmagan:
                print(f"  ⚠ Topilmagan: {topilmagan}")
            if not belgilangan:
                return False, "Fan topilmadi"
        except Exception as e:
            return False, f"Fan: {e}"

        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//button[@type='submit' and contains(@onclick,'validateSelectedSubjects')]")))
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(0.3)
            btn.click()
            print("  ✓ Saqlash")
            time.sleep(2)
        except Exception as e:
            return False, f"Saqlash: {e}"

        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            print(f"  Alert: {alert.text}")
            alert.accept()
            time.sleep(3)
        except TimeoutException:
            pass
        except Exception:
            pass

        try:
            oqituvchi_qidirish_va_tanlash()
        except Exception as e:
            print(f"  ⚠ O'qituvchi: {e}")

        try:
            nazorat_sanasi_yozish()
        except Exception as e:
            print(f"  ⚠ Muddat: {e}")

        try:
            final = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//button[@type='submit' and contains(@class,'btn-primary') and contains(.,'Saqlash')]")))
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", final)
            time.sleep(0.3)
            try:
                final.click()
            except Exception:
                driver.execute_script("arguments[0].click();", final)
            print("  ✓ Yakuniy Saqlash")
            time.sleep(2.5)
            try:
                alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                at = alert.text
                alert.accept()
                if any(w in at.lower() for w in ["muvaffaqiyatli", "saqlandi", "success"]):
                    print("  ✅ OK")
                    return True, "Muvaffaqiyatli"
                return False, f"Alert: {at}"
            except TimeoutException:
                print("  ✅ OK (alert yo'q)")
                return True, "Muvaffaqiyatli"
        except Exception as e:
            return False, f"Yakuniy: {e}"

    except Exception as e:
        return False, f"Umumiy: {str(e)[:120]}"


def main():
    print("\n" + "=" * 60)
    print("PTT TALABA QO'SHISH BOTI")
    print("=" * 60)

    if not login():
        driver.quit()
        return

    df = excel_oquvchi_va_guruhla()
    if df is None:
        driver.quit()
        return

    ok_c = fail_c = 0
    for index, row in df.iterrows():
        print(f"\n--- {index + 1}/{len(df)} ---")
        try:
            natija, sabab = ptt_talaba_qoshish(row)
            fanlar = row[FAN_COLUMN]
            if fanlar and isinstance(fanlar[0], dict):
                fan_str = "; ".join(
                    f"{x['fan']}" +
                    (f" [{x['semestr']}]" if x.get("semestr") else "")
                    for x in fanlar)
            else:
                fan_str = str(fanlar)

            if natija:
                ok_c += 1
            else:
                fail_c += 1
                muvaffaqiyatsiz_talabalar.append({
                    "hemis_id": row[HEMIS_ID_COLUMN],
                    "talaba_fio": row.get(TALABA_FIO_COLUMN, ""),
                    "buyruq_nomi": row[BUYRUK_NOMI_COLUMN],
                    "buyruq_sanasi": row[BUYRUK_SANASI_COLUMN],
                    "fanlar": fan_str,
                    "xatolik_sababi": sabab
                })
                print(f"  ❌ {sabab}")
            time.sleep(1)
        except Exception as e:
            fail_c += 1
            print(f"  ✗ {e}")

    print("\n" + "=" * 60)
    print(f"Jami: {len(df)} | ✅ {ok_c} | ❌ {fail_c}")
    if muvaffaqiyatsiz_talabalar:
        pd.DataFrame(muvaffaqiyatsiz_talabalar).to_excel(
            "personal_sheet/ptt_muvaffaqiyatsiz_talabalar.xlsx", index=False)
        print("📄 ptt_muvaffaqiyatsiz_talabalar.xlsx")

    driver.quit()
    print("Tugadi!")


if __name__ == "__main__":
    main()
