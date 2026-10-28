from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum


class Venue(models.Model):
    name = models.CharField(max_length=150, unique=True)
    address = models.CharField(max_length=255)
    capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(check=Q(capacity__gt=0), name="venue_capacity_positive"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.capacity <= 0:
            raise ValidationError({"capacity": "Venue capacity must be greater than zero."})
        if self.pk and self.events.exists():
            largest_event = (
                self.events.order_by("-capacity")
                .values_list("capacity", flat=True)
                .first()
            )
            if largest_event and self.capacity < largest_event:
                raise ValidationError(
                    {"capacity": "Venue capacity cannot be lower than an existing event capacity."}
                )


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_events",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="events")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField(db_index=True)
    capacity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "title"]
        indexes = [
            models.Index(fields=["venue", "starts_at"], name="event_venue_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(capacity__gt=0),
                name="event_capacity_positive",
            ),
        ]

    def clean(self):
        if self.capacity <= 0:
            raise ValidationError({"capacity": "Event capacity must be greater than zero."})
        if self.venue_id and self.capacity > self.venue.capacity:
            raise ValidationError({"capacity": "Event capacity cannot exceed venue capacity."})
        if self.pk:
            booked = (
                ReservationLine.objects.filter(
                    reservation__event_id=self.pk,
                    reservation__status=Reservation.Status.CONFIRMED,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            if self.capacity < booked:
                raise ValidationError(
                    {"capacity": "Capacity cannot be lower than tickets reserved."}
                )

    def __str__(self):
        return self.title


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ["price", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="unique_ticket_type_per_event",
            ),
            models.CheckConstraint(
                check=Q(price__gte=0),
                name="ticket_price_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(capacity__gt=0),
                name="ticket_capacity_positive",
            ),
        ]

    def clean(self):
        if self.capacity <= 0:
            raise ValidationError({"capacity": "Ticket type capacity must be greater than zero."})
        if self.price < 0:
            raise ValidationError({"price": "Ticket price cannot be negative."})
        if self.event_id and self.capacity > self.event.capacity:
            raise ValidationError(
                {"capacity": "Ticket type capacity cannot exceed event capacity."}
            )
        if self.pk:
            booked = (
                self.reservation_lines.filter(
                    reservation__status=Reservation.Status.CONFIRMED
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            if self.capacity < booked:
                raise ValidationError(
                    {"capacity": "Capacity cannot be lower than tickets reserved."}
                )

    def __str__(self):
        return f"{self.event.title} - {self.name}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="reservations")
    ticket_types = models.ManyToManyField(
        TicketType,
        through="ReservationLine",
        related_name="reservations",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="reservation_user_created_idx"),
            models.Index(fields=["event", "status"], name="reservation_event_status_idx"),
        ]

    def __str__(self):
        return f"Reservation {self.pk} for {self.event}"


class ReservationLine(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        related_name="reservation_lines",
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["reservation", "ticket_type"],
                name="unique_ticket_per_reservation",
            ),
            models.CheckConstraint(check=Q(quantity__gt=0), name="reservation_qty_positive"),
        ]

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Reservation quantity must be greater than zero."})
        if (
            self.reservation_id
            and self.ticket_type_id
            and self.reservation.event_id != self.ticket_type.event_id
        ):
            raise ValidationError("Ticket type must belong to the reservation event.")
