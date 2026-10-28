from django.contrib import admin

from .models import Event, Reservation, ReservationLine, Tag, TicketType, Venue


admin.site.register([Venue, Tag, Event, TicketType, Reservation, ReservationLine])
