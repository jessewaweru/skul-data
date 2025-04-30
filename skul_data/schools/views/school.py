from rest_framework import viewsets
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.schools.models.school import School
from skul_data.users.models.base_user import User
from rest_framework.permissions import IsAuthenticated, AllowAny
from skul_data.users.permissions.permission import IsPrimaryAdmin
from rest_framework.exceptions import PermissionDenied


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["create"]:
            return [AllowAny()]  # Allow school registration
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPrimaryAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.SCHOOL_ADMIN:
            return School.objects.filter(id=user.school_admin_profile.school.id)
        return School.objects.all()

    # def get_queryset(self):
    #     qs = super().get_queryset()
    #     if not self.request.user.is_superuser:
    #         # School admins can only see their own school
    #         qs = qs.filter(administrators__user=self.request.user)
    #     return qs

    def perform_create(self, serializer):
        # This will be handled by the SchoolRegistrationSerializer instead
        raise PermissionDenied("Schools can only be created via registration endpoint")
