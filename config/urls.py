from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.views import (
    EventViewSet,
    HealthView,
    RegistrationView,
    ReservationViewSet,
    TagViewSet,
    TicketTypeViewSet,
    VenueViewSet,
)

router = DefaultRouter()
router.register("venues", VenueViewSet)
router.register("tags", TagViewSet)
router.register("events", EventViewSet)
router.register("ticket-types", TicketTypeViewSet)
router.register("reservations", ReservationViewSet, basename="reservation")

urlpatterns = [
    path('admin/', admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("api/register/", RegistrationView.as_view(), name="register"),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="swagger-ui",
    ),
    path("api/", include(router.urls)),
]
