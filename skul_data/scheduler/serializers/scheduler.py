from rest_framework import serializers
from skul_data.scheduler.models.scheduler import SchoolEvent
from django.utils import timezone
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.schools.models.schoolclass import SchoolClass
from django.contrib.auth import get_user_model
from skul_data.users.serializers.base_user import BaseUserSerializer
from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.users.serializers.parent import ParentSerializer
from skul_data.schools.serializers.schoolclass import SchoolClassSerializer
from skul_data.scheduler.models.scheduler import EventRSVP


User = get_user_model()


class EventRSVPSerializer(serializers.ModelSerializer):
    user = BaseUserSerializer(read_only=True)

    class Meta:
        model = EventRSVP
        fields = ["id", "user", "status", "response_note", "responded_at"]
        read_only_fields = ["responded_at"]


class SchoolEventSerializer(serializers.ModelSerializer):
    created_by = BaseUserSerializer(read_only=True)
    targeted_teachers = TeacherSerializer(many=True, read_only=True)
    targeted_parents = ParentSerializer(many=True, read_only=True)
    targeted_classes = SchoolClassSerializer(many=True, read_only=True)
    rsvps = EventRSVPSerializer(many=True, read_only=True)
    can_rsvp = serializers.SerializerMethodField()

    class Meta:
        model = SchoolEvent
        fields = [
            "id",
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "event_type",
            "target_type",
            "created_by",
            "school",
            "targeted_teachers",
            "targeted_parents",
            "targeted_classes",
            # "current_school_year",
            # "current_term",
            "location",
            "is_all_day",
            "attachment",
            "requires_rsvp",
            "rsvp_deadline",
            "created_at",
            "updated_at",
            "rsvps",
            "can_rsvp",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at", "school"]

    def get_can_rsvp(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        if not obj.requires_rsvp:
            return False

        if obj.rsvp_deadline and timezone.now() > obj.rsvp_deadline:
            return False

        return not obj.rsvps.filter(user=request.user).exists()

    def create(self, validated_data):
        # Get user and school from context
        user = self.context["request"].user
        school = validated_data.pop("school", None) or user.school

        # Extract many-to-many relationships
        targeted_teachers = validated_data.pop("targeted_teachers", [])
        targeted_parents = validated_data.pop("targeted_parents", [])
        targeted_classes = validated_data.pop("targeted_classes", [])

        # Create the event
        event = SchoolEvent.objects.create(
            created_by=user, school=school, **validated_data
        )

        # Add many-to-many relationships
        if targeted_teachers:
            event.targeted_teachers.set(targeted_teachers)
        if targeted_parents:
            event.targeted_parents.set(targeted_parents)
        if targeted_classes:
            event.targeted_classes.set(targeted_classes)

        return event


class CreateSchoolEventSerializer(serializers.ModelSerializer):
    targeted_teachers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Teacher.objects.all(), required=False
    )
    targeted_parents = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Parent.objects.all(), required=False
    )
    targeted_classes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=SchoolClass.objects.all(), required=False
    )

    class Meta:
        model = SchoolEvent
        fields = [
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "event_type",
            "target_type",
            "targeted_teachers",
            "targeted_parents",
            "targeted_classes",
            "location",
            "is_all_day",
            "attachment",
            "requires_rsvp",
            "rsvp_deadline",
        ]

    def validate(self, data):
        if data["end_datetime"] < data["start_datetime"]:
            raise serializers.ValidationError(
                "End datetime must be after start datetime"
            )

        if data.get("rsvp_deadline") and data["rsvp_deadline"] > data["start_datetime"]:
            raise serializers.ValidationError(
                "RSVP deadline must be before event start time"
            )

        return data

    def create(self, validated_data):
        # Remove many-to-many fields first
        targeted_teachers = validated_data.pop("targeted_teachers", [])
        targeted_parents = validated_data.pop("targeted_parents", [])
        targeted_classes = validated_data.pop("targeted_classes", [])

        # Create the event with remaining validated_data
        event = SchoolEvent.objects.create(**validated_data)

        # Set many-to-many relationships
        if targeted_teachers:
            event.targeted_teachers.set(targeted_teachers)
        if targeted_parents:
            event.targeted_parents.set(targeted_parents)
        if targeted_classes:
            event.targeted_classes.set(targeted_classes)

        return event
