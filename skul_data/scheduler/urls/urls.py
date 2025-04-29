from django.urls import path
from skul_data.scheduler.views.scheduler import (
    UserEventListView,
    SchoolEventDetailView,
    SchoolEventListView,
)
from skul_data.scheduler.views.scheduler import EventRSVPView, EventRSVPListView
from skul_data.scheduler.views.scheduler import SchoolCalendarExportView

urlpatterns = [
    path("user-events/", UserEventListView.as_view(), name="user-event-list"),
    path("events/", SchoolEventListView.as_view(), name="event-list"),
    path("events/<int:pk>/", SchoolEventDetailView.as_view(), name="event-detail"),
    path("events/<int:event_id>/rsvp/", EventRSVPView.as_view(), name="event-rsvp"),
    path(
        "events/<int:event_id>/rsvps/",
        EventRSVPListView.as_view(),
        name="event-rsvp-list",
    ),
    path(
        "export-calendar/", SchoolCalendarExportView.as_view(), name="export-calendar"
    ),
    # path("events/create/", SchoolEventCreateView.as_view(), name="event-create"),
    # path(
    #     "events/<int:pk>/update/", SchoolEventUpdateView.as_view(), name="event-update"
    # ),
    # path(
    #     "events/<int:pk>/delete/", SchoolEventDeleteView.as_view(), name="event-delete"
    # ),
]
