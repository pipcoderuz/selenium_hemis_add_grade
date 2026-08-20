import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time
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

MASUL_SHAXS = "SHARIPOV KAMRONBEK KONGRATBAYEVICH"
OQITUVCHI = "SHOKIR"

# Semestr endi dinamik: Sirtqi → 10-semestr, Kunduzgi → 8-semestr
SEMESTR = "10-semestr"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# options.add_argument("--headless=new")
driver = webdriver.Chrome(options=options)

muvaffaqiyatsiz_talabalar = []


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
    except:
        print("OneID login maydoni topilmadi")
        return False

    driver.find_element(By.NAME, "login").clear()
    driver.find_element(By.NAME, "login").send_keys(LOGIN_VALUE)
    print("Login kiritildi")

    driver.find_element(By.NAME, "password").clear()
    driver.find_element(By.NAME, "password").send_keys(PASSWORD_VALUE)
    print("Parol kiritildi")

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
        print("Dashboard yuklandi (kirish muvaffaqiyatli)")
        return True
    except:
        print("Kirishdan keyin sahifa yuklanmadi")
        return False


# ==================== EXCEL O'QISH + GURUHLASH ====================
def excel_oquvchi_va_guruhla():
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
        print(f"Excel fayldan {len(df)} ta qator o'qildi")

        required = [HEMIS_ID_COLUMN, BUYRUK_NOMI_COLUMN,
                    BUYRUK_SANASI_COLUMN, FAN_COLUMN]
        for col in required:
            if col not in df.columns:
                print(f"Xatolik: Excelda '{col}' ustuni topilmadi!")
                print(f"Mavjud ustunlar: {list(df.columns)}")
                return None

        df = df.dropna(
            subset=[HEMIS_ID_COLUMN, BUYRUK_NOMI_COLUMN, BUYRUK_SANASI_COLUMN, FAN_COLUMN])
        df[HEMIS_ID_COLUMN] = df[HEMIS_ID_COLUMN].astype(str).str.strip()
        df[BUYRUK_NOMI_COLUMN] = df[BUYRUK_NOMI_COLUMN].astype(str).str.strip()
        df[BUYRUK_SANASI_COLUMN] = df[BUYRUK_SANASI_COLUMN].astype(
            str).str.strip()
        df[FAN_COLUMN] = df[FAN_COLUMN].astype(str).str.strip()

        grouped = (
            df.groupby([HEMIS_ID_COLUMN, BUYRUK_NOMI_COLUMN,
                       BUYRUK_SANASI_COLUMN], as_index=False)
            .agg({
                FAN_COLUMN: lambda x: list(dict.fromkeys(x)),
                **({TALABA_FIO_COLUMN: "first"} if TALABA_FIO_COLUMN in df.columns else {})
            })
        )

        print(
            f"Guruhlashdan keyin {len(grouped)} ta unikal talaba/buyruq topildi")
        return grouped

    except Exception as e:
        print(f"Excel o'qishda xatolik: {e}")
        return None


# ==================== O'QITUVCHI — BARCHA QATORLARGA ====================
def oqituvchi_qidirish_va_tanlash():
    try:
        selectize_inputs = driver.find_elements(
            By.CSS_SELECTOR, "div.selectize-input input[type='text']"
        )

        if not selectize_inputs:
            print("  ✗ Hech qanday o'qituvchi Selectize topilmadi")
            return False

        print(f"  O'qituvchi uchun {len(selectize_inputs)} ta maydon topildi")

        for i, inp in enumerate(selectize_inputs):
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", inp)
                time.sleep(0.3)

                parent = inp.find_element(
                    By.XPATH, "./ancestor::div[contains(@class,'selectize-input')]"
                )
                existing = parent.find_elements(By.CSS_SELECTOR, "div.item")
                if existing:
                    current_name = existing[0].text.strip()
                    if OQITUVCHI in current_name or current_name in OQITUVCHI:
                        print(f"  → #{i+1} allaqachon to'g'ri: {current_name}")
                        continue
                    try:
                        clear_btn = parent.find_element(
                            By.CSS_SELECTOR, "a.remove")
                        clear_btn.click()
                        time.sleep(0.3)
                    except:
                        pass

                inp.click()
                time.sleep(0.2)
                inp.clear()
                inp.send_keys(OQITUVCHI)
                time.sleep(1.2)

                options = driver.find_elements(
                    By.CSS_SELECTOR, "div.selectize-dropdown-content div.option"
                )
                selected = False
                for opt in options:
                    if OQITUVCHI in opt.text or opt.text in OQITUVCHI:
                        opt.click()
                        selected = True
                        break

                if not selected:
                    inp.send_keys(Keys.ENTER)

                print(f"  ✓ #{i+1} o'qituvchi tanlandi: {OQITUVCHI}")
                time.sleep(0.4)

            except Exception as e:
                print(f"  ⚠ #{i+1} o'qituvchi yozishda xato: {e}")
                continue

        return True

    except Exception as e:
        print(f"  ✗ O'qituvchilarni tanlashda umumiy xato: {e}")
        return False


# ==================== MUDDAT — 3 OY KEYINGI SANA ====================
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
            print("  ✗ Muddat (control_date) inputlari topilmadi")
            return False

        future_date = datetime.now() + timedelta(days=90)
        future_date_str = future_date.strftime("%Y-%m-%d")

        print(
            f"  Muddat uchun {len(date_inputs)} ta input topildi → {future_date_str}")

        for i, date_input in enumerate(date_inputs):
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", date_input
                )
                time.sleep(0.25)

                driver.execute_script(
                    """
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('input',  { bubbles: true }));
                    """,
                    date_input,
                    future_date_str
                )

                date_input.clear()
                date_input.send_keys(future_date_str)
                date_input.send_keys(Keys.TAB)

                print(f"  ✓ Muddat #{i+1} yozildi: {future_date_str}")

            except Exception as e:
                print(f"  ⚠ Muddat #{i+1} yozishda xato: {e}")

        return True

    except Exception as e:
        print(f"  ✗ Muddatlarni yozishda umumiy xato: {e}")
        return False


# ==================== PTT TALABA QO'SHISH ====================
def ptt_talaba_qoshish(row):
    global SEMESTR

    try:
        hemis_id = str(row[HEMIS_ID_COLUMN]).strip()
        buyruq_nomi = f"№ {str(row[BUYRUK_NOMI_COLUMN]).strip()}"
        buyruq_sanasi = str(row[BUYRUK_SANASI_COLUMN]).strip()
        fanlar = row[FAN_COLUMN]

        talaba_fio = ""
        if TALABA_FIO_COLUMN in row and pd.notna(row.get(TALABA_FIO_COLUMN)):
            talaba_fio = str(row[TALABA_FIO_COLUMN]).strip()

        print(
            f"\n--- Talaba qo'shilmoqda: HEMIS ID={hemis_id} {talaba_fio} ---")
        print(f"  Buyruq: {buyruq_nomi} / {buyruq_sanasi}")
        print(f"  Fanlar ({len(fanlar)} ta): {fanlar}")

        # PTT sahifasi
        driver.get("https://hemis.timeedu.uz/performance/ptt-edit")
        time.sleep(2)

        # HEMIS ID qidirish
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "estudentpttmeta-search"))
            )
            search_input.clear()
            search_input.send_keys(hemis_id)
            search_input.send_keys(Keys.ENTER)
            print(f"  ✓ HEMIS ID qidiruvga yozildi: {hemis_id}")
            time.sleep(2)
        except Exception as e:
            print(f"  ✗ Qidiruv maydoni topilmadi: {e}")
            return False, "Qidiruv xatoligi"

        # Buyruqni topib "Qo'shish" bosish + Ta'lim turini o'qish
        try:
            rows = driver.find_elements(By.XPATH, "//table//tbody/tr")
            qoshish_topildi = False
            talim_turi_text = ""

            for tr in rows:
                try:
                    cells = tr.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 7:
                        continue

                    # Guruh ustuni (indeks 5) — buyruq nomi va sanasi shu yerda
                    guruh_text = cells[5].text.strip()

                    if buyruq_nomi in guruh_text and buyruq_sanasi in guruh_text:
                        # Ta'lim turi (indeks 3)
                        talim_turi_text = cells[3].text.strip()
                        print(
                            f"  ✓ Ta'lim turi o'qildi: {talim_turi_text.replace(chr(10), ' / ')}")

                        # Semestrni belgilash
                        if "Sirtqi" in talim_turi_text:
                            SEMESTR = "10-semestr"
                        elif "Magistr" in talim_turi_text:
                            # Magistr 
                            SEMESTR = "4-semestr"
                        else:
                            # Kunduzgi yoki boshqa
                            SEMESTR = "8-semestr"
                        print(f"  ✓ Semestr belgilandi: {SEMESTR}")

                        # Qo'shish tugmasi (indeks 6)
                        qoshish_links = cells[6].find_elements(
                            By.XPATH, ".//a[contains(text(), \"Qo'shish\")]"
                        )
                        if not qoshish_links:
                            print(
                                "  ✗ 'Qo'shish' tugmasi yo'q — shaxsiy qaydnoma allaqachon yaratilgan")
                            return False, "Shaxsiy qaydnoma buyruqda yaratilgan"

                        td_qoshish = qoshish_links[0]
                        driver.execute_script(
                            "arguments[0].scrollIntoView(true);", td_qoshish)
                        time.sleep(0.5)
                        td_qoshish.click()
                        print("  ✓ 'Qo'shish' tugmasi bosildi")
                        qoshish_topildi = True
                        break
                except Exception:
                    continue

            if not qoshish_topildi:
                print(f"  ✗ Buyruq topilmadi: {buyruq_nomi} / {buyruq_sanasi}")
                return False, "Buyruq topilmadi"

        except Exception as e:
            print(f"  ✗ Buyruqni topishda xatolik: {e}")
            return False, "Buyruq topilmadi"

        time.sleep(2)

        # Forma ochilganini tekshirish
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.ID, "estudentptt-date"))
            )
            print("  ✓ Forma ochildi")
        except TimeoutException:
            print("  ✗ Forma ochilmadi — shaxsiy qaydnoma buyruqda yaratilgan")
            return False, "Shaxsiy qaydnoma buyruqda yaratilgan"

        # Sana va raqam
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            date_input = driver.find_element(By.ID, "estudentptt-date")
            date_input.clear()
            date_input.send_keys(today)
            print(f"  ✓ Sana kiritildi: {today}")

            timestamp = str(int(time.time()))
            number_input = driver.find_element(By.ID, "estudentptt-number")
            number_input.clear()
            number_input.send_keys(timestamp)
            print(f"  ✓ Raqam kiritildi: {timestamp}")
        except Exception as e:
            print(f"  ✗ Sana/raqam kiritishda xatolik: {e}")
            return False, "Sana/raqam xatoligi"

        # Mas'ul shaxs
        try:
            admin_select = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "estudentptt-_admin"))
            )
            Select(admin_select).select_by_visible_text(MASUL_SHAXS)
            print(f"  ✓ Mas'ul shaxs tanlandi: {MASUL_SHAXS}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ✗ Mas'ul shaxsni tanlashda xatolik: {e}")
            return False, "Mas'ul shaxs xatoligi"

        # Semestr (dinamik: Sirtqi=10, Kunduzgi=8)
        try:
            semester_select = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "estudentptt-_semester"))
            )
            Select(semester_select).select_by_visible_text(SEMESTR)
            print(f"  ✓ Semestr tanlandi: {SEMESTR}")
            time.sleep(2)
        except Exception as e:
            print(f"  ✗ Semestrni tanlashda xatolik: {e}")
            return False, "Semestr xatoligi"

        # Fanlarni belgilash
        try:
            fan_checkboxes = driver.find_elements(
                By.XPATH, "//table//tbody/tr/td[2]/input[@type='checkbox' and @class='ptt-items']"
            )

            belgilangan = []
            topilmagan = []

            for checkbox in fan_checkboxes:
                try:
                    tr = checkbox.find_element(By.XPATH, "./ancestor::tr")
                    fan_nomi = tr.find_element(
                        By.XPATH, ".//td[3]").text.strip()

                    if fan_nomi in fanlar:
                        if checkbox.get_attribute("disabled"):
                            print(f"  ⚠ Fan o'chirilgan: {fan_nomi}")
                            topilmagan.append(f"{fan_nomi} (o'chirilgan)")
                        else:
                            driver.execute_script(
                                "arguments[0].scrollIntoView(true);", checkbox)
                            time.sleep(0.3)
                            driver.execute_script(
                                "arguments[0].click();", checkbox)
                            belgilangan.append(fan_nomi)
                            print(f"  ✓ Fan belgilandi: {fan_nomi}")
                except:
                    continue

            for fan in fanlar:
                if fan not in belgilangan and fan not in [f.split(" (")[0] for f in topilmagan]:
                    topilmagan.append(fan)

            if topilmagan:
                print(f"  ⚠ Topilmagan / o'chirilgan fanlar: {topilmagan}")

            if not belgilangan:
                print("  ✗ Hech qanday fan belgilanmadi!")
                return False, "Fan topilmadi"

            print(f"  ✓ Jami {len(belgilangan)} ta fan belgilandi")

        except Exception as e:
            print(f"  ✗ Fanlarni belgilashda xatolik: {e}")
            return False, "Fan topilmadi"

        # Birinchi saqlash
        try:
            save_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//button[@type='submit' and contains(@onclick, 'validateSelectedSubjects')]")
                )
            )
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", save_button)
            time.sleep(0.5)
            save_button.click()
            print("  ✓ Saqlash tugmasi bosildi")
            time.sleep(2)
        except Exception as e:
            print(f"  ✗ Saqlash tugmasini bosishda xatolik: {e}")
            return False, "Saqlash xatoligi"

        # Alert
        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert_text = alert.text
            print(f"  Alert matni: {alert_text}")
            alert.accept()
            if "shaxsiy jadval yaratish" in alert_text.lower():
                print("  ✓ Alert qabul qilindi (shaxsiy jadval)")
            time.sleep(3)
        except TimeoutException:
            print("  ⚠ Alert kelmadi, davom etilmoqda...")
        except Exception as e:
            print(f"  ⚠ Alertda xatolik: {e}")

        # O'qituvchi
        try:
            if not oqituvchi_qidirish_va_tanlash():
                print("  ⚠ O'qituvchi tanlanmadi, davom etilmoqda...")
        except Exception as e:
            print(f"  ⚠ O'qituvchi qidirishda xatolik: {e}")

        # Muddat
        try:
            if not nazorat_sanasi_yozish():
                print("  ⚠ Muddatlar yozilmadi, davom etilmoqda...")
        except Exception as e:
            print(f"  ⚠ Muddat yozishda xatolik: {e}")

        # ==================== YAKUNIY SAQLASH ====================
        try:
            final_save = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//button[@type='submit' and contains(@class,'btn-primary') and contains(., 'Saqlash')]")
                )
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", final_save)
            time.sleep(0.5)

            try:
                final_save.click()
            except:
                driver.execute_script("arguments[0].click();", final_save)

            print("  ✓ Yakuniy Saqlash tugmasi bosildi")
            time.sleep(2.5)

            try:
                alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert_text = alert.text
                print(f"  Yakuniy alert: {alert_text}")
                alert.accept()

                if any(w in alert_text.lower() for w in ["muvaffaqiyatli", "saqlandi", "success"]):
                    print("  ✅ Talaba muvaffaqiyatli qo'shildi!")
                    return True, "Muvaffaqiyatli"
                else:
                    return False, f"Alert: {alert_text}"

            except TimeoutException:
                print("  ✅ Talaba muvaffaqiyatli qo'shildi! (alert yo'q)")
                return True, "Muvaffaqiyatli"

        except Exception as e:
            print(f"  ✗ Yakuniy saqlashda xatolik: {e}")
            return False, "Yakuniy saqlash xatoligi"

    except Exception as e:
        print(f"  ✗ Umumiy xatolik: {e}")
        return False, f"Umumiy xatolik: {str(e)}"


# ==================== ASOSIY ====================
def main():
    print("\n" + "=" * 60)
    print("PTT TALABA QO'SHISH BOTI ISHGA TUSHIRILDI")
    print("=" * 60)

    if not login():
        print("Login muvaffaqiyatsiz! Dastur to'xtatiladi.")
        driver.quit()
        return

    df = excel_oquvchi_va_guruhla()
    if df is None:
        driver.quit()
        return

    print(f"\nJami {len(df)} ta unikal talaba/buyruq qayta ishlanadi")

    muvaffaqiyatli = 0
    muvaffaqiyatsiz = 0

    for index, row in df.iterrows():
        try:
            print(f"\n--- {index + 1}/{len(df)} ---")
            natija, sabab = ptt_talaba_qoshish(row)

            if natija:
                muvaffaqiyatli += 1
            else:
                muvaffaqiyatsiz += 1
                muvaffaqiyatsiz_talabalar.append({
                    "hemis_id": row[HEMIS_ID_COLUMN],
                    "talaba_fio": row.get(TALABA_FIO_COLUMN, ""),
                    "buyruq_nomi": row[BUYRUK_NOMI_COLUMN],
                    "buyruq_sanasi": row[BUYRUK_SANASI_COLUMN],
                    "fanlar": "; ".join(row[FAN_COLUMN]) if isinstance(row[FAN_COLUMN], list) else row[FAN_COLUMN],
                    "xatolik_sababi": sabab
                })

            time.sleep(1)

        except Exception as e:
            print(f"\n--- {index + 1}/{len(df)} ---")
            print(f"  ✗ Qatorda xatolik: {e}")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                "hemis_id": row.get(HEMIS_ID_COLUMN, "Noma'lum"),
                "talaba_fio": row.get(TALABA_FIO_COLUMN, ""),
                "buyruq_nomi": row.get(BUYRUK_NOMI_COLUMN, "Noma'lum"),
                "buyruq_sanasi": row.get(BUYRUK_SANASI_COLUMN, "Noma'lum"),
                "fanlar": str(row.get(FAN_COLUMN, "")),
                "xatolik_sababi": f"Qator xatoligi: {str(e)}"
            })

    print("\n" + "=" * 60)
    print("JARAYON YAKUNLANDI!")
    print("=" * 60)
    print(f"Jami unikal talaba/buyruq: {len(df)}")
    print(f"✅ Muvaffaqiyatli: {muvaffaqiyatli}")
    print(f"❌ Muvaffaqiyatsiz: {muvaffaqiyatsiz}")
    print("=" * 60)

    if muvaffaqiyatsiz_talabalar:
        df_err = pd.DataFrame(muvaffaqiyatsiz_talabalar)
        error_file = "personal_sheet/ptt_muvaffaqiyatsiz_talabalar.xlsx"
        df_err.to_excel(error_file, index=False,
                        sheet_name="Muvaffaqiyatsizlar")
        print(
            f"\n📄 Muvaffaqiyatsizlar '{error_file}' ga yozildi ({len(df_err)} ta)")
    else:
        print("\n✅ Barcha talabalar muvaffaqiyatli qo'shildi!")

    time.sleep(2)
    driver.quit()
    print("\nDastur tugadi!")


if __name__ == "__main__":
    main()
