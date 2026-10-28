from django.db import transaction
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import Event, Reservation, ReservationLine, Tag, TicketType, Venue


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]
        extra_kwargs = {"email": {"required": True}}

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "address", "capacity"]

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Venue capacity must be greater than zero.")
        if self.instance:
            largest_event = (
                self.instance.events.order_by("-capacity")
                .values_list("capacity", flat=True)
                .first()
            )
            if largest_event and value < largest_event:
                raise serializers.ValidationError(
                    "Venue capacity cannot be lower than an existing event capacity."
                )
        return value


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class EventSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = Event
        fields = [
            "id",
            "venue",
            "created_by",
            "tags",
            "title",
            "description",
            "starts_at",
            "capacity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        venue = attrs.get("venue", getattr(self.instance, "venue", None))
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", None))
        if capacity is not None and capacity <= 0:
            raise serializers.ValidationError(
                {"capacity": "Event capacity must be greater than zero."}
            )
        if venue and capacity and capacity > venue.capacity:
            raise serializers.ValidationError(
                {"capacity": "Event capacity cannot exceed venue capacity."}
            )
        if self.instance and capacity:
            booked = (
                ReservationLine.objects.filter(
                    reservation__event=self.instance,
                    reservation__status=Reservation.Status.CONFIRMED,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            if capacity < booked:
                raise serializers.ValidationError(
                    {
                        "capacity": "Capacity cannot be lower than tickets reserved."
                    }
                )
        return attrs


class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "event", "name", "price", "capacity"]
        validators = [
            UniqueTogetherValidator(
                queryset=TicketType.objects.all(),
                fields=["event", "name"],
            )
        ]

    def validate(self, attrs):
        event = attrs.get("event", getattr(self.instance, "event", None))
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", None))
        price = attrs.get("price", getattr(self.instance, "price", None))
        if capacity is not None and capacity <= 0:
            raise serializers.ValidationError(
                {"capacity": "Ticket type capacity must be greater than zero."}
            )
        if price is not None and price < 0:
            raise serializers.ValidationError({"price": "Ticket price cannot be negative."})
        if event and capacity and capacity > event.capacity:
            raise serializers.ValidationError(
                {"capacity": "Ticket type capacity cannot exceed event capacity."}
            )
        if self.instance and capacity:
            booked = (
                self.instance.reservation_lines.filter(
                    reservation__status=Reservation.Status.CONFIRMED
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            if capacity < booked:
                raise serializers.ValidationError(
                    {"capacity": "Capacity cannot be lower than tickets reserved."}
                )
        return attrs


class TicketSelectionSerializer(serializers.Serializer):
    ticket_type = serializers.PrimaryKeyRelatedField(queryset=TicketType.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class ReservationLineSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    price = serializers.DecimalField(
        source="ticket_type.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ReservationLine
        fields = ["ticket_type", "ticket_type_name", "price", "quantity"]


class ReservationSerializer(serializers.ModelSerializer):
    items = TicketSelectionSerializer(many=True, write_only=True, required=False)
    lines = ReservationLineSerializer(many=True, read_only=True)
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Reservation
        fields = ["id", "user", "event", "status", "items", "lines", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance and "event" in attrs and attrs["event"] != self.instance.event:
            raise serializers.ValidationError(
                {"event": "A reservation's event cannot be changed."}
            )
        if not self.instance and "items" not in attrs:
            raise serializers.ValidationError(
                {"items": "At least one ticket selection is required."}
            )
        if not self.partial and self.instance and "items" not in attrs:
            raise serializers.ValidationError({"items": "This field is required."})

        items = attrs.get("items")
        if items is not None:
            if not items:
                raise serializers.ValidationError({"items": "Select at least one ticket."})
            if self.instance and self.instance.status != Reservation.Status.CONFIRMED:
                raise serializers.ValidationError(
                    {"status": "Cancelled reservations cannot be modified."}
                )
            ticket_ids = [item["ticket_type"].id for item in items]
            if len(ticket_ids) != len(set(ticket_ids)):
                raise serializers.ValidationError(
                    {"items": "Each ticket type may only appear once per reservation."}
                )
            event = attrs.get("event", self.instance.event if self.instance else None)
            if event and any(item["ticket_type"].event_id != event.id for item in items):
                raise serializers.ValidationError(
                    {"items": "All ticket types must belong to the selected event."}
                )
        return attrs

    def create(self, validated_data):
        items = validated_data.pop("items")
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=validated_data["event"].pk)
            validated_data["event"] = event
            reservation = Reservation.objects.create(**validated_data)
            self._replace_lines(reservation, items)
        return reservation

    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=instance.event_id)
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            if items is not None:
                self._replace_lines(instance, items, event=event)
        return instance

    @staticmethod
    def _replace_lines(reservation, items, event=None):
        event = event or Event.objects.select_for_update().get(pk=reservation.event_id)
        ticket_ids = [item["ticket_type"].id for item in items]
        locked_tickets = {
            ticket.id: ticket
            for ticket in TicketType.objects.select_for_update()
            .filter(id__in=ticket_ids, event=event)
            .order_by("id")
        }
        if len(locked_tickets) != len(ticket_ids):
            raise serializers.ValidationError(
                {"items": "All ticket types must belong to the selected event."}
            )

        current_reservation_id = reservation.id
        existing_lines = ReservationLine.objects.filter(
            ticket_type_id__in=ticket_ids,
            reservation__status=Reservation.Status.CONFIRMED,
        )
        if current_reservation_id:
            existing_lines = existing_lines.exclude(reservation_id=current_reservation_id)

        requested_total = sum(item["quantity"] for item in items)
        booked_total = (
            ReservationLine.objects.filter(
                reservation__event=event,
                reservation__status=Reservation.Status.CONFIRMED,
            )
            .exclude(reservation_id=current_reservation_id)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        if booked_total + requested_total > event.capacity:
            raise serializers.ValidationError({"items": "Not enough event capacity is available."})

        for item in items:
            ticket = locked_tickets[item["ticket_type"].id]
            booked = (
                existing_lines.filter(ticket_type=ticket).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            if booked + item["quantity"] > ticket.capacity:
                raise serializers.ValidationError(
                    {"items": f"Not enough '{ticket.name}' tickets are available."}
                )

        reservation.lines.all().delete()
        ReservationLine.objects.bulk_create(
            [
                ReservationLine(
                    reservation=reservation,
                    ticket_type=locked_tickets[item["ticket_type"].id],
                    quantity=item["quantity"],
                )
                for item in items
            ]
        )
