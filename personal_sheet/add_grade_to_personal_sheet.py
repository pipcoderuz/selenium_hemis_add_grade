import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    UnexpectedAlertPresentException, InvalidElementStateException,
    StaleElementReferenceException
)
from selenium.webdriver.common.alert import Alert
import time
import re
import unicodedata
from datetime import datetime, date
from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "personal_sheet/personal_sheet_grades.xlsx"
SHEET_NAME = "Imtihonlar"
BASE_URL = "https://hemis.timeedu.uz/performance/ptt-fill"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# options.add_argument("--headless=new")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 30)


# ==================== Nom normalizatsiya ====================
def normalize_name(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip().upper()
    text = text.replace("‘", "'").replace("’", "'").replace("`", "'")
    text = text.replace("O'", "O").replace("G'", "G").replace("Q'", "Q")
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^A-Z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ==================== Muddat sanasini parse qilish ====================
def parse_muddat_date(muddat_text: str):
    """
    Muddat matnidan sanani oladi.
    Misollar: '3.7.2027', '7.8.2025', '03.07.2027'
    """
    if not muddat_text:
        return None
    text = muddat_text.strip()
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if not match:
        return None
    day, month, year = int(match.group(1)), int(
        match.group(2)), int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


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
    submit_button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH,
             "//button[contains(text(), 'Kirish') or @type='submit']")
        )
    )
    submit_button.click()
    print("Kirish bosildi")
except Exception as e:
    print("Kirish tugmasi muammosi:", e)

time.sleep(1)

try:
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    print("Dashboard yuklandi (kirish muvaffaqiyatli)")
except:
    print("Kirishdan keyin sahifa yuklanmadi")
    driver.quit()
    exit()


# ==================== Excel ====================
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)

required_cols = ["student_full_name", "subject_name", "grade"]
for col in required_cols:
    if col not in df.columns:
        print(f"Xato: Excelda '{col}' ustuni yo'q!")
        driver.quit()
        exit()

df["grade"] = pd.to_numeric(df["grade"], errors="coerce").fillna(0)
print(f"Jami {len(df)} ta yozuv topildi.")


# ==================== Select2 talabani tanlash ====================
def select_student_by_name(student_name: str) -> bool:
    try:
        select2 = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#estudentpttsubject-_student + .select2-container")
            )
        )
        select2.click()
        time.sleep(0.6)

        search = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-container--open .select2-search__field")
            )
        )
        search.clear()
        search.send_keys(student_name)
        time.sleep(0.5)

        options = driver.find_elements(
            By.CSS_SELECTOR, ".select2-results__option")
        if not options:
            print(f"  ✗ Select2 natija yo'q: {student_name}")
            return False

        target = normalize_name(student_name)
        best = None

        for opt in options:
            txt = opt.text.strip()
            if not txt or "Talabani tanlang" in txt:
                continue
            if normalize_name(txt) == target:
                best = opt
                break

        if best is None:
            for opt in options:
                txt = opt.text.strip()
                if not txt or "Talabani tanlang" in txt:
                    continue
                if target in normalize_name(txt) or normalize_name(txt) in target:
                    best = opt
                    break

        if best is None:
            for opt in options:
                if opt.text.strip() and "Talabani tanlang" not in opt.text:
                    best = opt
                    break

        if best is None:
            print(f"  ✗ Option topilmadi: {student_name}")
            return False

        print(f"  ✓ Talaba tanlandi: {best.text.strip()}")
        best.click()
        return True

    except Exception as e:
        print(f"  ✗ Select2 xato ({student_name}): {e}")
        return False


# ==================== Jadval yuklanishini kutish ====================
def wait_for_table_with_student(student_name: str, timeout: int = 30) -> bool:
    target = normalize_name(student_name)
    end = time.time() + timeout

    print(f"  → Jadval yuklanishini kutmoqdaman (max {timeout}s)...")

    while time.time() < end:
        try:
            loaders = driver.find_elements(
                By.CSS_SELECTOR,
                ".loading, .kv-grid-loading, .pjax-loading, .overlay, "
                ".spinner, .fa-spinner, [class*='loading']"
            )
            if any(l.is_displayed() for l in loaders):
                time.sleep(0.5)
                continue

            rows = driver.find_elements(
                By.CSS_SELECTOR, "table.table tbody tr")
            if not rows:
                time.sleep(0.5)
                continue

            match_count = 0
            valid_count = 0

            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 6:
                        continue
                    valid_count += 1
                    talaba_text = cells[2].text
                    if target in normalize_name(talaba_text):
                        match_count += 1
                except StaleElementReferenceException:
                    continue

            if valid_count > 0 and match_count == valid_count:
                print(
                    f"  ✓ Jadval tayyor: {valid_count} ta qator, barchasi '{student_name}'")
                return True

            empty = driver.find_elements(
                By.XPATH,
                "//td[contains(@colspan,'') or contains(text(),'topilmadi') or contains(text(),'No results')]"
            )
            if empty and valid_count == 0:
                print(f"  ⚠ Jadval bo'sh (talaba tanlandi, lekin yozuv yo'q)")
                return False

        except Exception:
            pass

        time.sleep(0.6)

    print(
        f"  ✗ Jadval {timeout}s ichida yuklanmadi yoki talaba FIO si chiqmadi")
    return False


# ==================== Talaba + Fan + Muddat tekshirish ====================
def find_and_click_subject(student_name: str, subject_name: str):
    """
    Qaytaradi: (True, None) yoki (False, "xato matni")
    """
    target_student = normalize_name(student_name)
    target_subject = normalize_name(subject_name)
    today = date.today()

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
        if not rows:
            return False, "Jadvalda qator yo'q"

        print(f"  → {len(rows)} ta qator ichidan qidirilmoqda...")

        found_but_expired = False

        for i, row in enumerate(rows, 1):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 13:
                    continue

                # Talaba (indeks 2)
                talaba_raw = cells[2].text.strip()
                talaba_ok = target_student in normalize_name(talaba_raw)

                # Fanlar (indeks 5)
                fan_cell = cells[5]
                links = fan_cell.find_elements(By.TAG_NAME, "a")
                if not links:
                    continue
                fan_link = links[0]
                fan_raw = fan_link.text.strip()
                fan_norm = normalize_name(fan_raw)
                subject_ok = (target_subject in fan_norm) or (
                    fan_norm in target_subject)

                if not (talaba_ok and subject_ok):
                    continue

                # Muddat (indeks 12)
                muddat_raw = cells[12].text.strip()
                muddat_date = parse_muddat_date(muddat_raw)

                print(f"  ✓ Mos qator topildi (#{i})")
                print(f"     Talaba : {talaba_raw}")
                print(f"     Fan    : {fan_raw}")
                print(f"     Muddat : {muddat_raw}")

                if muddat_date is None:
                    print(f"  ⚠ Muddat sanasi o'qilmadi, baribir davom etiladi")
                    fan_link.click()
                    return True, None

                if muddat_date < today:
                    print(f"  ✗ Muddat o'tib ketgan ({muddat_date} < {today})")
                    found_but_expired = True
                    continue

                # Muddat hali o'tmagan
                fan_link.click()
                return True, None

            except StaleElementReferenceException:
                continue
            except Exception:
                continue

        if found_but_expired:
            return False, "Baho kiritish sanasi o'tib ketgan"

        print(f"  ✗ Hech qaysi qator mos kelmadi")
        print(f"     Qidirilgan talaba : {student_name}")
        print(f"     Qidirilgan fan    : {subject_name}")
        return False, "Talaba + Fan birga mos qator topilmadi"

    except Exception as e:
        print(f"  ✗ Qidirish xatosi: {e}")
        return False, f"Qidirish xatosi: {e}"


# ==================== Baho kiritish ====================
def enter_grade(grade_value: float) -> bool:
    try:
        grade_input = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR,
                 "input.form-control.acr[name*='total_point']")
            )
        )

        if grade_input.get_attribute("disabled") or grade_input.get_attribute("readonly"):
            print("  ⚠ Baho maydoni bloklangan")
            return False

        current = grade_input.get_attribute("value") or "0"
        try:
            if abs(float(current) - float(grade_value)) < 0.01:
                print(f"  → Baho allaqachon {grade_value}")
                return True
        except:
            pass

        grade_input.clear()
        time.sleep(0.25)
        grade_input.send_keys(str(grade_value))
        print(f"  ✓ Baho kiritildi: {grade_value}")

        try:
            save_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR,
                     "button[type='submit'].btn.btn-primary, button.btn-success")
                )
            )
            save_btn.click()
            print("  ✓ Saqlash bosildi")

            try:
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert = Alert(driver)
                print(f"  Alert: {alert.text}")
                alert.accept()
            except TimeoutException:
                pass

        except (NoSuchElementException, TimeoutException):
            print("  ⚠ Saqlash tugmasi topilmadi")

        return True

    except Exception as e:
        print(f"  ✗ Baho kiritish xato: {e}")
        return False


# ==================== Asosiy jarayon ====================
print("\n=== PTT Fill sahifasiga o'tyapman ===")
driver.get(BASE_URL)

results = []

# Jadval yuklanmagan talabalar (qayta qidirilmasin)
failed_students = set()  # normalize_name(student_name)

for idx, row in df.iterrows():
    student_name = str(row["student_full_name"]).strip()
    subject_name = str(row["subject_name"]).strip()
    grade = float(row["grade"])
    student_key = normalize_name(student_name)

    print(f"\n[{idx+1}/{len(df)}] {student_name} | {subject_name} → {grade}")

    record = {
        "student_full_name": student_name,
        "subject_name": subject_name,
        "grade": grade,
        "status": "",
        "error": ""
    }

    # Agar bu talaba avval jadval yuklanmagan bo'lsa — qayta izlamaymiz
    if student_key in failed_students:
        print(f"  ⏭ Bu talaba uchun jadval avval yuklanmagan → o'tkazib yuborildi")
        record["status"] = "Xato"
        record["error"] = "Jadval yuklanmadi yoki talaba FIO si chiqmadi"
        results.append(record)
        continue

    # Har safar toza sahifa
    driver.get(BASE_URL)

    # 1. Talabani tanlash
    if not select_student_by_name(student_name):
        record["status"] = "Xato"
        record["error"] = "Talaba Select2 dan topilmadi"
        results.append(record)
        # Select2 dan topilmasa ham keyingi fanlari uchun qayta urinish mumkin,
        # shuning uchun failed_students ga qo'shmaymiz
        continue

    # 2. Jadval yuklanishini kutish
    if not wait_for_table_with_student(student_name, timeout=30):
        print(
            f"  ✗ Jadval yuklanmadi → shu talabaning qolgan fanlari ham o'tkazib yuboriladi")
        failed_students.add(student_key)
        record["status"] = "Xato"
        record["error"] = "Jadval yuklanmadi yoki talaba FIO si chiqmadi"
        results.append(record)
        continue

    # 3. Talaba + Fan + Muddat tekshirish va bosish
    ok, err_msg = find_and_click_subject(student_name, subject_name)
    if not ok:
        record["status"] = "Xato"
        record["error"] = err_msg
        results.append(record)
        continue

    time.sleep(1.5)

    # 4. Bahoni kiritish
    if not enter_grade(grade):
        record["status"] = "Xato"
        record["error"] = "Baho kiritilmadi yoki bloklangan"
        results.append(record)
        continue

    # Muvaffaqiyatli
    record["status"] = "Muvaffaqiyatli"
    record["error"] = ""
    results.append(record)
    print("  ✅ Muvaffaqiyatli saqlandi")

    time.sleep(0.5)


# ==================== Natija ====================
print("\n" + "=" * 60)
results_df = pd.DataFrame(results)

success_count = (results_df["status"] == "Muvaffaqiyatli").sum()
fail_count = (results_df["status"] == "Xato").sum()

print(f"Jami: {len(results_df)}")
print(f"✅ Muvaffaqiyatli: {success_count}")
print(f"❌ Xato: {fail_count}")
print("=" * 60)

out_file = "personal_sheet/not_found_personal_sheet_grades.xlsx"
results_df.to_excel(out_file, index=False)
print(f"\n📁 Barcha natijalar '{out_file}' fayliga saqlandi")
print("   (status: Muvaffaqiyatli / Xato)")

print("\n✅ Jarayon tugadi.")
driver.quit()
