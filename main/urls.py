# -*- coding: utf-8 -*-
"""CMDB URL Configuration

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
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from main import settings
from main.docs import schema_view as doc_view

v1_urlpatterns = [
    path('openstacks/', include('apps.openstacks.urls')),
]

api_urlpatterns = [
    path('v1/', include((v1_urlpatterns, 'v1'))),
    path('docs/', RedirectView.as_view(pattern_name='api:swagger')),
    re_path(r'^schema(?P<format>\.json|\.yaml)$', doc_view.without_ui(), name='schema'),
    re_path(r'^swagger/$', doc_view.with_ui('swagger'), name='swagger'),
    re_path(r'^redoc/$', doc_view.with_ui('redoc'), name='redoc'),
]

urlpatterns = [
    path('api/', include((api_urlpatterns, 'api')))
]

if settings.DEBUG:
    urlpatterns += [
        path('admin/', admin.site.urls),
        path("__debug__/", include("debug_toolbar.urls")),
    ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
