import typing as t

from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from rest_framework import serializers

from apps.openstacks.models.images import ImagesModel
from apps.openstacks.serializers.base import RefreshSerializer, RegionBaseChoices
from libs.base.serializers import ChoicesField, SABaseSerializer


class ImagesRefreshSerializer(RefreshSerializer):
    region_id = serializers.CharField()

    def to_internal_value(self, data: t.Any) -> t.Any:
        if 'win' in data['name'].lower():
            data['is_win'] = True

        return super().to_internal_value(data)

    class Meta(RefreshSerializer.Meta):
        model = ImagesModel


class ImagesChoices(RegionBaseChoices):
    product_perm = ChoicesField(id_type=openapi.TYPE_INTEGER, help_text=_('產品權限'))
    module_perm = ChoicesField(id_type=openapi.TYPE_INTEGER, help_text=_('模組權限'))
    enable = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('啓用狀態'))
    is_win = ChoicesField(id_type=openapi.TYPE_BOOLEAN, help_text=_('是否為Windows'))
    status = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('狀態'))

    class Meta(RegionBaseChoices.Meta):
        fields = [
            'product_perm',
            'module_perm',
            'enable',
            'is_win',
            'status',
            *RegionBaseChoices.Meta.fields,
        ]


class ImagesSerializer(SABaseSerializer):
    region_display = serializers.CharField(source='region.name', read_only=True)

    class Meta(SABaseSerializer.Meta):
        model = ImagesModel


class ImagesUpdate(SABaseSerializer):
    class Meta(SABaseSerializer.Meta):
        model = ImagesModel
        read_only_fields = [
            'id',
            'create_by',
            'update_by',
            'update_time',
            'create_time',
            'region',
            'name',
            'status',
            'visibility',
            'container_format',
            'disk_format',
            'os_distro',
            'is_win',
        ]
        write_only_fields = ['product_perm', 'module_perm', 'enable']
