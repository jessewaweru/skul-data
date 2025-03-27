from rest_framework import serializers
from skul_data.users.models.teacher import Teacher


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = ["id", "username", "email", "school", "subjects_taught"]
