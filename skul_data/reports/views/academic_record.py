from rest_framework import viewsets, permissions
from skul_data.reports.models.academic_record import AcademicRecord
from skul_data.reports.serializers.academic_record import (
    AcademicRecordSerializer,
    TeacherCommentSerializer,
)
from skul_data.users.permissions.permission import IsTeacher, IsAdministrator
from rest_framework.decorators import action
from django.db import models
from skul_data.reports.models.academic_record import TeacherComment


class AcademicRecordViewSet(viewsets.ModelViewSet):
    queryset = AcademicRecord.objects.all()
    serializer_class = AcademicRecordSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            return [IsTeacher()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Teachers only see records they created or for their students
        if self.request.user.user_type == "TEACHER":
            teacher = self.request.user.teacher_profile
            return queryset.filter(
                models.Q(teacher=teacher)
                | models.Q(student__school_class__teacher_assigned=teacher)
            ).filter(is_published=True)

        # Parents only see their children's published records
        elif self.request.user.user_type == "PARENT":
            return queryset.filter(
                student__guardians=self.request.user, is_published=True
            )

        return queryset


class TeacherCommentViewSet(viewsets.ModelViewSet):
    queryset = TeacherComment.objects.all()
    serializer_class = TeacherCommentSerializer

    def get_permissions(self):
        if self.action == "approve":
            return [IsAdministrator()]
        elif self.action in ["create", "update"]:
            return [IsTeacher()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        comment = self.get_object()
        comment.approve(request.user)
        return Response({"status": "comment approved"})
