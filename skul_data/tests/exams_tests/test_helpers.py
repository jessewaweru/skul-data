import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Student, Subject
from skul_data.users.models.teacher import Teacher
from skul_data.exams.models.exam import (
    ExamType,
    GradingSystem,
    GradeRange,
    Exam,
    ExamSubject,
    ExamResult,
    TermReport,
)
from skul_data.users.models.base_user import User
from skul_data.users.models.parent import Parent
from skul_data.users.models.role import Role
from skul_data.users.models.role import Permission
from django.contrib.auth import get_user_model
from skul_data.users.models.school_admin import SchoolAdmin


def create_test_exam_type(name="Test Exam Type", is_default=False):
    return ExamType.objects.create(name=name, is_default=is_default)


def create_test_grading_system(school, name="Test Grading System", is_default=False):
    return GradingSystem.objects.create(school=school, name=name, is_default=is_default)


def create_test_grade_range(
    grading_system,
    min_score=0,
    max_score=100,
    grade="A",
    remark="Excellent",
    points=Decimal("12.0"),
):
    return GradeRange.objects.create(
        grading_system=grading_system,
        min_score=min_score,
        max_score=max_score,
        grade=grade,
        remark=remark,
        points=points,
    )


# Updated exam creation to ensure proper serializer field names
def create_test_exam(school_class, exam_type, grading_system, **kwargs):
    today = timezone.now().date()
    unique_id = uuid.uuid4().hex[:4]
    return Exam.objects.create(
        name=kwargs.get("name", f"Test Exam {unique_id}"),
        exam_type=exam_type,
        school=school_class.school,
        school_class=school_class,
        term=kwargs.get("term", "Term 1"),
        academic_year=kwargs.get("academic_year", "2023"),
        start_date=kwargs.get("start_date", today),
        end_date=kwargs.get("end_date", today + timedelta(days=7)),
        grading_system=grading_system,
        created_by=kwargs.get("created_by", None),
        include_in_term_report=kwargs.get("include_in_term_report", True),
    )


def create_test_exam_subject(exam, subject, teacher=None, **kwargs):
    return ExamSubject.objects.create(
        exam=exam,
        subject=subject,
        teacher=teacher,
        max_score=kwargs.get("max_score", 100),
        pass_score=kwargs.get("pass_score", 50),
        weight=kwargs.get("weight", 100),
    )


def create_test_exam_result(exam_subject, student, **kwargs):
    return ExamResult.objects.create(
        exam_subject=exam_subject,
        student=student,
        score=kwargs.get("score", Decimal("75.0")),
        is_absent=kwargs.get("is_absent", False),
        teacher_comment=kwargs.get("teacher_comment", "Good performance"),
    )


def test_create_exam_result(self):
    exam_result = create_test_exam_result(
        self.exam_subject, create_test_student(self.school), score=Decimal("75.0")
    )
    self.assertEqual(str(exam_result), f"{exam_result.student} - {self.subject} (75.0)")


def create_test_term_report(student, school_class, **kwargs):
    return TermReport.objects.create(
        student=student,
        school_class=school_class,
        term=kwargs.get("term", "Term 1"),
        academic_year=kwargs.get("academic_year", "2023"),
        total_score=kwargs.get("total_score", Decimal("450.0")),
        average_score=kwargs.get("average_score", Decimal("75.0")),
        overall_grade=kwargs.get("overall_grade", "B+"),
        overall_position=kwargs.get("overall_position", 5),
        class_average=kwargs.get("class_average", Decimal("65.0")),
        class_highest=kwargs.get("class_highest", Decimal("95.0")),
        class_lowest=kwargs.get("class_lowest", Decimal("30.0")),
        is_published=kwargs.get("is_published", False),
    )


def create_default_grading_system(school):
    grading_system = create_test_grading_system(school, "Default Grading System", True)

    grade_ranges = [
        (90, 100, "A", "Excellent"),
        (85, 89, "A-", "Very Good"),
        (80, 84, "B+", "Good Plus"),
        (75, 79, "B", "Good"),
        (70, 74, "B-", "Above Average"),
        (65, 69, "C+", "Average Plus"),
        (60, 64, "C", "Average"),
        (55, 59, "C-", "Below Average"),
        (50, 54, "D+", "Pass Plus"),
        (45, 49, "D", "Pass"),
        (40, 44, "D-", "Marginal"),
        (0, 39, "E", "Fail"),
    ]

    for min_score, max_score, grade, remark in grade_ranges:
        create_test_grade_range(
            grading_system,
            min_score=min_score,
            max_score=max_score,
            grade=grade,
            remark=remark,
            points=Decimal(
                str(12 - (grade_ranges.index((min_score, max_score, grade, remark))))
            ),
        )

    return grading_system


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

    # Use date objects instead of datetime
    term_start = timezone.now().date() - timedelta(days=30)
    term_end = timezone.now().date() + timedelta(days=30)

    school = School.objects.create(
        name=name,
        email=f"contact@{name.replace(' ', '').lower()}.com",
        schooladmin=admin_user,
        code=unique_code,
        term_start_date=term_start,
        term_end_date=term_end,
        current_term="term_1",
        current_school_year="2023",
    )

    # ADD THIS: Create SchoolAdmin profile
    from skul_data.users.models.school_admin import SchoolAdmin

    SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

    # Create admin role with permissions
    admin_role = Role.objects.create(name="Admin", school=school, role_type="SYSTEM")
    permissions = [
        ("manage_grading_systems", "Can manage grading systems"),
        ("manage_exams", "Can manage exams"),
        ("view_exam_results", "Can view exam results"),
        ("enter_exam_results", "Can enter exam results"),  # ADD THIS
        ("publish_exam_results", "Can publish exam results"),  # ADD THIS
        ("generate_term_reports", "Can generate term reports"),
    ]
    for code, name in permissions:
        perm, _ = Permission.objects.get_or_create(code=code, name=name)
        admin_role.permissions.add(perm)

    admin_user.role = admin_role
    admin_user.save()

    return school, admin_user


def create_test_teacher(school, email=None, **kwargs):
    if not email:
        base_email = f"teacher_{uuid.uuid4().hex[:6]}@test.com"
        email = kwargs.get("email", base_email)

    username = f"teacher_{uuid.uuid4().hex[:6]}"  # Unique username
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
        email = f"parent_{uuid.uuid4().hex[:8]}@test.com"  # Generate unique email

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

    # Use date object for date_of_birth and admission_date
    birth_date = timezone.now().date() - timedelta(
        days=365 * 10 + random.randint(0, 1000)
    )
    admission_date = kwargs.get("admission_date", timezone.now().date())

    student = Student.objects.create(
        first_name=f"Test{unique_id}",
        last_name=f"Student{unique_id}",
        date_of_birth=birth_date,
        admission_date=admission_date,
        gender=kwargs.get("gender", "M"),
        school=school,
        parent=parent,
        teacher=teacher,
        # Use the correct field name from your Student model
        student_class=kwargs.get("student_class"),  # This is the ForeignKey field
    )

    return student


# Alternative helper to create student with class
def create_test_student_with_class(school, school_class, **kwargs):
    """Create a student and assign them to a specific class"""
    student = create_test_student(school, student_class=school_class, **kwargs)
    return student


def create_test_class(school, name="Class 1", **kwargs):
    # Get the first valid choice from the model's grade_level choices
    grade_choices = SchoolClass._meta.get_field("grade_level").choices
    default_grade = grade_choices[0][0] if grade_choices else "1"

    return SchoolClass.objects.create(
        name=name,
        school=school,
        grade_level=kwargs.get("grade_level", default_grade),
    )


def create_test_subject(school, name="Mathematics", **kwargs):
    # Generate unique code using school abbreviation and random string
    school_abbrev = school.code[:3].upper()
    unique_code = f"{school_abbrev}-{uuid.uuid4().hex[:4]}"

    return Subject.objects.create(
        name=name,
        school=school,
        code=kwargs.get("code", unique_code),  # Use unique code
        description=kwargs.get("description", "Test subject description"),
    )


def create_test_user(email=None, username=None, password="testpass", **kwargs):
    """
    Creates a test user with sensible defaults.

    Args:
        email: User email (default: generates a unique email)
        username: Username (default: email prefix if email provided, otherwise random)
        password: Password (default: "testpass")
        **kwargs: Additional user attributes including:
            - user_type: One of User.USER_TYPE_CHOICES
            - school: School instance (required for non-superusers)
            - role: Role instance
            - role_permissions: List of permission codes to assign to role
            - is_staff: Boolean (default False)
            - is_superuser: Boolean (default False)

    Returns:
        User instance
    """
    User = get_user_model()

    # Generate unique email if not provided
    if email is None:
        unique_id = uuid.uuid4().hex[:8]
        email = f"user_{unique_id}@test.com"

    # Generate username if not provided
    if username is None:
        username = email.split("@")[0]

    # Create the user
    user = User.objects.create_user(
        email=email,
        username=username,
        password=password,
        **{
            k: v
            for k, v in kwargs.items()
            if k not in ["school", "role", "role_permissions"]
        },
    )

    # Handle role creation if permissions are specified
    if "role_permissions" in kwargs:
        school = kwargs.get("school")
        if not school:
            # Create a school if none provided but permissions are requested
            school, _ = School.objects.get_or_create(
                name="Test School",
                defaults={"email": "admin@test.com", "code": "TEST123"},
            )

        # Create or get role
        role_name = kwargs.get("role_name", "Test Role")
        role, _ = Role.objects.get_or_create(
            name=role_name, school=school, defaults={"role_type": "CUSTOM"}
        )

        # Add permissions to role
        for perm_code in kwargs["role_permissions"]:
            perm, _ = Permission.objects.get_or_create(
                code=perm_code, defaults={"name": f"Can {perm_code.replace('_', ' ')}"}
            )
            role.permissions.add(perm)

        user.role = role
        user.save()

    # Handle school admin profile creation
    if kwargs.get("user_type") == User.SCHOOL_ADMIN and "school" in kwargs:
        SchoolAdmin.objects.get_or_create(
            user=user, school=kwargs["school"], defaults={"is_primary": True}
        )

    return user
