from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student
from skul_data.documents.models.document import Document
from skul_data.reports.models.academic_record import AcademicRecord


class ParentDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Returns dashboard data for a logged-in Parent"""

        if not hasattr(request.user, "parent"):
            return Response({"error": "Unautjhorised"}, status=403)

        parent = request.user.parent
        children = Student.objects.filter(parent=parent).count()
        reports = AcademicRecord.objects.filter(student__parent=parent).count()
        teachers = Teacher.objects.filter(
            class_assigned__in=Student.objects.filter(parent=parent)
        ).count()

        data = {
            "children_count": children,
            "reports_count": reports,
            "teachers_count": teachers,
        }

        return Response(data)
