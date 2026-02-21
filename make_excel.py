import requests
import time
import pandas as pd
from config import HEMIS_TOKEN


EDUCATION_YEAR = 2025
SEMESTR = 13  # 11->1-semestr, 12->2-semestr
# 13 -> Yakuniy Nazorat; 12 -> Oraliq nazorat; 11 -> Joriy nazorat; 17 -> 1-on; 18 -> 2-on;
EXAM_TYPE = 13

headers = {
    "Authorization": f"Bearer {HEMIS_TOKEN}"
}
API_DELAY = 0.1  # 100ms delay between requests
PAGE_LIMIT = 200  # Maximum items per request


def fetch_student_info(student_id):
    """Fetch individual student details from student-info API"""
    response = requests.get(
        f"https://talaba.timeedu.uz/rest/v1/data/student-info?student_id={student_id}",
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        student_data = data.get("data", {})
        return {
            'student_id': student_data.get('id'),
            'student_full_name': student_data.get('full_name'),
            'student_hemis_id': student_data.get('student_id_number'),
        }
    return None


def fetch_student_subjects(education_year, semester):
    """Fetch subjects assigned to students (student-subject-list API)"""
    page = 1
    all_subjects = []

    # This API returns which students are assigned to which subjects
    # Key fields: _student (student_id), _group (group_id), _subject (subject_id)

    while True:
        response = requests.get(
            f"https://talaba.timeedu.uz/rest/v1/data/student-subject-list",
            params={
                "limit": PAGE_LIMIT,
                "page": page,
                "_education_year": education_year,
                "_semester": semester,
            },
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            pagination = data.get("data", {}).get("pagination", {})
            total_pages = pagination.get("pageCount", 0)

            for item in items:
                curriculum_subject = item.get("curriculumSubject", {})
                subject = curriculum_subject.get("subject", {})

                all_subjects.append({
                    'student_id': item.get('_student'),
                    'group_id': item.get('_group'),
                    'subject_id': subject.get('id'),
                    'subject_name': subject.get('name'),
                    'subject_code': subject.get('code'),
                })

            print(
                f"Student-Subjects: Page {page}/{total_pages} loaded ({len(items)} items)")

            if page >= total_pages:
                break

            page += 1
            time.sleep(API_DELAY)
        else:
            print(f"Error fetching student-subjects: {response.status_code}")
            break

    return all_subjects


def fetch_exam_list(education_year, semester, exam_type):
    """Fetch exam list (subject-exam-list API)"""
    page = 1
    all_exams = []

    # This API returns exams with their group_id
    # Key fields: id (exam_id), group.id (group_id), subject.id (subject_id)

    while True:
        response = requests.get(
            f"https://talaba.timeedu.uz/rest/v1/data/subject-exam-list",
            params={
                "limit": PAGE_LIMIT,
                "page": page,
                "_semester": semester,
                "_exam_type": exam_type,
                "_education_year": education_year
            },
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            pagination = data.get("data", {}).get("pagination", {})
            total_pages = pagination.get("pageCount", 0)

            for item in items:
                subject = item.get("subject", {})
                semester_info = item.get("semester", {})
                education_year_info = item.get("educationYear", {})
                group = item.get("group", {})
                exam_type_info = item.get("examType", {})
                faculty = item.get("faculty", {})
                department = item.get("department", {})

                all_exams.append({
                    'exam_id': item.get('id'),
                    'group_id': group.get('id'),
                    'group_name': group.get('name'),
                    'subject_id': subject.get('id'),
                    'subject_name': subject.get('name'),
                    'subject_code': subject.get('code'),
                    'faculty_id': faculty.get('id'),
                    'faculty_name': faculty.get('name'),
                    'department_id': department.get('id'),
                    'department_name': department.get('name'),
                    'exam_type_code': exam_type_info.get('code'),
                    'exam_type_name': exam_type_info.get('name'),
                    'education_year_code': education_year_info.get('code'),
                    'education_year_name': education_year_info.get('name'),
                    'semester_code': semester_info.get('code'),
                    'semester_name': semester_info.get('name'),
                })

            print(
                f"Exams: Page {page}/{total_pages} loaded ({len(items)} items)")

            if page >= total_pages:
                break

            page += 1
            time.sleep(API_DELAY)
        else:
            print(f"Error fetching exams: {response.status_code}")
            break

    return all_exams


def create_excel_report():
    """Main function to fetch all data and create Excel report"""

    # STEP 1: Fetch all exams
    print("Fetching exam list...")
    exams_data = fetch_exam_list(
        education_year=EDUCATION_YEAR,
        semester=SEMESTR,
        exam_type=EXAM_TYPE
    )
    exams_df = pd.DataFrame(exams_data)
    print(f"Total exams fetched: {len(exams_df)}")

    # STEP 2: Fetch all student-subject assignments
    print("\nFetching student-subject assignments...")
    subjects_data = fetch_student_subjects(
        education_year=EDUCATION_YEAR,
        semester=SEMESTR
    )
    subjects_df = pd.DataFrame(subjects_data)
    print(f"Total student-subject records fetched: {len(subjects_df)}")

    # STEP 3: Get unique student IDs
    unique_student_ids = subjects_df['student_id'].unique(
    ) if not subjects_df.empty else []
    print(f"\nFetching info for {len(unique_student_ids)} unique students...")

    # STEP 4: Fetch student info for each unique student
    students_info = []
    for student_id in unique_student_ids:
        student_info = fetch_student_info(student_id)
        if student_info:
            students_info.append(student_info)
            if len(students_info) % 100 == 0:  # Progress indicator
                print(
                    f"Fetched {len(students_info)}/{len(unique_student_ids)} students")
        time.sleep(API_DELAY)

    students_df = pd.DataFrame(students_info)
    print(f"Total student info records: {len(students_df)}")

    # STEP 5: First, merge student-subjects with student info to get full names
    print("\nMerging student data...")
    if not subjects_df.empty and not students_df.empty:
        students_with_names = pd.merge(
            subjects_df,
            students_df,
            on='student_id',
            how='inner'  # Only keep students we have info for
        )
    else:
        students_with_names = subjects_df.copy()

    print(f"Students with names: {len(students_with_names)}")

    # STEP 6: Now merge exams with students based on group_id AND subject_id
    print("Merging exams with students...")

    if not exams_df.empty and not students_with_names.empty:
        # Critical: Merge on both group_id AND subject_id
        # This ensures a student gets an exam only if they are in the same group AND study the same subject
        final_df = pd.merge(
            exams_df,
            students_with_names,
            on=['group_id', 'subject_id'],  # Merge on both keys!
            how='inner'  # Only keep matches where student belongs to that group and subject
        )
    else:
        final_df = pd.DataFrame()

    print(f"Final records after merge: {len(final_df)}")

    # STEP 7: Select and rename columns for final output
    if not final_df.empty:
        # Define the columns we want in the final Excel
        output_columns = {
            'exam_id': 'exam_id',
            'student_hemis_id': 'student_hemis_id',
            'student_full_name': 'student_full_name',
            'group_name': 'group_name',
            'subject_name': 'subject_name',
            'exam_type_name': 'exam_type_name',
            'grade': '',
            'education_year_name': 'education_year_name',
            'department_name': 'department_name',
            'faculty_name': 'faculty_name',
            'student_id': 'student_id',
            'subject_code': 'subject_code',
            'exam_type_code': 'exam_type_code',
            'education_year_code': 'education_year_code',
        }

        # Create final DataFrame with only required columns that exist
        available_columns = [
            col for col in output_columns.keys() if col in final_df.columns]
        final_result = final_df[available_columns].copy()

        # Rename columns
        final_result.rename(columns={k: v for k, v in output_columns.items(
        ) if k in final_df.columns}, inplace=True)

        # Remove duplicates (just in case)
        final_result.drop_duplicates(inplace=True)

        # Sort by exam_id and student_id for better readability
        final_result.sort_values(['exam_id', 'student_id'], inplace=True)

        # Export to Excel
        output_file = 'exam_report.xlsx'
        final_result.to_excel(output_file, index=False, engine='openpyxl')

        print(f"\n✅ Excel file '{output_file}' created successfully!")
        print(f"Total records: {len(final_result)}")
        print("\nColumns in final file:")
        for col in final_result.columns:
            print(f"  - {col}")

        # Show sample of duplicate check
        exam_counts = final_result['exam_id'].value_counts()
        print(f"\n📊 Statistics:")
        print(f"  - Unique exams: {final_result['exam_id'].nunique()}")
        print(f"  - Unique students: {final_result['student_id'].nunique()}")
        print(
            f"  - Average students per exam: {len(final_result)/final_result['exam_id'].nunique():.1f}")

    else:
        print("❌ No data to export!")


if __name__ == "__main__":
    create_excel_report()
