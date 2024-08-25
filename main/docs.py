from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from selfpackage.django import authentication as selfpackage_authentication

api_info = openapi.Info(
    title='AMDB API',
    default_version='v1',
    description='',
)

schema_view = get_schema_view(
    info=api_info,
    public=True,
    authentication_classes=[selfpackage_authentication.SSOAuthentication],
    permission_classes=[permissions.IsAuthenticated],
)
