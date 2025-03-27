from rest_framework import serializers
from skul_data.action_logs.models.action_log import Actionlog


class ActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actionlog
        fields = "__all__"
        read_only_fields = ["timestamp"]
