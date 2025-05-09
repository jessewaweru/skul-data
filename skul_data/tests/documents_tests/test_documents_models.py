import os
from datetime import timedelta
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from skul_data.tests.documents_tests.documents_factories import (
    SchoolFactory,
    UserFactory,
    DocumentCategoryFactory,
    DocumentFactory,
    DocumentShareLinkFactory,
)
from skul_data.documents.models.document import Document, DocumentCategory
from skul_data.users.models.base_user import User


class DocumentCategoryModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.user = UserFactory()

    def test_create_category(self):
        category = DocumentCategoryFactory(
            name="Test Category", school=self.school, is_custom=True
        )
        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.school, self.school)
        self.assertTrue(category.is_custom)

    def test_system_category(self):
        category = DocumentCategoryFactory(
            name="System Category", school=None, is_custom=False
        )
        self.assertIsNone(category.school)
        self.assertFalse(category.is_custom)

    def test_unique_name_per_school(self):
        DocumentCategoryFactory(name="Duplicate", school=self.school)
        with self.assertRaises(ValidationError):
            category = DocumentCategory(name="Duplicate", school=self.school)
            category.full_clean()

    def test_same_name_different_schools(self):
        school2 = SchoolFactory()
        DocumentCategoryFactory(name="Same Name", school=self.school)

        # Try creating with the same name in a different school
        try:
            category = DocumentCategory(name="Same Name", school=school2)
            category.full_clean()  # Just validate, no need to save
            # If we get here, no ValidationError was raised
        except ValidationError:
            self.fail("Same name should be allowed for different schools")


class DocumentModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = self.school.schooladmin
        self.category = DocumentCategoryFactory(school=self.school)
        self.test_file = SimpleUploadedFile(
            "test_file.pdf", b"file_content", content_type="application/pdf"
        )

    def test_create_document(self):
        doc = DocumentFactory(
            title="Test Document",
            file=self.test_file,
            category=self.category,
            school=self.school,
            uploaded_by=self.admin,
        )
        self.assertEqual(doc.title, "Test Document")
        self.assertEqual(doc.school, self.school)
        self.assertEqual(doc.uploaded_by, self.admin)
        self.assertEqual(doc.file_type, ".pdf")
        self.assertGreater(doc.file_size, 0)

    def test_file_validation(self):
        # Test invalid file type
        invalid_file = SimpleUploadedFile(
            "test_file.exe", b"file_content", content_type="application/exe"
        )
        doc = Document(
            title="Invalid File",
            file=invalid_file,
            category=self.category,
            school=self.school,
            uploaded_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            doc.full_clean()

        # Test file size limit
        large_file = SimpleUploadedFile(
            "large_file.pdf",
            b"0" * (10 * 1024 * 1024 + 1),  # 10MB + 1 byte
            content_type="application/pdf",
        )
        doc.file = large_file
        with self.assertRaises(ValidationError):
            doc.full_clean()

    def test_upload_path_generation(self):
        # Create a document with a real file
        doc = Document.objects.create(
            title="Path Test",
            file=self.test_file,
            category=self.category,
            school=self.school,
            uploaded_by=self.admin,
        )

        # Skip this test if the file path isn't set correctly in the test environment
        if not hasattr(doc.file, "path") or not doc.file.path:
            self.skipTest("File path not available in test environment")

        # Get the actual path
        path = doc.file.path

        # Check if the path contains expected elements
        self.assertIn(str(self.school.id), path)
        self.assertIn(self.category.name.lower().replace(" ", "_"), path)

    def test_school_auto_assignment(self):
        # Create a teacher user
        teacher = UserFactory(user_type=User.TEACHER)

        # Create the teacher profile with school already assigned
        from skul_data.users.models.teacher import Teacher

        teacher_profile = Teacher.objects.create(user=teacher, school=self.school)

        # Now assign the teacher to the test school
        teacher_profile.school = self.school
        teacher_profile.save()

        # Create a document without explicitly setting school
        doc = Document.objects.create(
            title="Auto School",
            file=self.test_file,
            category=self.category,
            uploaded_by=teacher,
        )

        # Check that school was auto-assigned
        self.assertEqual(doc.school, self.school)


class DocumentShareLinkModelTest(TestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = self.school.schooladmin
        self.document = DocumentFactory(school=self.school, uploaded_by=self.admin)

    def test_create_share_link(self):
        expires_at = timezone.now() + timedelta(days=7)
        share_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=expires_at,
            download_limit=5,
        )
        self.assertEqual(share_link.document, self.document)
        self.assertEqual(share_link.created_by, self.admin)
        self.assertEqual(share_link.download_limit, 5)
        self.assertEqual(share_link.download_count, 0)

    def test_link_validity(self):
        # Valid link
        valid_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=1),
            download_limit=5,
            download_count=0,
        )
        self.assertTrue(valid_link.is_valid())

        # Expired link
        expired_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=timezone.now() - timedelta(days=1),
            download_limit=5,
            download_count=0,
        )
        self.assertFalse(expired_link.is_valid())

        # Exceeded download limit
        exceeded_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=1),
            download_limit=5,
            download_count=5,
        )
        self.assertFalse(exceeded_link.is_valid())

        # Unlimited downloads
        unlimited_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=1),
            download_limit=None,
            download_count=100,
        )
        self.assertTrue(unlimited_link.is_valid())


# python manage.py test skul_data.tests.documents_tests.test_documents_models
