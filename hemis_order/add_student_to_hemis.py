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
EXCEL_FILE = "hemis_order/abiturients.xlsx"
SHEET_NAME = "talabalar"

COL_FIO = "fio"
COL_FAKULTET = "fakultet"
COL_FARMOYISH = "farmoyish"
COL_SPECIALTY = "specialty"
COL_PASSPORT = "passport_number"
COL_PIN = "passport_pin"
COL_PHONE = "phone"

BASE_URL = "https://hemis.timeedu.uz"
STUDENT_LIST_URL = f"{BASE_URL}/student/student"
STUDENT_CREATE_URL = f"{BASE_URL}/student/student-edit"

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
        wait.until(EC.presence_of_element_located((By.NAME, "login")))
    except Exception:
        print("OneID login maydoni topilmadi")
        return False

    driver.find_element(By.NAME, "login").clear()
    driver.find_element(By.NAME, "login").send_keys(LOGIN_VALUE)
    driver.find_element(By.NAME, "password").clear()
    driver.find_element(By.NAME, "password").send_keys(PASSWORD_VALUE)

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
        print("Dashboard yuklandi")
        return True
    except Exception:
        print("Kirishdan keyin sahifa yuklanmadi")
        return False


# ==================== EXCEL ====================
def load_excel():
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    required = [COL_FAKULTET, COL_FARMOYISH,
                COL_SPECIALTY, COL_PASSPORT, COL_PIN, COL_PHONE]
    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"Excelda '{col}' ustuni yo'q. Mavjud: {list(df.columns)}")
    print(f"Exceldan {len(df)} ta yozuv o'qildi")
    return df


def _s(row, col, default=""):
    if col not in row.index or pd.isna(row.get(col)):
        return default
    return str(row[col]).strip()


def normalize_phone_9(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("998") and len(digits) >= 12:
        digits = digits[3:]
    if digits.startswith("8") and len(digits) == 10:
        digits = digits[1:]
    if len(digits) > 9:
        digits = digits[-9:]
    return digits


def fill_phone(phone_raw: str) -> bool:
    phone9 = normalize_phone_9(phone_raw)
    if len(phone9) != 9:
        print(f"  ⚠ Telefon 9 xonali emas: '{phone_raw}' → '{phone9}'")

    try:
        phone_inp = wait.until(
            EC.presence_of_element_located((By.ID, "estudent-phone"))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", phone_inp
        )
        time.sleep(0.15)

        driver.execute_script("""
            var el = document.getElementById('estudent-phone');
            if (!el) return false;
            var nine = arguments[0] || '';
            el.focus();
            if (window.jQuery) {
                var $el = jQuery(el);
                try {
                    if ($el.inputmask) {
                        $el.inputmask('setvalue', '+998' + nine);
                        $el.trigger('input').trigger('change').trigger('blur');
                        return true;
                    }
                } catch (e) {}
                try {
                    $el.val('+998' + nine).trigger('input').trigger('change');
                    return true;
                } catch (e) {}
            }
            el.value = '+998' + nine;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        """, phone9)

        time.sleep(0.3)

        cur = driver.execute_script(
            "return (document.getElementById('estudent-phone').value || '');"
        )
        digits_in_field = re.sub(r"\D", "", cur)
        if phone9 and phone9 not in digits_in_field:
            phone_inp.click()
            time.sleep(0.1)
            phone_inp.send_keys(Keys.CONTROL, "a")
            phone_inp.send_keys(Keys.DELETE)
            time.sleep(0.1)
            for ch in phone9:
                phone_inp.send_keys(ch)
                time.sleep(0.03)
            time.sleep(0.2)

        final = driver.execute_script(
            "return (document.getElementById('estudent-phone').value || '');"
        )
        print(f"  ✓ Telefon: {final}  (kirish: {phone9})")
        return True

    except Exception as e:
        print(f"  ⚠ Telefon xato: {e}")
        return False


# ==================== SELECT2 ====================
def select2_by_text(select_id: str, search_text: str, partial: bool = True, wait_opts: int = 12) -> bool:
    search_text = (search_text or "").strip()
    if not search_text:
        print(f"  ⚠ {select_id}: qidiruv matni bo'sh")
        return False

    for _ in range(wait_opts):
        count = driver.execute_script(f"""
            var el = document.getElementById('{select_id}');
            if (!el) return 0;
            var n = 0;
            for (var i = 0; i < el.options.length; i++) {{
                if ((el.options[i].value || '').trim()) n++;
            }}
            return n;
        """)
        if count and count > 0:
            break
        time.sleep(0.4)

    result = driver.execute_script("""
        var el = document.getElementById(arguments[0]);
        var needle = (arguments[1] || '').toLowerCase().trim();
        var partial = arguments[2];
        if (!el) return {ok:false, reason:'element_yoq'};

        var val = null, txt = null;
        for (var i = 0; i < el.options.length; i++) {
            var o = el.options[i];
            var v = (o.value || '').trim();
            var t = (o.textContent || o.innerText || '').trim();
            if (!v) continue;
            var tl = t.toLowerCase();
            if (partial) {
                if (tl.indexOf(needle) !== -1) { val = v; txt = t; break; }
            } else {
                if (tl === needle) { val = v; txt = t; break; }
            }
        }
        if (!val) return {ok:false, reason:'option_topilmadi', count: el.options.length};

        el.value = val;
        if (window.jQuery) {
            var $el = jQuery(el);
            $el.val(val).trigger('change');
            try { $el.trigger('select2:select'); } catch(e) {}
            try {
                var $s2 = $el.next('.select2-container').find('.select2-selection__rendered');
                if ($s2.length) {
                    $s2.text(txt).removeClass('select2-selection__placeholder').attr('title', txt);
                }
            } catch(e) {}
        }
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.setAttribute('aria-invalid', 'false');
        var fg = el.closest('.form-group');
        if (fg) {
            fg.classList.remove('has-error');
            var hb = fg.querySelector('.help-block');
            if (hb) hb.innerHTML = '';
        }
        return {ok:true, value: val, text: txt, count: el.options.length};
    """, select_id, search_text, partial)

    if not result or not result.get("ok"):
        print(f"  ⚠ {select_id} tanlanmadi: {search_text!r} → {result}")
        return False

    print(f"  ✓ {select_id}: {result.get('text')}")
    time.sleep(0.6)
    return True


def select_first_if_empty(select_id: str, label: str = "") -> bool:
    try:
        result = driver.execute_script("""
            var el = document.getElementById(arguments[0]);
            if (!el) return {ok:false, reason:'element_yoq'};

            var current = (el.value || '').trim();
            if (current) {
                var curTxt = '';
                for (var i = 0; i < el.options.length; i++) {
                    if (el.options[i].value === current) {
                        curTxt = (el.options[i].textContent || '').trim();
                        break;
                    }
                }
                return {ok:true, skipped:true, value: current, text: curTxt};
            }

            var val = null, txt = null;
            for (var i = 0; i < el.options.length; i++) {
                var o = el.options[i];
                var v = (o.value || '').trim();
                var t = (o.textContent || o.innerText || '').trim();
                if (!v) continue;
                var tl = t.toLowerCase();
                if (tl.indexOf('tanlang') !== -1) continue;
                val = v; txt = t; break;
            }
            if (!val) return {ok:false, reason:'option_yoq', count: el.options.length};

            el.value = val;
            if (window.jQuery) {
                var $el = jQuery(el);
                $el.val(val).trigger('change');
                try { $el.trigger('select2:select'); } catch(e) {}
                try {
                    var $s2 = $el.next('.select2-container').find('.select2-selection__rendered');
                    if ($s2.length) {
                        $s2.text(txt).removeClass('select2-selection__placeholder').attr('title', txt);
                    }
                } catch(e) {}
            }
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.setAttribute('aria-invalid', 'false');
            var fg = el.closest('.form-group');
            if (fg) {
                fg.classList.remove('has-error');
                var hb = fg.querySelector('.help-block');
                if (hb) hb.innerHTML = '';
            }
            return {ok:true, skipped:false, value: el.value, text: txt, count: el.options.length};
        """, select_id)

        if not result or not result.get("ok"):
            print(f"  ⚠ {label or select_id}: {result}")
            return False

        if result.get("skipped"):
            print(f"  ℹ {label or select_id} allaqachon: {result.get('text')}")
        else:
            print(
                f"  ✓ {label or select_id}: {result.get('text')} ({result.get('value')})")
        time.sleep(0.7)
        return True
    except Exception as e:
        print(f"  ⚠ {label or select_id} xato: {e}")
        return False


def select_any_terrain() -> bool:
    try:
        try:
            field = driver.find_element(
                By.CSS_SELECTOR, ".field-_terrain, #_terrain")
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", field)
            time.sleep(0.2)
        except Exception:
            pass

        for _ in range(15):
            n = driver.execute_script("""
                var el = document.getElementById('_terrain');
                if (!el) return 0;
                var c = 0;
                for (var i=0;i<el.options.length;i++) {
                    if ((el.options[i].value||'').trim()) c++;
                }
                return c;
            """)
            if n and n > 0:
                break
            time.sleep(0.4)

        result = driver.execute_script("""
            var el = document.getElementById('_terrain');
            if (!el) return {ok:false, reason:'element_yoq'};
            var val=null, txt=null;
            for (var i=0;i<el.options.length;i++){
                var o=el.options[i];
                var v=(o.value||'').trim();
                var t=(o.textContent||o.innerText||'').trim();
                if (v && t && t.toLowerCase()!=='tanlash'){ val=v; txt=t; break; }
            }
            if (!val) return {ok:false, reason:'option_yoq', count:el.options.length};
            el.value = val;
            if (window.jQuery) {
                var $el = jQuery(el);
                $el.val(val).trigger('change');
                try { $el.trigger('select2:select'); } catch(e){}
                try {
                    var $s2 = $el.next('.select2-container').find('.select2-selection__rendered');
                    if ($s2.length) {
                        $s2.text(txt).removeClass('select2-selection__placeholder').attr('title', txt);
                    }
                } catch(e){}
            }
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.setAttribute('aria-invalid','false');
            var fg = el.closest('.form-group, .field-_terrain');
            if (fg) {
                fg.classList.remove('has-error');
                var hb = fg.querySelector('.help-block');
                if (hb) hb.innerHTML = '';
            }
            return {ok:true, value:el.value, text:txt, count:el.options.length};
        """)

        if not result or not result.get("ok"):
            print(f"  ⚠ Terrain: {result}")
            return False
        print(f"  ✓ Terrain: {result.get('text')} ({result.get('value')})")
        return True
    except Exception as e:
        print(f"  ⚠ Terrain xato: {e}")
        return False


def fill_if_empty(input_id: str, value: str, label: str = "") -> bool:
    try:
        result = driver.execute_script("""
            var el = document.getElementById(arguments[0]);
            if (!el) return {ok:false, reason:'element_yoq'};
            var cur = (el.value || '').trim();
            if (cur) return {ok:true, skipped:true, value: cur};
            el.value = arguments[1];
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.setAttribute('aria-invalid', 'false');
            var fg = el.closest('.form-group');
            if (fg) {
                fg.classList.remove('has-error');
                var hb = fg.querySelector('.help-block');
                if (hb) hb.innerHTML = '';
            }
            return {ok:true, skipped:false, value: el.value};
        """, input_id, value)

        if not result or not result.get("ok"):
            print(f"  ⚠ {label or input_id}: {result}")
            return False
        if result.get("skipped"):
            print(
                f"  ℹ {label or input_id} allaqachon: {result.get('value')[:40]}")
        else:
            print(f"  ✓ {label or input_id}: {value}")
        return True
    except Exception as e:
        print(f"  ⚠ {label or input_id} xato: {e}")
        return False


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
    return pil.filter(ImageFilter.MedianFilter(size=3))


def _variants_strong(img: Image.Image) -> list:
    variants = []
    w, h = img.size
    big = img.resize((max(w * 3, 200), max(h * 3, 60)),
                     Image.Resampling.LANCZOS)
    variants.append(("orig", np.array(big.convert("RGB"))))
    clean = _remove_strike_lines(big)
    variants.append(("clean", np.array(clean.convert("RGB"))))
    variants.append(("blur", np.array(clean.filter(
        ImageFilter.GaussianBlur(0.5)).convert("RGB"))))
    variants.append(("inv", np.array(ImageOps.invert(clean).convert("RGB"))))
    gray = ImageOps.autocontrast(big.convert("L"))
    variants.append(("gray", np.array(gray.convert("RGB"))))
    for thr in (90, 120, 150, 180):
        bw = gray.point(lambda x, t=thr: 0 if x < t else 255)
        variants.append((f"thr{thr}", np.array(bw.convert("RGB"))))
    return variants


def _pil_to_png_bytes(arr_or_img) -> bytes:
    im = Image.fromarray(arr_or_img) if isinstance(
        arr_or_img, np.ndarray) else arr_or_img
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
            text = ddd_ocr.classification(_pil_to_png_bytes(arr))
            digits = _digits_only(text)
            if digits:
                score = 3.0 if len(digits) in (4, 5) else 1.0
                if 3 <= len(digits) <= 6:
                    score += 1.0
                votes.append((digits, score))
        except Exception:
            continue

    try:
        digits = _digits_only(ddd_ocr.classification(raw))
        if digits:
            votes.append((digits, 4.0 if len(digits) in (4, 5) else 1.5))
    except Exception:
        pass

    for name, arr in _variants_strong(img)[:6]:
        try:
            for _, text, conf in reader.readtext(
                arr, allowlist="0123456789", detail=1, paragraph=False, mag_ratio=2.0
            ):
                digits = _digits_only(text)
                if digits and conf >= 0.2:
                    votes.append(
                        (digits, float(conf) + (1.0 if len(digits) in (4, 5) else 0)))
        except Exception:
            continue

    if not votes:
        return ""

    score_sum = defaultdict(float)
    count = defaultdict(int)
    for dig, sc in votes:
        score_sum[dig] += sc
        count[dig] += 1

    ranked = sorted(
        score_sum.keys(),
        key=lambda d: count[d] * 2 + score_sum[d] +
        (5 if len(d) in (4, 5) else 0),
        reverse=True,
    )
    best = ranked[0]
    print(f"    → OCR: {best} (x{count[best]})")
    return best


def captcha_error_toast() -> bool:
    try:
        for el in driver.find_elements(By.CSS_SELECTOR, ".toast-error .toast-message"):
            t = (el.text or "").lower()
            if "himoya" in t or "noto" in t or "kod" in t:
                return True
    except Exception:
        pass
    return False


def close_captcha_modal():
    driver.execute_script("""
        var m = document.getElementById('captchaModal');
        if (m) {
            m.style.display = 'none';
            m.classList.remove('in', 'show');
            m.setAttribute('aria-hidden', 'true');
            if (window.jQuery) {
                try { jQuery(m).modal('hide'); } catch(e) {}
            }
        }
        document.querySelectorAll('.modal-backdrop').forEach(function(b){ b.remove(); });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('padding-right');
        document.body.style.overflow = '';
    """)
    time.sleep(0.4)


def open_captcha_modal() -> bool:
    close_captcha_modal()

    btn = None
    selectors = [
        (By.XPATH, "//button[@onclick='getCaptchaInfo()']"),
        (By.XPATH, "//button[.//i[@id='fa_search_captcha']]"),
        (By.CSS_SELECTOR, "button[onclick='getCaptchaInfo()']"),
        (By.ID, "fa_search_captcha"),
    ]

    for by, sel in selectors:
        try:
            el = driver.find_element(by, sel)
            if el.tag_name.lower() == "i":
                try:
                    el = el.find_element(By.XPATH, "./ancestor::button[1]")
                except Exception:
                    pass
            btn = el
            break
        except Exception:
            continue

    if btn is None:
        print("  ⚠ Captcha qidiruv tugmasi topilmadi")
        return False

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", btn)
        time.sleep(0.2)

        driver.execute_script("""
            var s = document.getElementById('fa_spinner_captcha');
            var i = document.getElementById('fa_search_captcha');
            if (s) s.style.display = 'none';
            if (i) i.style.display = '';
        """)

        try:
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            pass

        time.sleep(0.5)
        opened = driver.execute_script("""
            var m = document.getElementById('captchaModal');
            var img = document.getElementById('captcha-image');
            if (m && (m.classList.contains('in') || m.style.display === 'block')) return true;
            if (img && img.offsetParent !== null) return true;
            return false;
        """)

        if not opened:
            print("  ℹ click ishlamadi → getCaptchaInfo()")
            driver.execute_script("""
                if (typeof getCaptchaInfo === 'function') { getCaptchaInfo(); }
            """)
            time.sleep(0.8)

        wait.until(EC.visibility_of_element_located((By.ID, "captcha-image")))
        print("  ✓ Captcha modal ochildi")
        return True

    except Exception as e:
        print(f"  ⚠ Captcha ochilmadi: {e}")
        return False


def solve_captcha_create(max_retries: int = 5) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            if not open_captcha_modal():
                print(f"  ⚠ [{attempt}] modal ochilmadi")
                time.sleep(0.5)
                continue

            img_el = wait.until(
                EC.presence_of_element_located((By.ID, "captcha-image"))
            )
            src = img_el.get_attribute("src") or ""
            if "base64" not in src:
                print(f"  ⚠ [{attempt}] captcha src yo'q")
                close_captcha_modal()
                continue

            code = ocr_captcha_combined(src)
            print(f"  🔍 [{attempt}] captcha: '{code}'")
            if not code or len(code) < 3:
                close_captcha_modal()
                continue

            inp = wait.until(
                EC.presence_of_element_located((By.ID, "captcha")))
            inp.clear()
            inp.send_keys(code)
            time.sleep(0.2)

            search_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@onclick='getPassportInfo()']")
            ))
            driver.execute_script("arguments[0].click();", search_btn)
            print(f"  ✓ Captcha yuborildi: {code}")
            time.sleep(0.8)

            if captcha_error_toast():
                print("  ⚠ Himoya kodi noto'g'ri → qayta")
                close_captcha_modal()
                time.sleep(0.5)
                continue

            return True

        except Exception as e:
            print(f"  ⚠ [{attempt}] captcha xato: {e}")
            close_captcha_modal()
            time.sleep(0.4)

    return False


def close_any_modal(modal_id: str):
    driver.execute_script("""
        var m = document.getElementById(arguments[0]);
        if (m) {
            m.style.display = 'none';
            m.classList.remove('in', 'show');
            m.setAttribute('aria-hidden', 'true');
            if (window.jQuery) { try { jQuery(m).modal('hide'); } catch(e) {} }
        }
        document.querySelectorAll('.modal-backdrop').forEach(function(b){ b.remove(); });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('padding-right');
        document.body.style.overflow = '';
    """, modal_id)
    time.sleep(0.3)


def check_student_exists_modal(timeout: float = 2.5) -> str | None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            modal = driver.find_elements(
                By.CSS_SELECTOR,
                "#studentModal.in, #studentModal[style*='display: block']"
            )
            if not modal:
                time.sleep(0.2)
                continue

            title = ""
            try:
                title = driver.find_element(
                    By.CSS_SELECTOR, "#studentModal .modal-title"
                ).text.strip()
            except Exception:
                pass

            body_hint = ""
            try:
                body_hint = driver.find_element(
                    By.CSS_SELECTOR, "#studentModal .modal-body"
                ).text.strip()[:120]
            except Exception:
                pass

            low = (title + " " + body_hint).lower()
            if "mavjud" in low or "tizimda" in low or title:
                print(f"  ⚠ studentModal: {title or body_hint[:80]}")
                try:
                    close_btn = driver.find_element(
                        By.CSS_SELECTOR,
                        "#studentModal button.close, #studentModal [data-dismiss='modal']"
                    )
                    driver.execute_script("arguments[0].click();", close_btn)
                except Exception:
                    close_any_modal("studentModal")
                return "Talaba hemisda mavjud"

        except Exception:
            pass
        time.sleep(0.2)
    return None


def check_removal_modal(timeout: float = 2.0) -> str | None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            modal = driver.find_elements(
                By.CSS_SELECTOR, "#removalModal.in, #removalModal[style*='display: block']"
            )
            if modal:
                ps = driver.find_elements(
                    By.CSS_SELECTOR, "#removalModal .modal-body p")
                txt = (ps[0].text or "").strip(
                ) if ps else "Talaba boshqa OTMda mavjud"
                try:
                    close_btn = driver.find_element(
                        By.CSS_SELECTOR,
                        "#removalModal button[data-dismiss], #removalModal .close"
                    )
                    driver.execute_script("arguments[0].click();", close_btn)
                except Exception:
                    close_any_modal("removalModal")
                return txt or "Talaba boshqa OTMda mavjud (removal modal)"
        except Exception:
            pass
        time.sleep(0.25)
    return None


def click_save() -> bool:
    try:
        save_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "submitButton")))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", save_btn)
        time.sleep(0.2)
        try:
            save_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", save_btn)
        print("  ✓ Saqlash bosildi")
        return True
    except Exception as e:
        print(f"  ✗ Saqlash: {e}")
        return False


def wait_save_result(timeout: float = 4.0) -> tuple[bool, str]:
    """
    Saqlashdan keyin toastlarni o'qiydi.
    Success + HEMIS_ERROR birga chiqsa → HEMIS_ERROR (xato).
    Faqat success bo'lsa → muvaffaqiyatli.
    """
    end = time.time() + timeout
    success_msg = None
    error_msg = None

    while time.time() < end:
        try:
            # --- barcha toast-message larni yig'ish ---
            for el in driver.find_elements(By.CSS_SELECTOR, ".toast-message"):
                t = (el.text or "").strip()
                if not t:
                    continue
                low = t.lower()

                # HEMIS_ERROR / boshqa OTMda o'qiydi
                if (
                    "hemis_error" in low
                    or "o'qiydi" in low
                    or "o‘qiydi" in low
                    or "o'qimoqda" in low
                    or "o‘qimoqda" in low
                ):
                    if not error_msg:
                        error_msg = t
                    continue

                # muvaffaqiyat
                if any(w in low for w in [
                    "muvaffaqiyatli", "saqlandi", "qo'shildi", "yaratildi"
                ]):
                    if not success_msg:
                        success_msg = t

            # toast-error container (message classsiz bo'lishi mumkin)
            for el in driver.find_elements(By.CSS_SELECTOR, ".toast-error"):
                t = (el.text or "").strip()
                if not t:
                    continue
                low = t.lower()
                if "himoya" in low or "captcha" in low:
                    continue
                if "hemis_error" in low or len(t) > 15:
                    if not error_msg:
                        error_msg = t

            # toast-success
            for el in driver.find_elements(By.CSS_SELECTOR, ".toast-success"):
                t = (el.text or "").strip()
                if not t:
                    continue
                low = t.lower()
                if any(w in low for w in [
                    "muvaffaqiyatli", "saqlandi", "qo'shildi", "yaratildi"
                ]):
                    if not success_msg:
                        success_msg = t

        except Exception:
            pass

        # HEMIS_ERROR topilgan bo'lsa — darhol xato (success bo'lsa ham)
        if error_msg:
            print(
                f"  ❌ HEMIS_ERROR (success bilan birga bo'lishi mumkin): {error_msg}")
            return False, error_msg

        # Faqat success
        if success_msg:
            print(f"  ✅ Toast: {success_msg}")
            return True, success_msg

        time.sleep(0.25)

    # timeout: oxirgi holat
    if error_msg:
        return False, error_msg
    if success_msg:
        return True, success_msg
    return False, "Saqlashdan keyin muvaffaqiyat toast chiqmadi"

# ==================== BITTA TALABA ====================
def process_student(row) -> tuple[bool, str]:
    fio = _s(row, COL_FIO)
    fakultet = _s(row, COL_FAKULTET)
    farmoyish = _s(row, COL_FARMOYISH)
    specialty = _s(row, COL_SPECIALTY)
    passport = _s(row, COL_PASSPORT)
    pin = _s(row, COL_PIN)
    phone = _s(row, COL_PHONE)

    print(f"\n--- {fio or pin} | {passport} ---")

    try:
        driver.get(STUDENT_LIST_URL)
        time.sleep(0.8)

        try:
            create_btn = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//a[contains(@href,'/student/student-edit') and "
                "(contains(.,'Talaba yaratish') or contains(@class,'btn-success'))]"
            )))
            driver.execute_script("arguments[0].click();", create_btn)
            print("  ✓ Talaba yaratish bosildi")
        except Exception:
            driver.get(STUDENT_CREATE_URL)
            print("  ✓ student-edit sahifasiga o'tildi")

        time.sleep(1.0)
        wait.until(EC.presence_of_element_located((By.ID, "_department")))

        if not select2_by_text("_department", fakultet, partial=True):
            return False, f"Fakultet topilmadi: {fakultet}"

        if not select2_by_text("_decree_info_enroll", farmoyish, partial=True, wait_opts=20):
            return False, f"Farmoyish topilmadi: {farmoyish}"

        if not select2_by_text("_specialty", specialty, partial=True, wait_opts=20):
            return False, f"Mutaxassislik topilmadi: {specialty}"

        try:
            p_inp = wait.until(EC.presence_of_element_located(
                (By.ID, "passport_number")))
            p_inp.clear()
            p_inp.send_keys(passport)
            print(f"  ✓ Passport: {passport}")
        except Exception as e:
            return False, f"Passport maydoni: {e}"

        try:
            pin_inp = wait.until(
                EC.presence_of_element_located((By.ID, "passport_pin")))
            pin_inp.clear()
            pin_inp.send_keys(pin)
            print(f"  ✓ PIN: {pin}")
        except Exception as e:
            return False, f"PIN maydoni: {e}"

        if not solve_captcha_create(max_retries=5):
            return False, "Captcha yechilmadi"

        exists_msg = check_student_exists_modal(timeout=2.5)
        if exists_msg:
            return False, exists_msg

        removal_msg = check_removal_modal(timeout=2.0)
        if removal_msg:
            print(f"  ⚠ Removal: {removal_msg[:120]}")
            return False, removal_msg

        time.sleep(0.5)

        fill_if_empty("estudent-other", "///", "other")
        select_first_if_empty("_district", "Viloyat/Tuman")

        if not select_any_terrain():
            print("  ⚠ Mahalla tanlanmadi (davom etiladi)")

        fill_if_empty("home_address", "///", "home_address")

        if not fill_phone(phone):
            return False, f"Telefon yozilmadi: {phone}"

        if not click_save():
            return False, "Saqlash tugmasi topilmadi"

        ok, msg = wait_save_result(timeout=4.0)
        if ok:
            return True, "Muvaffaqiyatli"
        return False, msg

    except Exception as e:
        return False, f"Umumiy xato: {str(e)[:150]}"


# ==================== MAIN ====================
def main():
    print("\n" + "=" * 60)
    print("TALABA YARATISH BOTI")
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
        print(f"\n[{idx + 1}/{total}]")
        success, msg = process_student(row)

        results.append({
            "fio": _s(row, COL_FIO),
            "passport": _s(row, COL_PASSPORT),
            "pin": _s(row, COL_PIN),
            "fakultet": _s(row, COL_FAKULTET),
            "farmoyish": _s(row, COL_FARMOYISH),
            "specialty": _s(row, COL_SPECIALTY),
            "status": "Muvaffaqiyatli" if success else "Xato",
            "xabar": msg,
        })

        if success:
            ok_count += 1
            print(f"  ✅ {msg}")
        else:
            fail_count += 1
            print(f"  ❌ {msg}")

        time.sleep(0.8)

    print("\n" + "=" * 60)
    print(f"Jami: {total} | ✅ {ok_count} | ❌ {fail_count}")
    print("=" * 60)

    # HEMIS_ERROR larni alohida xulosa
    hemis_errs = [
        r for r in results
        if r["status"] == "Xato" and "HEMIS_ERROR" in str(r.get("xabar", "")).upper()
    ]
    if hemis_errs:
        print(f"\n⚠ HEMIS_ERROR ({len(hemis_errs)} ta):")
        for r in hemis_errs:
            print(
                f"  - {r.get('fio') or r.get('pin')}: {r.get('xabar')[:100]}")

    out = "hemis_order/talaba_yaratish_natija.xlsx"
    pd.DataFrame(results).to_excel(out, index=False)
    print(f"\n📄 Natija: {out}")

    driver.quit()
    print("Dastur tugadi!")


if __name__ == "__main__":
    main()
