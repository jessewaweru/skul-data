import factory
from django.contrib.auth import get_user_model
from faker import Faker
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.parent import Parent, ParentNotification, ParentStatusChange
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.users.models.teacher import Teacher
from skul_data.students.models.student import Subject
from skul_data.users.models.role import Role, Permission
from skul_data.users.models.session import UserSession
from skul_data.users.models.teacher import (
    TeacherAttendance,
    TeacherDocument,
    TeacherWorkload,
)
from django.utils import timezone
from django.contrib.sessions.models import Session


fake = Faker()
User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password")
    first_name = fake.first_name()
    last_name = fake.last_name()
    is_active = True


class SchoolAdminUserFactory(UserFactory):
    user_type = User.SCHOOL_ADMIN


class SchoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = School
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"School {n}")
    code = factory.Sequence(lambda n: f"SCH{n:04d}")
    location = factory.LazyAttribute(lambda _: fake.address())
    phone = factory.LazyAttribute(lambda _: fake.numerify(text="###########"))
    email = factory.LazyAttribute(lambda _: fake.email())
    type = "PRI"
    country = "Kenya"
    # Create a school admin user and assign it
    schooladmin = factory.SubFactory(SchoolAdminUserFactory)


class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    name = factory.Sequence(lambda n: f"Unique Role {n}")  # More unique names
    school = factory.SubFactory(SchoolFactory)
    role_type = "CUSTOM"


class PermissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Permission

    code = factory.Sequence(lambda n: f"can_do_something_{n}")
    name = factory.Sequence(lambda n: f"Can do something {n}")


class ParentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Parent

    user = factory.SubFactory(UserFactory, user_type=User.PARENT)
    school = factory.SubFactory(SchoolFactory)
    phone_number = factory.LazyAttribute(
        lambda _: fake.numerify(text="###########")
    )  # 11 digits
    address = factory.LazyAttribute(
        lambda _: fake.street_address()[:100]
    )  # Limit address length
    occupation = factory.LazyAttribute(
        lambda _: fake.job()[:50]
    )  # Limit occupation length
    status = "ACTIVE"


class TeacherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Teacher

    hire_date = factory.LazyAttribute(lambda _: fake.date_object())
    user = factory.SubFactory(UserFactory, user_type=User.TEACHER)
    school = factory.SubFactory(SchoolFactory)
    status = "ACTIVE"
    qualification = fake.sentence()
    specialization = fake.word()
    years_of_experience = fake.random_int(min=1, max=30)


class SchoolAdminFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SchoolAdmin

    user = factory.SubFactory(SchoolAdminUserFactory)
    school = factory.SubFactory(
        SchoolFactory, schooladmin=factory.SelfAttribute("..user")
    )
    school = factory.SubFactory(SchoolFactory)
    is_primary = True


class SessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Session  # from django.contrib.sessions.models import Session

    session_key = factory.Sequence(lambda n: f"sessionkey{n}")
    session_data = "{}"
    expire_date = factory.LazyFunction(timezone.now)
    # expire_date = factory.LazyFunction(
    #     lambda: timezone.now() + timezone.timedelta(days=1)
    # )


class UserSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserSession

    user = factory.SubFactory(UserFactory)
    session = factory.SubFactory(SessionFactory)
    ip_address = fake.ipv4()
    user_agent = fake.user_agent()
    device = fake.word()
    browser = fake.word()
    os = fake.word()
    location = fake.city()


class ParentNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ParentNotification

    parent = factory.SubFactory(ParentFactory)
    message = fake.sentence()
    notification_type = "ACADEMIC"
    is_read = False


class ParentStatusChangeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ParentStatusChange

    parent = factory.SubFactory(ParentFactory)
    changed_by = factory.SubFactory(UserFactory)
    from_status = "ACTIVE"
    to_status = "INACTIVE"
    reason = fake.sentence()


class SchoolClassFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SchoolClass

    name = factory.Sequence(lambda n: f"Class {n}")
    grade_level = factory.Iterator(
        [choice[0] for choice in SchoolClass.GRADE_LEVEL_CHOICES]
    )
    stream = None  # Or create a `SchoolStreamFactory` if needed
    level = factory.Iterator([choice[0] for choice in SchoolClass.LEVEL_CHOICES])
    class_teacher = factory.SubFactory(TeacherFactory)
    school = factory.SubFactory(SchoolFactory)
    academic_year = "2024"
    room_number = factory.Sequence(lambda n: f"R{n}")
    capacity = factory.LazyAttribute(lambda _: fake.random_int(min=10, max=50))
    is_active = True


class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject

    name = factory.Sequence(lambda n: f"Subject {n}")
    code = factory.Sequence(lambda n: f"SUB{n:03d}")
    description = factory.Faker("sentence")
    school = factory.SubFactory(SchoolFactory)


class TeacherWorkloadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TeacherWorkload

    teacher = factory.SubFactory(TeacherFactory)
    school_class = factory.SubFactory(SchoolClassFactory)
    subject = factory.SubFactory(SubjectFactory)
    hours_per_week = fake.random_int(min=1, max=20)
    term = "Term 1"
    school_year = "2023"


class TeacherAttendanceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TeacherAttendance

    teacher = factory.SubFactory(TeacherFactory)
    date = fake.date_this_year()
    status = "PRESENT"
    check_in = fake.time()
    recorded_by = factory.SubFactory(UserFactory)


class TeacherDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TeacherDocument

    teacher = factory.SubFactory(TeacherFactory)
    title = fake.sentence()
    document_type = "QUALIFICATION"
    description = fake.paragraph()
    uploaded_by = factory.SubFactory(UserFactory)
    is_confidential = False
