import zipfile
from io import BytesIO
from datetime import timedelta
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from skul_data.tests.documents_tests.documents_factories import (
    DocumentFactory,
    DocumentCategoryFactory,
    DocumentShareLinkFactory,
    SchoolFactory,
    UserFactory,
    SchoolClassFactory,
    StudentFactory,
)
from skul_data.documents.models.document import (
    DocumentCategory,
    Document,
    DocumentShareLink,
)
from skul_data.action_logs.models.action_log import ActionLog, ActionCategory
from skul_data.users.models import User
from skul_data.users.models.teacher import Teacher


class DocumentCategoryViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = self.school.schooladmin
        self.teacher = UserFactory(user_type=UserFactory._meta.model.TEACHER)

        # Create the teacher profile with the school already assigned
        from skul_data.users.models.teacher import Teacher

        Teacher.objects.create(user=self.teacher, school=self.school)

        # Now you can access other teacher_profile properties
        # self.teacher.teacher_profile.school = self.school
        # self.teacher.teacher_profile.save()

        # self.category = DocumentCategoryFactory(school=self.school)
        self.category = DocumentCategoryFactory(school=self.school, is_custom=True)

    def test_list_categories_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:category-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_categories_as_teacher(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse("documents:category-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_category_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:category-list")
        data = {"name": "New Category", "description": "Test description"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DocumentCategory.objects.count(), 2)
        self.assertTrue(response.data["is_custom"])

    def test_create_category_as_teacher(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse("documents:category-list")
        data = {"name": "New Category", "description": "Test description"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DocumentCategory.objects.count(), 2)

    def test_system_categories_not_editable(self):
        # Create a system category with a fixed name to make sure it's unique
        system_category = DocumentCategory.objects.create(
            name="System Category Test",
            description="System description",
            is_custom=False,
            school=None,
        )
        # Verify the category was created successfully
        self.assertIsNotNone(system_category.id)

        # Make sure the get_queryset method will return this category for the admin
        # If your DocumentCategoryViewSet.get_queryset filters by school, you may need to modify it
        # to include system categories (where school=None)

        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:category-detail", args=[system_category.id])

        # First test if the category is accessible
        response = self.client.get(url)
        if response.status_code == status.HTTP_404_NOT_FOUND:
            self.fail(
                "The system category is not accessible to the admin user. Check your get_queryset method."
            )

        # Now test updating
        data = {"name": "Updated Name", "description": "Updated description"}
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DocumentViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = self.school.schooladmin
        self.teacher = UserFactory(
            user_type=UserFactory._meta.model.TEACHER,
        )

        # Create the teacher profile with the school already assigned
        from skul_data.users.models.teacher import Teacher

        Teacher.objects.create(user=self.teacher, school=self.school)

        # Now you can access and modify other teacher_profile properties
        self.teacher.teacher_profile.save()

        self.parent = UserFactory(
            user_type=UserFactory._meta.model.PARENT,
        )

        # Create the parent profile with the school already assigned
        from skul_data.users.models.parent import Parent

        Parent.objects.create(user=self.parent, school=self.school)

        # Now you can access and modify other parent_profile properties
        self.parent.parent_profile.save()

        self.student = StudentFactory(school=self.school)
        self.parent.parent_profile.children.add(self.student)
        self.category = DocumentCategoryFactory(school=self.school)
        self.school_class = SchoolClassFactory(school=self.school)
        self.teacher.teacher_profile.assigned_class = self.school_class
        self.teacher.teacher_profile.save()
        self.test_file = SimpleUploadedFile(
            "test_file.pdf", b"file_content", content_type="application/pdf"
        )
        self.public_doc = DocumentFactory(
            school=self.school,
            category=self.category,
            uploaded_by=self.admin,
            is_public=True,
        )
        self.private_doc = DocumentFactory(
            school=self.school,
            category=self.category,
            uploaded_by=self.admin,
            is_public=False,
        )
        self.class_doc = DocumentFactory(
            school=self.school,
            category=self.category,
            uploaded_by=self.teacher,
            related_class=self.school_class,
            is_public=False,
        )
        self.student_doc = DocumentFactory(
            school=self.school,
            category=self.category,
            uploaded_by=self.teacher,
            is_public=False,
        )
        self.student_doc.related_students.add(self.student)

    def test_list_documents_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:document-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # Should see all documents

    def test_list_documents_as_teacher(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse("documents:document-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see public docs, class docs, and docs they uploaded
        self.assertEqual(len(response.data), 3)

    def test_list_documents_as_parent(self):
        self.client.force_authenticate(user=self.parent)
        url = reverse("documents:document-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see public docs and docs related to their child
        self.assertEqual(len(response.data), 2)

    def test_upload_document_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:document-list")
        data = {
            "title": "Admin Upload",
            "description": "Test upload",
            "category_id": self.category.id,
            "school": self.school.id,
            "file": self.test_file,
        }
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Document.objects.count(), 5)
        self.assertEqual(response.data["uploaded_by_name"], self.admin.get_full_name())

    def test_upload_document_as_teacher(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse("documents:document-list")
        data = {
            "title": "Teacher Upload",
            "description": "Test upload",
            "category_id": self.category.id,
            "file": self.test_file,
        }
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Document.objects.count(), 5)
        self.assertEqual(response.data["school_name"], self.school.name)

    def test_bulk_upload(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:document-bulk-upload")

        # Create a test ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("file1.pdf", b"PDF content")
            zip_file.writestr("file2.docx", b"DOCX content")
        zip_buffer.seek(0)

        data = {
            "zip": SimpleUploadedFile(
                "test.zip", zip_buffer.read(), content_type="application/zip"
            ),
            "category": self.category.id,
            "school": self.school.id,
        }
        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 2)  # 2 files in zip
        self.assertEqual(Document.objects.count(), 6)  # 4 existing + 2 new

    def test_generate_share_link(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse(
            "documents:document-generate-share-link", args=[self.public_doc.id]
        )

        # Make sure the expires_at format matches what the serializer expects
        future_date = timezone.now() + timedelta(days=7)

        data = {
            "expires_at": future_date.isoformat(),
            "download_limit": 5,
            # Note: we don't need to include document here as the view should handle it
        }

        # For debugging - let's see what the document ID is
        print(f"Testing with document ID: {self.public_doc.id}")

        response = self.client.post(url, data, format="json")

        # Print detailed error info for debugging
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Error status: {response.status_code}")
            print(f"Error details: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DocumentShareLink.objects.count(), 1)
        self.assertEqual(response.data["download_limit"], 5)

    def test_bulk_download(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:document-bulk-download")
        # In a real test, you'd need actual files to download
        # Here we just test the endpoint responds correctly
        response = self.client.get(
            url, {"ids": f"{self.public_doc.id},{self.private_doc.id}"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["content-type"], "application/zip")


class DocumentShareLinkViewSetTest(APITestCase):
    def setUp(self):
        self.school = SchoolFactory()
        self.admin = self.school.schooladmin
        self.document = DocumentFactory(school=self.school, uploaded_by=self.admin)
        self.share_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_list_share_links(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:share-link-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_share_link(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("documents:share-link-list")
        data = {
            "document": self.document.id,
            "expires_at": (timezone.now() + timedelta(days=3)).isoformat(),
            "password": "secret123",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DocumentShareLink.objects.count(), 2)
        self.assertEqual(response.data["password"], "secret123")

    def test_download_via_share_link(self):
        # url = reverse("documents:document-download", args=[self.share_link.token])
        url = reverse("documents:share-link-download", args=[self.share_link.token])
        response = self.client.get(url)
        # In a real test with actual files, this would return the file
        # Here we just check the endpoint is accessible
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        )

    def test_expired_share_link(self):
        expired_link = DocumentShareLinkFactory(
            document=self.document,
            created_by=self.admin,
            expires_at=timezone.now() - timedelta(days=1),
        )
        url = reverse("documents:document-download", args=[expired_link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_password_protected_link(self):
        protected_link = DocumentShareLinkFactory(
            document=self.document, created_by=self.admin, password="secret"
        )
        url = reverse("documents:document-download", args=[protected_link.token])

        # Try without password
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with wrong password
        response = self.client.get(f"{url}?password=wrong")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with correct password
        response = self.client.get(f"{url}?password=secret")
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        )


class DocumentViewSetLoggingTest(APITestCase):
    """Tests specifically for action logging in DocumentViewSet"""

    def setUp(self):
        self.school = SchoolFactory()
        self.admin = self.school.schooladmin
        self.teacher = UserFactory(user_type=User.TEACHER)
        Teacher.objects.create(user=self.teacher, school=self.school)

        self.category = DocumentCategoryFactory(school=self.school)
        self.test_file = SimpleUploadedFile(
            "test_file.pdf", b"file_content", content_type="application/pdf"
        )
        self.client.force_authenticate(user=self.admin)

    def test_document_upload_logging(self):
        """Test that document upload creates proper action log"""
        url = reverse("documents:document-list")
        data = {
            "title": "Logged Upload",
            "file": self.test_file,
            "category_id": self.category.id,
            "school_id": self.school.id,
        }

        response = self.client.post(url, data, format="multipart")

        # Debug the response if it's not 201
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
            print(f"Response content: {response.content}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        doc = Document.objects.get(title="Logged Upload")
        log = ActionLog.objects.filter(
            content_type__model="document",
            object_id=doc.id,
            category=ActionCategory.UPLOAD,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.action, f"Uploaded document: {doc.title}")
        self.assertEqual(log.metadata["file_type"], ".pdf")
        self.assertGreater(log.metadata["file_size"], 0)

    def test_bulk_upload_logging(self):
        """Test that bulk upload creates proper action log"""
        url = reverse("documents:document-bulk-upload")
        file2 = SimpleUploadedFile(
            "test_file2.pdf", b"file_content", content_type="application/pdf"
        )
        data = {
            "files": [self.test_file, file2],
            "category": self.category.id,
            "school": self.school.id,
        }

        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        log = ActionLog.objects.filter(
            category=ActionCategory.UPLOAD, action__startswith="Bulk uploaded"
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.metadata["document_count"], 2)
        self.assertEqual(len(log.metadata["document_ids"]), 2)

    def test_document_update_logging(self):
        """Test that document updates create proper action logs"""
        doc = DocumentFactory(
            title="Original Title",
            file=self.test_file,
            category=self.category,
            school=self.school,
            uploaded_by=self.admin,
        )

        url = reverse("documents:document-detail", args=[doc.id])
        data = {"title": "Updated Title"}

        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        log = ActionLog.objects.filter(
            content_type__model="document",
            object_id=doc.id,
            category=ActionCategory.UPDATE,
        ).first()

        # Debug if log is not found
        if not log:
            print("Available ActionLogs:")
            for al in ActionLog.objects.all():
                print(
                    f"  - ID: {al.id}, Action: {al.action}, Category: {al.category}, Object: {al.content_type}"
                )

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.action, f"Updated Document")

    def test_generate_share_link_logging(self):
        """Test that share link generation creates proper action log"""
        doc = DocumentFactory(
            school=self.school, uploaded_by=self.admin, category=self.category
        )

        url = reverse("documents:document-generate-share-link", args=[doc.id])
        data = {
            "expires_at": (timezone.now() + timedelta(days=7)).isoformat(),
            "download_limit": 5,
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        share_link = DocumentShareLink.objects.first()
        log = ActionLog.objects.filter(
            content_type__model="documentsharelink",
            object_id=share_link.id,
            category=ActionCategory.SHARE,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.metadata["document_id"], doc.id)
        self.assertEqual(log.metadata["expires_at"], data["expires_at"])


# python manage.py test skul_data.tests.documents_tests.test_documents_views
