import typing as t

from datetime import datetime

from dateutil import parser
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from apps.openstacks.models.servers import ServersModel
from apps.openstacks.models.volumes import (
    VolumesAttachments,
    VolumesModel,
    VolumeTypeModel,
)
from apps.openstacks.serializers.base import (
    BatchParamsSerializer,
    ProjectBaseChoices,
    ProjectRefreshSerializer,
    RefreshSerializer,
)
from libs.base.serializers import ChoicesField, SABaseSerializer


class VolumesRefreshSerializer(ProjectRefreshSerializer):
    class Meta(ProjectRefreshSerializer.Meta):
        model = VolumesModel


class VolumesTypeRefreshSerializer(RefreshSerializer):
    class Meta(RefreshSerializer.Meta):
        model = VolumeTypeModel


class VolumesAttachmentsRefresh(RefreshSerializer):
    volume_id = serializers.CharField()
    server_id = serializers.CharField()

    def to_internal_value(self, data: t.Any) -> t.Any:
        if not isinstance(data['attached_at'], datetime):
            data['attached_at'] = parser.isoparse(data['attached_at']).replace(tzinfo=None)

        data['id'] = data.get('attachment_id', data['id'])
        return super().to_internal_value(data)

    class Meta:
        model = VolumesAttachments
        exclude = (*RefreshSerializer.Meta.exclude, 'volume', 'server')


class VolumesSerializer(SABaseSerializer):
    region_display = serializers.CharField(source='region.name', read_only=True)
    project_display = serializers.CharField(source='project.name', read_only=True)
    is_attached = serializers.BooleanField(
        source='attachments.exists', help_text=_('是否已綁定'), read_only=True
    )

    class Meta(SABaseSerializer.Meta):
        model = VolumesModel


class VolumesCreate(SABaseSerializer):
    id = serializers.CharField(read_only=True)

    def validate(self, attrs: t.Any) -> t.Any:
        if attrs['project'].idc_id != attrs['region'].idc_id:
            raise ParseError('所屬IDC與所屬區域不匹配')

        vt = VolumeTypeModel.objects.get(pk=attrs['volume_type'])
        if vt.region_id != attrs['region'].id:
            raise ParseError('所屬區域與盤類型不匹配')

        attrs['volume_type'] = vt.name
        return super().validate(attrs)

    class Meta(SABaseSerializer.Meta):
        model = VolumesModel
        exclude = ('status', 'volume_image_metadata', *SABaseSerializer.Meta.exclude)


class VolumesChoices(ProjectBaseChoices):
    status = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('狀態'))
    volume_type = ChoicesField(
        id_type=openapi.TYPE_STRING,
        help_text=_('磁盤類型'),
        extra_properties={
            'region_id': {'type': openapi.TYPE_STRING},
        },
    )
    region = ChoicesField(
        id_type=openapi.TYPE_STRING,
        help_text=_('所屬區域'),
        extra_properties={
            'idc_id': {'type': openapi.TYPE_INTEGER},
        },
    )
    project = ChoicesField(
        id_type=openapi.TYPE_STRING,
        help_text=_('所屬項目'),
        extra_properties={
            'idc_id': {'type': openapi.TYPE_INTEGER},
        },
    )

    class Meta:
        fields = ['status', 'volume_type', *ProjectBaseChoices.Meta.fields]


class VolumesAttachChoices(serializers.Serializer):
    attachments = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('可綁定虛擬機列表'))

    class Meta:
        fields = ['attachments']


class VolumesAttachParams(serializers.ModelSerializer):
    server = serializers.PrimaryKeyRelatedField(
        queryset=ServersModel.objects.all(), help_text=_('虛擬機ID'), pk_field=serializers.CharField()
    )

    def to_representation(self, instance: VolumesModel) -> t.Dict:
        return VolumesSerializer(instance).data

    class Meta:
        model = VolumesModel
        fields = ['server']


class VolumeAattachSerializer(serializers.ModelSerializer):
    id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    attached_at = serializers.DateTimeField(default=None)
    device = serializers.CharField(default='')

    class Meta:
        model = VolumesModel
        fields = ['id', 'name', 'status', 'attached_at', 'device']


class BatchVolumes(BatchParamsSerializer):
    class Meta(BatchParamsSerializer.Meta):
        model = VolumesModel
