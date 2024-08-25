import typing as t

from datetime import datetime

from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from selfpackage.django import contexts

from apps.openstacks.models.servers import ServersModel
from apps.openstacks.models.volumes import VolumesModel
from apps.openstacks.serializers.base import (
    BatchParamsSerializer,
    ProjectBaseChoices,
    ProjectRefreshSerializer,
)
from apps.openstacks.serializers.volumes import VolumeAattachSerializer
from apps.openstacks.services.volumes import add_attachments, del_attachments
from libs.base.serializers import ChoicesField, SABaseSerializer


class ServersVolumeChoices(serializers.Serializer):
    attach_vols = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('卷'))

    class Meta:
        fields = ['attach_vols']


class ServersChoices(ProjectBaseChoices):
    image = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('鏡像'))
    flavor = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('規格'))
    zone = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('可用區'))
    app = ChoicesField(id_type=openapi.TYPE_INTEGER, help_text=_('業務'))
    status = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('狀態'))

    class Meta:
        fields = ['image', 'flavor', 'zone', 'app', 'status', *ProjectBaseChoices.Meta.fields]


class ServersRefreshSerializer(ProjectRefreshSerializer):
    image_id = serializers.CharField(allow_null=True)
    flavor_id = serializers.CharField(allow_null=True)
    zone_id = serializers.CharField(allow_null=True)
    app_id = serializers.CharField(allow_null=True)

    def to_internal_value(self, data: t.Any) -> t.Any:
        data['project_id'] = data['tenant_id']
        data['hypervisor_hostname'] = data['OS-EXT-SRV-ATTR:host'] or ''
        return super().to_internal_value(data)

    class Meta(ProjectRefreshSerializer.Meta):
        model = ServersModel
        exclude = (*ProjectRefreshSerializer.Meta.exclude, 'image', 'flavor', 'zone', 'app')


class ServersSerializer(SABaseSerializer):
    app_display = serializers.CharField(source='app.alias', default=None, read_only=True)
    region_display = serializers.CharField(source='region.name', read_only=True)
    project_display = serializers.CharField(source='project.name', read_only=True)
    zone_display = serializers.CharField(source='zone.name', read_only=True)
    flavor_display = serializers.CharField(source='flavor.name', default=None, read_only=True)
    image_display = serializers.CharField(source='image.name', default=None, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    attach_vols = serializers.SerializerMethodField(help_text=_('已綁定卷'))
    security_groups = serializers.SerializerMethodField(help_text=_('所屬安全組'))

    @swagger_serializer_method(VolumeAattachSerializer)
    def get_attach_vols(self, obj: ServersModel) -> t.List:
        attach = {v.volume_id: v for v in obj.attach.all()}
        data = list(obj.attach_vols.all())
        for d in data:
            d.attached_at = attach.get(d.id).attached_at
            d.device = attach.get(d.id).device

        return VolumeAattachSerializer(data, many=True).data

    def get_security_groups(self, obj: ServersModel) -> t.List[dict]:
        security_groups = [
            {'id': o.id, 'name': o.name}
            for port in obj.ports.all()
            for o in port.security_groups.all()
            if not o.is_default
        ]
        return security_groups

    class Meta(SABaseSerializer.Meta):
        model = ServersModel


class ServersUpdate(SABaseSerializer):
    attach_vols = serializers.PrimaryKeyRelatedField(
        many=True, write_only=True, queryset=VolumesModel.objects.all()
    )

    def update(self, instance: ServersModel, validated_data: t.Any) -> t.Any:
        request = contexts.request.get()
        if request is not None:
            instance.update_by = request.user.username

        _old = instance.attach_vols.all()
        _new = validated_data['attach_vols']
        item: VolumesModel
        for item in set(_new) - set(_old):
            res = add_attachments(
                region=instance.region,
                project=instance.project,
                server_id=instance.id,
                volume_id=item.id,
            )
            through_defaults = {
                'id': res['volumeAttachment']['id'],
                'region_id': instance.region_id,
                'update_by': instance.update_by,
                'attached_at': datetime.now(),
                'device': res['volumeAttachment']['device'],
            }
            item.attachments.add(instance.id, through_defaults=through_defaults)

        for item in set(_old) - set(_new):
            del_attachments(
                region=instance.region,
                server_id=instance.id,
                volume_id=item.id,
            )
            instance.attach_vols.remove(item)

        instance.save()
        return instance

    class Meta:
        model = ServersModel
        fields = ['attach_vols']


class ServersRetrieve(SABaseSerializer):
    attach_vols = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = ServersModel
        fields = ['attach_vols']


class BatchServers(BatchParamsSerializer):
    class Meta(BatchParamsSerializer.Meta):
        model = ServersModel
