from django.test import TestCase
from skul_data.tests.teachers_tests.test_helpers import (
    create_test_teacher,
    create_test_teacher_workload,
    create_test_teacher_attendance,
    create_test_teacher_document,
    create_test_school,
)
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Subject
from skul_data.users.models.base_user import User
from django.utils import timezone


class TeacherModelTest(TestCase):
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

    def test_teacher_creation(self):
        self.assertEqual(self.teacher.user.user_type, User.TEACHER)
        self.assertEqual(self.teacher.school, self.school)
        self.assertEqual(self.teacher.status, "ACTIVE")
        self.assertEqual(self.teacher.subjects_taught.count(), 1)
        self.assertEqual(self.teacher.assigned_classes.count(), 1)

    def test_teacher_str_representation(self):
        self.assertEqual(
            str(self.teacher),
            f"{self.teacher.user.get_full_name()} - {self.school.name}",
        )

    def test_teacher_full_name_property(self):
        self.assertEqual(
            self.teacher.full_name,
            f"{self.teacher.user.first_name} {self.teacher.user.last_name}",
        )

    def test_teacher_email_property(self):
        self.assertEqual(self.teacher.email, self.teacher.user.email)

    def test_teacher_active_students_count(self):
        # This would need students to be created to test properly
        self.assertEqual(self.teacher.active_students_count, 0)

    def test_teacher_current_classes(self):
        # Option 1: Set academic year to current year
        current_year = str(timezone.now().year)
        self.school_class.academic_year = current_year
        self.school_class.save()

        current_classes = self.teacher.current_classes
        self.assertEqual(current_classes.count(), 1)
        self.assertEqual(current_classes.first(), self.school_class)

    def test_teacher_status_change_signal(self):
        # Refresh the teacher instance to ensure we're working with DB state
        self.teacher.refresh_from_db()

        # Test TERMINATED status deactivates user
        self.teacher.status = "TERMINATED"
        self.teacher.save()
        self.teacher.user.refresh_from_db()  # Important!
        self.assertFalse(self.teacher.user.is_active)

        # Test reactivating when status changes back to ACTIVE
        self.teacher.status = "ACTIVE"
        self.teacher.save()
        self.teacher.user.refresh_from_db()  # Important!
        self.assertTrue(self.teacher.user.is_active)


class TeacherWorkloadModelTest(TestCase):
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
        self.teacher = create_test_teacher(self.school)
        self.workload = create_test_teacher_workload(
            self.teacher, self.school_class, self.subject
        )

    def test_workload_creation(self):
        self.assertEqual(self.workload.teacher, self.teacher)
        self.assertEqual(self.workload.school_class, self.school_class)
        self.assertEqual(self.workload.subject, self.subject)
        self.assertEqual(self.workload.hours_per_week, 10)

    def test_workload_str_representation(self):
        self.assertEqual(
            str(self.workload), f"{self.teacher} - {self.subject} (10 hrs/wk)"
        )

    def test_workload_unique_together(self):
        with self.assertRaises(Exception):
            create_test_teacher_workload(
                self.teacher,
                self.school_class,
                self.subject,
                term="Term 1",
                school_year="2023",
            )


class TeacherAttendanceModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.attendance = create_test_teacher_attendance(self.teacher)

    def test_attendance_creation(self):
        self.assertEqual(self.attendance.teacher, self.teacher)
        self.assertEqual(self.attendance.status, "PRESENT")
        self.assertIsNotNone(self.attendance.check_in)
        self.assertIsNotNone(self.attendance.check_out)

    def test_attendance_str_representation(self):
        expected_str = (
            f"{self.teacher} - {self.attendance.date}: "
            f"{self.attendance.get_status_display()}"
        )
        self.assertEqual(str(self.attendance), expected_str)

    def test_attendance_unique_together(self):
        with self.assertRaises(Exception):
            create_test_teacher_attendance(self.teacher, date=self.attendance.date)


class TeacherDocumentModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.teacher = create_test_teacher(self.school)
        self.document = create_test_teacher_document(self.teacher, self.admin)

    def test_document_creation(self):
        self.assertEqual(self.document.teacher, self.teacher)
        self.assertEqual(self.document.title, "Test Document")
        self.assertEqual(self.document.document_type, "QUALIFICATION")
        self.assertEqual(self.document.uploaded_by, self.admin)

    def test_document_str_representation(self):
        expected_str = f"Test Document (Qualification) for {self.teacher}"
        self.assertEqual(str(self.document), expected_str)


# python manage.py test skul_data.tests.teachers_tests.test_teachers_models
