from django.test import TestCase
from rest_framework.exceptions import ValidationError
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Subject
from skul_data.users.models.base_user import User
from .test_helpers import create_test_teacher
from skul_data.users.serializers.teacher import (
    TeacherSerializer,
    TeacherCreateSerializer,
    TeacherStatusChangeSerializer,
    TeacherAssignmentSerializer,
    TeacherSubjectAssignmentSerializer,
    TeacherWorkloadSerializer,
    TeacherAttendanceSerializer,
    TeacherDocumentSerializer,
)
from skul_data.tests.teachers_tests.test_helpers import (
    create_test_teacher,
    create_test_teacher_workload,
    create_test_teacher_attendance,
    create_test_teacher_document,
    create_test_school,
)


class TeacherSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH", school=self.school
        )
        self.school_class = SchoolClass.objects.create(
            name="Form 1",
            grade_level="Form 1",
            school=self.school,
            academic_year="2023",
        )
        self.teacher = create_test_teacher(
            self.school, subjects=[self.subject], classes=[self.school_class]
        )

    def test_teacher_serializer(self):
        serializer = TeacherSerializer(self.teacher)
        data = serializer.data

        self.assertEqual(data["first_name"], self.teacher.user.first_name)
        self.assertEqual(data["last_name"], self.teacher.user.last_name)
        self.assertEqual(data["email"], self.teacher.user.email)
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(len(data["subjects_taught"]), 1)
        self.assertEqual(len(data["assigned_classes_ids"]), 1)

    def test_teacher_create_serializer(self):
        user = User.objects.create_user(
            email="newteacher@test.com",
            username="newteacher",
            password="testpass",
            first_name="New",
            last_name="Teacher",
            user_type=User.TEACHER,
        )

        data = {
            "user_id": user.id,
            "school": self.school.id,
            "phone_number": "+254711111111",
            "status": "ACTIVE",
            "qualification": "B.Ed",
            "specialization": "English",
            "years_of_experience": 3,
            "subject_ids": [self.subject.id],
            "class_ids": [self.school_class.id],
        }

        serializer = TeacherCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        teacher = serializer.save()

        self.assertEqual(teacher.user, user)
        self.assertEqual(teacher.school, self.school)
        self.assertEqual(teacher.subjects_taught.count(), 1)
        self.assertEqual(teacher.assigned_classes.count(), 1)

    def test_teacher_create_serializer_invalid_user(self):
        # Test with user who is already a teacher
        data = {
            "user_id": self.teacher.user.id,
            "school": self.school.id,
        }

        serializer = TeacherCreateSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TeacherStatusChangeSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)

    def test_status_change_serializer_valid(self):
        data = {"status": "TERMINATED", "termination_date": "2023-12-31"}
        serializer = TeacherStatusChangeSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_status_change_serializer_missing_termination_date(self):
        data = {"status": "TERMINATED"}
        serializer = TeacherStatusChangeSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TeacherAssignmentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.school_class = SchoolClass.objects.create(
            name="Form 1",
            grade_level="Form 1",
            school=self.school,
            academic_year="2023",
        )

    def test_assignment_serializer_valid(self):
        data = {"class_ids": [self.school_class.id], "action": "ADD"}
        serializer = TeacherAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_assignment_serializer_invalid_action(self):
        data = {"class_ids": [self.school_class.id], "action": "INVALID"}
        serializer = TeacherAssignmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class TeacherSubjectAssignmentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH", school=self.school
        )
        self.subject2 = Subject.objects.create(
            name="English", code="ENG", school=self.school
        )
        self.teacher = create_test_teacher(self.school)

    def test_subject_assignment_serializer_valid(self):
        data = {"subject_ids": [self.subject.id, self.subject2.id], "action": "ADD"}
        serializer = TeacherSubjectAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_subject_assignment_serializer_invalid_action(self):
        data = {"subject_ids": [self.subject.id], "action": "INVALID_ACTION"}
        serializer = TeacherSubjectAssignmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("action", serializer.errors)

    def test_subject_assignment_serializer_empty_subjects(self):
        data = {"subject_ids": [], "action": "ADD"}
        serializer = TeacherSubjectAssignmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("subject_ids", serializer.errors)


class TeacherWorkloadSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH", school=self.school
        )
        self.school_class = SchoolClass.objects.create(
            name="Form 1",
            grade_level="Form 1",
            school=self.school,
            academic_year="2023",
        )
        self.workload = create_test_teacher_workload(
            self.teacher, self.school_class, self.subject
        )

    def test_workload_serializer(self):
        serializer = TeacherWorkloadSerializer(self.workload)
        data = serializer.data

        self.assertEqual(data["teacher"]["id"], self.teacher.id)
        self.assertEqual(data["school_class"]["id"], self.school_class.id)
        self.assertEqual(data["subject"]["id"], self.subject.id)
        self.assertEqual(data["hours_per_week"], 10)

    def test_workload_serializer_create(self):
        data = {
            "teacher_id": self.teacher.id,
            "school_class_id": self.school_class.id,
            "subject_id": self.subject.id,
            "hours_per_week": 15,
            "term": "Term 2",
            "school_year": "2024",
        }
        serializer = TeacherWorkloadSerializer(data=data)
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
        self.assertTrue(serializer.is_valid())
        workload = serializer.save()
        self.assertEqual(workload.hours_per_week, 15)


class TeacherAttendanceSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.attendance = create_test_teacher_attendance(self.teacher)

    def test_attendance_serializer(self):
        serializer = TeacherAttendanceSerializer(self.attendance)
        data = serializer.data

        self.assertEqual(data["teacher"]["id"], self.teacher.id)
        self.assertEqual(data["status"], "PRESENT")
        self.assertIsNotNone(data["check_in"])
        self.assertIsNotNone(data["check_out"])

    def test_attendance_serializer_create(self):
        data = {
            "teacher_id": self.teacher.id,
            "date": "2023-01-01",
            "status": "ABSENT",
            "recorded_by_id": self.admin.id,
        }
        serializer = TeacherAttendanceSerializer(data=data)
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
        self.assertTrue(serializer.is_valid())
        attendance = serializer.save()
        self.assertEqual(attendance.status, "ABSENT")


class TeacherDocumentSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.document = create_test_teacher_document(self.teacher, self.admin)

    def test_document_serializer(self):
        serializer = TeacherDocumentSerializer(self.document)
        data = serializer.data

        self.assertEqual(data["teacher"]["id"], self.teacher.id)
        self.assertEqual(data["title"], "Test Document")
        self.assertEqual(data["document_type"], "QUALIFICATION")
        self.assertEqual(data["uploaded_by"]["id"], self.admin.id)

    def test_document_serializer_create(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("test.pdf", b"test content")

        data = {
            "teacher_id": self.teacher.id,
            "title": "New Document",
            "document_type": "CONTRACT",
            "file": file,
            "uploaded_by_id": self.admin.id,
            "is_confidential": True,
        }
        serializer = TeacherDocumentSerializer(data=data)
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
        self.assertTrue(serializer.is_valid())
        document = serializer.save()
        self.assertEqual(document.title, "New Document")


# python manage.py test skul_data.tests.teachers_tests.test_teachers_serializers
