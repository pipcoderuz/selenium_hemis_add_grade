import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime
from config import BILLING_LOGIN_VALUE, BILLING_PASSWORD_VALUE


# ==================== O'ZGARUVCHILAR ====================
EXCEL_FILE = "billing/rejected_contracts.xlsx"
SHEET_NAME = "shartnomalar"
CONTRACT_COLUMN = "shartnoma_raqami"

# Chrome sozlamalari
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)

# Natijalarni saqlash
natijalar = []
muvaffaqiyatsizlar = []


# ==================== LOGIN ====================
def login():
    """Billing tizimiga OneID orqali kirish"""
    print("Billing login sahifasiga o'tyapman...")
    driver.get("https://billing.e-edu.uz/login")
    time.sleep(2)

    try:
        oneid_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href, 'oneIdAdmin')]"))
        )
        oneid_button.click()
        print("OneID tugmasi bosildi")
    except Exception as e:
        print("OneID tugmasi topilmadi:", e)
        return False

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "login")))
        print("OneID forma yuklandi")
    except:
        print("OneID login maydoni topilmadi")
        return False

    driver.find_element(By.NAME, "login").clear()
    driver.find_element(By.NAME, "login").send_keys(BILLING_LOGIN_VALUE)
    driver.find_element(By.NAME, "password").clear()
    driver.find_element(By.NAME, "password").send_keys(BILLING_PASSWORD_VALUE)

    try:
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Kirish') or @type='submit']"))
        )
        submit_button.click()
        print("Kirish bosildi")
    except Exception as e:
        print("Kirish tugmasi muammosi:", e)
        return False

    time.sleep(3)

    try:
        driver.get(
            "https://billing.e-edu.uz/financial-activity/contracts?academicYearId=3")
        time.sleep(2)
        print("Shartnomalar sahifasiga o'tildi")
        return True
    except Exception as e:
        print(f"Shartnomalar sahifasiga o'tishda xatolik: {e}")
        return False


# ==================== EXCEL O'QISH ====================
def excel_oquvchi():
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
        print(f"Excel fayldan {len(df)} ta shartnoma raqami o'qildi")

        if CONTRACT_COLUMN not in df.columns:
            print(f"Xatolik: Excelda '{CONTRACT_COLUMN}' ustuni topilmadi!")
            return None

        # Bo'sh qiymatlarni olib tashlash
        df = df[df[CONTRACT_COLUMN].notna()]
        df[CONTRACT_COLUMN] = df[CONTRACT_COLUMN].astype(str).str.strip()
        df = df[df[CONTRACT_COLUMN] != '']

        return df
    except Exception as e:
        print(f"Excel faylni o'qishda xatolik: {e}")
        return None


# ==================== SHARTNOMANI QAYTA ISHLASH ====================
def shartnoma_qayta_ishlash(contract_number, row_index, total_count):
    """Bitta shartnomani qayta ishlash"""
    try:
        print(f"\n{'='*40}")
        print(f"📌 {row_index+1}/{total_count} - {contract_number}")
        print(f"{'='*40}")

        # Qidiruv
        try:
            search_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//input[@placeholder='Qidirish']"))
            )
            search_input.clear()
            search_input.send_keys(contract_number)
            search_input.send_keys(Keys.ENTER)
            time.sleep(1.5)
        except Exception as e:
            print(f"  ✗ Qidiruv xatoligi: {e}")
            return False, "Qidiruv xatoligi"

        # Ma'lumotlarni olish
        try:
            rows = driver.find_elements(
                By.XPATH, "//table//tbody/tr[@data-row-key]")
            rows = [
                row for row in rows if 'ant-table-measure-row' not in row.get_attribute('class')]

            if not rows:
                print(f"  ✗ Ma'lumot topilmadi")
                return False, "Ma'lumot topilmadi"

            found = False
            for tr in rows:
                try:
                    td = tr.find_elements(By.XPATH, ".//td")
                    if len(td) >= 15:
                        contract_text = td[9].text.strip()
                        if contract_number == contract_text:
                            natijalar.append({
                                'shartnoma_raqami': contract_number,
                                'fio': td[1].text.strip(),
                                'summa': td[11].text.strip(),
                                'chegirma': td[12].text.strip(),
                                'holati': td[13].text.strip()
                            })
                            found = True
                            print(f"  ✅ Shartnoma topildi")
                            break
                except:
                    continue

            if not found:
                return False, "Shartnoma topilmadi"

        except Exception as e:
            return False, f"Jadval xatoligi: {e}"

        # "Ko'rish" tugmasi
        try:
            eye_button = driver.find_element(
                By.XPATH, "//span[@role='img' and contains(@class, 'anticon-eye')]/ancestor::button"
            )
            driver.execute_script("arguments[0].click();", eye_button)
            time.sleep(1.5)

            handles = driver.window_handles
            if len(handles) > 1:
                driver.switch_to.window(handles[-1])
                time.sleep(1)
        except Exception as e:
            return False, f"'Ko'rish' tugmasi xatoligi: {e}"

        # "Rad qilish" tugmasi (tez usul)
        rad_bosildi = False
        try:
            # To'g'ridan-to'g'ri span orqali
            rad_button = driver.find_element(
                By.XPATH, "//button[.//span[text()='Rad qilish'] and contains(@style, 'rgb(255, 77, 79)')]"
            )
            driver.execute_script("arguments[0].click();", rad_button)
            rad_bosildi = True
            print(f"  ✅ 'Rad qilish' bosildi")
        except:
            try:
                # Alternativ
                rad_button = driver.find_element(
                    By.XPATH, "//div[contains(@class, 'ant-card-extra')]//button[contains(text(), 'Rad qilish')]"
                )
                driver.execute_script("arguments[0].click();", rad_button)
                rad_bosildi = True
                print(f"  ✅ 'Rad qilish' bosildi")
            except:
                pass

        if not rad_bosildi:
            # Yangi oynani yopish va asosiyga qaytish
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            print(f"  ✗ 'Rad qilish' topilmadi, o'tkazib yuborildi")
            return False, "'Rad qilish' topilmadi"

        time.sleep(1)

        # Modal matn va tugma
        try:
            textarea = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "basic_message"))
            )
            textarea.send_keys("Kursdan kursga uchun")
            time.sleep(0.5)

            # Modal "Rad qilish" tugmasi
            modal_bosildi = False
            try:
                modal_btn = driver.find_element(
                    By.XPATH, "//div[contains(@class, 'ant-modal-footer')]//button[.//span[text()='Rad qilish']]"
                )
                driver.execute_script("arguments[0].click();", modal_btn)
                modal_bosildi = True
            except:
                try:
                    modal_btn = driver.find_element(
                        By.XPATH, "//button[contains(@class, 'ant-btn-primary') and contains(text(), 'Rad qilish')]"
                    )
                    driver.execute_script("arguments[0].click();", modal_btn)
                    modal_bosildi = True
                except:
                    pass

            if not modal_bosildi:
                print(f"  ✗ Modal tugma topilmadi")
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                return False, "Modal tugma topilmadi"

            print(f"  ✅ Modal bosildi")
            time.sleep(2)

        except Exception as e:
            print(f"  ✗ Modal xatoligi: {e}")
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            return False, f"Modal xatoligi: {e}"

        # Yangi oynani yopish va asosiyga qaytish
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            # Sahifani yangilamasdan qidiruvni tozalash
            search_input = driver.find_element(
                By.XPATH, "//input[@placeholder='Qidirish']")
            search_input.clear()
            search_input.send_keys(Keys.CONTROL + "a")
            search_input.send_keys(Keys.DELETE)

        except:
            # Agar xatolik bo'lsa, sahifani yangilash
            driver.get(
                "https://billing.e-edu.uz/financial-activity/contracts?academicYearId=3")
            time.sleep(2)

        return True, "Muvaffaqiyatli"

    except Exception as e:
        return False, f"Umumiy xatolik: {e}"


# ==================== ASOSIY ====================
def main():
    print("\n" + "="*60)
    print("🏛️ BILLING SHARTNOMALAR BOTI")
    print("="*60)

    if not login():
        print("Login muvaffaqiyatsiz!")
        driver.quit()
        return

    df = excel_oquvchi()
    if df is None or df.empty:
        print("Excelda ma'lumot topilmadi!")
        driver.quit()
        return

    total_count = len(df)
    print(f"\n📊 Jami {total_count} ta shartnoma\n")

    muvaffaqiyatli = 0

    for index, row in df.iterrows():
        contract_number = row[CONTRACT_COLUMN]
        natija, sabab = shartnoma_qayta_ishlash(
            contract_number, index, total_count)

        if natija:
            muvaffaqiyatli += 1
            print(f"  ✅ Muvaffaqiyatli")
        else:
            muvaffaqiyatsizlar.append({
                'shartnoma_raqami': contract_number,
                'xatolik_sababi': sabab
            })
            print(f"  ❌ Muvaffaqiyatsiz: {sabab}")
            # Keyingi shartnomaga o'tish uchun sahifani yangilash
            try:
                driver.get(
                    "https://billing.e-edu.uz/financial-activity/contracts?academicYearId=3")
                time.sleep(2)
            except:
                pass

        time.sleep(0.5)

    # ==================== NATIJALAR ====================
    print("\n" + "="*60)
    print("📊 JARAYON YAKUNLANDI!")
    print("="*60)
    print(f"📌 Jami: {total_count}")
    print(f"✅ Muvaffaqiyatli: {muvaffaqiyatli}")
    print(f"❌ Muvaffaqiyatsiz: {len(muvaffaqiyatsizlar)}")
    print("="*60)

    # Excelga yozish

    try:
        with pd.ExcelWriter(f"billing/shartnoma_natijalari.xlsx", engine='openpyxl') as writer:
            if natijalar:
                pd.DataFrame(natijalar).to_excel(
                    writer, index=False, sheet_name="Natijalar")
            if muvaffaqiyatsizlar:
                pd.DataFrame(muvaffaqiyatsizlar).to_excel(
                    writer, index=False, sheet_name="Muvaffaqiyatsizlar")
        print(f"\n📄 Natijalar saqlandi")
    except Exception as e:
        print(f"Excelga yozishda xatolik: {e}")

    time.sleep(3)
    driver.quit()
    print("\n✅ Dastur tugadi!")


if __name__ == "__main__":
    main()
