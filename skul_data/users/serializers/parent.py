from rest_framework import serializers
from skul_data.users.models.parent import Parent


class ParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = ["id", "username", "email", "children"]
