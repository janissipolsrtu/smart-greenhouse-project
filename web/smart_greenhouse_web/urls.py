"""
URL configuration for smart_greenhouse_web project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/smart-greenhouse/', permanent=False)),
    path('smart-greenhouse', RedirectView.as_view(url='/smart-greenhouse/', permanent=False)),
    path('smart-greenhouse/', include('smart_greenhouse.urls')),
    path('watering/', RedirectView.as_view(url='/smart-greenhouse/', permanent=False)),
    path('api/', include('smart_greenhouse.api_urls')),
]