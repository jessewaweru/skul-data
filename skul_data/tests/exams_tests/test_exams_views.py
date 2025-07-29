from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from skul_data.tests.exams_tests.test_helpers import (
    create_test_exam_type,
    create_test_grading_system,
    create_test_grade_range,
    create_test_exam,
    create_test_exam_subject,
    create_test_exam_result,
    create_default_grading_system,
    create_test_term_report,
    create_test_school,
    create_test_class,
    create_test_teacher,
    create_test_subject,
    create_test_student,
    create_test_user,
    create_test_parent,
)

from skul_data.exams.models.exam import ExamResult, TermReport


class ExamTypeViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        # Create exam types - note: ExamType doesn't have school field based on error
        self.default_type = create_test_exam_type("Default Type", True)
        self.custom_type = create_test_exam_type("Custom Type")

        self.url = reverse("examtype-list")

    def test_list_exam_types(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Since ExamType doesn't filter by school, we expect all exam types
        self.assertGreaterEqual(len(response.data), 2)

    def test_retrieve_exam_type(self):
        url = reverse("examtype-detail", args=[self.default_type.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Default Type")


class GradingSystemViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        # Create grading systems
        self.default_system = create_default_grading_system(self.school)
        self.custom_system = create_test_grading_system(self.school, "Custom System")

        self.list_url = reverse("gradingsystem-list")

    def test_list_grading_systems(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify only systems for our test school are returned
        self.assertEqual(
            len([x for x in response.data["results"] if x["school"] == self.school.id]),
            2,
        )

    def test_create_grading_system(self):
        data = {
            "name": "New Grading System",
            "is_default": False,
            "school": self.school.id,
        }

        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Grading System")

    def test_set_default_grading_system(self):
        detail_url = reverse("gradingsystem-detail", args=[self.custom_system.id])
        set_default_url = f"{detail_url}set_default/"

        response = self.client.post(set_default_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the custom system is now default and the previous default is not
        self.custom_system.refresh_from_db()
        self.default_system.refresh_from_db()
        self.assertTrue(self.custom_system.is_default)
        self.assertFalse(self.default_system.is_default)


class GradeRangeViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.grading_system = create_default_grading_system(self.school)
        self.grade_range = create_test_grade_range(self.grading_system)

        self.list_url = reverse("graderange-list")

    def test_list_grade_ranges(self):
        # Create another grade range
        create_test_grade_range(
            self.grading_system, min_score=0, max_score=50, grade="D"
        )

        response = self.client.get(
            self.list_url, {"grading_system": self.grading_system.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return the grade ranges we created plus the default ones
        self.assertGreaterEqual(len(response.data), 2)

    def test_create_grade_range(self):
        data = {
            "grading_system": self.grading_system.id,
            "min_score": 60,
            "max_score": 69,
            "grade": "C+",
            "remark": "Average Plus",
            "points": "7.0",
        }

        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["grade"], "C+")

    def test_invalid_grade_range(self):
        data = {
            "grading_system": self.grading_system.id,
            "min_score": 70,
            "max_score": 60,
            "grade": "Invalid",
            "points": "5.0",
        }

        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ExamViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_default_grading_system(self.school)

        self.list_url = reverse("exam-list")

    def test_list_exams(self):
        # Create exams for this specific test
        exam1 = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Term 1 Opener",
            term="Term 1",
            created_by=self.admin,
        )
        exam2 = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Term 1 Midterm",
            term="Term 1",
            created_by=self.admin,
        )

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_filter_exams(self):
        # Create exams with different terms for this specific test
        exam1 = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Term 1 Exam",
            term="Term 1",
            created_by=self.admin,
        )
        exam2 = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Term 3 Exam",
            term="Term 3",
            created_by=self.admin,
        )

        # Filter by existing term
        response = self.client.get(self.list_url, {"term": "Term 1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        # Filter by non-existent term
        response = self.client.get(self.list_url, {"term": "Term 2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_create_exam(self):
        data = {
            "name": "Term 1 Endterm",
            "exam_type_id": self.exam_type.id,  # Changed from exam_type to exam_type_id
            "school_class_id": self.school_class.id,  # Changed from school_class to school_class_id
            "grading_system_id": self.grading_system.id,  # Changed from grading_system to grading_system_id
            "term": "Term 1",
            "academic_year": "2023",
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
            "include_in_term_report": True,
        }
        response = self.client.post(self.list_url, data)
        print("Response data:", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_publish_exam(self):
        # Create exam for this specific test
        exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Test Exam",
            term="Term 1",
            created_by=self.admin,
        )

        detail_url = reverse("exam-detail", args=[exam.id])
        publish_url = f"{detail_url}publish/"

        response = self.client.post(publish_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        exam.refresh_from_db()
        self.assertTrue(exam.is_published)

    def test_generate_term_report(self):
        # Create exam for this specific test
        exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            name="Term Report Exam",
            term="Term 1",
            created_by=self.admin,
            include_in_term_report=True,
        )

        # Create exam subjects and results
        subject = create_test_subject(self.school)
        exam_subject = create_test_exam_subject(exam, subject)
        student = create_test_student(self.school)

        # IMPORTANT: Add student to class using the ForeignKey relationship
        # Your view uses exam.school_class.class_students which is the related_name
        # from the student_class ForeignKey field
        student.student_class = self.school_class
        student.save()

        print("Students in class:", list(self.school_class.class_students.all()))
        print("Term reports before:", TermReport.objects.count())

        create_test_exam_result(exam_subject, student, score=Decimal("80.0"))

        print("Exam results exist:", ExamResult.objects.exists())

        detail_url = reverse("exam-detail", args=[exam.id])
        generate_url = f"{detail_url}generate_term_report/"

        response = self.client.post(generate_url)
        print("Generate term report response:", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify term report was created
        term_report = TermReport.objects.filter(
            student=student,
            school_class=self.school_class,
            term=exam.term,
            academic_year=exam.academic_year,
        ).first()
        print("Term report exists:", TermReport.objects.exists())
        self.assertIsNotNone(term_report, "Term report was not created")


class ExamSubjectViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_default_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            created_by=self.admin,
        )
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)

        # Create exam subjects
        self.exam_subject1 = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )
        self.exam_subject2 = create_test_exam_subject(
            self.exam, create_test_subject(self.school, name="English"), self.teacher
        )

        self.list_url = reverse("examsubject-list")

    def test_list_exam_subjects(self):
        response = self.client.get(self.list_url, {"exam": self.exam.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data["count"], 2)

    def test_create_exam_subject(self):
        new_subject = create_test_subject(self.school, name="Science")
        data = {
            "exam": self.exam.id,
            "subject_id": new_subject.id,
            "teacher_id": self.teacher.id,
            "max_score": 100,
            "pass_score": 50,
            "weight": 100,
        }

        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_publish_exam_subject(self):
        detail_url = reverse("examsubject-detail", args=[self.exam_subject1.id])
        publish_url = f"{detail_url}publish/"

        response = self.client.post(publish_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.exam_subject1.refresh_from_db()
        self.assertTrue(self.exam_subject1.is_published)

    def test_bulk_update_results(self):
        # Create students
        student1 = create_test_student(self.school)
        student2 = create_test_student(self.school)

        detail_url = reverse("examsubject-detail", args=[self.exam_subject1.id])
        bulk_url = f"{detail_url}bulk_update_results/"

        data = [
            {
                "student_id": student1.id,
                "score": 85.0,
                "is_absent": False,
                "teacher_comment": "Excellent work",
            },
            {"student_id": student2.id, "is_absent": True, "teacher_comment": "Absent"},
        ]

        response = self.client.post(bulk_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify results were created/updated
        results = ExamResult.objects.filter(exam_subject=self.exam_subject1)
        self.assertEqual(results.count(), 2)


class ExamResultViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_default_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            created_by=self.admin,
        )
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)
        self.exam_subject = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )
        self.student = create_test_student(self.school)
        self.exam_result = create_test_exam_result(self.exam_subject, self.student)

        self.list_url = reverse("examresult-list")

    def test_list_exam_results(self):
        response = self.client.get(
            self.list_url, {"exam_subject": self.exam_subject.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["student"]["id"], self.student.id)

    def test_update_exam_result(self):
        detail_url = reverse("examresult-detail", args=[self.exam_result.id])
        data = {"score": 90.0, "is_absent": False, "teacher_comment": "Updated comment"}

        response = self.client.patch(detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.exam_result.refresh_from_db()
        self.assertEqual(self.exam_result.score, Decimal("90.0"))
        self.assertEqual(self.exam_result.teacher_comment, "Updated comment")


class TermReportViewSetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()
        self.client.force_authenticate(user=self.admin)

        self.school_class = create_test_class(self.school)
        self.list_url = reverse("termreport-list")

    def test_list_term_reports(self):
        # Create data for this specific test
        student = create_test_student(self.school)
        term_report = create_test_term_report(student, self.school_class)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["student"]["id"], student.id)

    def test_filter_term_reports(self):
        # Create data with different terms for this specific test
        student1 = create_test_student(self.school)
        student2 = create_test_student(self.school)

        term_report1 = create_test_term_report(
            student1, self.school_class, term="Term 1"
        )
        term_report2 = create_test_term_report(
            student2, self.school_class, term="Term 3"
        )

        # Filter by existing term
        response = self.client.get(self.list_url, {"term": "Term 1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        # Filter by non-existent term
        response = self.client.get(self.list_url, {"term": "Term 2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_publish_term_report(self):
        # Create data for this specific test
        student = create_test_student(self.school)
        term_report = create_test_term_report(student, self.school_class)

        detail_url = reverse("termreport-detail", args=[term_report.id])
        publish_url = f"{detail_url}publish/"

        response = self.client.post(publish_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        term_report.refresh_from_db()
        self.assertTrue(term_report.is_published)


class PermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school, self.admin = create_test_school()

        # Create exam data first
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_default_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            created_by=self.admin,
        )
        self.subject = create_test_subject(self.school)

        # Create student first
        self.student = create_test_student(self.school)

        # Properly create teacher and parent with profiles
        self.teacher = create_test_teacher(self.school)
        self.teacher_user = self.teacher.user

        self.parent = create_test_parent(self.school)
        self.parent_user = self.parent.user

        # Create exam subject
        self.exam_subject = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )

        # Assign student to parent
        self.student.parent = self.parent
        self.student.save()

        self.exam_result = create_test_exam_result(self.exam_subject, self.student)
        self.term_report = create_test_term_report(self.student, self.school_class)

    def test_admin_access(self):
        self.client.force_authenticate(user=self.admin)

        # Make sure admin has all needed permissions
        self.assertTrue(
            self.admin.role.permissions.filter(code="manage_exams").exists()
        )
        self.assertTrue(
            self.admin.role.permissions.filter(code="view_exam_results").exists()
        )

        # Then test endpoints
        endpoints = [
            reverse("examtype-list"),
            reverse("gradingsystem-list"),
            reverse("exam-list"),
            reverse("examsubject-list"),
            reverse("examresult-list"),
            reverse("termreport-list"),
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Failed for {endpoint}, got {response.status_code}",
            )

    def test_teacher_access(self):
        self.client.force_authenticate(user=self.teacher_user)

        # Teacher should be able to access their exam subjects
        response = self.client.get(reverse("examsubject-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Teacher should be able to update their exam results
        detail_url = reverse("examresult-detail", args=[self.exam_result.id])
        response = self.client.patch(detail_url, {"score": 85.0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_parent_access(self):
        self.client.force_authenticate(user=self.parent_user)

        # Parent should be able to view their child's term reports
        response = self.client.get(reverse("termreport-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data["count"], 1)

        # Parent should not be able to create exams
        response = self.client.post(reverse("exam-list"), {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# python manage.py test skul_data.tests.exams_tests.test_exams_views
