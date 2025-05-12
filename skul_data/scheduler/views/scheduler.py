from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView
from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from skul_data.scheduler.models.scheduler import SchoolEvent, EventRSVP
from skul_data.scheduler.serializers.scheduler import EventRSVPSerializer
from skul_data.scheduler.serializers.scheduler import (
    SchoolEventSerializer,
    CreateSchoolEventSerializer,
)
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from skul_data.users.permissions.permission import CanManageEvent


User = get_user_model()


class IsSchoolAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == User.SCHOOL_ADMIN
        )


class SchoolEventListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SchoolEventSerializer

    def get_queryset(self):
        user = self.request.user
        school = user.school

        # Filter by date range if provided
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        queryset = SchoolEvent.objects.filter(school=school)

        if start_date and end_date:
            queryset = queryset.filter(
                start_datetime__gte=start_date, end_datetime__lte=end_date
            )

        # School admin see all events
        if user.user_type == User.SCHOOL_ADMIN:
            return queryset.order_by("-start_datetime")

        # Teachers see events targeted to them or their classes
        if user.user_type == User.TEACHER:
            teacher = user.teacher_profile
            return (
                queryset.filter(
                    Q(target_type="all")
                    | Q(target_type="teachers")
                    | Q(targeted_teachers=teacher)
                    | Q(targeted_classes__in=teacher.assigned_classes.all())
                )
                .distinct()
                .order_by("-start_datetime")
            )

        # Parents see events targeted to them or their children's classes
        if user.user_type == User.PARENT:
            parent = user.parent_profile
            return (
                queryset.filter(
                    Q(target_type="all")
                    | Q(target_type="parents")
                    | Q(targeted_parents=parent)
                    | Q(
                        targeted_classes__in=[
                            child.school_class for child in parent.children.all()
                        ]
                    )
                )
                .distinct()
                .order_by("-start_datetime")
            )

        return SchoolEvent.objects.none()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateSchoolEventSerializer
        return SchoolEventSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, school=self.request.user.school)


# 🔍 List events relevant to logged-in user (teacher or parent)
class UserEventListView(generics.ListAPIView):
    """List events relevant to the current user with filters"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SchoolEventSerializer

    def get_queryset(self):
        user = self.request.user
        today = timezone.now().date()

        queryset = SchoolEvent.objects.filter(
            school=user.school, start_datetime__gte=today
        ).order_by("start_datetime")

        # Apply filters
        event_type = self.request.query_params.get("type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        target_type = self.request.query_params.get("target")
        if target_type:
            queryset = queryset.filter(target_type=target_type)

        return queryset[:10]  # Limit to 10 upcoming events


class SchoolEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SchoolEventSerializer
    queryset = SchoolEvent.objects.all()

    def get_permissions(self):
        """
        Allow any authenticated user to retrieve,
        but only event creators or admins can update/delete.
        """
        # if self.request.method in ["PUT", "PATCH", "DELETE"]:
        #     return [CanManageEvent()]
        # return super().get_permissions()

        if (
            hasattr(self, "request") and self.request.method in SAFE_METHODS
        ):  # GET, HEAD, OPTIONS
            return [IsAuthenticated()]
        return [CanManageEvent()]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return CreateSchoolEventSerializer
        return SchoolEventSerializer

    def get_queryset(self):
        if self.request.user.user_type == User.SCHOOL_ADMIN:
            return SchoolEvent.objects.filter(school=self.request.user.school)
        return SchoolEvent.objects.filter(
            school=self.request.user.school, created_by=self.request.user
        )


class EventRSVPView(CreateAPIView):
    serializer_class = EventRSVPSerializer
    permission_classes = [IsAuthenticated]

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(SchoolEvent, id=kwargs["event_id"])

        if not self.event.requires_rsvp:
            return Response(
                {"detail": "This event does not require RSVP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self.event.rsvp_deadline and timezone.now() > self.event.rsvp_deadline:
            return Response(
                {"detail": "RSVP deadline has passed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve the user before filtering
        user_id = request.user.id
        if EventRSVP.objects.filter(event=self.event, user_id=user_id).exists():
            return Response(
                {"detail": "You have already responded to this event"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().dispatch(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(event=self.event, user=self.request.user)


class EventRSVPListView(generics.ListAPIView):
    permission_classes = [IsSchoolAdmin]
    serializer_class = EventRSVPSerializer

    def get_queryset(self):
        event_id = self.kwargs["event_id"]
        return EventRSVP.objects.filter(event__id=event_id)


class SchoolCalendarExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from icalendar import Calendar, Event as ICalEvent
        from datetime import datetime

        events = SchoolEvent.objects.filter(
            school=request.user.school,
            start_datetime__gte=timezone.now() - timezone.timedelta(days=30),
        )

        cal = Calendar()
        cal.add("prodid", "-//School Calendar//example.com//")
        cal.add("version", "2.0")

        for event in events:
            ical_event = ICalEvent()
            ical_event.add("uid", f"{event.id}@example.com")
            ical_event.add("dtstart", event.start_datetime)
            ical_event.add("dtend", event.end_datetime)
            ical_event.add("summary", event.title)
            ical_event.add("description", event.description or "")
            ical_event.add("location", event.location or "")
            cal.add_component(ical_event)

        response = HttpResponse(cal.to_ical(), content_type="text/calendar")
        response["Content-Disposition"] = 'attachment; filename="school_calendar.ics"'
        return response
