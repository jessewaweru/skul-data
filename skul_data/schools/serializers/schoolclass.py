from rest_framework import serializers
from skul_data.schools.models.schoolclass import (
    SchoolClass,
    ClassTimetable,
    ClassDocument,
    ClassAttendance,
)

# from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.students.serializers.student import StudentSerializer, SubjectSerializer
from skul_data.users.serializers.base_user import BaseUserSerializer
from skul_data.schools.serializers.schoolstream import SchoolStreamSerializer
from skul_data.schools.models.schoolstream import SchoolStream


class SchoolClassSerializer(serializers.ModelSerializer):

    # class_teacher = TeacherSerializer(read_only=True)
    class_teacher_id = serializers.PrimaryKeyRelatedField(
        read_only=True, source="class_teacher"
    )
    class_teacher_name = serializers.SerializerMethodField()
    students = StudentSerializer(many=True, read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    average_performance = serializers.FloatField(read_only=True)
    stream = SchoolStreamSerializer(read_only=True)
    stream_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolStream.objects.all(),
        source="stream",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = SchoolClass
        fields = [
            "id",
            "name",
            "grade_level",
            "stream",
            "stream_id",
            "level",
            "class_teacher",
            "school",
            "students",
            "subjects",
            "academic_year",
            "room_number",
            "capacity",
            "is_active",
            "student_count",
            "average_performance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "student_count",
            "average_performance",
        ]

    def validate_stream_id(self, value):
        if value and value.school != self.context["request"].user.school:
            raise serializers.ValidationError("Invalid stream for this school")
        return value

    def get_class_teacher_name(self, obj):
        if obj.class_teacher:
            return f"{obj.class_teacher.user.first_name} {obj.class_teacher.user.last_name}"
        return None


class SchoolClassCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolClass
        fields = [
            "name",
            "grade_level",
            "stream",
            "level",
            "class_teacher",
            "academic_year",
            "room_number",
            "capacity",
        ]

    def validate(self, data):
        """Example: Prevent duplicate class names within same academic year"""
        school = self.context["request"].user.school
        if SchoolClass.objects.filter(
            school=school,
            grade_level=data["grade_level"],
            stream=data.get("stream"),
            academic_year=data["academic_year"],
        ).exists():
            raise serializers.ValidationError(
                "A class with these attributes already exists"
            )
        return data


class SchoolClassPromoteSerializer(serializers.Serializer):
    new_academic_year = serializers.CharField(max_length=20)

    def validate_new_academic_year(self, value):
        if not value or len(value) < 4:
            raise serializers.ValidationError("Invalid academic year format")
        return value


class ClassTimetableSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassTimetable
        fields = [
            "id",
            "school_class",
            "file",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ClassDocumentSerializer(serializers.ModelSerializer):
    created_by = BaseUserSerializer(read_only=True)

    class Meta:
        model = ClassDocument
        fields = [
            "id",
            "school_class",
            "title",
            "document_type",
            "file",
            "description",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "created_by"]


class ClassAttendanceSerializer(serializers.ModelSerializer):
    present_students = StudentSerializer(many=True, read_only=True)
    taken_by = BaseUserSerializer(read_only=True)
    attendance_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = ClassAttendance
        fields = [
            "id",
            "school_class",
            "date",
            "present_students",
            "taken_by",
            "notes",
            "attendance_rate",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "attendance_rate", "taken_by"]
