import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.alert import Alert
import time
from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== O'ZGARUVCHILAR ====================
EXCEL_FILE = "exam_report.xlsx"
SHEET_NAME = "Sheet1"

# Chrome sozlamalari
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# options.add_argument("--headless=new")  # yangi headless rejim (agar kerak bo'lsa)
driver = webdriver.Chrome(options=options)

# ==================== LOGIN QISMI (o'zgarmadi) ====================
print("Login sahifasiga o'tyapman...")
driver.get("https://hemis.timeedu.uz/")

try:
    oneid_button = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/auth/edu-id') or contains(text(), 'OneID')]"))
    )
    oneid_button.click()
    print("OneID tugmasi bosildi")
except Exception as e:
    print("OneID tugmasi topilmadi:", e)
    driver.quit()
    exit()

try:
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "login")))
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
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Kirish') or @type='submit']"))
    )
    submit_button.click()
    print("Kirish bosildi")
except Exception as e:
    print("Kirish tugmasi muammosi:", e)

time.sleep(3)

try:
    WebDriverWait(driver, 25).until( EC.presence_of_element_located((By.TAG_NAME, "body")))
    print("Dashboard yuklandi (kirish muvaffaqiyatli)")
except:
    print("Kirishdan keyin sahifa yuklanmadi")
    driver.quit()
    exit()

# ==================== Excel o'qish ====================
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
# barcha NaN qiymatlarni 0 bilan almashtiradi
df['grade'] = pd.to_numeric(df['grade'], errors='coerce').fillna(0).astype(int)

# exam_type_code ni tekshirish uchun (har bir exam uchun bir xil deb faraz qilamiz)
# Agar har bir exam_id ichida turli bo'lsa, group ichida ham tekshirish mumkin
exam_types = df.groupby('exam_id')['exam_type_code'].first().to_dict()

grouped = df.groupby('exam_id')
print(f"Jami {len(grouped)} ta exam topildi.")

# ==================== Har bir exam uchun ishlash ====================
print(str(grouped))
for exam_id, group in grouped:
    exam_type_code = exam_types.get(exam_id, None)
    print(f"\n=== Exam ID: {exam_id} | Type: {exam_type_code} | Talabalar: {len(group)} ===")

    if exam_type_code == 13:
        url = f"https://hemis.timeedu.uz/teacher/check-overall-rating?id={exam_id}"
        input_suffix = "[13]"
        is_final = True
    elif exam_type_code == 12:
        url = f"https://hemis.timeedu.uz/teacher/check-rating?id={exam_id}"
        # yoki "[12]" agar bo'lsa, lekin oldingi kodda bo'sh edi
        input_suffix = ""
        is_final = False
    else:
        print(f"  → Noma'lum exam_type_code ({exam_type_code}), o'tkazib yuborildi")
        continue

    driver.get(url)
    time.sleep(2.5)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='number'].form-control"))
        )
    except TimeoutException:
        print("  Sahifada baho inputlari topilmadi → o'tkazib yuborildi")
        continue

    updated = 0
    for _, row in group.iterrows():
        student_id = str(row['student_id'])
        grade = str(row['grade'])

        input_name = f"student_id[{student_id}]{input_suffix}"

        try:
            selector = f"input[name='student_id\\[{student_id}\\]{input_suffix}']"
            input_field = driver.find_element(By.CSS_SELECTOR, selector)

            current_val = input_field.get_attribute("value") or ""
            # Yangi baho bilan solishtirish
            if current_val == grade:
                print(f"  {row.get('student_full_name', '—')} ({student_id}) → bir xil ({grade}), o'zgartirish yo'q")
                continue

            # Farq bo'lsa yoki bo'sh bo'lsa → yangilash
            input_field.clear()
            input_field.send_keys(grade)
            updated += 1
            print(f"  {row.get('student_full_name', '—')} ({student_id}) → {grade} kiritildi")
        except NoSuchElementException:
            print(f"  Input topilmadi → {input_name}")

    if updated > 0:
        try:
            save_btn = driver.find_element(
                By.CSS_SELECTOR,"button[type='submit'].btn.btn-primary[name='btn']"
            )
            save_btn.click()
            print(f"Saqlash bosildi ({updated} ta yangilandi)")

            # Yakuniy nazorat uchun alertni qabul qilish
            if is_final:
                try:
                    WebDriverWait(driver, 6).until(EC.alert_is_present())
                    alert = Alert(driver)
                    alert_text = alert.text
                    print(f"  Alert chiqdi: {alert_text}")
                    # alert.dismiss()
                    # print("  Alert qabul qilinmadi (dismiss)")
                    alert.accept()          # "OK" / "Ha" / "Saqlash" ni tasdiqlash
                    print("  Alert qabul qilindi (accept)")
                    time.sleep(1.5)
                except TimeoutException:
                    print("  Alert chiqmadi (ehtimol bu safar yo'q)")
                except Exception as e:
                    print("  Alert bilan muammo:", e)

            time.sleep(2.5)
        except Exception as e:
            print("Saqlash tugmasi topilmadi yoki bosib bo'lmadi:", e)
    else:
        print("Yangilanish yo'q")

    time.sleep(1.8)

print("\nBarcha examlar tugadi.")
driver.quit()
