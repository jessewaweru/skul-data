from django.urls import path
from skul_data.scheduler.views.scheduler import (
    UserEventListView,
    SchoolEventCreateView,
    SchoolEventUpdateView,
    SchoolEventDeleteView,
)

urlpatterns = [
    path("events/", UserEventListView.as_view(), name="user-event-list"),
    path("events/create/", SchoolEventCreateView.as_view(), name="event-create"),
    path(
        "events/<int:pk>/update/", SchoolEventUpdateView.as_view(), name="event-update"
    ),
    path(
        "events/<int:pk>/delete/", SchoolEventDeleteView.as_view(), name="event-delete"
    ),
]
