import typing as t

from dateutil import parser
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from IPy import IP
from rest_framework import serializers

from apps.openstacks.models.networks import PortsModel, SubnetsModel
from apps.openstacks.serializers.base import (
    ProjectBaseChoices,
    ProjectRefreshSerializer,
)
from libs.base.serializers import ChoicesField, SABaseSerializer


class PortsRefreshSerializer(ProjectRefreshSerializer):
    device_id = serializers.CharField(allow_blank=True, allow_null=True, default='')
    update_time = serializers.DateTimeField()
    description = serializers.CharField(allow_blank=True, default='')

    def to_internal_value(self, data):
        data['update_time'] = parser.isoparse(data['updated_at']).replace(tzinfo=None)
        return super().to_internal_value(data)

    class Meta(ProjectRefreshSerializer.Meta):
        model = PortsModel
        exclude = (*ProjectRefreshSerializer.Meta.exclude, 'device', 'security_groups')


class SubnetsRefreshSerializer(ProjectRefreshSerializer):
    def to_internal_value(self, data: t.Any) -> t.Any:
        data['total_ips'] = IP(data['cidr'], make_net=True).len()
        return super().to_internal_value(data)

    class Meta(ProjectRefreshSerializer.Meta):
        model = SubnetsModel


class PortsChoices(ProjectBaseChoices):
    device = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('已連接裝置'))
    status = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('狀態'))

    class Meta(ProjectBaseChoices.Meta):
        fields = ['device', 'status', *ProjectBaseChoices.Meta.fields]


class PortsSerializer(SABaseSerializer):
    region_display = serializers.CharField(source='region.name', read_only=True)
    project_display = serializers.CharField(source='project.name', read_only=True)
    device_display = serializers.CharField(source='device.name', read_only=True)

    class Meta(SABaseSerializer.Meta):
        model = PortsModel
