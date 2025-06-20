from rest_framework import serializers
from skul_data.users.models.teacher import (
    Teacher,
    TeacherAttendance,
    TeacherWorkload,
    TeacherDocument,
)
from skul_data.users.models.base_user import User
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer
from skul_data.users.serializers.base_user import BaseUserSerializer
from skul_data.students.serializers.student import SubjectSerializer
from skul_data.schools.models.schoolclass import SchoolClass
from skul_data.students.models.student import Subject
from django.utils import timezone
from datetime import datetime, date


class DateFieldWithoutTime(serializers.DateField):
    def to_representation(self, value):
        if value is None:
            return None

        # Convert datetime to date if needed
        if isinstance(value, datetime):
            return value.date().isoformat()
        elif isinstance(value, date):
            return value.isoformat()

        return super().to_representation(value)

    def to_internal_value(self, data):
        # Ensure we always return a date object
        result = super().to_internal_value(data)
        if isinstance(result, datetime):
            return result.date()
        return result


class TeacherSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True
    )
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    # phone_number = serializers.CharField(source="user.phone_number")
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    subjects_taught = SubjectSerializer(many=True, read_only=True)
    assigned_classes_ids = serializers.PrimaryKeyRelatedField(
        source="assigned_classes", many=True, read_only=True
    )
    active_students_count = serializers.IntegerField(read_only=True)
    current_classes_ids = serializers.PrimaryKeyRelatedField(
        source="current_classes", many=True, read_only=True
    )
    is_administrator = serializers.BooleanField()
    # administrator_since = serializers.DateField(required=False)
    # administrator_until = serializers.DateField(required=False)
    administrator_since = DateFieldWithoutTime(required=False)
    administrator_until = DateFieldWithoutTime(required=False)
    administrator_notes = serializers.CharField(required=False)

    class Meta:
        model = Teacher
        fields = [
            "id",
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "school",
            "status",
            "hire_date",
            "phone_number",
            "termination_date",
            "qualification",
            "specialization",
            "years_of_experience",
            "bio",
            "office_location",
            "office_hours",
            "is_class_teacher",
            "is_department_head",
            "payroll_number",
            "subjects_taught",
            # "assigned_classes",
            "assigned_classes_ids",
            "active_students_count",
            # "current_classes",
            "current_classes_ids",
            "last_login",
            "is_administrator",
            "administrator_since",
            "administrator_until",
            "administrator_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_assigned_classes(self, obj):
        from skul_data.schools.serializers.schoolclass import SchoolClassSerializer

        return SchoolClassSerializer(obj.assigned_classes.all(), many=True).data

    def get_current_classes(self, obj):
        from skul_data.schools.serializers.schoolclass import SchoolClassSerializer

        return SchoolClassSerializer(obj.current_classes.all(), many=True).data

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        user = instance.user

        # Update user fields
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        # Update teacher fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class TeacherCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True
    )
    subject_ids = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(),
        source="subjects_taught",
        many=True,
        required=False,
    )
    class_ids = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(),
        source="assigned_classes",
        many=True,
        required=False,
    )
    hire_date = serializers.DateField(required=False)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Teacher
        fields = [
            "user_id",
            "school",
            "phone_number",
            "status",
            "hire_date",
            "qualification",
            "specialization",
            "years_of_experience",
            "subject_ids",
            "class_ids",
            "is_class_teacher",
            "is_department_head",
            "payroll_number",
            "first_name",
            "last_name",
            "email",
        ]

    def validate_user_id(self, value):
        if hasattr(value, "teacher_profile"):
            raise serializers.ValidationError("This user is already a teacher")
        return value

    def get_subjects_taught(self, obj):
        from skul_data.students.serializers.student import SubjectSerializer

        return SubjectSerializer(obj.subjects_taught.all(), many=True).data

    def create(self, validated_data):
        if "hire_date" not in validated_data:
            validated_data["hire_date"] = timezone.now().date()
        return super().create(validated_data)


class TeacherStatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Teacher.STATUS_CHOICES)
    termination_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        if data["status"] == "TERMINATED" and not data.get("termination_date"):
            raise serializers.ValidationError(
                "Termination date is required when status is TERMINATED"
            )
        return data


class TeacherAssignmentSerializer(serializers.Serializer):
    class_ids = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), many=True
    )
    action = serializers.ChoiceField(choices=["ADD", "REMOVE", "REPLACE"])


class TeacherSubjectAssignmentSerializer(serializers.Serializer):
    subject_ids = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), many=True
    )
    action = serializers.ChoiceField(choices=["ADD", "REMOVE", "REPLACE"])

    def validate_subject_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one subject is required.")
        return value


class TeacherWorkloadSerializer(serializers.ModelSerializer):
    teacher = TeacherSerializer(read_only=True)
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(), source="teacher", write_only=True, required=True
    )
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(),
        source="school_class",
        write_only=True,
        required=True,
    )
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), source="subject", write_only=True, required=True
    )

    class Meta:
        model = TeacherWorkload
        fields = [
            "id",
            "teacher",
            "teacher_id",
            "school_class",
            "school_class_id",
            "subject",
            "subject_id",
            "hours_per_week",
            "term",
            "school_year",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    teacher = TeacherSerializer(read_only=True)
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(), source="teacher", write_only=True, required=True
    )
    recorded_by = BaseUserSerializer(read_only=True)
    recorded_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="recorded_by",
        write_only=True,
        required=False,
    )

    class Meta:
        model = TeacherAttendance
        fields = [
            "id",
            "teacher",
            "teacher_id",
            "date",
            "status",
            "check_in",
            "check_out",
            "notes",
            "recorded_by",
            "recorded_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class TeacherDocumentSerializer(serializers.ModelSerializer):
    teacher = TeacherSerializer(read_only=True)
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(), source="teacher", write_only=True, required=True
    )
    uploaded_by = BaseUserSerializer(read_only=True)
    uploaded_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="uploaded_by",
        write_only=True,
        required=True,
    )

    class Meta:
        model = TeacherDocument
        fields = [
            "id",
            "teacher",
            "teacher_id",
            "title",
            "document_type",
            "file",
            "description",
            "uploaded_by",
            "uploaded_by_id",
            "is_confidential",
            "uploaded_at",
        ]
        read_only_fields = ["uploaded_at"]
