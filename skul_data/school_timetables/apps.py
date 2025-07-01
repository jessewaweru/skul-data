from django.apps import AppConfig


class SchoolTimetablesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skul_data.school_timetables"
    label = "school_timetables"

    def ready(self):
        from skul_data.school_timetables.signals import school_timetable
