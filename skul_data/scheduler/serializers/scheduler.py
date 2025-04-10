# school/serializers/event_serializer.py

from rest_framework import serializers
from skul_data.scheduler.models.scheduler import SchoolEvent
from django.contrib.auth import get_user_model

User = get_user_model()


class SchoolEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolEvent
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]
