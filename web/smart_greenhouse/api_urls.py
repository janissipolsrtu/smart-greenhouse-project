from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import WateringPlanViewSet, WateringCycleViewSet

router = DefaultRouter()
router.register(r'plans', WateringPlanViewSet, basename='wateringplan')
router.register(r'cycles', WateringCycleViewSet, basename='wateringcycle')

urlpatterns = [
    path('', include(router.urls)),
]