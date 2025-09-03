import decimal
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db.models import Q, Avg
from rest_framework import serializers
from skul_data.exams.models.exam import (
    ExamType,
    GradingSystem,
    GradeRange,
    Exam,
    ExamSubject,
    ExamResult,
    TermReport,
)
from skul_data.students.models.student import Subject, Student
from skul_data.users.models.teacher import Teacher
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer
from skul_data.students.serializers.student import StudentSerializer
from skul_data.students.serializers.student import SubjectSerializer
from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.exams.models.exam import ExamConsolidationRule, ConsolidatedReport


class ExamTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamType
        fields = "__all__"


class GradeRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeRange
        fields = "__all__"

    def validate(self, data):
        if data.get("min_score", 0) > data.get("max_score", 100):
            raise serializers.ValidationError(
                "Minimum score cannot be greater than maximum score"
            )
        return data


class GradingSystemSerializer(serializers.ModelSerializer):
    grade_ranges = GradeRangeSerializer(many=True, read_only=True)

    class Meta:
        model = GradingSystem
        fields = "__all__"

    def validate(self, data):
        if data.get("is_default", False):
            # Ensure only one default grading system per school
            existing_query = GradingSystem.objects.filter(
                school=data["school"], is_default=True
            )

            # If updating, exclude current instance
            if self.instance:
                existing_query = existing_query.exclude(pk=self.instance.pk)

            if existing_query.exists():
                raise serializers.ValidationError(
                    "School already has a default grading system"
                )
        return data


class ExamSubjectSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), source="subject", write_only=True
    )
    teacher = serializers.SerializerMethodField()
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(),
        source="teacher",
        write_only=True,
        required=False,
        allow_null=True,
    )
    average_score = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()

    # Custom datetime handling
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = ExamSubject
        fields = [
            "id",
            "exam",
            "subject",
            "subject_id",
            "teacher",
            "teacher_id",
            "max_score",
            "pass_score",
            "weight",
            "is_published",
            "created_at",
            "updated_at",
            "average_score",
            "pass_rate",
        ]

    def get_average_score(self, obj):
        return obj.average_score

    def get_pass_rate(self, obj):
        return obj.pass_rate

    def get_teacher(self, obj):
        if not obj.teacher:
            return None
        return {
            "id": obj.teacher.id,
            "full_name": obj.teacher.full_name,
            "email": obj.teacher.email,
        }

    def get_created_at(self, obj):
        return obj.created_at.isoformat() if obj.created_at else None

    def get_updated_at(self, obj):
        return obj.updated_at.isoformat() if obj.updated_at else None


class ExamResultSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), source="student", write_only=True
    )

    class Meta:
        model = ExamResult
        fields = "__all__"
        read_only_fields = ("grade", "points", "remark", "created_at", "updated_at")

    def validate_score(self, value):
        # Check if exam_subject is in context
        exam_subject = self.context.get("exam_subject")
        if exam_subject and value and value > exam_subject.max_score:
            raise serializers.ValidationError(
                f"Score cannot be greater than maximum score of {exam_subject.max_score}"
            )
        return value


class ExamResultBulkSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        required=False,
        allow_null=True,
    )
    is_absent = serializers.BooleanField(default=False)
    teacher_comment = serializers.CharField(required=False, allow_blank=True)


class ExamSubjectResultsSerializer(serializers.ModelSerializer):
    results = ExamResultSerializer(many=True, read_only=True)
    subject = SubjectSerializer(read_only=True)

    class Meta:
        model = ExamSubject
        fields = [
            "id",
            "subject",
            "max_score",
            "pass_score",
            "weight",
            "results",
            "is_published",
        ]


class ExamSerializer(serializers.ModelSerializer):
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), source="school_class", write_only=True
    )
    grading_system = GradingSystemSerializer(read_only=True)
    grading_system_id = serializers.PrimaryKeyRelatedField(
        queryset=GradingSystem.objects.all(), source="grading_system", write_only=True
    )
    exam_type = ExamTypeSerializer(read_only=True)
    exam_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ExamType.objects.all(), source="exam_type", write_only=True
    )
    subjects = ExamSubjectSerializer(many=True, read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Exam
        fields = "__all__"
        read_only_fields = ("school",)

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError("End date cannot be before start date")

        # Ensure grading system belongs to the school
        if data["grading_system"].school != data["school_class"].school:
            raise serializers.ValidationError(
                "Grading system does not belong to the school"
            )

        return data


class TermReportSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    school_class = SchoolClassSerializer(read_only=True)

    class Meta:
        model = TermReport
        fields = "__all__"


class ExamConsolidationRuleSerializer(serializers.ModelSerializer):
    exam_type = ExamTypeSerializer(read_only=True)
    exam_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ExamType.objects.all(), source="exam_type", write_only=True
    )

    class Meta:
        model = ExamConsolidationRule
        fields = "__all__"
        read_only_fields = ("school", "created_at", "updated_at")

    def validate(self, data):
        if data["weight"] < 0 or data["weight"] > 100:
            raise serializers.ValidationError("Weight must be between 0 and 100")
        return data


class ConsolidatedReportSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    school_class = SchoolClassSerializer(read_only=True)

    class Meta:
        model = ConsolidatedReport
        fields = "__all__"
