from django.test import TestCase
from decimal import Decimal
from rest_framework.exceptions import ValidationError
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
)
from skul_data.exams.serializers.exam import (
    ExamTypeSerializer,
    GradingSystemSerializer,
    GradeRangeSerializer,
    ExamSerializer,
    ExamSubjectSerializer,
    ExamResultSerializer,
    ExamResultBulkSerializer,
    TermReportSerializer,
)


class ExamTypeSerializerTest(TestCase):
    def setUp(self):
        self.exam_type = create_test_exam_type()
        self.serializer = ExamTypeSerializer(instance=self.exam_type)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()), {"id", "name", "description", "is_default", "created_at"}
        )

    def test_name_field_content(self):
        data = self.serializer.data
        self.assertEqual(data["name"], "Test Exam Type")


class GradingSystemSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.grading_system = create_test_grading_system(self.school)
        self.serializer = GradingSystemSerializer(instance=self.grading_system)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "name",
                "school",
                "is_default",
                "created_at",
                "updated_at",
                "grade_ranges",
            },
        )

    def test_grade_ranges_relationship(self):
        # Create grade ranges
        create_test_grade_range(
            self.grading_system, min_score=0, max_score=50, grade="D"
        )
        create_test_grade_range(
            self.grading_system, min_score=51, max_score=100, grade="A"
        )

        data = self.serializer.data
        self.assertEqual(len(data["grade_ranges"]), 2)
        self.assertEqual(data["grade_ranges"][0]["grade"], "A")

    def test_validate_unique_default(self):
        # Create a default grading system
        create_test_grading_system(self.school, "Default System", True)

        data = {"name": "Another Default", "school": self.school.id, "is_default": True}

        serializer = GradingSystemSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class GradeRangeSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.grading_system = create_test_grading_system(self.school)
        self.grade_range = create_test_grade_range(self.grading_system)
        self.serializer = GradeRangeSerializer(instance=self.grade_range)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        # Fixed: Removed 'created_at' from expected fields if it's not in the model
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "grading_system",
                "min_score",
                "max_score",
                "grade",
                "remark",
                "points",
            },
        )

    def test_min_max_score_validation(self):
        data = {
            "grading_system": self.grading_system.id,
            "min_score": 60,
            "max_score": 50,
            "grade": "B",
            "remark": "Test",
            "points": 5.0,
        }

        serializer = GradeRangeSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class ExamSerializerTest(TestCase):
    def setUp(self):
        self.school, self.admin = create_test_school()
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_test_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class,
            self.exam_type,
            self.grading_system,
            created_by=self.admin,
        )
        self.serializer = ExamSerializer(instance=self.exam)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        # Fixed: Removed the _id fields that are write_only
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "name",
                "exam_type",
                "school",
                "school_class",
                "term",
                "academic_year",
                "start_date",
                "end_date",
                "grading_system",
                "is_published",
                "include_in_term_report",
                "created_by",
                "created_at",
                "updated_at",
                "subjects",
                "status",
            },
        )

    def test_date_validation(self):
        data = {
            "name": "Invalid Date Exam",
            "exam_type_id": self.exam_type.id,
            "school_class_id": self.school_class.id,
            "term": "Term 1",
            "academic_year": "2023",
            "start_date": "2023-01-10",
            "end_date": "2023-01-01",
            "grading_system_id": self.grading_system.id,
        }

        serializer = ExamSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_grading_system_school_validation(self):
        # Create another school and grading system
        other_school, _ = create_test_school(name="Other School")
        other_grading_system = create_test_grading_system(other_school)

        data = {
            "name": "Invalid Grading System",
            "exam_type_id": self.exam_type.id,
            "school_class_id": self.school_class.id,
            "term": "Term 1",
            "academic_year": "2023",
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
            "grading_system_id": other_grading_system.id,
        }

        serializer = ExamSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class ExamSubjectSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_test_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class, self.exam_type, self.grading_system
        )
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)
        self.exam_subject = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )
        self.serializer = ExamSubjectSerializer(instance=self.exam_subject)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        # Fixed: Only include fields that should be in the serialized output
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "exam",
                "subject",
                "teacher",
                "max_score",
                "pass_score",
                "weight",
                "is_published",
                "created_at",
                "updated_at",
                "average_score",
                "pass_rate",
            },
        )

    def test_average_score_calculation(self):
        # Create students and results
        student1 = create_test_student(self.school)
        student2 = create_test_student(self.school)

        create_test_exam_result(self.exam_subject, student1, score=Decimal("80.0"))
        create_test_exam_result(self.exam_subject, student2, score=Decimal("70.0"))

        # Create a fresh serializer instance to get updated data
        fresh_serializer = ExamSubjectSerializer(instance=self.exam_subject)
        data = fresh_serializer.data
        self.assertEqual(data["average_score"], 75.0)


class ExamResultSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.exam_type = create_test_exam_type()
        self.grading_system = create_default_grading_system(self.school)
        self.exam = create_test_exam(
            self.school_class, self.exam_type, self.grading_system
        )
        self.subject = create_test_subject(self.school)
        self.teacher = create_test_teacher(self.school)
        self.exam_subject = create_test_exam_subject(
            self.exam, self.subject, self.teacher
        )
        self.student = create_test_student(self.school)
        self.exam_result = create_test_exam_result(self.exam_subject, self.student)
        self.serializer = ExamResultSerializer(instance=self.exam_result)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        # Fixed: Removed _id fields that are write_only
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "exam_subject",
                "student",
                "score",
                "grade",
                "points",
                "remark",
                "teacher_comment",
                "is_absent",
                "created_at",
                "updated_at",
            },
        )

    def test_grade_calculation(self):
        data = self.serializer.data
        self.assertEqual(data["grade"], "B")
        self.assertEqual(data["points"], "9.00")
        self.assertEqual(data["remark"], "Good")

    def test_score_validation(self):
        data = {
            "exam_subject": self.exam_subject.id,
            "student_id": self.student.id,
            "score": 150,  # Above max_score of 100
        }

        serializer = ExamResultSerializer(
            data=data, context={"exam_subject": self.exam_subject}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class ExamResultBulkSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.student1 = create_test_student(self.school)
        self.student2 = create_test_student(self.school)

    def test_valid_bulk_data(self):
        data = [
            {
                "student_id": self.student1.id,
                "score": 80.0,
                "is_absent": False,
                "teacher_comment": "Good work",
            },
            {
                "student_id": self.student2.id,
                "is_absent": True,
                "teacher_comment": "Absent",
            },
        ]

        serializer = ExamResultBulkSerializer(data=data, many=True)
        self.assertTrue(serializer.is_valid())

    def test_invalid_bulk_data(self):
        data = [
            {
                "student_id": self.student1.id,
                "score": -10,  # Invalid score
                "is_absent": False,
            }
        ]

        serializer = ExamResultBulkSerializer(data=data, many=True)
        self.assertFalse(serializer.is_valid())


class TermReportSerializerTest(TestCase):
    def setUp(self):
        self.school, _ = create_test_school()
        self.school_class = create_test_class(self.school)
        self.student = create_test_student(self.school)
        self.term_report = create_test_term_report(self.student, self.school_class)
        self.serializer = TermReportSerializer(instance=self.term_report)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertEqual(
            set(data.keys()),
            {
                "id",
                "student",
                "school_class",
                "term",
                "academic_year",
                "total_score",
                "average_score",
                "overall_grade",
                "overall_position",
                "class_average",
                "class_highest",
                "class_lowest",
                "principal_comment",
                "class_teacher_comment",
                "is_published",
                "created_at",
                "updated_at",
            },
        )

    def test_student_relationship(self):
        data = self.serializer.data
        self.assertEqual(data["student"]["id"], self.student.id)
        self.assertEqual(data["school_class"]["id"], self.school_class.id)


# python manage.py test skul_data.tests.exams_tests.test_exams_serializers
