from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    """GET /notifications/ -- the user's notifications, most recent first. ?unread=true filters to unread only."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        if request.query_params.get("unread") == "true":
            qs = qs.filter(read=False)
        qs = qs[:100]
        return Response({
            "results": NotificationSerializer(qs, many=True).data,
            "unread_count": Notification.objects.filter(user=request.user, read=False).count(),
        })


class MarkNotificationReadView(APIView):
    """POST /notifications/<id>/read/ -- marks a single notification read."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)

        notification.read = True
        notification.save(update_fields=["read"])
        return Response(NotificationSerializer(notification).data)


class MarkAllNotificationsReadView(APIView):
    """POST /notifications/read-all/ -- marks every unread notification read."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"marked_read": updated})


class KYCStatusView(APIView):
    """
    GET /notifications/kyc-status/
    Used on every login to decide whether to show the KYC pop-up modal.
    `should_prompt` is true whenever the user isn't yet verified --
    regardless of whether they've already read/dismissed the KYC
    notification in their dropdown, per product decision (the modal
    keeps reappearing every login until actually verified).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "kyc_status": user.kyc_status,
            "is_kyc_verified": user.is_kyc_verified,
            "should_prompt": not user.is_kyc_verified,
        })