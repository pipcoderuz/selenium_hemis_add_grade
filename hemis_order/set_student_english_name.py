import pandas as pd
import base64
import re
import time
import io
from datetime import datetime
from collections import defaultdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

from PIL import Image, ImageOps, ImageFilter
import numpy as np
import easyocr
import ddddocr

from config import LOGIN_VALUE, PASSWORD_VALUE


# ==================== SOZLAMALAR ====================
EXCEL_FILE = "hemis_order/students.xlsx"
SHEET_NAME = "talabalar"
HEMIS_ID_COLUMN = "hemis_id"
FIO_COLUMN = "fio"

BASE_URL = "https://hemis.timeedu.uz"
STUDENT_LIST_URL = f"{BASE_URL}/student/student"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

print("EasyOCR model yuklanmoqda...")
reader = easyocr.Reader(["en"], gpu=False)
print("EasyOCR tayyor.")

ddd_ocr = ddddocr.DdddOcr(show_ad=False)
print("ddddocr tayyor.")

results = []


# ==================== LOGIN ====================
def login() -> bool:
    print("Login sahifasiga o'tyapman...")
    driver.get(BASE_URL)

    try:
        oneid_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href, '/auth/edu-id') or contains(text(), 'OneID')]")
            )
        )
        oneid_button.click()
        print("OneID tugmasi bosildi")
    except Exception as e:
        print("OneID tugmasi topilmadi:", e)
        return False

    try:
        wait.until(EC.presence_of_element_located((By.NAME, "login")))
        print("OneID forma yuklandi")
    except Exception:
        print("OneID login maydoni topilmadi")
        return False

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
        return False

    time.sleep(2)
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Dashboard yuklandi (kirish muvaffaqiyatli)")
        return True
    except Exception:
        print("Kirishdan keyin sahifa yuklanmadi")
        return False


# ==================== EXCEL ====================
def load_excel():
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    if HEMIS_ID_COLUMN not in df.columns:
        raise ValueError(
            f"Excelda '{HEMIS_ID_COLUMN}' ustuni yo'q. Mavjud: {list(df.columns)}")
    df = df.dropna(subset=[HEMIS_ID_COLUMN])
    df[HEMIS_ID_COLUMN] = df[HEMIS_ID_COLUMN].astype(str).str.strip()
    df = df[df[HEMIS_ID_COLUMN] != ""]
    print(f"Exceldan {len(df)} ta yozuv o'qildi")
    return df


# ==================== CAPTCHA OCR ====================
def _digits_only(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def _remove_strike_lines(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGB"))
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(
        int), arr[:, :, 2].astype(int)

    near_white = (r > 230) & (g > 230) & (b > 230)
    blue_line = (b > r + 30) & (b > g + 20) & (b > 100) & ~near_white
    red_line = (r > g + 40) & (r > b + 40) & (r > 140) & ~near_white

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    saturation = max_c - min_c
    digit_like = (~near_white) & (~blue_line) & (~red_line) & (
        (saturation > 25) | (max_c < 200)
    )

    out = np.ones(arr.shape[:2], dtype=np.uint8) * 255
    out[digit_like] = 0
    pil = Image.fromarray(out, mode="L")
    pil = pil.filter(ImageFilter.MedianFilter(size=3))
    return pil


def _variants_strong(img: Image.Image) -> list:
    variants = []
    w, h = img.size
    big = img.resize((max(w * 3, 200), max(h * 3, 60)),
                    Image.Resampling.LANCZOS)

    variants.append(("orig", np.array(big.convert("RGB"))))

    clean = _remove_strike_lines(big)
    variants.append(("clean", np.array(clean.convert("RGB"))))

    blur = clean.filter(ImageFilter.GaussianBlur(radius=0.5))
    variants.append(("blur", np.array(blur.convert("RGB"))))

    inv = ImageOps.invert(clean)
    variants.append(("inv", np.array(inv.convert("RGB"))))

    gray = ImageOps.autocontrast(big.convert("L"))
    variants.append(("gray", np.array(gray.convert("RGB"))))

    for thr in (90, 120, 150, 180):
        bw = gray.point(lambda x, t=thr: 0 if x < t else 255)
        variants.append((f"thr{thr}", np.array(bw.convert("RGB"))))

    return variants


def _pil_to_png_bytes(arr_or_img) -> bytes:
    if isinstance(arr_or_img, np.ndarray):
        im = Image.fromarray(arr_or_img)
    else:
        im = arr_or_img
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def ocr_captcha_combined(b64_data: str) -> str:
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]

    raw = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw)).convert("RGB")

    votes = []

    for name, arr in _variants_strong(img):
        try:
            png = _pil_to_png_bytes(arr)
            text = ddd_ocr.classification(png)
            digits = _digits_only(text)
            if digits:
                score = 3.0 if len(digits) in (4, 5) else 1.0
                if 3 <= len(digits) <= 6:
                    score += 1.0
                votes.append((digits, score, f"ddd:{name}"))
        except Exception:
            continue

    try:
        text = ddd_ocr.classification(raw)
        digits = _digits_only(text)
        if digits:
            score = 4.0 if len(digits) in (4, 5) else 1.5
            votes.append((digits, score, "ddd:raw"))
    except Exception:
        pass

    for name, arr in _variants_strong(img)[:6]:
        try:
            result = reader.readtext(
                arr,
                allowlist="0123456789",
                detail=1,
                paragraph=False,
                mag_ratio=2.0,
            )
            for _, text, conf in result:
                digits = _digits_only(text)
                if digits and conf >= 0.2:
                    score = float(conf) + (1.0 if len(digits) in (4, 5) else 0)
                    votes.append((digits, score, f"easy:{name}"))
        except Exception:
            continue

    if not votes:
        return ""

    score_sum = defaultdict(float)
    count = defaultdict(int)
    for dig, sc, eng in votes:
        score_sum[dig] += sc
        count[dig] += 1

    ranked = sorted(
        score_sum.keys(),
        key=lambda d: (
            count[d] * 2 + score_sum[d] + (5 if len(d) in (4, 5) else 0)
        ),
        reverse=True,
    )

    best = ranked[0]
    print(
        f"    → tanlandi: {best}  (x{count[best]}, score={score_sum[best]:.1f})")
    return best


def _refresh_captcha():
    try:
        refresh_btn = driver.find_element(
            By.XPATH, "//button[@onclick='getCaptchaInfo()']"
        )
        driver.execute_script("arguments[0].click();", refresh_btn)
        time.sleep(0.8)
    except Exception:
        pass


def _captcha_rejected() -> bool:
    try:
        help_blocks = driver.find_elements(
            By.CSS_SELECTOR, ".field-captcha .help-block, .field-captcha.has-error"
        )
        error_text = " ".join(h.text for h in help_blocks if h.text.strip())
        if error_text and any(
            w in error_text.lower()
            for w in ["xato", "noto", "wrong", "invalid", "kod"]
        ):
            return True
        return False
    except Exception:
        return False


def solve_captcha_in_modal(max_retries: int = 5) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            img_el = wait.until(
                EC.presence_of_element_located((By.ID, "captcha-image"))
            )
            src = img_el.get_attribute("src") or ""
            if "base64" not in src and not src.startswith("data:image"):
                print(f"  ⚠ [{attempt}] Captcha src yo'q")
                time.sleep(0.5)
                continue

            try:
                b64 = src.split(",", 1)[1] if "," in src else src
                with open(f"hemis_order/captcha_debug_{attempt}.png", "wb") as f:
                    f.write(base64.b64decode(b64))
            except Exception:
                pass

            code = ocr_captcha_combined(src)
            print(f"  🔍 [{attempt}] OCR: '{code}'")

            if not code or len(code) < 3:
                print("  ⚠ OCR ishonchsiz → captcha yangilanadi")
                _refresh_captcha()
                continue

            captcha_input = wait.until(
                EC.presence_of_element_located((By.ID, "captcha"))
            )
            captcha_input.clear()
            captcha_input.send_keys(code)
            time.sleep(0.3)

            search_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@onclick='getPassportInfo()']")
                )
            )
            driver.execute_script("arguments[0].click();", search_btn)
            print(f"  ✓ Captcha yuborildi: {code}")
            time.sleep(1.2)

            if _captcha_rejected():
                print("  ⚠ Captcha rad etildi → yangilanadi")
                _refresh_captcha()
                continue

            return True

        except Exception as e:
            print(f"  ⚠ [{attempt}] Captcha xatoligi: {e}")
            time.sleep(0.5)

    return False


# ==================== SAQLASH + TOAST + TERRAIN ====================
def click_save() -> bool:
    try:
        save_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "submitButton"))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", save_btn
        )
        time.sleep(0.2)
        try:
            save_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", save_btn)
        print("  ✓ Saqlash bosildi")
        return True
    except Exception as e:
        print(f"  ✗ Saqlash tugmasi: {e}")
        return False


def wait_success_toast(timeout: float = 2.0) -> bool:
    """Qisqa kutish — toast chiqmasa tez davom etadi."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            els = driver.find_elements(
                By.CSS_SELECTOR, ".toast-success .toast-message"
            )
            for el in els:
                txt = (el.text or "").strip()
                if "muvaffaqiyatli" in txt.lower():
                    print(f"  ✅ Toast: {txt}")
                    return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def select_any_terrain() -> bool:
    """
    #_terrain — faqat JS.
    Select2/krajee: jQuery val + trigger('change').
    """
    try:
        # Maydonni ekranga keltirish
        try:
            field = driver.find_element(
                By.CSS_SELECTOR, ".field-_terrain, #_terrain")
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", field
            )
            time.sleep(0.2)
        except Exception:
            pass

        result = driver.execute_script("""
            var el = document.getElementById('_terrain');
            if (!el) return {ok: false, reason: 'element_yoq'};

            // Birinchi bo'sh bo'lmagan option
            var val = null, txt = null;
            for (var i = 0; i < el.options.length; i++) {
                var o = el.options[i];
                var v = (o.value || '').trim();
                var t = (o.textContent || o.innerText || '').trim();
                if (v && t && t.toLowerCase() !== 'tanlash') {
                    val = v;
                    txt = t;
                    break;
                }
            }
            if (!val) return {ok: false, reason: 'option_yoq', count: el.options.length};

            // Qiymatni o'rnatish
            el.value = val;

            // Select2 / jQuery (Yii2 krajee)
            if (window.jQuery) {
                var $el = jQuery(el);
                $el.val(val).trigger('change');
                try { $el.trigger('select2:select'); } catch (e) {}
                // Select2 UI matnini yangilash
                try {
                    var $s2 = $el.next('.select2-container').find('.select2-selection__rendered');
                    if ($s2.length) {
                        $s2.text(txt).removeClass('select2-selection__placeholder');
                        $s2.attr('title', txt);
                    }
                } catch (e) {}
            }

            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('input', { bubbles: true }));

            // Validatsiya xatosini olib tashlash
            el.setAttribute('aria-invalid', 'false');
            var fg = el.closest('.form-group, .field-_terrain');
            if (fg) {
                fg.classList.remove('has-error');
                var hb = fg.querySelector('.help-block');
                if (hb) hb.innerHTML = '';
            }

            return {
                ok: true,
                value: el.value,
                text: txt,
                count: el.options.length
            };
        """)

        if not result:
            print("  ⚠ Terrain JS natija yo'q")
            return False

        if not result.get("ok"):
            print(f"  ⚠ Terrain tanlanmadi: {result.get('reason')} "
                f"(options={result.get('count')})")
            return False

        print(f"  ✓ Terrain: {result.get('text')} ({result.get('value')}) "
            f"[{result.get('count')} option]")
        time.sleep(0.3)

        # Qayta tekshirish
        cur = driver.execute_script(
            "return document.getElementById('_terrain') "
            "? document.getElementById('_terrain').value : '';"
        )
        if not cur:
            print("  ⚠ Terrain value bo'sh qoldi")
            return False
        return True

    except Exception as e:
        print(f"  ⚠ Terrain xato: {e}")
        return False


def save_with_fallback() -> tuple[bool, str]:
    """
    1) Saqlash → toast (max 2s)
    2) Yo'q bo'lsa terrain → yana saqlash → toast (max 2s)
    """
    if not click_save():
        return False, "Saqlash tugmasi topilmadi"

    if wait_success_toast(timeout=2.0):
        return True, "Muvaffaqiyatli"

    print("  ⚠ Toast yo'q → Mahalla tanlanadi...")
    if not select_any_terrain():
        return False, "Toast yo'q va terrain tanlanmadi"

    if not click_save():
        return False, "Terrain tanlandi, qayta saqlash ishlamadi"

    if wait_success_toast(timeout=2.0):
        return True, "Muvaffaqiyatli (terrain bilan)"

    return False, "Saqlashdan keyin toast chiqmadi"


# ==================== BITTA TALABA ====================
def process_student(hemis_id: str, fio: str = "") -> tuple[bool, str]:
    print(f"\n--- {hemis_id} {fio} ---")

    try:
        driver.get(STUDENT_LIST_URL)
        time.sleep(0.5)

        search = wait.until(
            EC.presence_of_element_located((By.ID, "estudent-search"))
        )
        search.clear()
        search.send_keys(str(hemis_id))
        search.send_keys(Keys.ENTER)
        print(f"  ✓ Qidiruv: {hemis_id}")
        time.sleep(1.2)

        try:
            rows = driver.find_elements(
                By.CSS_SELECTOR, "table.toggle_table tbody tr")
            if not rows:
                return False, "Talaba topilmadi (jadval bo'sh)"

            link = None
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 4:
                    continue
                anchors = cells[3].find_elements(By.TAG_NAME, "a")
                if anchors:
                    link = anchors[0]
                    break

            if link is None:
                links = driver.find_elements(
                    By.XPATH, "//table//a[contains(@href, 'student-edit')]"
                )
                if not links:
                    return False, "Talaba linki topilmadi"
                link = links[0]

            student_name = link.text.strip().split("\n")[0]
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", link
            )
            time.sleep(0.3)
            link.click()
            print(f"  ✓ Talaba ochildi: {student_name}")
            time.sleep(0.8)
        except Exception as e:
            return False, f"Talaba linkiga o'tishda xato: {e}"

        try:
            captcha_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@onclick='getCaptchaInfo()']")
                )
            )
            driver.execute_script("arguments[0].click();", captcha_btn)
            print("  ✓ Captcha tugmasi bosildi")
            time.sleep(0.8)
        except Exception as e:
            return False, f"Captcha tugmasi topilmadi: {e}"

        try:
            wait.until(EC.visibility_of_element_located(
                (By.ID, "captcha-image")))
        except TimeoutException:
            return False, "Captcha modal ochilmadi"

        if not solve_captcha_in_modal(max_retries=5):
            return False, "Captcha yechilmadi"

        time.sleep(1.0)

        return save_with_fallback()

    except Exception as e:
        return False, f"Umumiy xato: {str(e)[:150]}"


# ==================== MAIN ====================
def main():
    print("\n" + "=" * 60)
    print("TALABA PASSPORT / CAPTCHA BOTI (ddddocr + EasyOCR)")
    print("=" * 60)

    if not login():
        print("Login muvaffaqiyatsiz!")
        driver.quit()
        return

    try:
        df = load_excel()
    except Exception as e:
        print(e)
        driver.quit()
        return

    total = len(df)
    ok_count = 0
    fail_count = 0

    for idx, row in df.iterrows():
        hemis_id = str(row[HEMIS_ID_COLUMN]).strip()
        fio = ""
        if FIO_COLUMN in df.columns and pd.notna(row.get(FIO_COLUMN)):
            fio = str(row[FIO_COLUMN]).strip()

        print(f"\n[{idx + 1}/{total}]")
        success, msg = process_student(hemis_id, fio)

        results.append({
            "hemis_id": hemis_id,
            "fio": fio,
            "status": "Muvaffaqiyatli" if success else "Xato",
            "xabar": msg,
        })

        if success:
            ok_count += 1
            print(f"  ✅ {msg}")
        else:
            fail_count += 1
            print(f"  ❌ {msg}")

        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"Jami: {total} | ✅ {ok_count} | ❌ {fail_count}")
    print("=" * 60)

    out = "hemis_order/student_captcha_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"📄 Natija: {out}")

    driver.quit()
    print("Dastur tugadi!")


if __name__ == "__main__":
    main()
