"""
URL configuration for irrigation_web project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/irrigation/', permanent=False)),
    path('irrigation/', include('irrigation.urls')),
    path('api/', include('irrigation.api_urls')),
]