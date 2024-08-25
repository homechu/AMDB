from datetime import datetime

from django_filters.rest_framework import FilterSet, filters
from drf_yasg.utils import no_body, swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from apps.openstacks.models.base import ProjectsModel, RegionModel
from apps.openstacks.models.servers import ServersModel
from apps.openstacks.models.volumes import VolumesModel, VolumeTypeModel
from apps.openstacks.resouces import VolumesResource
from apps.openstacks.serializers.volumes import (
    BatchVolumes,
    VolumesAttachChoices,
    VolumesAttachParams,
    VolumesChoices,
    VolumesCreate,
    VolumesSerializer,
)
from apps.openstacks.services.volumes import (
    add_attachments,
    add_volumes,
    del_attachments,
    del_volumes,
    refresh_volume_resource,
)
from apps.openstacks.views.base import OpenstacksViewSet
from libs.base.exceptions import ValidationMessage


class VolumeFilterset(FilterSet):
    can_attach = filters.BooleanFilter(field_name='attachments', lookup_expr='isnull')

    class Meta:
        model = VolumesModel
        fields = VolumesChoices.Meta.fields


class VolumesViewSet(
    OpenstacksViewSet, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin
):
    swagger_tags = ['Openstack管理 - 卷管理']
    swagger_generate_tag = 'openstack_volumes'
    swagger_summaries = {
        'list': '獲取 - 卷',
        'refresh': '執行 - 卷 [刷新]',
        'create': '創建 - 卷',
        'attach': '執行 - 卷 [綁定]',
        'detach': '執行 - 卷 [解綁]',
        'destroy': '刪除 - 卷',
        'batch_destroy': '批量刪除 - 卷',
        'export': '導出 - 卷',
        'export_choices': '獲取 - 卷 [導出選單]',
        'attach_choices': '獲取 - 卷 [掛載虛擬機下拉選單]',
        'choices': {'get': '獲取 - 卷 [下拉選單]'},
    }
    menu_action_key = 'openstacks:volumes'
    queryset = (
        VolumesModel.objects.select_related('region', 'project')
        .prefetch_related('attachments')
        .all()
    )
    serializer_class = VolumesSerializer
    serializer_action_classes = {
        'create': VolumesCreate,
        'attach': VolumesAttachParams,
        'choices': VolumesChoices,
        'attach_choices': VolumesAttachChoices,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = VolumesResource
    filterset_class = VolumeFilterset
    search_fields = ['description', 'size', 'name']

    @property
    def choices_data(self):
        return {
            'region': RegionModel.objects.values('id', 'name', 'idc_id'),
            'project': ProjectsModel.objects.values('id', 'name', 'idc_id'),
            'volume_type': VolumeTypeModel.objects.values('id', 'name', 'region_id'),
        }

    def perform_destroy(self, instance: VolumesModel):
        if instance.attachments.filter(attach__is_deleted=None).exists():
            raise ValidationMessage('存在已綁定虛擬機的卷，請先解綁')

        del_volumes(region=instance.region, project=instance.project, id=instance.id)
        instance.update_by = self.request.user.username
        instance.delete()
        self.message = '卷已刪除'

    def perform_create(self, serializer):
        data = serializer.validated_data
        res = add_volumes(**data)
        data['name'] = data['name'] or res['volume']['id']
        serializer.save(
            id=res['volume']['id'],
            create_by=self.request.user.username,
            status=res['volume']['status'],
        )
        self.message = '卷已新增'

    def perform_refresh(self, request, *args, **kwargs):
        refresh_volume_resource(**request.data)

    @swagger_auto_schema(responses={200: VolumesSerializer})
    @action(methods=['POST'], detail=True)
    def attach(self, request, *args, **kwargs):
        instance: VolumesModel = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        server_id = serializer.validated_data['server'].id
        res = add_attachments(region=instance.region, server_id=server_id, volume_id=instance.id)
        through_defaults = {
            'id': res['volumeAttachment']['id'],
            'region_id': instance.region_id,
            'update_by': request.user.username,
            'attached_at': datetime.now(),
            'device': res['volumeAttachment']['device'],
        }
        instance.attachments.add(server_id, through_defaults=through_defaults)
        instance.update_by = request.user.username
        instance.save()
        self.message = '卷已綁定'
        return Response(serializer.data)

    @swagger_auto_schema(request_body=no_body)
    @action(methods=['POST'], detail=True, serializer_class=Serializer)
    def detach(self, request, *args, **kwargs):
        instance: VolumesModel = self.get_object()
        if not instance.attachments.filter(attach__is_deleted=None).exists():
            raise ValidationMessage('卷未綁定')

        del_attachments(
            region=instance.region,
            server_id=instance.attachments.first().id,
            volume_id=instance.id,
        )
        instance.attachments.clear()
        instance.update_by = request.user.username
        instance.save()
        self.message = '卷已解綁'
        return Response()

    @action(methods=['GET'], detail=True)
    def attach_choices(self, request, *args, **kwargs) -> Response:
        instance: VolumesModel = self.get_object()
        if instance.attachments.filter(attach__is_deleted=None).exists():
            raise ValidationMessage('存在已綁定虛擬機的卷，請先解綁')

        queryset = ServersModel.objects.filter(
            region=instance.region, project=instance.project, attach_vols__isnull=True
        )
        serializer = self.get_serializer({'attachments': queryset.values('id', 'name')})
        return Response(serializer.data)

    @action(methods=[], detail=False)
    def batch(self, request, *args, **kwargs) -> Response:
        pass

    @swagger_auto_schema(request_body=BatchVolumes)
    @batch.mapping.delete
    def batch_destroy(self, request, *args, **kwargs) -> Response:
        serializer = self.batch_serializer(request, *args, **kwargs)
        for instance in serializer.validated_data['ids']:
            self.perform_destroy(instance)

        self.message = '批量刪除成功'
        return Response()
