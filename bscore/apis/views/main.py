from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckAPIView(APIView):
    """
    A simple health check view to verify that the API is running.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        """
        Returns a 200 OK response with a message indicating that the API is healthy.
        """
        return Response(
            {"status": "ok", "message": "API is healthy"}, status=status.HTTP_200_OK
        )