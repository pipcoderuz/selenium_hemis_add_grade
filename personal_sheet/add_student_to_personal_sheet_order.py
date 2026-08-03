import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, UnexpectedAlertPresentException, InvalidElementStateException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime
from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== O'ZGARUVCHILAR ====================
EXCEL_FILE = "personal_sheet/order_students.xlsx"
SHEET_NAME = "orders"
BUYRUK_ID_COLUMN = "buyruq_id"      # Excelda buyruq ID si bo'lgan ustun nomi
HEMIS_ID_COLUMN = "hemis_id"        # Excelda HEMIS ID bo'lgan ustun nomi
TALABA_FIO_COLUMN = "talaba_fio"    # Excelda talaba FIO si bo'lgan ustun nomi

# Chrome sozlamalari
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# options.add_argument("--headless=new")  # yangi headless rejim (agar kerak bo'lsa)
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

    # Kerakli ustunlar mavjudligini tekshirish
    if BUYRUK_ID_COLUMN not in df.columns:
        print(f"Xatolik: Excelda '{BUYRUK_ID_COLUMN}' ustuni topilmadi!")
        print(f"Mavjud ustunlar: {list(df.columns)}")
        driver.quit()
        exit()

    if HEMIS_ID_COLUMN not in df.columns:
        print(f"Xatolik: Excelda '{HEMIS_ID_COLUMN}' ustuni topilmadi!")
        print(f"Mavjud ustunlar: {list(df.columns)}")
        driver.quit()
        exit()

    if TALABA_FIO_COLUMN not in df.columns:
        print(f"Xatolik: Excelda '{TALABA_FIO_COLUMN}' ustuni topilmadi!")
        print(f"Mavjud ustunlar: {list(df.columns)}")
        driver.quit()
        exit()

except Exception as e:
    print(f"Excel faylni o'qishda xatolik: {e}")
    driver.quit()
    exit()

# ==================== TALABALARNI BUYRUQQA QO'SHISH ====================

# Muvaffaqiyatsiz talabalarni saqlash uchun ro'yxat
muvaffaqiyatsiz_talabalar = []


def talabani_buyruqqa_qoshish(buyruq_id, hemis_id, talaba_fio, row_index):
    """
    Bitta talabani buyruqqa qo'shish funksiyasi
    """
    try:
        print(
            f"\n--- Talaba qo'shilmoqda: Buyruq ID={buyruq_id}, HEMIS ID={hemis_id}, FIO={talaba_fio} ---")

        # Buyruq sahifasiga o'tish
        url = f"https://hemis.timeedu.uz/decree/edu-decree-edit-students?id={buyruq_id}"
        driver.get(url)
        time.sleep(2)

        # Qidiruv maydoniga HEMIS ID ni yozish
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "edecreeinfostudentmeta-search"))
            )
            search_input.clear()
            search_input.send_keys(str(hemis_id))
            search_input.send_keys(Keys.ENTER)
            print(f"  ✓ HEMIS ID qidiruvga yozildi: {hemis_id}")
            time.sleep(2)  # Natijalarni yuklash uchun
        except Exception as e:
            print(f"  ✗ Qidiruv maydoni topilmadi: {e}")
            return False, "Qidiruv maydoni topilmadi"

        # Checkboxni topish - value atributiga qarab emas, balki jadvaldagi birinchi checkboxni olish
        try:
            # Birinchi usul: Jadvaldagi checkboxlardan birinchisini olish
            checkboxes = driver.find_elements(
                By.XPATH, "//input[@type='checkbox' and @name='selection[]']")

            if len(checkboxes) == 0:
                print(f"  ✗ Hech qanday checkbox topilmadi")
                return False, "Checkbox topilmadi"

            # Birinchi checkboxni olish (agar bir nechta bo'lsa, birinchisi)
            checkbox = checkboxes[0]

            # Scroll qilish
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", checkbox)
            time.sleep(0.5)

            # Checkboxni bosish (JavaScript orqali)
            driver.execute_script("arguments[0].click();", checkbox)
            print(f"  ✓ Checkbox belgilandi")

            # Qo'shimcha: checkbox belgilanganligini tekshirish
            is_checked = driver.execute_script(
                "return arguments[0].checked;", checkbox)
            if is_checked:
                print(f"  ✓ Checkbox aktiv holatga keltirildi")
            else:
                print(f"  ⚠ Checkbox belgilanmadi, qayta urinish...")
                # Ikkinchi marta urinish
                driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(0.5)

        except Exception as e:
            print(f"  ✗ Checkbox bilan ishlashda xatolik: {e}")
            return False, f"Checkbox xatoligi: {str(e)}"

        # OK tugmasini bosish
        try:
            ok_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@onclick='return confirmStudent()']"))
            )
            # Scroll qilish
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", ok_button)
            time.sleep(0.5)
            ok_button.click()
            print("  ✓ OK tugmasi bosildi")
            time.sleep(1)
        except Exception as e:
            print(f"  ✗ OK tugmasi topilmadi: {e}")
            return False, f"OK tugmasi topilmadi: {str(e)}"

        # Alertni qabul qilish
        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert_text = alert.text
            print(f"  Alert matni: {alert_text}")
            alert.accept()
            print("  ✓ Alert qabul qilindi")
            time.sleep(2)

            # Muvaffaqiyatli qo'shilganligini tekshirish
            if "muvaffaqiyatli" in alert_text.lower() or "qo'shildi" in alert_text.lower():
                print(f"  ✅ Talaba muvaffaqiyatli qo'shildi!")
                return True, "Muvaffaqiyatli"
            else:
                print(f"  ⚠ Alert: {alert_text}")
                # Agar alertda xatolik haqida ma'lumot bo'lsa
                if "xatolik" in alert_text.lower() or "error" in alert_text.lower():
                    return False, f"Alert xatoligi: {alert_text}"
                return True, "Muvaffaqiyatli"

        except TimeoutException:
            print("  ✗ Alert topilmadi (vaqt tugadi)")
            return False, "Alert topilmadi"
        except UnexpectedAlertPresentException:
            try:
                alert = driver.switch_to.alert
                alert.accept()
                print("  ✓ Kutilmagan alert qabul qilindi")
                return True, "Muvaffaqiyatli"
            except:
                print("  ✗ Alert bilan ishlashda xatolik")
                return False, "Alert xatoligi"
        except Exception as e:
            print(f"  ✗ Alertda xatolik: {e}")
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

for index, row in df.iterrows():
    try:
        buyruq_id = row[BUYRUK_ID_COLUMN]
        hemis_id = row[HEMIS_ID_COLUMN]
        talaba_fio = row[TALABA_FIO_COLUMN] if TALABA_FIO_COLUMN in df.columns else "Noma'lum"

        # NaN qiymatlarni tekshirish
        if pd.isna(buyruq_id) or pd.isna(hemis_id):
            print(f"\n--- {index+1}/{len(df)} ---")
            print(
                f"  ⚠ Qator {index+1}: Ma'lumotlar to'liq emas (NaN), o'tkazib yuborildi")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                'buyruq_id': buyruq_id,
                'hemis_id': hemis_id,
                'talaba_fio': talaba_fio,
                'xatolik_sababi': "Ma'lumotlar to'liq emas (NaN)"
            })
            continue

        # Qiymatlarni to'g'ri formatga o'tkazish
        try:
            buyruq_id = int(float(buyruq_id)) if isinstance(
                buyruq_id, (int, float)) else int(buyruq_id)
            hemis_id = str(int(float(hemis_id))) if isinstance(
                hemis_id, (int, float)) else str(hemis_id)
        except:
            print(f"\n--- {index+1}/{len(df)} ---")
            print(
                f"  ⚠ Qator {index+1}: Ma'lumotlar formatini o'zgartirib bo'lmadi")
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                'buyruq_id': buyruq_id,
                'hemis_id': hemis_id,
                'talaba_fio': talaba_fio,
                'xatolik_sababi': "Ma'lumotlar formatini o'zgartirib bo'lmadi"
            })
            continue

        print(f"\n--- {index+1}/{len(df)} ---")

        natija, sabab = talabani_buyruqqa_qoshish(
            buyruq_id, hemis_id, talaba_fio, index)

        if natija:
            muvaffaqiyatli += 1
        else:
            muvaffaqiyatsiz += 1
            muvaffaqiyatsiz_talabalar.append({
                'buyruq_id': buyruq_id,
                'hemis_id': hemis_id,
                'talaba_fio': talaba_fio,
                'xatolik_sababi': sabab
            })

        # Har bir amaldan keyin qisqa pauza
        time.sleep(1)

    except Exception as e:
        print(f"\n--- {index+1}/{len(df)} ---")
        print(f"  ✗ Qatorda xatolik: {e}")
        muvaffaqiyatsiz += 1
        muvaffaqiyatsiz_talabalar.append({
            'buyruq_id': row.get(BUYRUK_ID_COLUMN, 'Noma\'lum'),
            'hemis_id': row.get(HEMIS_ID_COLUMN, 'Noma\'lum'),
            'talaba_fio': row.get(TALABA_FIO_COLUMN, 'Noma\'lum'),
            'xatolik_sababi': f"Qator xatoligi: {str(e)}"
        })

# ==================== NATIJALAR ====================
print("\n" + "="*60)
print("JARAYON YAKUNLANDI!")
print("="*60)
print(f"Jami talabalar: {len(df)}")
print(f"✅ Muvaffaqiyatli qo'shilganlar: {muvaffaqiyatli}")
print(f"❌ Muvaffaqiyatsizlar: {muvaffaqiyatsiz}")
print("="*60)

# ==================== MUVaffaqiyatsiz talabalarni Excelga yozish ====================
if muvaffaqiyatsiz_talabalar:
    # Muvaffaqiyatsiz talabalar ro'yxatini DataFrame ga o'tkazish
    df_muvaffaqiyatsiz = pd.DataFrame(muvaffaqiyatsiz_talabalar)

    # Fayl nomini vaqt bilan yaratish
    error_file = f"personal_sheet/qoshilmagan_talabalar.xlsx"

    try:
        df_muvaffaqiyatsiz.to_excel(
            error_file, index=False, sheet_name="Muvaffaqiyatsizlar")
        print(f"\n📄 Muvaffaqiyatsiz talabalar '{error_file}' fayliga yozildi")
        print(f"   Jami {len(df_muvaffaqiyatsiz)} ta talaba muvaffaqiyatsiz")

        # Qisqacha xatoliklar statistikasi
        print("\n📊 Xatoliklar statistikasi:")
        error_stats = df_muvaffaqiyatsiz['xatolik_sababi'].value_counts()
        for error, count in error_stats.items():
            print(f"   - {error}: {count} ta")

    except Exception as e:
        print(f"\n❌ Muvaffaqiyatsiz talabalarni Excelga yozishda xatolik: {e}")
else:
    print("\n✅ Barcha talabalar muvaffaqiyatli qo'shildi!")

# Brauzerni yopish
time.sleep(3)
driver.quit()
print("\nDastur tugadi!")
