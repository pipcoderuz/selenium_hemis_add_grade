import requests
import pandas as pd
from datetime import datetime
import time
from typing import List, Dict, Any, Optional
from config import HEMIS_TOKEN

# Konfiguratsiya
BASE_URL = "https://talaba.timeedu.uz/rest/v1/data"
headers = {
    "Authorization": f"Bearer {HEMIS_TOKEN}"
}
API_DELAY = 0.05  # 50ms delay
PAGE_LIMIT = 200


def extract_data_from_response(response_data: Any) -> Optional[List[Dict]]:
    """
    API javobidan haqiqiy ma'lumotlarni ajratib olish.
    Format: {'success': bool, 'error': str, 'data': {...}, 'code': int}
    """
    if isinstance(response_data, dict):
        # Agar 'data' kaliti bo'lsa
        if 'data' in response_data:
            data = response_data['data']

            # Data ichida 'items' bo'lishi mumkin
            if isinstance(data, dict) and 'items' in data:
                return data['items']
            # Data to'g'ridan-to'g'ri list bo'lishi mumkin
            elif isinstance(data, list):
                return data
            # Data dict bo'lsa, uni listga o'rash
            elif isinstance(data, dict):
                return [data]

        # Agar 'items' to'g'ridan-to'g'ri kalit bo'lsa
        elif 'items' in response_data:
            return response_data['items']

    # Agar list bo'lsa, to'g'ridan-to'g'ri qaytarish
    elif isinstance(response_data, list):
        return response_data

    return None


def fetch_all_pages(endpoint: str, params: Dict = None) -> List[Dict]:
    """Barcha sahifalarni yuklab olish"""
    all_data = []
    page = 1

    if params is None:
        params = {}

    params['limit'] = PAGE_LIMIT

    while True:
        params['page'] = page
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint}",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            response_data = response.json()

            # API muvaffaqiyatli ekanligini tekshirish
            if isinstance(response_data, dict):
                if response_data.get('success') is False:
                    error_msg = response_data.get('error', 'Noma\'lum xatolik')
                    print(f"  API xatolik: {error_msg}")
                    break

                # Haqiqiy ma'lumotlarni ajratib olish
                data = extract_data_from_response(response_data)
            else:
                data = response_data

            if not data:  # Bo'sh array qaytsa to'xtash
                break

            all_data.extend(data)
            print(f"  Yuklandi: {endpoint} - Sahifa {page} ({len(data)} ta)")

            if len(data) < PAGE_LIMIT:  # Oxirgi sahifa
                break

            page += 1
            time.sleep(API_DELAY)

        except Exception as e:
            print(f"  Xatolik {endpoint} sahifa {page}: {e}")
            break

    return all_data


def fetch_all_groups() -> List[Dict]:
    """Barcha guruhlarni olish"""
    print("\n📚 Guruhlar yuklanmoqda...")
    groups = fetch_all_pages("group-list")

    if groups:
        print(f"  ✅ Jami {len(groups)} ta guruh yuklandi")
        # Debug: Birinchi guruhni ko'rsatish
        if len(groups) > 0:
            print(
                f"  Namuna: {groups[0].get('name', 'N/A')} (ID: {groups[0].get('id', 'N/A')})")

    return groups


def fetch_exams_by_group(group_id: int) -> List[Dict]:
    """Guruh bo'yicha imtihonlarni olish"""
    return fetch_all_pages("subject-exam-list", {"_group": group_id})


def fetch_students_by_group(group_id: int) -> List[Dict]:
    """Guruh bo'yicha talabalarni olish"""
    return fetch_all_pages("student-list", {"_group": group_id})


def create_exam_student_excel():
    """Asosiy funksiya - Excel fayl yaratish"""
    print("=" * 60)
    print("🎓 HEMIS Imtihon-Talaba jadvali generatsiyasi")
    print("=" * 60)

    # 1. Barcha guruhlarni olish
    groups = fetch_all_groups()

    if not groups:
        print("\n❌ Guruhlar topilmadi!")
        return None

    print(f"\n✅ Jami {len(groups)} ta guruh topildi")

    # Excel uchun ma'lumotlar
    excel_data = []
    processed_groups = 0
    skipped_groups = 0

    # 2. Har bir guruh uchun
    for idx, group in enumerate(groups, 1):
        try:
            group_id = group.get('id')
            group_name = group.get('name', 'Noma\'lum')

            if not group_id:
                print(
                    f"\n⚠️ [{idx}/{len(groups)}] Guruhda ID topilmadi, o'tkazib yuborildi")
                skipped_groups += 1
                continue

            print(
                f"\n📋 [{idx}/{len(groups)}] Guruh: {group_name} (ID: {group_id})")

            # 3. Guruhning imtihonlarini olish
            exams = fetch_exams_by_group(group_id)
            print(f"  📝 Imtihonlar: {len(exams)} ta")

            if not exams:
                print(f"  ⏭️  Imtihonlar yo'q, o'tkazib yuborildi")
                skipped_groups += 1
                continue

            # 4. Guruhning talabalarini olish
            students = fetch_students_by_group(group_id)
            print(f"  👥 Talabalar: {len(students)} ta")

            if not students:
                print(f"  ⏭️  Talabalar yo'q, o'tkazib yuborildi")
                skipped_groups += 1
                continue

            # 5. Har bir imtihon va talaba uchun yozuv yaratish
            records_added = 0
            for exam in exams:
                if not isinstance(exam, dict):
                    continue

                exam_id = exam.get('id')

                # Imtihon ma'lumotlari
                subject = exam.get('subject', {})
                subject_id = subject.get('id') if isinstance(
                    subject, dict) else None
                subject_name = subject.get('name') if isinstance(
                    subject, dict) else None

                exam_type = exam.get('examType', {})
                exam_type_name = exam_type.get(
                    'name') if isinstance(exam_type, dict) else None
                exam_type_code = exam_type.get(
                    'code') if isinstance(exam_type, dict) else None

                faculty = exam.get('faculty', {})
                faculty_name = faculty.get('name') if isinstance(
                    faculty, dict) else None

                department = exam.get('department', {})
                department_name = department.get(
                    'name') if isinstance(department, dict) else None

                education_year = exam.get('educationYear', {})
                education_year_name = education_year.get(
                    'name') if isinstance(education_year, dict) else None

                semester = exam.get('semester', {})
                semester_name = semester.get(
                    'name') if isinstance(semester, dict) else None

                # Har bir talaba uchun
                for student in students:
                    if not isinstance(student, dict):
                        continue

                    excel_data.append({
                        'exam_id': exam_id,
                        'student_id': student.get('id'),
                        'student_hemis_id': student.get('student_id_number'),
                        'student_full_name': student.get('full_name'),
                        'group_id': group_id,
                        'group_name': group_name,
                        'subject_id': subject_id,
                        'subject_name': subject_name,
                        'exam_type_name': exam_type_name,
                        'exam_type_code': exam_type_code,
                        'faculty_name': faculty_name,
                        'department_name': department_name,
                        'education_year_name': education_year_name,
                        'semester_name': semester_name,
                        'grade': ''  # Bo'sh ustun
                    })
                    records_added += 1

            print(f"  ✅ {records_added} ta yozuv qo'shildi")
            processed_groups += 1

            # Delay qo'shish (guruhlar orasida)
            time.sleep(API_DELAY * 2)

        except Exception as e:
            print(f"  ❌ Xatolik: {e}")
            skipped_groups += 1
            continue

    # 6. DataFrame yaratish va Excel ga saqlash
    if excel_data:
        df = pd.DataFrame(excel_data)

        # Fayl nomi (sana va vaqt bilan)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"exam_report.xlsx"

        # Excel faylga saqlash
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Imtihonlar', index=False)

            # Ustunlar kengligini sozlash
            worksheet = writer.sheets['Imtihonlar']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        print("\n" + "=" * 60)
        print(f"✅ Muvaffaqiyatli yakunlandi!")
        print(f"📊 Jami yozuvlar: {len(excel_data)}")
        print(f"📁 Fayl nomi: {filename}")
        print(f"📈 Qayta ishlangan guruhlar: {processed_groups}")
        print(f"⏭️  O'tkazib yuborilgan: {skipped_groups}")
        print("=" * 60)

        # Statistikani ko'rsatish
        print("\n📈 Statistika:")
        print(f"  - Guruhlar soni: {df['group_id'].nunique()}")
        print(f"  - Imtihonlar soni: {df['exam_id'].nunique()}")
        print(f"  - Talabalar soni: {df['student_id'].nunique()}")
        print(f"  - Fanlar soni: {df['subject_id'].nunique()}")

        # Fanlar ro'yxati
        print("\n📚 Fanlar:")
        for subject in df['subject_name'].unique():
            if pd.notna(subject):
                count = df[df['subject_name'] == subject].shape[0]
                print(f"  - {subject}: {count} ta baholash")

        return df
    else:
        print("\n❌ Hech qanday ma'lumot topilmadi!")
        return None


def fetch_single_group_data(group_id: int):
    """Faqat bitta guruh uchun ma'lumot olish (test uchun)"""
    print(f"\n🎯 Test: Faqat {group_id} guruhi uchun")

    excel_data = []

    # Imtihonlarni olish
    exams = fetch_exams_by_group(group_id)
    print(f"📝 Imtihonlar: {len(exams)} ta")

    if not exams:
        print("❌ Imtihonlar topilmadi!")
        return None

    # Talabalarni olish
    students = fetch_students_by_group(group_id)
    print(f"👥 Talabalar: {len(students)} ta")

    if not students:
        print("❌ Talabalar topilmadi!")
        return None

    for exam in exams:
        for student in students:
            excel_data.append({
                'exam_id': exam['id'],
                'student_id': student.get('id'),
                'student_hemis_id': student.get('student_id_number'),
                'student_full_name': student.get('full_name'),
                'group_id': group_id,
                'group_name': exam.get('group', {}).get('name'),
                'subject_id': exam.get('subject', {}).get('id'),
                'subject_name': exam.get('subject', {}).get('name'),
                'exam_type_name': exam.get('examType', {}).get('name'),
                'exam_type_code': exam.get('examType', {}).get('code'),
                'faculty_name': exam.get('faculty', {}).get('name'),
                'department_name': exam.get('department', {}).get('name'),
                'education_year_name': exam.get('educationYear', {}).get('name'),
                'semester_name': exam.get('semester', {}).get('name'),
                'grade': ''
            })

    if excel_data:
        df = pd.DataFrame(excel_data)
        filename = f"hemis_exam_group_{group_id}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n✅ Saqlandi: {filename}")
        print(f"📊 Yozuvlar soni: {len(df)}")
        return df
    return None


if __name__ == "__main__":
    # Token mavjudligini tekshirish
    if not HEMIS_TOKEN:
        print("❌ Iltimos, HEMIS_TOKEN o'zgaruvchisiga tokeningizni kiriting!")
        print("Dastur to'xtatildi.")
        exit(1)

    try:
        # Test uchun: faqat bitta guruhni tekshirish
        # print("🧪 Test rejimi: IQ-121-21S guruhi tekshirilmoqda...")
        # print("=" * 60)

        # # Test qilish
        # test_group_id = 102  # IQ-121-21S guruhi
        # test_df = fetch_single_group_data(test_group_id)

        # if test_df is not None:
        #     print("\n" + "=" * 60)
        #     print("✅ Test muvaffaqiyatli! To'liq eksportni boshlash...")
        #     print("=" * 60)

        #     # To'liq ma'lumot olish
        # else:
        #     print("\n❌ Test muvaffaqiyatsiz. API formatini tekshiring.")
        print("=" * 60)
        print("\n✅ Ma'lumot olish boshlandi!")
        print("=" * 60)
        df = create_exam_student_excel()

    except KeyboardInterrupt:
        print("\n\n⚠️ Dastur foydalanuvchi tomonidan to'xtatildi!")
    except Exception as e:
        print(f"\n❌ Xatolik yuz berdi: {e}")
        import traceback
        traceback.print_exc()
