import random
import uuid
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass, ClassAttendance
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.teacher import Teacher, TeacherAttendance
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student, Subject
from skul_data.documents.models.document import Document, DocumentCategory
from skul_data.reports.models.report import GeneratedReport, ReportTemplate
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.analytics.models.analytics import (
    AnalyticsDashboard,
    CachedAnalytics,
    AnalyticsAlert,
)
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.documents.models.document import DocumentShareLink

User = get_user_model()


def create_test_action_log(
    user=None,
    category=ActionCategory.OTHER,
    content_type=None,
    object_id=None,
    **kwargs,
):
    """Helper to create action log entries for testing"""
    # Generate a system user_tag if no user is provided
    user_tag = kwargs.get("user_tag", None)
    if user is not None:
        user_tag = user.user_tag
    elif user_tag is None:
        # Create a special system user_tag for null user cases
        user_tag = uuid.UUID("00000000-0000-0000-0000-000000000000")

    return ActionLog.objects.create(
        user=user,
        user_tag=user_tag,
        action=kwargs.get("action", "Test action"),
        category=category,
        ip_address=kwargs.get("ip_address", "127.0.0.1"),
        user_agent=kwargs.get("user_agent", "TestAgent/1.0"),
        content_type=content_type,
        object_id=object_id,
        metadata=kwargs.get("metadata", {}),
        timestamp=kwargs.get("timestamp", timezone.now()),
    )


def create_test_school(name=None):
    if name is None:
        unique_id = uuid.uuid4().hex[:6]
        name = f"Test School {unique_id}"

    # Generate unique username with random suffix
    base_username = f"admin_{name.lower().replace(' ', '_')}"
    username = f"{base_username}_{uuid.uuid4().hex[:4]}"

    admin_user = User.objects.create_user(
        email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
        username=username,
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
        is_staff=True,
        first_name="Test",  # Ensure these are set
        last_name="Admin",
    )

    # Rest of your function remains the same...
    random_suffix = random.randint(1000, 9999)
    unique_code = f"{name.replace(' ', '')[0:3].upper()}{random_suffix}"

    school = School.objects.create(
        name=name,
        email=f"contact_{uuid.uuid4().hex[:4]}@test.com",
        schooladmin=admin_user,
        code=unique_code,
        term_start_date=timezone.now().date() - timedelta(days=30),
        term_end_date=timezone.now().date() + timedelta(days=30),
        current_term="term_1",
        current_school_year="2023",
    )

    # Create admin role with permissions
    admin_role = Role.objects.create(name="Admin", school=school, role_type="SYSTEM")
    permissions = [
        ("view_analytics", "Can view analytics"),
        ("manage_analytics", "Can manage analytics"),
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
    student = Student.objects.create(
        first_name=f"Test{unique_id}",
        last_name=f"Student{unique_id}",
        date_of_birth=timezone.now().date()
        - timedelta(days=365 * 10 + random.randint(0, 1000)),
        admission_date=kwargs.get("admission_date", timezone.now().date()),
        gender=kwargs.get("gender", "M"),
        school=school,
        parent=parent,
        teacher=teacher,
    )

    # Set current user for action logging if available
    current_user = User.get_current_user()
    if current_user:
        student._current_user = current_user

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


def create_test_document(school, uploaded_by, **kwargs):
    # Get or create a document category
    category_name = kwargs.get("category_name", "Test Category")
    category, _ = DocumentCategory.objects.get_or_create(
        name=category_name,
        school=school,
        defaults={"description": f"Test {category_name} category", "is_custom": True},
    )

    return Document.objects.create(
        title=kwargs.get("title", "Test Document"),
        school=school,
        uploaded_by=uploaded_by,
        file=SimpleUploadedFile("test.pdf", b"test content"),
        category=category,  # Use the actual category instance
        description=kwargs.get("description", "Test document description"),
    )


def create_test_report(school, generated_by, **kwargs):
    # First create or get a report template
    template, _ = ReportTemplate.objects.get_or_create(
        name=kwargs.get("template_name", "Test Template"),
        template_type="ACADEMIC",
        defaults={
            "description": "Test report template",
            "content": {},
            "is_system": True,
            "created_by": generated_by,
        },
    )

    return GeneratedReport.objects.create(
        title=kwargs.get("title", "Test Report"),
        report_type=template,  # Use the template instance
        school=school,
        generated_by=generated_by,  # Should receive User object
        generated_at=timezone.now(),  # Correct datetime assignment
        data={},
        parameters={},
    )


def create_test_dashboard(school, created_by, **kwargs):
    return AnalyticsDashboard.objects.create(
        name=kwargs.get("name", "Test Dashboard"),
        school=school,
        created_by=created_by,
        config={"widgets": ["attendance", "performance"]},
    )


def create_test_cached_analytics(school, **kwargs):
    return CachedAnalytics.objects.create(
        school=school,
        analytics_type=kwargs.get("analytics_type", "overview"),
        data={"metric1": 10, "metric2": 20},
        valid_until=timezone.now() + timedelta(days=1),
    )


def create_test_alert(school, **kwargs):
    return AnalyticsAlert.objects.create(
        school=school,
        alert_type=kwargs.get("alert_type", "ATTENDANCE"),
        title=kwargs.get("title", "Test Alert"),
        message=kwargs.get("message", "This is a test alert"),
        related_model=kwargs.get("related_model", "Student"),
        related_id=kwargs.get("related_id", 1),
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


def create_test_academic_record(student, subject, teacher, **kwargs):
    return AcademicRecord.objects.create(
        student=student,
        subject=subject,
        teacher=teacher,
        term=kwargs.get("term", "Term1"),
        school_year=kwargs.get("school_year", "2023"),
        score=kwargs.get("score", 75),
        # grade=kwargs.get("grade", "B"),
        created_at=timezone.now(),  # Add this line
    )


def create_test_teacher_attendance(teacher, **kwargs):
    # Generate unique date if not provided
    if "date" not in kwargs:
        # Base date on existing attendances for this teacher
        last_attendance = (
            TeacherAttendance.objects.filter(teacher=teacher).order_by("-date").first()
        )
        if last_attendance:
            base_date = last_attendance.date + timedelta(days=1)
        else:
            base_date = timezone.now().date() - timedelta(days=30)

        # Add random offset up to 14 days
        kwargs["date"] = base_date + timedelta(days=random.randint(0, 14))

    return TeacherAttendance.objects.create(
        teacher=teacher,
        status=kwargs.get("status", "PRESENT"),
        check_in=kwargs.get("check_in", timezone.now().time()),
        recorded_by=kwargs.get("recorded_by", teacher.user),
        notes=kwargs.get("notes", ""),  # Set default to empty string
        # notes=kwargs.get("notes", None),
        date=kwargs["date"],
    )


def create_test_class_attendance(school_class, taken_by, present_students=[], **kwargs):
    # Ensure students are added to class first
    for student in present_students:
        if student not in school_class.students.all():
            school_class.students.add(student)

    # Create unique date if not provided
    if "date" not in kwargs:
        last_attendance = (
            ClassAttendance.objects.filter(school_class=school_class)
            .order_by("-date")
            .first()
        )
        if last_attendance:
            kwargs["date"] = last_attendance.date + timedelta(days=1)
        else:
            kwargs["date"] = timezone.now().date() - timedelta(
                days=random.randint(1, 30)
            )

    attendance = ClassAttendance.objects.create(
        school_class=school_class,
        date=kwargs["date"],
        taken_by=taken_by,
        notes=kwargs.get("notes", "Test attendance"),
        total_students=school_class.students.count(),
    )
    attendance.present_students.set(present_students)

    return attendance


def create_test_document_category(school, name="Test Category", **kwargs):
    """
    Creates a test document category for testing purposes.

    Args:
        school: School instance the category belongs to
        name: Name of the category (default: "Test Category")
        **kwargs: Additional attributes to override defaults

    Returns:
        DocumentCategory instance
    """
    return DocumentCategory.objects.create(
        name=name,
        description=kwargs.get("description", f"Test {name} description"),
        is_custom=kwargs.get("is_custom", True),
        school=school,
    )


def create_test_document_share_link(document, created_by, **kwargs):
    return DocumentShareLink.objects.create(
        document=document,
        created_by=created_by,
        token=kwargs.get("token", uuid.uuid4().hex),
        expires_at=kwargs.get("expires_at", timezone.now() + timedelta(days=7)),
        download_limit=kwargs.get("download_limit", 10),
        password=kwargs.get("password", None),
    )


def create_test_document_with_share(school, uploaded_by, **kwargs):
    doc = create_test_document(school, uploaded_by, **kwargs)
    share = create_test_document_share_link(
        doc,
        uploaded_by,
        expires_at=kwargs.get("share_expires", timezone.now() + timedelta(days=7)),
    )
    return doc, share
