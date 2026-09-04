import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
from config import BILLING_LOGIN_VALUE, BILLING_PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "billing/create_billing_contracts.xlsx"
SHEET_NAME = "talabalar"

COL_HEMIS_ID = "hemis_id"
COL_FIO = "fio"
COL_TIL = "talim_tili"
COL_TEL = "tel_raqam"
COL_SUMMA = "shartnoma_summasi"
COL_SHOT = "shot_raqami"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)
wait = WebDriverWait(driver, 10)
short_wait = WebDriverWait(driver, 2)  # qisqa kutish

natijalar = []
muvaffaqiyatsizlar = []


# ==================== LOGIN ====================
def login():
    print("Billing login sahifasiga o'tyapman...")
    driver.get("https://billing.e-edu.uz/login")
    time.sleep(1.5)

    try:
        oneid_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href, 'oneIdAdmin')]"))
        )
        oneid_button.click()
        print("OneID tugmasi bosildi")
    except Exception as e:
        print("OneID tugmasi topilmadi:", e)
        return False

    try:
        wait.until(EC.presence_of_element_located((By.NAME, "login")))
    except:
        print("OneID login maydoni topilmadi")
        return False

    driver.find_element(By.NAME, "login").clear()
    driver.find_element(By.NAME, "login").send_keys(BILLING_LOGIN_VALUE)
    driver.find_element(By.NAME, "password").clear()
    driver.find_element(By.NAME, "password").send_keys(BILLING_PASSWORD_VALUE)

    try:
        submit_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Kirish') or @type='submit']"))
        )
        submit_button.click()
        print("Kirish bosildi")
    except Exception as e:
        print("Kirish tugmasi muammosi:", e)
        return False

    time.sleep(1.5)
    print("Login muvaffaqiyatli")
    return True


# ==================== EXCEL ====================
def excel_oquvchi():
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
        print(f"Excel fayldan {len(df)} ta talaba o'qildi")

        required = [COL_HEMIS_ID, COL_FIO,
                    COL_TIL, COL_TEL, COL_SUMMA, COL_SHOT]
        for col in required:
            if col not in df.columns:
                print(f"Xatolik: Excelda '{col}' ustuni topilmadi!")
                return None

        df = df[df[COL_HEMIS_ID].notna()]
        df[COL_HEMIS_ID] = df[COL_HEMIS_ID].astype(str).str.strip()
        df = df[df[COL_HEMIS_ID] != ""]
        return df
    except Exception as e:
        print(f"Excel faylni o'qishda xatolik: {e}")
        return None


# ==================== YORDAMCHI ====================
def safe_click(element):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.15)
        driver.execute_script("arguments[0].click();", element)
        return True
    except:
        try:
            element.click()
            return True
        except:
            return False


def select_ant_option(select_id, option_text, partial=False, retries=2):
    """Ant Design select — yozib tanlash"""
    for attempt in range(1, retries + 1):
        try:
            inp = wait.until(
                EC.presence_of_element_located((By.ID, select_id)))
            parent = inp.find_element(
                By.XPATH, "./ancestor::div[contains(@class,'ant-select')][1]")

            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", parent)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", parent)
            time.sleep(0.2)

            try:
                inp.clear()
            except:
                pass

            driver.execute_script("""
                arguments[0].focus();
                arguments[0].value = '';
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            """, inp)
            time.sleep(0.15)

            inp.send_keys(option_text)
            time.sleep(0.15)

            if partial:
                xpath = f"//div[contains(@class,'ant-select-item-option') and contains(@title, '{option_text}')]"
            else:
                xpath = f"//div[contains(@class,'ant-select-item-option') and (contains(@title, '{option_text}') or contains(., '{option_text}'))]"

            try:
                option = wait.until(
                    EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].click();", option)
                time.sleep(0.1)
                return True
            except:
                inp.send_keys(Keys.ENTER)
                time.sleep(0.2)
                return True

        except Exception as e:
            print(
                f"    [{attempt}] Select xatoligi ({select_id} → {option_text}): {str(e)[:80]}")
            try:
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except:
                pass
            time.sleep(0.15)

    return False


# ==================== ASOSIY ISHLOV ====================
def talaba_qayta_ishlash(row, index, total):
    hemis_id = str(row[COL_HEMIS_ID]).strip()
    fio = str(row[COL_FIO]).strip() if pd.notna(row[COL_FIO]) else ""
    til = str(row[COL_TIL]).strip() if pd.notna(
        row[COL_TIL]) else "O'zbek tili"
    tel = str(row[COL_TEL]).strip().replace(" ", "").replace(
        "+998", "").replace("-", "") if pd.notna(row[COL_TEL]) else ""
    summa = str(row[COL_SUMMA]).replace(" ", "").replace(
        ",", "") if pd.notna(row[COL_SUMMA]) else ""
    shot = str(row[COL_SHOT]).strip() if pd.notna(row[COL_SHOT]) else ""

    print(f"\n{'='*50}")
    print(f"📌 {index+1}/{total} | {hemis_id} | {fio}")
    print(f"{'='*50}")

    try:
        # ---------- 1. HEMIS STUDENT ----------
        driver.get("https://billing.e-edu.uz/financial-activity/hemis_student")
        time.sleep(0.5)

        search = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Qidirish']")))
        search.clear()
        search.send_keys(hemis_id)
        search.send_keys(Keys.ENTER)
        time.sleep(0.5)

        # Telefon
        try:
            phone_inputs = driver.find_elements(
                By.CSS_SELECTOR, "input.input-mask, input[placeholder*='998']")
            for inp in phone_inputs:
                val = inp.get_attribute("value") or ""
                if not val.strip() or val.strip() in ["+998 (__) ___-__-__", ""]:
                    safe_click(inp)
                    time.sleep(0.2)
                    inp.send_keys(Keys.CONTROL + "a")
                    inp.send_keys(Keys.DELETE)
                    time.sleep(0.15)
                    inp.send_keys(tel)
                    time.sleep(0.3)
                    print(f"  ✅ Telefon yozildi: {tel}")
                    break
        except Exception as e:
            print(f"  ⚠ Telefon maydoni: {e}")

        # Ariza shakllantirish — qisqa kutish (max 2 soniya)
        try:
            ariza_btn = short_wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Ariza shakllantirish']]")))
            safe_click(ariza_btn)
            print("  ✅ 'Ariza shakllantirish' bosildi")
            time.sleep(0.5)
        except:
            print("  ⚠ 'Ariza shakllantirish' topilmadi → keyingi sahifaga o'tiladi")

        # ---------- 2. HIGH-COURSE-APPLICATIONS ----------
        driver.get(
            "https://billing.e-edu.uz/financial-activity/high-course-applications?academicYear=4")
        time.sleep(0.5)

        search2 = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Qidirish']")))
        search2.clear()
        search2.send_keys(hemis_id)
        search2.send_keys(Keys.ENTER)
        time.sleep(0.8)

        # Eye tugmasi
        try:
            eye_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[@aria-label='eye'] or .//span[contains(@class,'anticon-eye')]]")))
            safe_click(eye_btn)
            print("  ✅ 'Ko'rish' (eye) bosildi")
            time.sleep(0.5)
        except:
            print("  ✗ Eye tugmasi topilmadi → Ariza shakllantirilmagan")
            return False, "Ariza shakllantirilmagan"

        # ---------- HOLATINI TEKSHIRISH ----------
        try:
            holat_elements = driver.find_elements(
                By.XPATH,
                "//th[contains(., 'Holati')]/following-sibling::td//span[contains(@class, 'ant-tag')]"
            )
            if not holat_elements:
                holat_elements = driver.find_elements(
                    By.XPATH,
                    "//span[contains(@class, 'ant-tag') and (contains(text(), 'Tasdiqlangan') or contains(text(), 'Yangi'))]"
                )

            holat_text = ""
            if holat_elements:
                holat_text = holat_elements[0].text.strip()
                print(f"  ℹ️ Holati: {holat_text}")

            if "Tasdiqlangan" in holat_text:
                print("  ⚠ Shartnoma allaqachon yaratilgan")
                return False, "Shartnoma allaqachon yaratilgan"

        except Exception as e:
            print(f"  ⚠ Holatini o'qishda xatolik: {e} → davom etiladi")

        # ---------- 3. FORMA TO'LDIRISH ----------
        if not select_ant_option("CreateContractWithoutAppForm_typeCode", "ikki tomonlama"):
            return False, "TypeCode (ikki tomonlama) tanlanmadi"
        print("  ✅ Type: ikki tomonlama")

        if not select_ant_option("CreateContractWithoutAppForm_eduContractTypeId", "Bazoviy shartnoma"):
            return False, "Bazoviy shartnoma tanlanmadi"
        print("  ✅ Edu type: Bazoviy shartnoma")

        # Til
        til_map = {
            "o'zbek": "O'zbek tili", "ozbek": "O'zbek tili", "uzbek": "O'zbek tili",
            "rus": "Rus tili", "russian": "Rus tili",
        }
        til_lower = til.lower().replace("'", "").replace("‘", "").replace("’", "")
        selected_til = "O'zbek tili"
        for k, v in til_map.items():
            if k in til_lower:
                selected_til = v
                break

        if not select_ant_option("CreateContractWithoutAppForm_languageId", selected_til):
            return False, f"Til tanlanmadi: {selected_til}"
        print(f"  ✅ Til: {selected_til}")

        if not select_ant_option("CreateContractWithoutAppForm_contractTemplateId", "2026-2027", partial=True):
            return False, "2026-2027 shablon topilmadi"
        print("  ✅ Shablon: 2026-2027...")

        if not select_ant_option("CreateContractWithoutAppForm_checkingAccountId", shot, partial=True):
            return False, f"Shot raqami topilmadi: {shot}"
        print(f"  ✅ Shot: {shot}...")

        # Summa
        try:
            sum_input = wait.until(EC.presence_of_element_located(
                (By.ID, "CreateContractWithoutAppForm_originalContractSum")))
            sum_input.click()
            time.sleep(0.15)
            sum_input.send_keys(Keys.CONTROL + "a")
            sum_input.send_keys(Keys.DELETE)
            sum_input.send_keys(summa)
            time.sleep(0.2)
            print(f"  ✅ Summa: {summa}")
        except Exception as e:
            return False, f"Summa yozilmadi: {e}"

        # Tasdiqlash
        try:
            confirm_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Tasdiqlash'] and contains(@style,'rgb(23, 198, 83)')]")))
            safe_click(confirm_btn)
            print("  ✅ 'Tasdiqlash' bosildi")
            time.sleep(0.5)
        except Exception as e:
            try:
                confirm_btn = driver.find_element(
                    By.XPATH, "//button[contains(@style,'background: rgb(23, 198, 83)')]//span[text()='Tasdiqlash']/..")
                safe_click(confirm_btn)
                print("  ✅ 'Tasdiqlash' bosildi (alt)")
                time.sleep(0.5)
            except:
                return False, f"Tasdiqlash tugmasi topilmadi: {e}"

        return True, "Muvaffaqiyatli"

    except Exception as e:
        return False, f"Umumiy xatolik: {str(e)[:120]}"


# ==================== MAIN ====================
def main():
    print("\n" + "=" * 60)
    print("🏛️  BILLING SHARTNOMA YARATISH BOTI")
    print("=" * 60)

    if not login():
        print("Login muvaffaqiyatsiz!")
        driver.quit()
        return

    df = excel_oquvchi()
    if df is None or df.empty:
        print("Excelda ma'lumot topilmadi!")
        driver.quit()
        return

    total = len(df)
    print(f"\n📊 Jami {total} ta talaba\n")

    muvaffaqiyatli = 0

    for idx, row in df.iterrows():
        ok, sabab = talaba_qayta_ishlash(row, idx, total)

        if ok:
            muvaffaqiyatli += 1
            natijalar.append({
                "hemis_id": str(row[COL_HEMIS_ID]),
                "fio": str(row[COL_FIO]) if pd.notna(row[COL_FIO]) else "",
                "holat": "Muvaffaqiyatli"
            })
            print("  ✅ Muvaffaqiyatli")
        else:
            muvaffaqiyatsizlar.append({
                "hemis_id": str(row[COL_HEMIS_ID]),
                "fio": str(row[COL_FIO]) if pd.notna(row[COL_FIO]) else "",
                "xatolik_sababi": sabab
            })
            print(f"  ❌ {sabab}")

        time.sleep(0.4)

    print("\n" + "=" * 60)
    print("📊 JARAYON YAKUNLANDI!")
    print("=" * 60)
    print(f"📌 Jami:           {total}")
    print(f"✅ Muvaffaqiyatli: {muvaffaqiyatli}")
    print(f"❌ Muvaffaqiyatsiz: {len(muvaffaqiyatsizlar)}")
    print("=" * 60)

    try:
        with pd.ExcelWriter("billing/shartnoma_yaratish_natijalari.xlsx", engine="openpyxl") as writer:
            if natijalar:
                pd.DataFrame(natijalar).to_excel(
                    writer, index=False, sheet_name="Muvaffaqiyatli")
            if muvaffaqiyatsizlar:
                pd.DataFrame(muvaffaqiyatsizlar).to_excel(
                    writer, index=False, sheet_name="Xatoliklar")

            all_data = natijalar + [
                {"hemis_id": x["hemis_id"], "fio": x["fio"],
                    "holat": x["xatolik_sababi"]}
                for x in muvaffaqiyatsizlar
            ]
            if all_data:
                pd.DataFrame(all_data).to_excel(
                    writer, index=False, sheet_name="Barcha")

        print("\n📄 Natijalar saqlandi → shartnoma_yaratish_natijalari.xlsx")
    except Exception as e:
        print(f"Excelga yozishda xatolik: {e}")

    time.sleep(1)
    driver.quit()
    print("\n✅ Dastur tugadi!")


if __name__ == "__main__":
    main()
