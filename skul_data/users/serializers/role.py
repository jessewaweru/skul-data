from rest_framework import serializers
from django.contrib.auth.models import Permission
from skul_data.users.models.role import Role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "codename", "name"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True
    )

    class Meta:
        model = Role
        fields = ["id", "name", "role_type", "permissions", "school"]
        read_only_fields = ["school"]

    def create(self, validated_data):
        permissions_data = validated_data.pop("permissions", [])
        role = Role.objects.create(**validated_data)
        for permission in permissions_data:
            role.permissions.add(permission["id"])
        return role

    def update(self, instance, validated_data):
        permissions_data = validated_data.pop("permissions", [])
        instance = super().update(instance, validated_data)
        instance.permissions.clear()
        for permission in permissions_data:
            instance.permissions.add(permission["id"])
        return instance
