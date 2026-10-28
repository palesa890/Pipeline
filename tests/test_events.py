from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import Event, Tag, TicketType, Venue


@pytest.fixture
def catalog():
    admin = get_user_model().objects.create_user(
        username="staff",
        password="SecurePassphrase-42",
        is_staff=True,
    )
    user = get_user_model().objects.create_user(
        username="customer",
        password="SecurePassphrase-42",
    )
    venue = Venue.objects.create(name="Main Hall", address="1 Main St", capacity=200)
    tag = Tag.objects.create(name="Music", slug="music")
    event = Event.objects.create(
        venue=venue,
        created_by=admin,
        title="Evening Concert",
        description="Live music.",
        starts_at=datetime.now(timezone.utc) + timedelta(days=2),
        capacity=100,
    )
    event.tags.add(tag)
    ticket_type = TicketType.objects.create(
        event=event,
        name="General",
        price="25.00",
        capacity=100,
    )
    return admin, user, venue, tag, event, ticket_type


@pytest.mark.django_db
def test_catalog_is_readable_by_users_but_writable_only_by_staff(catalog):
    admin, user, venue, tag, event, ticket_type = catalog
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.get(reverse("event-list")).status_code == 200
    assert client.get(reverse("venue-list")).status_code == 200
    assert client.get(reverse("tag-list")).status_code == 200
    assert client.get(reverse("tickettype-list")).status_code == 200
    invalid_venue = client.patch(
        reverse("venue-detail", kwargs={"pk": venue.pk}),
        {"capacity": 50},
        format="json",
    )
    assert invalid_venue.status_code == 403
    denied = client.post(reverse("tag-list"), {"name": "Jazz", "slug": "jazz"}, format="json")
    assert denied.status_code == 403
    assert "error" in denied.data

    client.force_authenticate(user=admin)
    created_venue = client.post(
        reverse("venue-list"),
        {"name": "Studio", "address": "2 Side St", "capacity": 40},
        format="json",
    )
    assert created_venue.status_code == 201
    rejected_venue_update = client.patch(
        reverse("venue-detail", kwargs={"pk": venue.pk}),
        {"capacity": 50},
        format="json",
    )
    assert rejected_venue_update.status_code == 400
    created_tag = client.post(
        reverse("tag-list"),
        {"name": "Jazz", "slug": "jazz"},
        format="json",
    )
    assert created_tag.status_code == 201
    created_event = client.post(
        reverse("event-list"),
        {
            "venue": venue.pk,
            "tags": [tag.pk],
            "title": "New Show",
            "description": "",
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "capacity": 150,
        },
        format="json",
    )
    assert created_event.status_code == 201
    assert created_event.data["created_by"] == admin.username
    event_detail = reverse("event-detail", kwargs={"pk": event.pk})
    update = client.patch(event_detail, {"title": "Updated Concert"}, format="json")
    assert update.status_code == 200
    created_ticket = client.post(
        reverse("tickettype-list"),
        {"event": event.pk, "name": "Balcony", "price": "35.00", "capacity": 20},
        format="json",
    )
    assert created_ticket.status_code == 201
    assert client.delete(
        reverse("tickettype-detail", kwargs={"pk": created_ticket.data["id"]})
    ).status_code == 204
    assert client.delete(event_detail).status_code == 204
    tag_detail = reverse("tag-detail", kwargs={"pk": created_tag.data["id"]})
    assert client.delete(tag_detail).status_code == 204
    assert client.delete(
        reverse("venue-detail", kwargs={"pk": created_venue.data["id"]})
    ).status_code == 204
    assert ticket_type.name == "General"


@pytest.mark.django_db
def test_model_validates_capacity_and_string_representations(catalog):
    admin, _, venue, tag, event, ticket_type = catalog
    assert str(venue) == "Main Hall"
    assert str(tag) == "Music"
    assert str(event) == "Evening Concert"
    assert str(ticket_type) == "Evening Concert - General"

    event.capacity = venue.capacity + 1
    with pytest.raises(ValidationError):
        event.full_clean()

    ticket_type.capacity = event.capacity + 1
    with pytest.raises(ValidationError):
        ticket_type.full_clean()
    venue.capacity = 0
    with pytest.raises(ValidationError):
        venue.full_clean()
    assert admin.created_events.count() == 1
