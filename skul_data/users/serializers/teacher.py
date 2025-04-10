from rest_framework import serializers
from skul_data.users.models.teacher import Teacher


class TeacherSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Teacher
        fields = ["id", "username", "email", "school", "subjects_taught"]
