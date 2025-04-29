from rest_framework import generics, permissions, status
from rest_framework.response import Response
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


User = get_user_model()


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


# 🆕 Create new event (superuser only)
# class SchoolEventCreateView(generics.CreateAPIView):
#     queryset = SchoolEvent.objects.all()
#     serializer_class = SchoolEventSerializer
#     permission_classes = [permissions.IsAuthenticated, IsSuperUser]

#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user)


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

        # Superusers see all events
        if user.is_superuser:
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


# ✏️ Update event (superuser only)
# class SchoolEventUpdateView(generics.RetrieveUpdateAPIView):
#     queryset = SchoolEvent.objects.all()
#     serializer_class = SchoolEventSerializer
#     permission_classes = [permissions.IsAuthenticated, IsSuperUser]


# # ❌ Delete event (superuser only)
# class SchoolEventDeleteView(generics.DestroyAPIView):
#     queryset = SchoolEvent.objects.all()
#     serializer_class = SchoolEventSerializer
#     permission_classes = [permissions.IsAuthenticated, IsSuperUser]


class SchoolEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SchoolEventSerializer
    queryset = SchoolEvent.objects.all()

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return CreateSchoolEventSerializer
        return SchoolEventSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return SchoolEvent.objects.filter(school=self.request.user.school)
        return SchoolEvent.objects.filter(
            school=self.request.user.school, created_by=self.request.user
        )


class EventRSVPView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(SchoolEvent, id=event_id)

        if not event.requires_rsvp:
            return Response(
                {"detail": "This event does not require RSVP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event.rsvp_deadline and timezone.now() > event.rsvp_deadline:
            return Response(
                {"detail": "RSVP deadline has passed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if EventRSVP.objects.filter(event=event, user=request.user).exists():
            return Response(
                {"detail": "You have already responded to this event"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EventRSVPSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(event=event, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventRSVPListView(generics.ListAPIView):
    permission_classes = [IsSuperUser]
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
