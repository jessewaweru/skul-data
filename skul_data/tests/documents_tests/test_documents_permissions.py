from django.test import TestCase, RequestFactory
from skul_data.documents.permissions.permission import (
    CanUploadDocument,
    CanViewDocument,
    CanManageDocument,
)
from skul_data.tests.documents_tests.documents_factories import (
    DocumentFactory,
    UserFactory,
    SchoolFactory,
    SchoolClassFactory,
    StudentFactory,
)
from skul_data.users.models.base_user import User


class DocumentPermissionsTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        # Create schools
        self.school1 = SchoolFactory()  # This creates a school with an admin
        self.school2 = SchoolFactory()

        # School 1 admin reference
        self.school1_admin = self.school1.schooladmin

        # Create teacher user
        self.school1_teacher_user = UserFactory(user_type=User.TEACHER)

        # Now create and configure the teacher profile with a school
        from skul_data.users.models.teacher import Teacher

        teacher = Teacher.objects.create(
            user=self.school1_teacher_user,
            school=self.school1,
        )

        # Create class and assign to teacher
        self.school1_class = SchoolClassFactory(school=self.school1)
        teacher.assigned_class = self.school1_class
        teacher.save()

        # Store reference to teacher profile and user for tests
        self.school1_teacher = self.school1_teacher_user.teacher_profile
        # Save teacher user reference separately
        self.school1_teacher_user = self.school1_teacher.user

        # Create parent user
        self.school1_parent_user = UserFactory(user_type=User.PARENT)

        # Now create and configure the parent profile with a school
        from skul_data.users.models.parent import Parent

        parent = Parent.objects.create(
            user=self.school1_parent_user,
            school=self.school1,
        )

        # Create student and associate with parent
        self.school1_student = StudentFactory(school=self.school1)
        parent.children.add(self.school1_student)
        parent.save()

        # Store reference to parent user for tests
        self.school1_parent = self.school1_parent_user

        # School 2 admin reference
        self.school2_admin = self.school2.schooladmin

        # Documents
        self.school1_doc = DocumentFactory(
            school=self.school1, uploaded_by=self.school1_admin
        )
        self.school1_class_doc = DocumentFactory(
            school=self.school1,
            uploaded_by=self.school1_teacher_user,  # Fixed: Use User object, not Teacher profile
            related_class=self.school1_class,
        )
        self.school1_student_doc = DocumentFactory(
            school=self.school1,
            uploaded_by=self.school1_teacher_user,  # Fixed: Use User object, not Teacher profile
        )
        self.school1_student_doc.related_students.add(self.school1_student)
        self.school1_public_doc = DocumentFactory(
            school=self.school1, uploaded_by=self.school1_admin, is_public=True
        )

    def test_can_upload_document(self):
        request = self.factory.get("/")
        request.user = self.school1_admin
        self.assertTrue(CanUploadDocument().has_permission(request, None))

        # request.user = self.school1_teacher
        request.user = self.school1_teacher_user
        self.assertTrue(CanUploadDocument().has_permission(request, None))

        request.user = self.school1_parent
        self.assertFalse(CanUploadDocument().has_permission(request, None))

    def test_can_view_document(self):
        # School admin can view all docs in their school
        request = self.factory.get("/")
        request.user = self.school1_admin
        self.assertTrue(
            CanViewDocument().has_object_permission(request, None, self.school1_doc)
        )
        self.assertTrue(
            CanViewDocument().has_object_permission(
                request, None, self.school1_class_doc
            )
        )
        self.assertTrue(
            CanViewDocument().has_object_permission(
                request, None, self.school1_student_doc
            )
        )

        # School admin cannot view docs from other schools
        request.user = self.school2_admin
        self.assertFalse(
            CanViewDocument().has_object_permission(request, None, self.school1_doc)
        )

        # Teacher can view docs for their school and assigned class
        request.user = (
            self.school1_teacher_user
        )  # Fixed: Use User object, not Teacher profile
        self.assertTrue(
            CanViewDocument().has_object_permission(
                request, None, self.school1_class_doc
            )
        )
        # Teacher can view student-specific docs because they're the uploader
        self.assertTrue(  # Fixed: Changed to assertTrue since they uploaded it
            CanViewDocument().has_object_permission(
                request, None, self.school1_student_doc
            )
        )

        # Parent can view public docs and docs for their children
        request.user = self.school1_parent
        self.assertTrue(
            CanViewDocument().has_object_permission(
                request, None, self.school1_public_doc
            )
        )
        self.assertTrue(
            CanViewDocument().has_object_permission(
                request, None, self.school1_student_doc
            )
        )
        # Parent cannot view other docs
        self.assertFalse(
            CanViewDocument().has_object_permission(
                request, None, self.school1_class_doc
            )
        )

    def test_can_manage_document(self):
        # Only uploader or school admin can manage
        request = self.factory.get("/")

        # Uploader can manage
        request.user = self.school1_admin
        self.assertTrue(
            CanManageDocument().has_object_permission(request, None, self.school1_doc)
        )

        # School admin can manage any doc in their school
        other_admin = UserFactory(
            user_type=User.SCHOOL_ADMIN
        )  # Fixed: Use User.SCHOOL_ADMIN instead of UserFactory._meta.model.SCHOOL_ADMIN
        other_admin.school_admin_profile.school = self.school1
        other_admin.school_admin_profile.save()
        request.user = other_admin
        self.assertTrue(
            CanManageDocument().has_object_permission(request, None, self.school1_doc)
        )

        # Teacher can manage their own docs
        request.user = (
            self.school1_teacher_user
        )  # Fixed: Use User object, not Teacher profile
        self.assertTrue(
            CanManageDocument().has_object_permission(
                request, None, self.school1_class_doc
            )
        )

        # Teacher cannot manage other teacher's docs
        other_teacher = UserFactory(
            user_type=User.TEACHER
        )  # Fixed: Use User.TEACHER instead of UserFactory._meta.model.TEACHER

        # Create teacher profile for this user
        from skul_data.users.models.teacher import Teacher

        Teacher.objects.create(user=other_teacher, school=self.school1)

        other_teacher.teacher_profile.school = self.school1
        other_teacher.teacher_profile.save()
        request.user = other_teacher
        self.assertFalse(
            CanManageDocument().has_object_permission(
                request, None, self.school1_class_doc
            )
        )

        # Parent cannot manage any docs
        request.user = self.school1_parent
        self.assertFalse(
            CanManageDocument().has_object_permission(
                request, None, self.school1_student_doc
            )
        )


# python manage.py test skul_data.tests.documents_tests.test_documents_permissions
