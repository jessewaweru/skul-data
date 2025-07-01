from django.urls import path, include
from rest_framework.routers import DefaultRouter
from skul_data.school_timetables.views.school_timetable import (
    TimeSlotViewSet,
    TimetableStructureViewSet,
    TimetableViewSet,
    LessonViewSet,
    TimetableConstraintViewSet,
    SubjectGroupViewSet,
    TeacherAvailabilityViewSet,
)

# router = DefaultRouter()
# router.register(r"time-slots", TimeSlotViewSet)
# router.register(r"timetable-structures", TimetableStructureViewSet)
# router.register(r"timetables", TimetableViewSet)
# router.register(r"lessons", LessonViewSet)
# router.register(r"timetable-constraints", TimetableConstraintViewSet)
# router.register(r"subject-groups", SubjectGroupViewSet)
# router.register(r"teacher-availability", TeacherAvailabilityViewSet)

# urlpatterns = [
#     path("", include(router.urls)),
# ]


app_name = "school_timetables"  # This registers the namespace

router = DefaultRouter()
router.register(r"time-slots", TimeSlotViewSet, basename="time-slots")
router.register(
    r"timetable-structures", TimetableStructureViewSet, basename="timetable-structures"
)
router.register(r"timetables", TimetableViewSet, basename="timetables")
router.register(r"lessons", LessonViewSet, basename="lessons")
router.register(
    r"timetable-constraints",
    TimetableConstraintViewSet,
    basename="timetable-constraints",
)
router.register(r"subject-groups", SubjectGroupViewSet, basename="subject-groups")
router.register(
    r"teacher-availability", TeacherAvailabilityViewSet, basename="teacher-availability"
)

urlpatterns = [
    path("", include(router.urls)),
]
