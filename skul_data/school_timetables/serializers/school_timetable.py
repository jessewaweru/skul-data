from rest_framework import serializers
from skul_data.school_timetables.models.school_timetable import (
    TimeSlot,
    TimetableStructure,
    Timetable,
    Lesson,
    TimetableConstraint,
    SubjectGroup,
    TeacherAvailability,
)
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer
from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.students.serializers.student import SubjectSerializer
from skul_data.students.models.student import Subject
from datetime import datetime


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = [
            "id",
            "name",
            "start_time",
            "end_time",
            "day_of_week",
            "is_break",
            "break_name",
            "order",
            "is_active",
        ]


class TimetableStructureSerializer(serializers.ModelSerializer):
    time_slots = serializers.SerializerMethodField()

    class Meta:
        model = TimetableStructure
        fields = "__all__"
        extra_kwargs = {
            "school": {"required": False}  # Make school not required in input
        }

    def get_time_slots(self, obj):
        timeslots = TimeSlot.objects.filter(school=obj.school)
        return TimeSlotSerializer(timeslots, many=True).data

    def validate(self, data):
        # Ensure school is either in data or context
        if "school" not in data and "school" not in self.context:
            raise serializers.ValidationError("School is required")
        return data

    def create(self, validated_data):
        # Get school from context if not in data
        if "school" not in validated_data:
            validated_data["school"] = self.context["school"]

        # Create the structure
        instance = super().create(validated_data)

        # Generate time slots
        instance.generate_time_slots()
        return instance


class LessonSerializer(serializers.ModelSerializer):
    subject_details = SubjectSerializer(source="subject", read_only=True)
    teacher_details = TeacherSerializer(source="teacher", read_only=True)
    time_slot_details = TimeSlotSerializer(source="time_slot", read_only=True)
    day_of_week = serializers.CharField(source="time_slot.day_of_week", read_only=True)
    start_time = serializers.TimeField(source="time_slot.start_time", read_only=True)
    end_time = serializers.TimeField(source="time_slot.end_time", read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id",
            "timetable",
            "subject",
            "subject_details",
            "teacher",
            "teacher_details",
            "time_slot",
            "time_slot_details",
            "day_of_week",
            "start_time",
            "end_time",
            "is_double_period",
            "room",
            "notes",
        ]


# In TimetableSerializer, add lessons details
class TimetableSerializer(serializers.ModelSerializer):
    school_class_details = SchoolClassSerializer(source="school_class", read_only=True)
    lessons_count = serializers.SerializerMethodField()
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Timetable
        fields = [
            "id",
            "school_class",
            "school_class_details",
            "academic_year",
            "term",
            "is_active",
            "lessons_count",
            "lessons",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_lessons_count(self, obj):
        return obj.lessons.count()


# Fix the LessonSerializer to include proper relationships


class TimetableConstraintSerializer(serializers.ModelSerializer):
    category = serializers.CharField(read_only=True)

    class Meta:
        model = TimetableConstraint
        fields = [
            "id",
            "school",
            "constraint_type",
            "category",
            "is_hard_constraint",
            "parameters",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "category"]

    def validate(self, data):
        constraint_type = data.get("constraint_type")
        parameters = data.get("parameters", {})

        # Validate parameters for specific constraint types
        if constraint_type == "SUBJECT_GROUPING":
            if not parameters.get("subject_group"):
                raise serializers.ValidationError(
                    "Subject grouping requires a subject group ID"
                )

        return data


class SubjectGroupSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)
    subject_ids = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), source="subjects", many=True, write_only=True
    )

    class Meta:
        model = SubjectGroup
        fields = [
            "id",
            "school",
            "name",
            "subjects",
            "subject_ids",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class TeacherAvailabilitySerializer(serializers.ModelSerializer):
    teacher_details = TeacherSerializer(source="teacher", read_only=True)

    # Custom field to handle datetime to date conversion if needed
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = TeacherAvailability
        fields = [
            "id",
            "teacher",
            "teacher_details",
            "day_of_week",
            "is_available",
            "available_from",
            "available_to",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_created_at(self, obj):
        """Convert datetime to date if necessary"""
        if hasattr(obj, "created_at") and obj.created_at:
            if isinstance(obj.created_at, datetime):
                return obj.created_at.date()
            return obj.created_at
        return None

    def get_updated_at(self, obj):
        """Convert datetime to date if necessary"""
        if hasattr(obj, "updated_at") and obj.updated_at:
            if isinstance(obj.updated_at, datetime):
                return obj.updated_at.date()
            return obj.updated_at
        return None


class TimetableGenerateSerializer(serializers.Serializer):
    school_class_ids = serializers.ListField(
        child=serializers.IntegerField(), required=True
    )
    academic_year = serializers.CharField(required=True)
    term = serializers.IntegerField(required=True)
    regenerate_existing = serializers.BooleanField(default=False)
    apply_constraints = serializers.BooleanField(default=True)

    # ADDED: Subject assignments field
    subject_assignments = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="List of subject assignments with subject_id, teacher_id, and required_periods",
    )

    def validate_school_class_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one class ID must be provided")
        return value

    def validate_subject_assignments(self, value):
        """Validate subject assignments structure"""
        if not value:
            return value

        for idx, assignment in enumerate(value):
            if "subject_id" not in assignment:
                raise serializers.ValidationError(
                    f"Assignment {idx}: missing subject_id"
                )
            if "teacher_id" not in assignment:
                raise serializers.ValidationError(
                    f"Assignment {idx}: missing teacher_id"
                )
            if "required_periods" not in assignment:
                assignment["required_periods"] = 5  # Default

        return value


class TimetableCloneSerializer(serializers.Serializer):
    source_academic_year = serializers.CharField(required=True)
    source_term = serializers.IntegerField(required=True)
    target_academic_year = serializers.CharField(required=True)
    target_term = serializers.IntegerField(required=True)
    school_class_ids = serializers.ListField(
        child=serializers.IntegerField(), required=True
    )

    def validate_school_class_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one class ID must be provided")
        return value
