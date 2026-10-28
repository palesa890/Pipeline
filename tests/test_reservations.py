from datetime import datetime, timedelta, timezone
import logging
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import Event, Reservation, ReservationLine, TicketType, Venue


@pytest.fixture
def ticket_setup():
    user = get_user_model().objects.create_user(
        username="buyer",
        password="SecurePassphrase-42",
    )
    other_user = get_user_model().objects.create_user(
        username="other",
        password="SecurePassphrase-42",
    )
    venue = Venue.objects.create(name="Arena", address="10 Center Rd", capacity=100)
    event = Event.objects.create(
        venue=venue,
        created_by=user,
        title="Final Match",
        starts_at=datetime.now(timezone.utc) + timedelta(days=1),
        capacity=10,
    )
    ticket = TicketType.objects.create(event=event, name="Standard", price="50.00", capacity=5)
    return user, other_user, venue, event, ticket


@pytest.mark.django_db
def test_reservation_crud_owner_scope_and_cancellation(ticket_setup, caplog):
    caplog.set_level(logging.INFO)
    user, other_user, _, event, ticket = ticket_setup
    client = APIClient()
    client.force_authenticate(user=user)
    create = client.post(
        reverse("reservation-list"),
        {"event": event.pk, "items": [{"ticket_type": ticket.pk, "quantity": 2}]},
        format="json",
    )
    assert create.status_code == 201
    reservation_id = create.data["id"]
    assert create.data["lines"][0]["quantity"] == 2
    assert create.data["lines"][0]["price"] == "50.00"
    assert client.get(reverse("reservation-list")).data[0]["id"] == reservation_id
    detail_url = reverse("reservation-detail", kwargs={"pk": reservation_id})
    assert client.get(detail_url).status_code == 200

    update = client.patch(
        detail_url,
        {"items": [{"ticket_type": ticket.pk, "quantity": 3}]},
        format="json",
    )
    assert update.status_code == 200
    assert update.data["lines"][0]["quantity"] == 3
    ticket.capacity = 2
    with pytest.raises(ValidationError):
        ticket.full_clean()

    client.force_authenticate(user=other_user)
    assert client.get(detail_url).status_code == 404
    assert client.delete(detail_url).status_code == 404

    client.force_authenticate(user=user)
    cancel_url = reverse("reservation-cancel", kwargs={"pk": reservation_id})
    cancelled = client.post(cancel_url)
    assert cancelled.status_code == 200
    assert cancelled.data["status"] == Reservation.Status.CANCELLED
    repeated = client.post(cancel_url)
    assert repeated.status_code == 400
    assert "error" in repeated.data

    new_reservation = client.post(
        reverse("reservation-list"),
        {"event": event.pk, "items": [{"ticket_type": ticket.pk, "quantity": 5}]},
        format="json",
    )
    assert new_reservation.status_code == 201
    assert client.delete(
        reverse("reservation-detail", kwargs={"pk": new_reservation.data["id"]})
    ).status_code == 204
    logged_events = {
        getattr(record, "event_type", None)
        for record in caplog.records
    }
    assert {"reservation_created", "reservation_cancelled"} <= logged_events


@pytest.mark.django_db
def test_reservation_rejects_capacity_and_invalid_ticket_selections(ticket_setup, caplog):
    caplog.set_level(logging.WARNING)
    user, _, _, event, ticket = ticket_setup
    client = APIClient()
    client.force_authenticate(user=user)
    too_many = client.post(
        reverse("reservation-list"),
        {"event": event.pk, "items": [{"ticket_type": ticket.pk, "quantity": 6}]},
        format="json",
    )
    assert too_many.status_code == 400
    assert "error" in too_many.data

    missing_items = client.post(
        reverse("reservation-list"),
        {"event": event.pk, "items": []},
        format="json",
    )
    assert missing_items.status_code == 400

    duplicate_lines = client.post(
        reverse("reservation-list"),
        {
            "event": event.pk,
            "items": [
                {"ticket_type": ticket.pk, "quantity": 1},
                {"ticket_type": ticket.pk, "quantity": 1},
            ],
        },
        format="json",
    )
    assert duplicate_lines.status_code == 400

    second_event = Event.objects.create(
        venue=ticket_setup[2],
        created_by=user,
        title="Other Match",
        starts_at=datetime.now(timezone.utc) + timedelta(days=4),
        capacity=10,
    )
    other_ticket = TicketType.objects.create(
        event=second_event,
        name="Other",
        price="10.00",
        capacity=5,
    )
    wrong_event = client.post(
        reverse("reservation-list"),
        {"event": event.pk, "items": [{"ticket_type": other_ticket.pk, "quantity": 1}]},
        format="json",
    )
    assert wrong_event.status_code == 400
    assert any(
        getattr(record, "event_type", None) == "reservation_rejected_ticket_capacity"
        for record in caplog.records
    )


@pytest.mark.django_db
def test_reservation_model_relationship_and_line_validation(ticket_setup):
    user, _, _, event, ticket = ticket_setup
    reservation = Reservation.objects.create(user=user, event=event)
    line = ReservationLine(reservation=reservation, ticket_type=ticket, quantity=1)
    line.full_clean()
    line.save()
    assert reservation.ticket_types.get() == ticket
    assert str(reservation).startswith("Reservation")

    other_event = Event.objects.create(
        venue=event.venue,
        created_by=user,
        title="Second Event",
        starts_at=datetime.now(timezone.utc) + timedelta(days=5),
        capacity=5,
    )
    other_ticket = TicketType.objects.create(
        event=other_event,
        name="Other",
        price="10.00",
        capacity=5,
    )
    invalid_line = ReservationLine(reservation=reservation, ticket_type=other_ticket, quantity=1)
    with pytest.raises(ValidationError):
        invalid_line.full_clean()


@pytest.mark.django_db
def test_health_endpoint_reports_database_state_and_openapi():
    client = APIClient()
    healthy = client.get(reverse("health"))
    assert healthy.status_code == 200
    assert healthy.data["status"] == "ok"
    assert healthy.data["database"] == "connected"
    assert healthy.data["uptime_seconds"] >= 0

    live = client.get(reverse("health-live"))
    assert live.status_code == 200
    assert live.data["status"] == "ok"
    assert "database" not in live.data

    ready = client.get(reverse("health-ready"))
    assert ready.status_code == 200
    assert ready.data["database"] == "connected"

    with patch("apps.core.views.connections") as mocked_connections:
        connection_lookup = mocked_connections.__getitem__.return_value
        connection_lookup.cursor.side_effect = DatabaseError("offline")
        live_while_database_is_down = client.get(reverse("health-live"))
        unhealthy = client.get(reverse("health-ready"))
    assert live_while_database_is_down.status_code == 200
    assert unhealthy.status_code == 503
    assert unhealthy.data["status"] == "unavailable"

    assert client.get(reverse("schema")).status_code == 200
    assert client.get(reverse("swagger-ui")).status_code == 200


@pytest.mark.django_db
def test_health_endpoints_propagate_request_id():
    client = APIClient()
    supplied_id = "request-123"

    response = client.get(reverse("health-live"), HTTP_X_REQUEST_ID=supplied_id)

    assert response["X-Request-ID"] == supplied_id
    generated = client.get(reverse("health-live"), HTTP_X_REQUEST_ID="bad\r\nid")
    assert generated["X-Request-ID"] != "bad\r\nid"
    assert len(generated["X-Request-ID"]) == 36
