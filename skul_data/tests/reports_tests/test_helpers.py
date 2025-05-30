import random
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.contrib.auth import get_user_model
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student, Subject
from skul_data.reports.models.report import (
    ReportTemplate,
    GeneratedReport,
)
from skul_data.reports.models.academic_record import (
    AcademicRecord,
    TeacherComment,
)


User = get_user_model()


def create_test_school(name="Test School"):
    """Create a test school with unique constraints"""
    # Make school name unique using timestamp
    unique_name = f"{name}_{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}"

    # Generate unique username based on school name
    username = f"admin_{unique_name.lower().replace(' ', '_').replace('-', '_')}"
    admin_user = User.objects.create_user(
        email=f"admin_{timezone.now().microsecond}@{unique_name.replace(' ', '').lower()}.com",
        username=username,
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
        is_staff=True,
    )

    # Generate a unique code based on the school name with timestamp
    unique_code = f"{unique_name.replace(' ', '')[0:3].upper()}{timezone.now().strftime('%m%d%H%M%S')}"

    school = School.objects.create(
        name=unique_name,
        email=f"contact_{timezone.now().microsecond}@{unique_name.replace(' ', '').lower()}.com",
        schooladmin=admin_user,
        code=unique_code,
    )

    # Ensure the admin has a school_admin_profile
    from skul_data.users.models.school_admin import SchoolAdmin

    SchoolAdmin.objects.create(user=admin_user, school=school, is_primary=True)

    return school, admin_user


def create_test_teacher(school, email="teacher@test.com", **kwargs):
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="testpass",
        user_type=User.TEACHER,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Teacher"),
    )

    teacher = Teacher.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get("phone_number", "+254700000000"),
        status=kwargs.get("status", "ACTIVE"),
    )
    return teacher


def create_test_parent(school, email="parent@test.com", **kwargs):
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="testpass",
        user_type=User.PARENT,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Parent"),
    )

    parent = Parent.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get("phone_number", "+254700000000"),
    )
    return parent


def create_test_student(school, parent=None, **kwargs):
    """Create a test student with unique constraints"""
    # Generate unique first/last names based on kwargs or timestamp
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S_%f")
    first_name = kwargs.get("first_name", f"Test{timestamp}")
    last_name = kwargs.get("last_name", f"Student{timestamp}")

    student = Student.objects.create(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=kwargs.get(
            "date_of_birth", timezone.now().date() - timedelta(days=365 * 10)
        ),
        admission_date=kwargs.get("admission_date", timezone.now().date()),
        gender=kwargs.get("gender", "M"),
        school=school,
        status=kwargs.get("status", "ACTIVE"),
        parent=parent,
    )

    if parent:
        # Set both parent reference and guardian relationship
        student.parent = parent
        student.guardians.add(parent)
        parent.children.add(student)
        student.save()

    return student


def create_test_class(school, name=None, teacher=None, academic_year=None):
    """Create a test class with unique constraints to avoid validation errors"""
    # Generate unique name based on timestamp to avoid duplicates
    if name is None:
        # Use microseconds for uniqueness
        name = f"TestClass_{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}"

    # Ensure academic year is set
    if academic_year is None:
        academic_year = f"2023-{timezone.now().year}"

    try:
        # Try to get existing class first
        existing_class = SchoolClass.objects.filter(
            name=name, school=school, academic_year=academic_year
        ).first()

        if existing_class:
            # If class exists, modify the name to make it unique
            name = f"{name}_{random.randint(1000, 9999)}"
    except:
        pass

    school_class = SchoolClass.objects.create(
        name=name,
        school=school,
        grade_level="Grade 3",
        level="PRIMARY",
        academic_year=academic_year,
    )

    if teacher:
        # Assign as class teacher (FK)
        school_class.class_teacher = teacher
        school_class.save()

        # Add to assigned_classes (M2M) - ensure the relationship exists
        if hasattr(teacher, "assigned_classes"):
            teacher.assigned_classes.add(school_class)

        # Also ensure reverse relationship
        teacher.save()

    return school_class


def create_test_report_template(school, created_by, **kwargs):
    """Create a test report template with unique constraints"""
    # Generate unique name using timestamp to avoid duplicates
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S_%f")
    name = kwargs.get("name", f"Test Template {timestamp}")

    return ReportTemplate.objects.create(
        name=name,
        template_type=kwargs.get("template_type", "ACADEMIC"),
        description=kwargs.get("description", "Test description"),
        content=kwargs.get("content", {"fields": [], "layout": "portrait"}),
        is_system=kwargs.get("is_system", False),
        school=school if not kwargs.get("is_system") else None,
        created_by=created_by,
        preferred_format=kwargs.get("preferred_format", "PDF"),
    )


def create_test_generated_report(school, report_type, generated_by, **kwargs):
    file = SimpleUploadedFile(
        "test_report.pdf", b"test content", content_type="application/pdf"
    )

    return GeneratedReport.objects.create(
        title=kwargs.get("title", "Test Report"),
        report_type=report_type,
        school=school,
        generated_by=generated_by,
        status=kwargs.get("status", "DRAFT"),
        file=file,
        file_format=kwargs.get("file_format", "PDF"),
        data=kwargs.get("data", {"test": "data"}),
        parameters=kwargs.get("parameters", {}),
        is_public=kwargs.get("is_public", False),
        requires_approval=kwargs.get("requires_approval", False),
    )


def create_test_subject(school, name="Math", **kwargs):
    # Add random suffix to make name unique
    unique_name = f"{name}_{random.randint(1, 1000)}"
    return Subject.objects.create(
        name=unique_name,
        code=kwargs.get("code", f"{name.upper()[:3]}{random.randint(100, 999)}"),
        description=kwargs.get("description", f"Test {name} subject"),
        school=school,
    )


def create_test_academic_record(student, subject, teacher, **kwargs):
    # If subject is a string, create a Subject instance
    if isinstance(subject, str):
        subject = create_test_subject(student.school, name=subject)

    return AcademicRecord.objects.create(
        student=student,
        subject=subject,  # Now this is a Subject instance
        teacher=teacher,
        term=kwargs.get("term", "Term 1"),
        school_year=kwargs.get("school_year", "2023"),
        score=kwargs.get("score", 75.5),
        grade=kwargs.get("grade", "B"),
        subject_comments=kwargs.get("subject_comments", "Good performance"),
        is_published=kwargs.get("is_published", True),
    )


def create_test_teacher_comment(student, teacher, **kwargs):
    return TeacherComment.objects.create(
        student=student,
        teacher=teacher,
        term=kwargs.get("term", "Term 1"),
        school_year=kwargs.get("school_year", "2023"),
        comment_type=kwargs.get("comment_type", "GENERAL"),
        content=kwargs.get("content", "Test comment"),
        is_approved=kwargs.get("is_approved", True),
    )
