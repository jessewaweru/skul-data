import factory
from django.contrib.auth import get_user_model
from skul_data.schools.models.school import School
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.users.models.role import Role
from skul_data.students.models.student import Student
from skul_data.users.models.school_admin import SchoolAdmin
from skul_data.documents.models.document import (
    DocumentCategory,
    Document,
    DocumentShareLink,
)
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password")

    @factory.post_generation
    def create_profile(self, create, extracted, **kwargs):
        if not create:
            return
        if hasattr(self, "user_type"):
            if self.user_type == User.TEACHER:
                from skul_data.users.models.teacher import Teacher

                # Don't create the Teacher object directly here
                # We'll create and configure it in the test setup instead
                pass
            elif self.user_type == User.PARENT:
                from skul_data.users.models.parent import Parent

                # Don't create the Parent object directly here
                # We'll create and configure it in the test setup instead
                pass
            elif self.user_type == User.SCHOOL_ADMIN:
                from skul_data.users.models.school_admin import SchoolAdmin

                # Don't save immediately - we'll handle this in SchoolFactory
                return SchoolAdmin(user=self)


class SchoolAdminFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SchoolAdmin

    user = factory.SubFactory(UserFactory)
    is_primary = True


class SchoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = School

    name = factory.Sequence(lambda n: f"School {n}")
    code = factory.Sequence(lambda n: f"SCH{n}")
    location = "Test Location"
    email = factory.Sequence(lambda n: f"school{n}@example.com")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # First create the admin user
        admin_user = UserFactory(user_type=User.SCHOOL_ADMIN)

        # Create the school
        school = model_class.objects.create(schooladmin=admin_user, *args, **kwargs)

        # Now set the school on the admin profile and save
        admin_profile = admin_user.school_admin_profile
        admin_profile.school = school
        admin_profile.save()

        return school


class SchoolClassFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SchoolClass

    name = factory.Sequence(lambda n: f"Class {n}")
    school = factory.SubFactory(SchoolFactory)


class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    name = factory.Sequence(lambda n: f"Role {n}")
    school = factory.SubFactory(SchoolFactory)


class DocumentCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    description = "Test description"
    is_custom = True  # Default to custom categories in tests
    school = factory.SubFactory(SchoolFactory)  # Only used if is_custom=True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Handle school assignment based on is_custom
        is_custom = kwargs.get("is_custom", True)
        if not is_custom:
            kwargs["school"] = None
        return super()._create(model_class, *args, **kwargs)


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Sequence(lambda n: f"Document {n}")
    description = "Test document description"
    school = factory.SubFactory(SchoolFactory)
    category = factory.SubFactory(DocumentCategoryFactory)
    uploaded_by = factory.SelfAttribute("school.schooladmin")
    is_public = False

    # Create a proper test file
    @factory.lazy_attribute
    def file(self):
        test_file = SimpleUploadedFile(
            name="test_file.pdf",
            content=b"file content",
            content_type="application/pdf",
        )
        return test_file

    # Calculate file properties after creation
    @factory.post_generation
    def set_file_properties(self, create, extracted, **kwargs):
        if not create or not self.file:
            return

        # Set file metadata
        self.file_size = self.file.size
        self.file_type = ".pdf"


class DocumentShareLinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentShareLink

    document = factory.SubFactory(DocumentFactory)
    created_by = factory.SelfAttribute("document.uploaded_by")
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    download_limit = 10
    download_count = 0


class StudentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Student

    first_name = "Test"
    last_name = "Student"
    school = factory.SubFactory(SchoolFactory)
    date_of_birth = factory.Faker("date_of_birth", minimum_age=5, maximum_age=18)
