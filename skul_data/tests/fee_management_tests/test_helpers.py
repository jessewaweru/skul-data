import uuid
import random
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from skul_data.fee_management.models.fee_management import (
    FeeStructure,
    FeeRecord,
    FeePayment,
    FeeUploadLog,
    FeeInvoiceTemplate,
    FeeReminder,
)
from skul_data.users.models.base_user import User
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.schools.models.school import School
from skul_data.users.models.role import Role, Permission
from skul_data.students.models.student import Student
from skul_data.users.models.parent import Parent
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.school_admin import SchoolAdmin


def create_test_fee_structure(school, school_class, **kwargs):
    """Create a test fee structure with sensible defaults"""
    # Use provided values or defaults, but don't randomize if specific values are given
    term = kwargs.get("term", f"term_{random.randint(1, 3)}")
    year = kwargs.get("year", str(timezone.now().year + random.randint(0, 2)))

    # Only ensure uniqueness if we're using random values
    if "term" not in kwargs or "year" not in kwargs:
        while FeeStructure.objects.filter(
            school_class=school_class, term=term, year=year
        ).exists():
            term = f"term_{random.randint(1, 3)}"
            year = str(timezone.now().year + random.randint(0, 5))

    return FeeStructure.objects.create(
        school=school,
        school_class=school_class,
        term=term,
        year=year,
        amount=kwargs.get("amount", Decimal("15000.00")),
        due_date=kwargs.get("due_date", timezone.now().date() + timedelta(days=30)),
        is_active=kwargs.get("is_active", True),
    )


def create_test_fee_record(student, parent, fee_structure, **kwargs):
    """Create a test fee record with sensible defaults"""
    # Check for existing records but handle them differently
    existing_record = FeeRecord.objects.filter(
        student=student, fee_structure=fee_structure
    ).first()

    if existing_record:
        # For the main test data setup, return the existing record
        # This prevents creating duplicate records
        return existing_record

    return FeeRecord.objects.create(
        student=student,
        parent=parent,
        fee_structure=fee_structure,
        amount_owed=kwargs.get("amount_owed", fee_structure.amount),
        amount_paid=kwargs.get("amount_paid", Decimal("0.00")),
        due_date=kwargs.get("due_date", fee_structure.due_date),
    )


def create_test_fee_payment(fee_record, **kwargs):
    """Create a test fee payment with sensible defaults"""
    # Use provided transaction_reference or default to expected test value
    transaction_ref = kwargs.get("transaction_reference", "MPESA12345")

    return FeePayment.objects.create(
        fee_record=fee_record,
        amount=kwargs.get("amount", Decimal("5000.00")),
        payment_method=kwargs.get("payment_method", "mpesa"),
        transaction_reference=transaction_ref,
        receipt_number=kwargs.get("receipt_number", "RCPT12345"),
        payment_date=kwargs.get("payment_date", timezone.now().date()),
        is_confirmed=kwargs.get("is_confirmed", True),
    )


def create_test_fee_upload_log(school, uploaded_by, **kwargs):
    """Create a test fee upload log with sensible defaults"""
    school_class = kwargs.get("school_class") or create_test_class(school)

    return FeeUploadLog.objects.create(
        school=school,
        uploaded_by=uploaded_by,
        school_class=school_class,
        term=kwargs.get("term", "term_1"),
        year=kwargs.get("year", str(timezone.now().year)),
        status=kwargs.get("status", "pending"),
        total_records=kwargs.get("total_records", 0),
        successful_records=kwargs.get("successful_records", 0),
        failed_records=kwargs.get("failed_records", 0),
    )


def create_test_fee_invoice_template(school, **kwargs):
    """Create a test fee invoice template with sensible defaults"""
    # Use provided name or default to expected test value
    name = kwargs.get("name", "Default Template")

    return FeeInvoiceTemplate.objects.create(
        school=school,
        name=name,
        header_html=kwargs.get("header_html", "<h1>School Fees Invoice</h1>"),
        footer_html=kwargs.get("footer_html", "<p>Payment instructions here</p>"),
        is_active=kwargs.get("is_active", True),
        # Add the template_file field that's required
        template_file=kwargs.get("template_file", "default_template.html"),
    )


def create_test_fee_reminder(fee_record, sent_by, **kwargs):
    """Create a test fee reminder with sensible defaults"""
    return FeeReminder.objects.create(
        fee_record=fee_record,
        sent_via=kwargs.get("sent_via", "email"),
        message=kwargs.get("message", "Please pay your fees"),
        sent_by=sent_by,
        is_successful=kwargs.get("is_successful", True),
    )


def create_test_class(school, name=None, **kwargs):
    if name is None:
        name = f"Class_{uuid.uuid4().hex[:8]}"  # Longer unique name

    grade_choices = SchoolClass._meta.get_field("grade_level").choices
    default_grade = grade_choices[0][0] if grade_choices else "1"

    return SchoolClass.objects.create(
        name=name,
        school=school,
        grade_level=kwargs.get("grade_level", default_grade),
    )


def create_test_school(name=None):
    if name is None:
        name = f"Test School {uuid.uuid4().hex[:6]}"

    # Generate unique username based on school name
    username = f"admin_{uuid.uuid4().hex[:8]}"
    admin_user = User.objects.create_user(
        email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
        username=username,
        password="testpass",
        user_type=User.SCHOOL_ADMIN,
        is_staff=True,
    )

    # Generate a unique code
    unique_code = f"SCH{random.randint(10000, 99999)}"

    # Ensure code is unique
    while School.objects.filter(code=unique_code).exists():
        unique_code = f"SCH{random.randint(10000, 99999)}"

    # Use date objects instead of datetime
    term_start = timezone.now().date() - timedelta(days=30)
    term_end = timezone.now().date() + timedelta(days=30)

    school = School.objects.create(
        name=name,
        email=f"contact_{uuid.uuid4().hex[:6]}@test.com",
        schooladmin=admin_user,
        code=unique_code,
        term_start_date=term_start,
        term_end_date=term_end,
        current_term="term_1",
        current_school_year=str(timezone.now().year),
    )

    # Create admin role with permissions (if Role model exists)
    try:
        admin_role = Role.objects.create(
            name=f"Admin_{uuid.uuid4().hex[:6]}", school=school, role_type="SYSTEM"
        )
        permissions = [
            ("view_analytics", "Can view analytics"),
            ("manage_analytics", "Can manage analytics"),
        ]
        for code, name in permissions:
            perm, _ = Permission.objects.get_or_create(code=code, name=name)
            admin_role.permissions.add(perm)

        admin_user.role = admin_role
        admin_user.save()
    except:
        # If Role model doesn't exist or there's an issue, continue without it
        pass

    return school, admin_user


def create_test_teacher(school, email=None, **kwargs):
    if not email:
        email = f"teacher_{uuid.uuid4().hex[:8]}@test.com"

    username = f"teacher_{uuid.uuid4().hex[:8]}"
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
        phone_number=kwargs.get(
            "phone_number", f"+2547{random.randint(10000000, 99999999)}"
        ),
        status=kwargs.get("status", "ACTIVE"),
    )


def create_test_parent(school, email=None, **kwargs):
    if not email:
        email = f"parent_{uuid.uuid4().hex[:8]}@test.com"

    user = User.objects.create_user(
        email=email,
        username=f"parent_{uuid.uuid4().hex[:8]}",
        password="testpass",
        user_type=User.PARENT,
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "Parent"),
    )
    return Parent.objects.create(
        user=user,
        school=school,
        phone_number=kwargs.get(
            "phone_number", f"+2547{random.randint(10000000, 99999999)}"
        ),
    )


def create_test_student(school, **kwargs):
    teacher = kwargs.get("teacher") or create_test_teacher(school)
    parent = kwargs.get("parent") or create_test_parent(school)
    school_class = kwargs.get("school_class") or create_test_class(school)

    # Generate unique student attributes
    unique_id = uuid.uuid4().hex[:8]

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
    )

    # Set the student's class if the field exists
    if hasattr(student, "student_class"):
        student.student_class = school_class
        student.save()
    elif hasattr(student, "school_class"):
        student.school_class = school_class
        student.save()

    return student


def create_test_school_with_fee_data():
    """Create a complete test environment with school, class, students, parents, and fee data (NO PAYMENT)"""
    # Create school and admin
    school, admin = create_test_school()

    school_admin_profile = SchoolAdmin.objects.create(
        user=admin, school=school, is_primary=True
    )

    # Create 'manage_fees' permission
    from skul_data.users.models.role import Permission

    perm, _ = Permission.objects.get_or_create(
        code="manage_fees", defaults={"name": "Manage fees"}
    )

    # Create admin role and add permission
    admin_role = Role.objects.create(
        name=f"AdminRole_{uuid.uuid4().hex[:4]}", school=school, role_type="SYSTEM"
    )
    admin_role.permissions.add(perm)

    # Assign role to admin user
    admin.role = admin_role
    admin.save()

    # Create class
    school_class = create_test_class(school)

    # Create teacher
    teacher = create_test_teacher(school)

    # Create parent and student - PASS school_class to ensure proper association
    parent = create_test_parent(school)
    student = create_test_student(
        school, parent=parent, teacher=teacher, school_class=school_class
    )

    # Add student to parent's children if the relationship exists
    if hasattr(parent, "children"):
        parent.children.add(student)

    # Create fee structure
    fee_structure = create_test_fee_structure(school, school_class)

    # Create fee record using the updated function
    fee_record = FeeRecord.objects.create(
        student=student,
        parent=parent,
        fee_structure=fee_structure,
        amount_owed=fee_structure.amount,
        amount_paid=Decimal("0.00"),
        due_date=fee_structure.due_date,
    )

    # NO fee payment created here - fee record starts with "unpaid" status

    return {
        "school": school,
        "admin": admin,
        "school_admin_profile": school_admin_profile,
        "class": school_class,
        "teacher": teacher,
        "parent": parent,
        "student": student,
        "fee_structure": fee_structure,
        "fee_record": fee_record,
    }


def create_test_school_with_fee_data_and_payment():
    """Create test environment with fee data INCLUDING an initial payment"""
    data = create_test_school_with_fee_data()

    # Create fee payment which will trigger signals and update fee_record
    fee_payment = create_test_fee_payment(data["fee_record"])
    data["fee_payment"] = fee_payment

    return data
