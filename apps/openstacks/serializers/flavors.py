from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from rest_framework import serializers

from apps.openstacks.models.flavors import FlavorsModel
from apps.openstacks.serializers.base import RefreshSerializer, RegionBaseChoices
from libs.base.serializers import ChoicesField, SABaseSerializer


class FlavorsRefreshSerializer(RefreshSerializer):
    class Meta(RefreshSerializer.Meta):
        model = FlavorsModel


class FlavorsChoices(RegionBaseChoices):
    product_perm = ChoicesField(id_type=openapi.TYPE_INTEGER, help_text=_('產品權限'))
    module_perm = ChoicesField(id_type=openapi.TYPE_INTEGER, help_text=_('模組權限'))
    enable = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('啓用狀態'))

    class Meta(RegionBaseChoices.Meta):
        fields = ['product_perm', 'module_perm', 'enable', *RegionBaseChoices.Meta.fields]


class FlavorsSerializer(SABaseSerializer):
    region_display = serializers.CharField(source='region.name', read_only=True)

    class Meta(SABaseSerializer.Meta):
        model = FlavorsModel


class FlavorsUpdate(SABaseSerializer):
    class Meta(SABaseSerializer.Meta):
        model = FlavorsModel
        read_only_fields = [
            'id',
            'create_by',
            'update_by',
            'update_time',
            'create_time',
            'name',
            'vcpus',
            'ram',
            'disk',
            'region',
        ]
        write_only_fields = ['product_perm', 'module_perm', 'enable']
