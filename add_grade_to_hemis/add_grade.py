import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, UnexpectedAlertPresentException, InvalidElementStateException
from selenium.webdriver.common.alert import Alert
import time
from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== O'ZGARUVCHILAR ====================
EXCEL_FILE = "add_grade_to_hemis/exam_report.xlsx"
SHEET_NAME = "Imtihonlar"

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
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
# barcha NaN qiymatlarni 0 bilan almashtiradi
df['grade'] = pd.to_numeric(df['grade'], errors='coerce').fillna(0).astype(int)

# exam_type_code ni tekshirish uchun (har bir exam uchun bir xil deb faraz qilamiz)
exam_types = df.groupby('exam_id')['exam_type_code'].first().to_dict()

grouped = df.groupby('exam_id')
print(f"Jami {len(grouped)} ta exam topildi.")

# ==================== Har bir exam uchun ishlash ====================
print(str(grouped))
not_found_inputs = []
skipped_exams = []  # Skip qilingan examlarni hisobga olish uchun

for exam_id, group in grouped:
    exam_type_code = exam_types.get(exam_id, None)
    print(
        f"\n=== Exam ID: {exam_id} | Type: {exam_type_code} | Talabalar: {len(group)} ===")

    if exam_type_code == 13:
        url = f"https://hemis.timeedu.uz/teacher/check-overall-rating?id={exam_id}"
        input_suffix = "[13]"
        is_final = True
    elif exam_type_code == 14:
        url = f"https://hemis.timeedu.uz/teacher/check-overall?id={exam_id}"
        input_suffix = ""
        is_final = True
    elif exam_type_code == 12 or exam_type_code == 17 or exam_type_code == 18:
        url = f"https://hemis.timeedu.uz/teacher/check-rating?id={exam_id}"
        input_suffix = ""
        is_final = False
    else:
        print(
            f"  → Noma'lum exam_type_code ({exam_type_code}), o'tkazib yuborildi")
        continue

    driver.get(url)
    time.sleep(1)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='number'].form-control"))
        )
    except TimeoutException:
        print("  Sahifada baho inputlari topilmadi → o'tkazib yuborildi")
        continue

    updated = 0
    exam_has_interactivity_issue = False  # Bu examda interaktivlik muammosi bormi?

    for _, row in group.iterrows():
        student_id = str(row['student_id'])
        grade = str(row['grade'])

        input_name = f"student_id[{student_id}]{input_suffix}"

        try:
            selector = f"input[name='student_id\\[{student_id}\\]{input_suffix}']"
            input_field = driver.find_element(By.CSS_SELECTOR, selector)

            # Input maydonini interaktivligini tekshirish
            is_disabled = input_field.get_attribute(
                "disabled") == "true" or input_field.get_attribute("readonly") == "true"

            if is_disabled and exam_type_code == 13:
                print(
                    f"  ⚠ Exam ID {exam_id} (type 13) uchun baholar allaqachon qo'yilgan va o'zgartirib bo'lmaydi!")
                print(f"  → Butun exam o'tkazib yuboriladi (skip)")
                exam_has_interactivity_issue = True
                break  # Butun examni skip qilamiz

            current_val = input_field.get_attribute("value") or ""
            # Yangi baho bilan solishtirish
            if current_val == grade:
                print(
                    f"  {row.get('student_full_name', '—')} ({student_id}) → bir xil ({grade}), o'zgartirish yo'q")
                continue

            # Farq bo'lsa yoki bo'sh bo'lsa → yangilash
            input_field.clear()
            input_field.send_keys(grade)
            updated += 1
            print(
                f"  {row.get('student_full_name', '—')} ({student_id}) → {grade} kiritildi")

        except InvalidElementStateException as e:
            print(
                f"  ✗ {row.get('student_full_name', '—')} ({student_id}) → Interaktiv emas (ehtimol bloklangan): {grade}")
            if exam_type_code == 13:
                print(
                    f"  → Exam ID {exam_id} (type 13) uchun baholar bloklangan, butun exam skip qilinadi")
                exam_has_interactivity_issue = True
                break
            else:
                not_found_inputs.append({
                    "student_id": student_id,
                    "student_hemis_id": str(row['student_hemis_id']),
                    "student_full_name": str(row['student_full_name']),
                    "group_name": str(row['group_name']),
                    "subject_name": str(row['subject_name']),
                    "grade": grade,
                    "error": str(e)
                })

        except NoSuchElementException:
            print(
                f"  {row.get('student_full_name', '—')} ({student_id}) → {grade} kiritilmadi (element topilmadi)")
            not_found_inputs.append({
                "student_id": student_id,
                "student_hemis_id": str(row['student_hemis_id']),
                "student_full_name": str(row['student_full_name']),
                "group_name": str(row['group_name']),
                "subject_name": str(row['subject_name']),
                "grade": grade,
                "error": "Element not found"
            })

    # Agar interaktivlik muammosi bo'lsa, saqlashni o'tkazib yuboramiz
    if exam_has_interactivity_issue:
        skipped_exams.append({
            "exam_id": exam_id,
            "exam_type_code": exam_type_code,
            "reason": "Baholar allaqachon qo'yilgan va bloklangan (type 13 final exam)"
        })
        print(f"  → Exam {exam_id} skip qilindi (baholar bloklangan)")
        continue  # Keyingi examga o'tamiz

    if updated > 0:
        try:
            save_btn = driver.find_element(
                By.CSS_SELECTOR, "button[type='submit'].btn.btn-primary[name='btn']"
            )
            save_btn.click()
            print(f"✓ Saqlash bosildi ({updated} ta yangilandi)")
            time.sleep(1)

            # Yakuniy nazorat uchun alertni qabul qilish
            if is_final:
                try:
                    WebDriverWait(driver, 6).until(EC.alert_is_present())
                    alert = Alert(driver)
                    alert_text = alert.text
                    print(f"  Alert chiqdi: {alert_text}")
                    alert.accept()
                    print("  Alert qabul qilindi (accept)")
                    time.sleep(1)
                except TimeoutException:
                    print("  Alert chiqmadi (ehtimol bu safar yo'q)")
                except Exception as e:
                    print("  Alert bilan muammo:", e)

            time.sleep(1)
        except Exception as e:
            print("✗ Saqlash tugmasi topilmadi yoki bosib bo'lmadi:", e)
    else:
        print("  Yangilanish yo'q")

    time.sleep(1)

# Topilmaganlarni Excel ga saqlash
if len(not_found_inputs) > 0:
    print("="*60)
    print(f"📁 HEMISDA Topilmagan talabalar 'add_grade_to_hemis/not_found_students.xlsx' fayliga saqlandi")
    print("="*60)
    not_found_df = pd.DataFrame(not_found_inputs)
    not_found_df.to_excel("add_grade_to_hemis/not_found_students.xlsx", index=False)

# Skip qilingan examlar haqida hisobot
if len(skipped_exams) > 0:
    print("\n" + "="*60)
    print("⚠ SKIP QILINGAN EXAM LAR (baholar bloklangan):")
    print("="*60)
    skipped_df = pd.DataFrame(skipped_exams)
    print(skipped_df.to_string(index=False))
    skipped_df.to_excel("add_grade_to_hemis/skipped_exams.xlsx", index=False)
    print(f"\n📁 Skip qilingan examlar 'add_grade_to_hemis/skipped_exams.xlsx' fayliga saqlandi")

print("\n✅ Barcha examlar tugadi.")
driver.quit()
