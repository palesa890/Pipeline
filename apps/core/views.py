import time
import logging

from django.db import transaction
from django.db import DatabaseError, connections
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, Reservation, Tag, TicketType, Venue
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
from .serializers import (
    EventSerializer,
    ReservationSerializer,
    RegistrationSerializer,
    TagSerializer,
    TicketTypeSerializer,
    VenueSerializer,
)

STARTED_AT = time.monotonic()
logger = logging.getLogger(__name__)


class LiveHealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
            }
        )


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return Response(
                {
                    "status": "unavailable",
                    "database": "disconnected",
                    "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "status": "ok",
                "database": "connected",
                "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
            }
        )


class RegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"id": user.pk, "username": user.get_username()},
            status=status.HTTP_201_CREATED,
        )


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [IsAdminOrReadOnly]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAdminOrReadOnly]


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.select_related("venue", "created_by").prefetch_related("tags")
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TicketTypeViewSet(viewsets.ModelViewSet):
    queryset = TicketType.objects.select_related("event")
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAdminOrReadOnly]


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsOwnerOrAdmin]

    def get_queryset(self):
        queryset = Reservation.objects.select_related("event", "user").prefetch_related(
            "lines__ticket_type"
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        reservation = serializer.save(user=self.request.user)
        logger.info(
            "reservation_created",
            extra={
                "event_type": "reservation_created",
                "reservation_id": reservation.pk,
                "event_id": reservation.event_id,
                "user_id": reservation.user_id,
                "quantity": sum(line.quantity for line in reservation.lines.all()),
            },
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            reservation = get_object_or_404(
                self.get_queryset().select_for_update(),
                pk=pk,
            )
            self.check_object_permissions(request, reservation)
            if reservation.status == Reservation.Status.CANCELLED:
                raise ValidationError({"status": "Reservation is already cancelled."})
            reservation.status = Reservation.Status.CANCELLED
            reservation.save(update_fields=["status", "updated_at"])
        logger.info(
            "reservation_cancelled",
            extra={
                "event_type": "reservation_cancelled",
                "reservation_id": reservation.pk,
                "event_id": reservation.event_id,
                "user_id": reservation.user_id,
            },
        )
        return Response(self.get_serializer(reservation).data)
