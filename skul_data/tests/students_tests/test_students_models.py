# students/tests/test_models.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from skul_data.students.models.student import (
    StudentStatus,
    StudentStatusChange,
    StudentDocument,
    StudentNote,
    Subject,
    StudentAttendance,
    AttendanceStatus,
)
from skul_data.tests.students_tests.test_helpers import (
    create_test_school,
    create_test_student,
    create_test_teacher,
    create_test_parent,
    create_test_class,
    create_test_subject,
    get_last_action_log,
)
from skul_data.action_logs.models.action_log import ActionCategory
from skul_data.students.models.student import Student


class StudentModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)
        self.teacher = create_test_teacher(self.school)
        self.parent = create_test_parent(self.school)
        self.school_class = create_test_class(self.school)
        self.subject = create_test_subject(self.school)

    def test_student_creation(self):
        self.assertEqual(self.student.full_name, "John Doe")
        self.assertEqual(self.student.age, 10)
        self.assertEqual(self.student.status, StudentStatus.ACTIVE)
        self.assertTrue(self.student.is_active)

    def test_student_promote(self):
        new_class = create_test_class(
            self.school, name="Form 2", grade_level="Form 2", academic_year="2024"
        )
        self.student.promote(new_class)
        self.assertEqual(self.student.student_class, new_class)

    def test_student_transfer(self):
        new_school, _ = create_test_school(name="New School")
        self.student.transfer(new_school)
        self.assertEqual(self.student.school, new_school)

    def test_student_graduate(self):
        self.student.graduate()
        self.assertEqual(self.student.status, StudentStatus.GRADUATED)

    def test_student_deactivate(self):
        reason = "Left school"

        # Pass the admin user to the deactivate method
        self.student.deactivate(reason, user=self.admin)

        # Test the student state changes
        self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.status, StudentStatus.LEFT)
        self.assertEqual(self.student.deletion_reason, reason)

        # Test that StudentStatusChange was created (if you added it back)
        self.assertTrue(
            StudentStatusChange.objects.filter(student=self.student).exists()
        )

        # Test ActionLog creation - filter by content_type and object_id instead of content_object
        from django.contrib.contenttypes.models import ContentType
        from skul_data.action_logs.models.action_log import ActionLog

        student_content_type = ContentType.objects.get_for_model(Student)
        action_log_exists = ActionLog.objects.filter(
            content_type=student_content_type,
            object_id=self.student.id,
            user=self.admin,
        ).exists()

        self.assertTrue(action_log_exists)

    def test_student_phone_email_address(self):
        # Test with primary parent
        self.student.parent = self.parent
        self.student.save()

        # Phone number comes from Parent model, not User
        self.assertEqual(self.student.phone_number, self.parent.phone_number)
        # Email still comes from User model
        self.assertEqual(self.student.email, self.parent.user.email)
        # Address comes from Parent model
        self.assertEqual(self.student.address, self.parent.address)

        # Test with guardians
        self.student.parent = None
        self.student.guardians.add(self.parent)
        self.student.save()

        self.assertEqual(self.student.phone_number, self.parent.phone_number)
        self.assertEqual(self.student.email, self.parent.user.email)
        self.assertEqual(self.student.address, self.parent.address)


class StudentStatusChangeModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_status_change_creation(self):
        status_change = StudentStatusChange.objects.create(
            student=self.student,
            from_status=StudentStatus.ACTIVE,
            to_status=StudentStatus.LEFT,
            reason="Test reason",
            changed_by=self.admin,
        )
        self.assertEqual(status_change.student, self.student)
        self.assertEqual(str(status_change), f"{self.student} - ACTIVE to LEFT")

    def test_status_change_logging(self):
        status_change = StudentStatusChange.objects.create(
            student=self.student,
            from_status=StudentStatus.ACTIVE,
            to_status=StudentStatus.LEFT,
            reason="Test reason",
            changed_by=self.admin,
        )

        # Verify the status change log was created
        log = get_last_action_log()
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.category, ActionCategory.UPDATE)
        self.assertIn(f"Changed student {self.student} status", log.action)
        self.assertEqual(log.content_object, self.student)
        self.assertEqual(log.metadata["reason"], "Test reason")
        self.assertEqual(log.metadata["from_status"], "ACTIVE")
        self.assertEqual(log.metadata["to_status"], "LEFT")


class StudentDocumentModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_document_creation(self):
        doc = StudentDocument.objects.create(
            student=self.student,
            title="Birth Certificate",
            document_type="BIRTH_CERTIFICATE",
            file="test.pdf",
            uploaded_by=self.admin,
        )
        self.assertEqual(doc.student, self.student)
        self.assertEqual(str(doc), f"Birth Certificate for {self.student}")


class StudentNoteModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_note_creation(self):
        note = StudentNote.objects.create(
            student=self.student,
            note_type="ACADEMIC",
            content="Test note",
            created_by=self.admin,
        )
        self.assertEqual(note.student, self.student)
        self.assertEqual(str(note), f"Academic note for {self.student}")


class SubjectModelTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()

    def test_subject_creation(self):
        subject = Subject.objects.create(
            name="Mathematics",
            code="MATH",
            school=self.school,
        )
        self.assertEqual(str(subject), "Mathematics")


class StudentAttendanceModelTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.student = create_test_student(self.school)

    def test_attendance_creation(self):
        attendance = StudentAttendance.objects.create(
            student=self.student,
            date=timezone.now().date(),
            status=AttendanceStatus.PRESENT,
            recorded_by=self.admin,
        )
        self.assertEqual(attendance.student, self.student)
        self.assertTrue(attendance.is_present)
        self.assertFalse(attendance.is_absent)

    def test_attendance_methods(self):
        attendance = StudentAttendance.objects.create(
            student=self.student,
            date=timezone.now().date(),
            recorded_by=self.admin,
        )

        # Test mark_present
        attendance.mark_present(self.admin)
        self.assertEqual(attendance.status, AttendanceStatus.PRESENT)

        # Test mark_absent
        attendance.mark_absent("Sick", self.admin)
        self.assertEqual(attendance.status, AttendanceStatus.ABSENT)
        self.assertEqual(attendance.reason, "Sick")

        # Test mark_late
        attendance.mark_late("09:30", "Overslept", self.admin)
        self.assertEqual(attendance.status, AttendanceStatus.LATE)
        self.assertEqual(attendance.time_in, "09:30")

        # Test mark_excused
        attendance.mark_excused("Doctor appointment", self.admin)
        self.assertEqual(attendance.status, AttendanceStatus.EXCUSED)


# python manage.py test skul_data.tests.students_tests.test_students_models
