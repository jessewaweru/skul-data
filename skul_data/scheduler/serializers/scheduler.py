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
from skul_data.action_logs.utils.action_log import log_action
from skul_data.action_logs.models.action_log import ActionCategory

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
    attachment_url = serializers.SerializerMethodField()

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
            "location",
            "is_all_day",
            "attachment",
            "attachment_url",
            "requires_rsvp",
            "rsvp_deadline",
            "created_at",
            "updated_at",
            "rsvps",
            "can_rsvp",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at", "school"]

    def get_attachment_url(self, obj):
        if obj.attachment:
            return self.context["request"].build_absolute_uri(obj.attachment.url)
        return None

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
        request = self.context.get("request")
        user = request.user if request else None

        # Handle file upload separately
        attachment = validated_data.pop("attachment", None)

        # Create the event without attachment first
        event = SchoolEvent.objects.create(
            created_by=user,
            school=validated_data.pop("school", None)
            or (user.school if user else None),
            **validated_data,
        )

        # Set attachment if provided
        if attachment:
            event.attachment = attachment
            event.save()
            self.log_attachment_upload(event, user)

        return event

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        # Check if attachment is being updated
        old_attachment = instance.attachment
        new_attachment = validated_data.get("attachment")
        attachment_changed = new_attachment and new_attachment != old_attachment

        # Perform the update
        instance = super().update(instance, validated_data)

        # Log attachment changes
        if attachment_changed:
            self.log_attachment_upload(instance, user)
            if old_attachment:
                self.log_attachment_delete(instance, user, old_attachment)

        return instance

    def log_attachment_upload(self, event, user):
        """
        Logs when an attachment is uploaded to an event
        Args:
            event: SchoolEvent instance
            user: User who uploaded the file
        """
        if not event.attachment:
            return

        log_action(
            user=user,
            action=f"Uploaded attachment for event {event.id}",
            category=ActionCategory.UPLOAD,
            obj=event,
            metadata={
                "filename": event.attachment.name,
                "size": event.attachment.size,
                "event_title": event.title,
            },
        )

    def log_attachment_delete(self, event, user, old_attachment):
        """
        Logs when an attachment is removed from an event
        Args:
            event: SchoolEvent instance
            user: User who removed the file
            old_attachment: The attachment file that was removed
        """
        log_action(
            user=user,
            action=f"Removed attachment from event {event.id}",
            category=ActionCategory.DELETE,
            obj=event,
            metadata={
                "filename": old_attachment.name,
                "size": old_attachment.size,
                "event_title": event.title,
            },
        )


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
        # Only validate datetime fields if they're both present
        if "end_datetime" in data and "start_datetime" in data:
            if data["end_datetime"] < data["start_datetime"]:
                raise serializers.ValidationError(
                    "End datetime must be after start datetime"
                )

        if "rsvp_deadline" in data and "start_datetime" in data:
            if data["rsvp_deadline"] > data["start_datetime"]:
                raise serializers.ValidationError(
                    "RSVP deadline must be before event start time"
                )

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        # Remove many-to-many fields first
        targeted_teachers = validated_data.pop("targeted_teachers", [])
        targeted_parents = validated_data.pop("targeted_parents", [])
        targeted_classes = validated_data.pop("targeted_classes", [])

        # Handle file upload separately
        attachment = validated_data.pop("attachment", None)

        # Create the event without attachment first
        event = SchoolEvent.objects.create(
            created_by=user, school=user.school, **validated_data
        )

        # Set many-to-many relationships
        if targeted_teachers:
            event.targeted_teachers_set(targeted_teachers, user)
        if targeted_parents:
            event.targeted_parents_set(targeted_parents, user)
        if targeted_classes:
            event.targeted_classes_set(targeted_classes, user)

        # Set attachment if provided
        if attachment:
            event.attachment = attachment
            event.save()
            self.log_attachment_upload(event, user)

        return event

    def log_attachment_upload(self, event, user):
        """
        Consistent logging method shared with SchoolEventSerializer
        """
        if not event.attachment:
            return

        log_action(
            user=user,
            action=f"Uploaded attachment for event {event.id}",
            category=ActionCategory.UPLOAD,
            obj=event,
            metadata={
                "filename": event.attachment.name,
                "size": event.attachment.size,
                "event_title": event.title,
            },
        )
