from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from skul_data.users.models.teacher import Teacher
from skul_data.users.models.parent import Parent
from skul_data.students.models.student import Student
from skul_data.documents.models.document import Document
from skul_data.reports.models.academic_record import AcademicRecord


class SuperUserDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Returns dashboard data for a logged-in SuperUser"""
        if not hasattr(request.user, "superuser"):
            return Response({"error": "Unauthorised"}, status=403)

        superuser = request.user.superuser
        teachers = Teacher.objects.filter(school=superuser.school_name).count()
        parents = Parent.objects.filter(
            school=superuser.school_name
        ).count()  # 🛠️ Fix added
        students = Student.objects.filter(
            school=superuser.school_name
        ).count()  # 🛠️ Fix added
        documents = Document.objects.filter(school=superuser.school_name).count()
        reports = AcademicRecord.objects.filter(
            school=superuser.school_name
        ).count()  # 🛠️ Fix added

        data = {
            "teachers_count": teachers,
            "parents_count": parents,
            "students_count": students,
            "documents_count": documents,
            "reports_count": reports,
        }
        return Response(data)
