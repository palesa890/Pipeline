import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
                ("slug", models.SlugField(max_length=60, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Venue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("address", models.CharField(max_length=255)),
                ("capacity", models.PositiveIntegerField()),
            ],
            options={
                "ordering": ["name"],
                "constraints": [
                    models.CheckConstraint(
                        check=models.Q(("capacity__gt", 0)),
                        name="venue_capacity_positive",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("starts_at", models.DateTimeField(db_index=True)),
                ("capacity", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_events", to=settings.AUTH_USER_MODEL)),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="core.venue")),
                ("tags", models.ManyToManyField(blank=True, related_name="events", to="core.tag")),
            ],
            options={
                "ordering": ["starts_at", "title"],
                "indexes": [models.Index(fields=["venue", "starts_at"], name="event_venue_start_idx")],
                "constraints": [
                    models.CheckConstraint(check=models.Q(("capacity__gt", 0)), name="event_capacity_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TicketType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("capacity", models.PositiveIntegerField()),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ticket_types", to="core.event")),
            ],
            options={
                "ordering": ["price", "name"],
                "constraints": [
                    models.UniqueConstraint(fields=("event", "name"), name="unique_ticket_type_per_event"),
                    models.CheckConstraint(check=models.Q(("price__gte", 0)), name="ticket_price_nonnegative"),
                    models.CheckConstraint(check=models.Q(("capacity__gt", 0)), name="ticket_capacity_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("confirmed", "Confirmed"), ("cancelled", "Cancelled")], default="confirmed", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="core.event")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "created_at"], name="reservation_user_created_idx"),
                    models.Index(fields=["event", "status"], name="reservation_event_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ReservationLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("reservation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="core.reservation")),
                ("ticket_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservation_lines", to="core.tickettype")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("reservation", "ticket_type"), name="unique_ticket_per_reservation"),
                    models.CheckConstraint(check=models.Q(("quantity__gt", 0)), name="reservation_qty_positive"),
                ],
            },
        ),
        migrations.AddField(
            model_name="reservation",
            name="ticket_types",
            field=models.ManyToManyField(
                related_name="reservations",
                through="core.ReservationLine",
                to="core.tickettype",
            ),
        ),
    ]
