from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter

from apps.openstacks.views import (
    FlavorsViewSet,
    ImagesViewSet,
    OpenstackMgmtViewSet,
    PortsViewSet,
    RulesViewSet,
    SecurityGroupsViewSet,
    ServersViewSet,
    VolumesViewSet,
)

router = DefaultRouter(trailing_slash=False)

router.register(r'openstack_mgmt', OpenstackMgmtViewSet)
router.register(r'servers', ServersViewSet)
router.register(r'security_groups', SecurityGroupsViewSet)
router.register(r'rules', RulesViewSet)
router.register(r'volumes', VolumesViewSet)
router.register(r'flovers', FlavorsViewSet)
router.register(r'images', ImagesViewSet)
router.register(r'ports', PortsViewSet)


urlpatterns = [url('', include(router.urls))]
