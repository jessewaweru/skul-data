from rest_framework import viewsets
from skul_data.schools.serializers.school import SchoolSerializer
from skul_data.schools.models.school import School, SchoolSubscription, SecurityLog
from skul_data.users.models.base_user import User
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from skul_data.users.permissions.permission import IsPrimaryAdmin
from rest_framework.exceptions import PermissionDenied
from rest_framework import permissions
from skul_data.schools.serializers.school import (
    SchoolSubscriptionSerializer,
    SecurityLogSerializer,
)
from skul_data.users.permissions.permission import IsPrimaryAdmin, IsSchoolAdmin
from skul_data.users.models.teacher import Teacher
from skul_data.users.serializers.teacher import TeacherSerializer
from skul_data.users.models.parent import Parent
from skul_data.users.serializers.parent import ParentSerializer


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

    # def perform_create(self, serializer):
    #     # This will be handled by the SchoolRegistrationSerializer instead
    #     raise PermissionDenied("Schools can only be created via registration endpoint")


class SchoolSubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsPrimaryAdmin]

    def get_queryset(self):
        return SchoolSubscription.objects.filter(
            school=self.request.user.school_admin_profile.school
        )

    @action(detail=True, methods=["post"])
    def cancel_auto_renew(self, request, pk=None):
        subscription = self.get_object()
        subscription.auto_renew = False
        subscription.save()
        return Response({"status": "auto-renew cancelled"})

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        subscription = self.get_object()
        # In a real implementation, this would initiate a payment process
        return Response({"status": "renewal initiated"})


class SecurityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SecurityLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsSchoolAdmin]

    def get_queryset(self):
        return SecurityLog.objects.filter(user=self.request.user).order_by("-timestamp")


@api_view(["GET"])
@permission_classes([AllowAny])
# @permission_classes([IsAuthenticated, IsSchoolAdmin])
def school_teachers(request, school_id):
    teachers = Teacher.objects.filter(school_id=school_id).select_related("user")
    serializer = TeacherSerializer(teachers, many=True)
    return Response(
        {"school_id": school_id, "count": teachers.count(), "teachers": serializer.data}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def school_parents(request, school_id):
    """Get all parents for a specific school"""
    parents = (
        Parent.objects.filter(school_id=school_id)
        .select_related("user")
        .prefetch_related("children")
    )

    serializer = ParentSerializer(parents, many=True)

    return Response(
        {"school_id": school_id, "count": parents.count(), "parents": serializer.data}
    )
