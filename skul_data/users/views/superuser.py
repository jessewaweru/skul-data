from rest_framework import generics
from skul_data.users.models.superuser import SuperUser
from skul_data.users.serializers.superuser import SuperUserSerializer


class SuperUserCreateView(generics.CreateAPIView):
    queryset = SuperUser.objects.all()
    serializer_class = SuperUserSerializer
