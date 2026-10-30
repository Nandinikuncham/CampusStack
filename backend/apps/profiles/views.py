from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import OwnProfileSerializer, PublicProfileSerializer
from .services import with_contribution_statistics


class PublicProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        user = get_object_or_404(with_contribution_statistics(), pk=user_id)
        return Response(PublicProfileSerializer(user).data)


class CurrentProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get_profile_user(self, request):
        return get_object_or_404(
            with_contribution_statistics(),
            pk=request.user.pk,
        )

    def get(self, request):
        user = self.get_profile_user(request)
        return Response(OwnProfileSerializer(user).data)

    def patch(self, request):
        user = self.get_profile_user(request)
        serializer = OwnProfileSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
