from rest_framework import generics
from skul_data.users.models.teacher import Teacher
from skul_data.users.serializers.teacher import TeacherSerializer


class TeacherCreateView(generics.CreateAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
