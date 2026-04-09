from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import IrrigationPlanViewSet

router = DefaultRouter()
router.register(r'plans', IrrigationPlanViewSet, basename='irrigationplan')

urlpatterns = [
    path('', include(router.urls)),
]