from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import WateringCycleViewSet

router = DefaultRouter()
router.register(r'cycles', WateringCycleViewSet, basename='wateringcycle')

urlpatterns = [
    path('', include(router.urls)),
]