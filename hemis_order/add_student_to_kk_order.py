import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, UnexpectedAlertPresentException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time
from datetime import datetime
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

# Chrome sozlamalari
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

# ==================== LOGIN QISMI ====================
print("Login sahifasiga o'tyapman...")
driver.get("https://hemis.timeedu.uz/")

try:
    oneid_button = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(@href, '/auth/edu-id') or contains(text(), 'OneID')]"))
    )
    oneid_button.click()
    print("OneID tugmasi bosildi")
except Exception as e:
    print("OneID tugmasi topilmadi:", e)
    driver.quit()
    exit()

try:
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.NAME, "login")))
    print("OneID forma yuklandi")
except:
    print("OneID login maydoni topilmadi")
    driver.quit()
    exit()

driver.find_element(By.NAME, "login").clear()
driver.find_element(By.NAME, "login").send_keys(LOGIN_VALUE)
print("Login kiritildi")

driver.find_element(By.NAME, "password").clear()
driver.find_element(By.NAME, "password").send_keys(PASSWORD_VALUE)
print("Parol kiritildi")

try:
    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(), 'Kirish') or @type='submit']"))
    )
    submit_button.click()
    print("Kirish bosildi")
except Exception as e:
    print("Kirish tugmasi muammosi:", e)

time.sleep(1)

try:
    WebDriverWait(driver, 25).until(
        EC.presence_of_element_located((By.TAG_NAME, "body")))
    print("Dashboard yuklandi (kirish muvaffaqiyatli)")
except:
    print("Kirishdan keyin sahifa yuklanmadi")
    driver.quit()
    exit()

# ==================== Excel o'qish ====================
try:
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    print(f"Excel fayldan {len(df)} ta qator o'qildi")

    required_columns = [BUYRUK_ID_COLUMN, HEMIS_ID_COLUMN,
                        TALABA_FIO_COLUMN, GURUH_COLUMN, KURS_COLUMN, SEMESTR_COLUMN]
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

# ==================== TALABALARNI BUYRUQQA QO'SHISH ====================

muvaffaqiyatsiz_talabalar = []
checkbox_belgilanmaganlar = []


def selectlarni_tozalash():
    """Barcha select elementlarini default holatga qaytarish"""
    try:
        select_ids = [
            "edecreeinfostudentmeta-_group",
            "edecreeinfostudentmeta-_semestr",
            "edecreeinfostudentmeta-next_semester",
            "edecreeinfostudentmeta-_curriculum"
        ]

        for select_id in select_ids:
            try:
                # Elementni topish
                select_element = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.ID, select_id))
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", select_element)
                time.sleep(0.3)

                # Select ni tozalash
                select = Select(select_element)
                select.select_by_index(0)
                print(f"  ✓ {select_id} tozalandi")

            except StaleElementReferenceException:
                # Element stale bo'lsa, qayta topish
                try:
                    select_element = driver.find_element(By.ID, select_id)
                    select = Select(select_element)
                    select.select_by_index(0)
                    print(f"  ✓ {select_id} tozalandi (qayta)")
                except:
                    print(f"  ⚠ {select_id} tozalashda xatolik")
                    continue
            except Exception as e:
                print(f"  ⚠ {select_id} tozalashda xatolik: {e}")
                continue

        return True

    except Exception as e:
        print(f"  ✗ Selectlarni tozalashda xatolik: {e}")
        return False


def selectni_tanlash(select_id, qiymat, select_nomi):
    """Select elementi orqali tanlash - kuchaytirilgan usul"""
    try:
        # 1-usul: Standart Select
        try:
            select_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, select_id))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", select_element)
            time.sleep(0.5)

            select = Select(select_element)
            select.select_by_visible_text(qiymat)
            print(f"  ✓ {select_nomi} tanlandi: {qiymat}")
            return True, None
        except Exception as e:
            print(f"  ⚠ {select_nomi} tanlashda xatolik (usul 1): {e}")

        # 2-usul: JavaScript orqali
        try:
            js_code = f"""
                var select = document.getElementById('{select_id}');
                var options = select.options;
                for(var i = 0; i < options.length; i++) {{
                    if(options[i].text.trim() === '{qiymat}') {{
                        select.selectedIndex = i;
                        var event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);
                        return true;
                    }}
                }}
                return false;
            """
            result = driver.execute_script(js_code)
            if result:
                print(f"  ✓ {select_nomi} tanlandi (JavaScript): {qiymat}")
                return True, None
        except Exception as e:
            print(f"  ⚠ {select_nomi} tanlashda xatolik (usul 2): {e}")

        # 3-usul: Select2 orqali
        try:
            # Select2 containerini topish
            select2_container = driver.find_element(
                By.XPATH, f"//select[@id='{select_id}']/following-sibling::span[contains(@class, 'select2')]"
            )
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", select2_container)
            time.sleep(0.5)

            # Click orqali ochish
            try:
                select2_container.click()
            except:
                driver.execute_script(
                    "arguments[0].click();", select2_container)
            time.sleep(0.5)

            # Variantni topish va tanlash
            option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//li[contains(text(), '{qiymat}')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", option)
            time.sleep(0.3)

            try:
                option.click()
            except:
                driver.execute_script("arguments[0].click();", option)

            print(f"  ✓ {select_nomi} tanlandi (Select2): {qiymat}")
            return True, None
        except Exception as e:
            print(f"  ⚠ {select_nomi} tanlashda xatolik (usul 3): {e}")

        # 4-usul: Value bo'yicha
        try:
            select_element = driver.find_element(By.ID, select_id)
            options = select_element.find_elements(By.TAG_NAME, "option")

            for option in options:
                if option.text.strip() == qiymat:
                    value = option.get_attribute("value")
                    driver.execute_script(f"""
                        var select = document.getElementById('{select_id}');
                        select.value = '{value}';
                        var event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);
                    """)
                    print(f"  ✓ {select_nomi} tanlandi (value): {qiymat}")
                    return True, None
        except Exception as e:
            print(f"  ⚠ {select_nomi} tanlashda xatolik (usul 4): {e}")

        return False, f"{select_nomi} '{qiymat}' tanlanmadi"

    except Exception as e:
        print(f"  ✗ {select_nomi} tanlashda xatolik: {e}")
        return False, f"{select_nomi} xatoligi: {str(e)}"


def checkboxni_belgilash():
    """Checkboxni belgilash"""
    try:
        for attempt in range(3):
            try:
                checkboxes = driver.find_elements(
                    By.XPATH, "//input[@type='checkbox' and @name='selection[]']")

                if len(checkboxes) == 0:
                    print(f"  ✗ Hech qanday checkbox topilmadi")
                    time.sleep(1)
                    continue

                checkbox = checkboxes[0]
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", checkbox)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(0.5)

                is_checked = driver.execute_script(
                    "return arguments[0].checked;", checkbox)

                if is_checked:
                    print(f"  ✓ Checkbox aktiv holatga keltirildi")
                    return True, None
                else:
                    print(
                        f"  ⚠ Checkbox belgilanmadi, qayta urinish {attempt+1}")
                    time.sleep(1)

            except Exception as e:
                print(f"  ⚠ Urinish {attempt+1} xatolik: {e}")
                time.sleep(1)
                continue

        print(f"  ✗ Checkbox belgilanmadi (3 urinishdan keyin)")
        return False, "Checkbox belgilanmadi"

    except Exception as e:
        print(f"  ✗ Checkbox bilan ishlashda xatolik: {e}")
        return False, f"Checkbox xatoligi: {str(e)}"


def talabani_buyruqqa_qoshish(buyruq_id, hemis_id, talaba_fio, guruh, kurs, semestr, row_index, total_count):
    """
    Bitta talabani buyruqqa qo'shish funksiyasi
    """
    try:
        print(f"\n--- {row_index+1}/{total_count} ---")
        print(f"Talaba: {talaba_fio}")
        print(f"HEMIS ID: {hemis_id}, Buyruq ID: {buyruq_id}")
        print(f"Guruh: {guruh}, Kurs: {kurs}, Semestr: {semestr}")

        # Buyruq sahifasiga o'tish
        url = f"https://hemis.timeedu.uz/decree/edu-decree-edit-students?id={buyruq_id}"
        driver.get(url)
        time.sleep(2)

        # ========== 1. SELECTLARNI TOZALASH ==========
        print("  🔄 Selectlarni tozalash...")
        selectlarni_tozalash()
        time.sleep(0.5)

        # ========== 2. QIDIRUV ==========
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "edecreeinfostudentmeta-search"))
            )
            search_input.clear()
            search_input.send_keys(str(hemis_id))
            search_input.send_keys(Keys.ENTER)
            print(f"  ✓ HEMIS ID qidiruvga yozildi: {hemis_id}")
            time.sleep(2)
        except Exception as e:
            print(f"  ✗ Qidiruv xatoligi: {e}")
            return False, "Qidiruv xatoligi"

        # ========== 3. GURUH TANLASH ==========
        guruh_ok, guruh_err = selectni_tanlash(
            "edecreeinfostudentmeta-_group", guruh, "Guruh")
        if not guruh_ok:
            return False, guruh_err

        # ========== 4. SEMESTR TANLASH ==========
        semestr_ok, semestr_err = selectni_tanlash(
            "edecreeinfostudentmeta-_semestr", semestr, "Semestr")
        if not semestr_ok:
            return False, semestr_err

        # ========== 5. KURS TANLASH ==========
        kurs_ok, kurs_err = selectni_tanlash(
            "edecreeinfostudentmeta-next_semester", kurs, "Kurs")
        if not kurs_ok:
            return False, kurs_err

        # ========== 6. CHECKBOX BELGILASH ==========
        checkbox_ok, checkbox_err = checkboxni_belgilash()
        if not checkbox_ok:
            checkbox_belgilanmaganlar.append({
                'buyruq_id': buyruq_id,
                'hemis_id': hemis_id,
                'talaba_fio': talaba_fio,
                'guruh': guruh,
                'kurs': kurs,
                'semestr': semestr,
                'xatolik_sababi': checkbox_err
            })
            return False, checkbox_err

        # ========== 7. OK TUGMASI ==========
        try:
            ok_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@onclick='return confirmStudent()']"))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", ok_button)
            time.sleep(0.5)
            ok_button.click()
            print("  ✓ OK tugmasi bosildi")
            time.sleep(1)
        except Exception as e:
            print(f"  ✗ OK tugmasi xatoligi: {e}")
            return False, f"OK tugmasi topilmadi: {str(e)}"

        # ========== 8. ALERT ==========
        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert_text = alert.text
            print(f"  Alert: {alert_text}")
            alert.accept()
            print("  ✓ Alert qabul qilindi")
            time.sleep(2)

            if "muvaffaqiyatli" in alert_text.lower() or "qo'shildi" in alert_text.lower():
                return True, "Muvaffaqiyatli"
            else:
                if "xatolik" in alert_text.lower() or "error" in alert_text.lower():
                    return False, f"Alert xatoligi: {alert_text}"
                return True, "Muvaffaqiyatli"

        except TimeoutException:
            return False, "Alert topilmadi"
        except UnexpectedAlertPresentException:
            try:
                alert = driver.switch_to.alert
                alert.accept()
                return True, "Muvaffaqiyatli"
            except:
                return False, "Alert xatoligi"
        except Exception as e:
            return False, f"Alert xatoligi: {str(e)}"

    except Exception as e:
        print(f"  ✗ Umumiy xatolik: {e}")
        return False, f"Umumiy xatolik: {str(e)}"


# ==================== ASOSIY JARAYON ====================
print("\n" + "="*60)
print("TALABALARNI BUYRUQQA QO'SHISH JARAYONI BOSHLANDI")
print("="*60)

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

        # NaN tekshirish
        if pd.isna(buyruq_id) or pd.isna(hemis_id) or pd.isna(guruh) or pd.isna(kurs) or pd.isna(semestr):
            print(f"\n--- {index+1}/{total_count} ---")
            print(f"  ⚠ Ma'lumotlar to'liq emas, o'tkazib yuborildi")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                'buyruq_id': buyruq_id,
                'hemis_id': hemis_id,
                'talaba_fio': talaba_fio,
                'guruh': guruh,
                'kurs': kurs,
                'semestr': semestr,
                'xatolik_sababi': "Ma'lumotlar to'liq emas (NaN)"
            })
            continue

        # Format
        try:
            buyruq_id = int(float(buyruq_id)) if isinstance(
                buyruq_id, (int, float)) else int(buyruq_id)
            hemis_id = str(int(float(hemis_id))) if isinstance(
                hemis_id, (int, float)) else str(hemis_id)
        except:
            print(f"\n--- {index+1}/{total_count} ---")
            print(f"  ⚠ Format xatoligi")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                'buyruq_id': buyruq_id,
                'hemis_id': hemis_id,
                'talaba_fio': talaba_fio,
                'guruh': guruh,
                'kurs': kurs,
                'semestr': semestr,
                'xatolik_sababi': "Format xatoligi"
            })
            continue

        natija, sabab = talabani_buyruqqa_qoshish(
            buyruq_id, hemis_id, talaba_fio, guruh, kurs, semestr, index, total_count)

        if natija:
            muvaffaqiyatli += 1
        else:
            muvaffaqiyatsiz += 1
            if sabab not in ["Checkbox belgilanmadi"]:
                muvaffaqiyatsiz_talabalar.append({
                    'buyruq_id': buyruq_id,
                    'hemis_id': hemis_id,
                    'talaba_fio': talaba_fio,
                    'guruh': guruh,
                    'kurs': kurs,
                    'semestr': semestr,
                    'xatolik_sababi': sabab
                })

        time.sleep(0.5)

    except Exception as e:
        print(f"\n--- {index+1}/{total_count} ---")
        print(f"  ✗ Xatolik: {e}")
        muvaffaqiyatsiz += 1
        muvaffaqiyatsiz_talabalar.append({
            'buyruq_id': row.get(BUYRUK_ID_COLUMN, 'Noma\'lum'),
            'hemis_id': row.get(HEMIS_ID_COLUMN, 'Noma\'lum'),
            'talaba_fio': row.get(TALABA_FIO_COLUMN, 'Noma\'lum'),
            'guruh': row.get(GURUH_COLUMN, 'Noma\'lum'),
            'kurs': row.get(KURS_COLUMN, 'Noma\'lum'),
            'semestr': row.get(SEMESTR_COLUMN, 'Noma\'lum'),
            'xatolik_sababi': f"Umumiy xatolik: {str(e)}"
        })

# ==================== NATIJALAR ====================
print("\n" + "="*60)
print("JARAYON YAKUNLANDI!")
print("="*60)
print(f"Jami talabalar: {total_count}")
print(f"✅ Muvaffaqiyatli: {muvaffaqiyatli}")
print(f"❌ Muvaffaqiyatsiz: {muvaffaqiyatsiz}")
if checkbox_belgilanmaganlar:
    print(f"⚠️ Checkbox belgilanmaganlar: {len(checkbox_belgilanmaganlar)}")
print("="*60)

# ==================== EXCELGA YOZISH ====================

# 1. Umumiy muvaffaqiyatsizlar
if muvaffaqiyatsiz_talabalar:
    pd.DataFrame(muvaffaqiyatsiz_talabalar).to_excel(
        f"hemis_order/qoshilmagan_talabalar.xlsx",
        index=False,
        sheet_name="Muvaffaqiyatsizlar"
    )
    print(f"\n📄 Muvaffaqiyatsizlar: {len(muvaffaqiyatsiz_talabalar)} ta")

# 2. Checkbox belgilanmaganlar
if checkbox_belgilanmaganlar:
    pd.DataFrame(checkbox_belgilanmaganlar).to_excel(
        f"hemis_order/checkbox_belgilanmaganlar.xlsx",
        index=False,
        sheet_name="Checkbox belgilanmaganlar"
    )
    print(f"📄 Checkbox belgilanmaganlar: {len(checkbox_belgilanmaganlar)} ta")

if not muvaffaqiyatsiz_talabalar and not checkbox_belgilanmaganlar:
    print("\n✅ Barcha talabalar muvaffaqiyatli qo'shildi!")

time.sleep(3)
driver.quit()
print("\nDastur tugadi!")
