from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from skul_data.users.permissions.permission import IsAdministrator
from skul_data.users.models.parent import Parent, ParentStatusChange, ParentNotification
from skul_data.students.models.student import Student
from skul_data.users.serializers.parent import (
    ParentSerializer,
    ParentNotificationSerializer,
    ParentStatusChangeSerializer,
    ParentCreateSerializer,
    ParentChildAssignmentSerializer,
    ParentNotificationPreferenceSerializer,
)
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "status",
        "school",
        "receive_sms_notifications",
        "receive_email_notifications",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "phone_number",
        "children__first_name",
        "children__last_name",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return ParentCreateSerializer
        elif self.action in ["change_status", "activate", "deactivate"]:
            return ParentStatusChangeSerializer
        elif self.action == "assign_children":
            return ParentChildAssignmentSerializer
        elif self.action == "update_notification_preferences":
            return ParentNotificationPreferenceSerializer
        return ParentSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdministrator()]
        elif self.action in ["change_status", "assign_children"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        school = getattr(user, "school", None)
        if not school:
            return Parent.objects.none()

        queryset = queryset.filter(school=school)

        # Parents can only see their own profile
        if user.user_type == "parent":
            return queryset.filter(user=user)

        return queryset.select_related("user", "school").prefetch_related("children")

    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        parent = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent.status = serializer.validated_data["status"]
        parent.save()

        # Log the status change
        ParentStatusChange.objects.create(
            parent=parent,
            changed_by=request.user,
            from_status=parent.status,
            to_status=serializer.validated_data["status"],
            reason=serializer.validated_data.get("reason", ""),
        )

        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        parent = self.get_object()
        parent.status = "ACTIVE"
        parent.save()
        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        parent = self.get_object()
        parent.status = "INACTIVE"
        parent.save()
        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["post"])
    def assign_children(self, request, pk=None):
        parent = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        students = serializer.validated_data["student_ids"]
        action = serializer.validated_data["action"]

        if action == "ADD":
            parent.children.add(*students)
        elif action == "REMOVE":
            parent.children.remove(*students)
        elif action == "REPLACE":
            parent.children.set(students)

        return Response(ParentSerializer(parent).data)

    @action(detail=True, methods=["get"])
    def children_academic_records(self, request, pk=None):
        parent = self.get_object()
        records = AcademicRecord.objects.filter(
            student__in=parent.children.all(), is_published=True
        )
        serializer = AcademicRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def children_attendance(self, request, pk=None):
        parent = self.get_object()
        attendance = StudentAttendance.objects.filter(student__in=parent.children.all())
        serializer = StudentAttendanceSerializer(attendance, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def shared_documents(self, request, pk=None):
        parent = self.get_object()
        documents = Document.objects.filter(
            Q(related_students__in=parent.children.all()) | Q(is_public=True)
        ).distinct()
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def notifications(self, request, pk=None):
        parent = self.get_object()
        notifications = ParentNotification.objects.filter(parent=parent).order_by(
            "-created_at"
        )
        serializer = ParentNotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        parent = self.get_object()
        message = request.data.get("message")
        if not message:
            return Response(
                {"detail": "Message is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Send email
        send_parent_email(parent, subject="Message from School", message=message)

        # Create in-app notification
        notification = ParentNotification.objects.create(
            parent=parent,
            message=message,
            notification_type="MANUAL",  # You could also use a constant if you have enums
            sent_by=request.user,
        )

        return Response({"status": "message sent", "notification_id": notification.id})

    @action(detail=True, methods=["put", "patch"])
    def update_notification_preferences(self, request, pk=None):
        parent = self.get_object()
        serializer = self.get_serializer(parent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Basic counts
        total_parents = queryset.count()
        parents_by_status = queryset.values("status").annotate(count=Count("id"))

        # Children distribution
        children_distribution = (
            queryset.annotate(child_count=Count("children"))
            .values("child_count")
            .annotate(parent_count=Count("id"))
            .order_by("child_count")
        )

        # Activity metrics
        active_parents = queryset.filter(
            user__last_login__gte=timezone.now() - timedelta(days=30)
        ).count()

        return Response(
            {
                "total_parents": total_parents,
                "parents_by_status": parents_by_status,
                "children_distribution": children_distribution,
                "active_parents": active_parents,
            }
        )


class ParentNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = ParentNotificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "parent",
        "notification_type",
        "is_read",
        "related_student",
    ]

    def get_permissions(self):
        if self.action in ["create", "update", "destroy"]:
            return [IsAdministrator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = ParentNotification.objects.all()
        user = self.request.user

        if user.is_superuser:
            return queryset

        # School admins can see notifications for parents in their school
        if hasattr(user, "school"):
            queryset = queryset.filter(parent__school=user.school)
        else:
            return ParentNotification.objects.none()

        # Parents can only see their own notifications
        if user.user_type == "parent":
            return queryset.filter(parent__user=user)

        # Teachers can see notifications for parents of their students
        if user.user_type == "teacher":
            student_ids = Student.objects.filter(
                Q(teacher=user.teacher_profile)
                | Q(school_class__teacher_assigned=user.teacher_profile)
            ).values_list("id", flat=True)
            return queryset.filter(related_student__in=student_ids)

        return queryset

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        queryset.update(is_read=True)
        return Response({"status": "all notifications marked as read"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        count = queryset.filter(is_read=False).count()
        return Response({"unread_count": count})


class ParentStatusChangeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ParentStatusChangeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "parent",
        "changed_by",
        "from_status",
        "to_status",
    ]

    def get_queryset(self):
        queryset = ParentStatusChange.objects.all()
        user = self.request.user

        if user.is_superuser:
            return queryset

        # School admins can see status changes for parents in their school
        if hasattr(user, "school"):
            queryset = queryset.filter(parent__school=user.school)
        else:
            return ParentStatusChange.objects.none()

        # Parents can only see their own status changes
        if user.user_type == "parent":
            return queryset.filter(parent__user=user)

        return queryset

    @action(detail=False, methods=["get"])
    def recent_activity(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        recent = queryset.order_by("-changed_at")[:10]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)
