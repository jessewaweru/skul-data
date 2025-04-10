from rest_framework import serializers
from skul_data.schools.models.school import School


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = "__all__"
