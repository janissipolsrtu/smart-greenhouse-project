"""
URL configuration for irrigation_web project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/smart-greenhouse/', permanent=False)),
    path('smart-greenhouse', RedirectView.as_view(url='/smart-greenhouse/', permanent=False)),
    path('smart-greenhouse/', include('irrigation.urls')),
    path('watering/', RedirectView.as_view(url='/smart-greenhouse/', permanent=False)),
    path('api/', include('irrigation.api_urls')),
]