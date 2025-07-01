# tests/helpers/test_timetable_helpers.py
import random
import uuid
from datetime import time, timedelta
from skul_data.school_timetables.models.school_timetable import (
    TimeSlot,
    TimetableStructure,
    Timetable,
    Lesson,
    TimetableConstraint,
    SubjectGroup,
    TeacherAvailability,
)
from django.utils import timezone
from skul_data.schools.models.school import School
from skul_data.users.models.role import Role
from skul_data.users.models.role import Permission
from skul_data.users.models.base_user import User
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Subject
from django.contrib.auth import get_user_model
from skul_data.users.models.school_admin import SchoolAdmin


def create_test_timeslot(school, **kwargs):
    """Create a test timeslot with sensible defaults"""
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    return TimeSlot.objects.create(
        school=school,
        name=kwargs.get("name", f"Period {random.randint(1, 10)}"),
        start_time=kwargs.get("start_time", time(8, 0)),
        end_time=kwargs.get("end_time", time(8, 40)),
        day_of_week=kwargs.get("day_of_week", random.choice(days)),
        is_break=kwargs.get("is_break", False),
        break_name=kwargs.get("break_name", None),
        order=kwargs.get("order", 1),
        is_active=kwargs.get("is_active", True),
    )


def create_test_timetable_structure(school, **kwargs):
    """Create a test timetable structure with time slots"""
    # Create the structure first
    structure = TimetableStructure.objects.create(
        school=school,
        curriculum=kwargs.get("curriculum", "CBC"),
        days_of_week=kwargs.get("days_of_week", ["MON", "TUE", "WED", "THU", "FRI"]),
        default_start_time=kwargs.get("default_start_time", time(8, 0)),
        default_end_time=kwargs.get("default_end_time", time(16, 0)),
        period_duration=kwargs.get("period_duration", 40),
        break_duration=kwargs.get("break_duration", 30),
        lunch_duration=kwargs.get("lunch_duration", 60),
    )

    # Create some time slots for this structure if they don't exist
    if not kwargs.get("skip_timeslots", False):
        for i, day in enumerate(structure.days_of_week):
            TimeSlot.objects.get_or_create(
                school=school,
                day_of_week=day,
                name=f"Period 1 - {day}",
                defaults={
                    "start_time": time(8, 0),
                    "end_time": time(8, 40),
                    "is_break": False,
                    "order": 1,
                    "is_active": True,
                },
            )

    return structure


def create_test_timetable(school_class, **kwargs):
    """Create a test timetable"""
    return Timetable.objects.create(
        school_class=school_class,
        academic_year=kwargs.get("academic_year", "2023"),
        term=kwargs.get("term", 1),
        is_active=kwargs.get("is_active", False),
    )


def create_test_lesson(timetable, subject, teacher, time_slot, **kwargs):
    """Create a test lesson"""
    return Lesson.objects.create(
        timetable=timetable,
        subject=subject,
        teacher=teacher,
        time_slot=time_slot,
        is_double_period=kwargs.get("is_double_period", False),
        room=kwargs.get("room", "Room 101"),
        notes=kwargs.get("notes", "Test lesson"),
    )


def create_test_constraint(school, **kwargs):
    """Create a test timetable constraint"""
    return TimetableConstraint.objects.create(
        school=school,
        constraint_type=kwargs.get("constraint_type", "NO_TEACHER_CLASH"),
        is_hard_constraint=kwargs.get("is_hard_constraint", True),
        parameters=kwargs.get("parameters", {}),
        description=kwargs.get("description", "Test constraint"),
        is_active=kwargs.get("is_active", True),
    )


def create_test_subject_group(school, **kwargs):
    """Create a test subject group"""
    group = SubjectGroup.objects.create(
        school=school,
        name=kwargs.get("name", "Test Group"),
        description=kwargs.get("description", "Test subject group"),
    )

    # Add subjects if provided
    if "subjects" in kwargs:
        group.subjects.set(kwargs["subjects"])

    return group


def create_test_teacher_availability(teacher, **kwargs):
    """Create a test teacher availability record"""
    # Use date objects instead of datetime for date fields
    available_from = kwargs.get("available_from", time(8, 0))
    available_to = kwargs.get("available_to", time(16, 0))

    return TeacherAvailability.objects.create(
        teacher=teacher,
        day_of_week=kwargs.get("day_of_week", "MON"),
        is_available=kwargs.get("is_available", True),
        available_from=available_from,
        available_to=available_to,
        reason=kwargs.get("reason", "Available all day"),
    )


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

    # Use date object for date_of_birth and admission_date
    birth_date = timezone.now().date() - timedelta(
        days=365 * 10 + random.randint(0, 1000)
    )
    admission_date = kwargs.get("admission_date", timezone.now().date())

    return Student.objects.create(
        first_name=f"Test{unique_id}",
        last_name=f"Student{unique_id}",
        date_of_birth=birth_date,
        admission_date=admission_date,
        gender=kwargs.get("gender", "M"),
        school=school,
        parent=parent,
        teacher=teacher,
    )


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
