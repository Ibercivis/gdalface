"""gdalface URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include, re_path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


api_schema_view = get_schema_view( # pylint: disable=invalid-name
    openapi.Info(
        title="Gdalface API",
        default_version='v1',
        description="API documentation",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="email@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('django-rq/', include('django_rq.urls')),  # Add this for django_rq
    path('api/v1/', include('georeferencing.urls')),  # Adjust the path to your app's API
    path('accounts/', include('allauth.urls')),  # Add this for allauth
    path('user-profile/', include('user_profile.urls')),  # Add this for user_profile

    # Swagger and Redoc paths
    re_path(r'^swagger(?P<format>\.json|\.yaml)$',
            api_schema_view.without_ui(cache_timeout=0),
            name='schema-json',
            ),
    re_path(
        r'^swagger/$',
        api_schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui',
        ),
    re_path(
        r'^redoc/$',
        api_schema_view.with_ui('redoc', cache_timeout=0),
        name='schema-redoc',
        ),

    # Frontend path
    path('', include('frontend.urls')),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
