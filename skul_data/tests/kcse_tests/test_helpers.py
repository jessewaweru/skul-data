import random
import uuid
from datetime import date, timedelta
from django.utils import timezone
from skul_data.schools.models.school import School
from skul_data.students.models.student import Student, StudentStatus
from skul_data.users.models.parent import Parent
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Subject
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.kcse.models.kcse import (
    KCSEResult,
    KCSESubjectResult,
    KCSESchoolPerformance,
    KCSESubjectPerformance,
)
from skul_data.users.models.base_user import User
from skul_data.users.models.school_admin import SchoolAdmin


def create_test_school(name="Test School"):
    # Generate unique username based on school name
    username = f"admin_{name.lower().replace(' ', '_')}"
    admin_user = User.objects.create_user(
        email=f"admin@{name.replace(' ', '').lower()}.com",
        username=username,
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
        is_staff=True,
    )

    # Generate a unique code based on the school name with random suffix
    random_suffix = random.randint(1000, 9999)
    unique_code = f"{name.replace(' ', '')[0:3].upper()}{random_suffix}"

    school = School.objects.create(
        name=name,
        email=f"contact@{name.replace(' ', '').lower()}.com",
        code=unique_code,
        term_start_date=timezone.now().date() - timedelta(days=30),
        term_end_date=timezone.now().date() + timedelta(days=30),
        current_term="term_1",
        current_school_year="2023",
    )

    # Create SchoolAdmin profile
    SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

    return school, admin_user


def create_test_teacher(school, email=None, **kwargs):
    if not email:
        base_email = f"teacher_{uuid.uuid4().hex[:6]}@test.com"
        email = kwargs.get("email", base_email)

    username = f"teacher_{uuid.uuid4().hex[:6]}"
    user = User.objects.create_user(
        email=email,
        username=username,
        password="testpass",
        user_type=User.TEACHER,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Teacher"),
    )
    return Teacher.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get("phone_number", "+254700000000"),
        status=kwargs.get("status", "ACTIVE"),
    )


def create_test_parent(school, email=None, **kwargs):
    if not email:
        email = f"parent_{uuid.uuid4().hex[:8]}@test.com"

    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="testpass",
        user_type=User.PARENT,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Parent"),
    )
    return Parent.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get("phone_number", "+254700000000"),
    )


def create_test_student(school, **kwargs):
    teacher = kwargs.get("teacher") or create_test_teacher(school)
    parent = kwargs.get("parent") or create_test_parent(school)

    # Generate unique student attributes
    unique_id = uuid.uuid4().hex[:6]

    # Generate a random admission number if not provided
    admission_number = kwargs.get(
        "admission_number", f"ADM-{timezone.now().year}-{random.randint(1000, 9999)}"
    )

    return Student.objects.create(
        first_name=f"Test{unique_id}",
        last_name=f"Student{unique_id}",
        date_of_birth=timezone.now().date()
        - timedelta(days=365 * 10 + random.randint(0, 1000)),
        admission_date=kwargs.get("admission_date", timezone.now().date()),
        gender=kwargs.get("gender", "M"),
        school=school,
        parent=parent,
        teacher=teacher,
        admission_number=admission_number,
        student_class=kwargs.get("student_class"),  # Make sure this is passed through
        status=kwargs.get("status", "GRADUATED"),
    )


def create_test_class(school, name="Class 1", **kwargs):
    return SchoolClass.objects.create(
        name=name,
        school=school,
        grade_level=kwargs.get("grade_level", "Form 4"),
    )


def create_test_subject(school, name="Mathematics", **kwargs):
    school_abbrev = school.code[:3].upper()
    unique_code = f"{school_abbrev}-{uuid.uuid4().hex[:4]}"

    return Subject.objects.create(
        name=name,
        school=school,
        code=kwargs.get("code", unique_code),
        description=kwargs.get("description", "Test subject description"),
    )


def create_test_kcse_result(student, year=2023, **kwargs):
    return KCSEResult.objects.create(
        school=student.school,
        student=student,
        year=year,
        index_number=f"{student.school.code[:3]}{year}{random.randint(1000, 9999)}",
        mean_grade=kwargs.get("mean_grade", "B+"),
        mean_points=kwargs.get("mean_points", 10.5),
        division=kwargs.get("division", 1),
        uploaded_by=kwargs.get("uploaded_by"),
        is_published=kwargs.get("is_published", False),
    )


def create_test_kcse_subject_result(kcse_result, subject, **kwargs):
    return KCSESubjectResult.objects.create(
        kcse_result=kcse_result,
        subject=subject,
        subject_code=subject.code,
        grade=kwargs.get("grade", "B+"),
        points=kwargs.get("points", 10),
        subject_teacher=kwargs.get("subject_teacher"),
    )


def create_test_kcse_school_performance(school, year=2023, **kwargs):
    return KCSESchoolPerformance.objects.create(
        school=school,
        year=year,
        mean_grade=kwargs.get("mean_grade", "B"),
        mean_points=kwargs.get("mean_points", 9.5),
        total_students=kwargs.get("total_students", 100),
        university_qualified=kwargs.get("university_qualified", 70),
    )


def create_test_kcse_subject_performance(school_performance, subject, **kwargs):
    return KCSESubjectPerformance.objects.create(
        school_performance=school_performance,
        subject=subject,
        subject_code=subject.code,
        mean_score=kwargs.get("mean_score", 8.5),
        mean_grade=kwargs.get("mean_grade", "B-"),
        total_students=kwargs.get("total_students", 100),
        entered=kwargs.get("entered", 100),
        passed=kwargs.get("passed", 80),
        subject_teacher=kwargs.get("subject_teacher"),
    )
