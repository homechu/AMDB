from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.openstacks.models.servers import ServersModel
from apps.openstacks.models.volumes import VolumesModel
from apps.openstacks.resouces import ServersResource
from apps.openstacks.serializers.servers import (
    BatchServers,
    ServersChoices,
    ServersRetrieve,
    ServersSerializer,
    ServersUpdate,
    ServersVolumeChoices,
)
from apps.openstacks.services.servers import reboot, rebuild, refresh_server_resource
from apps.openstacks.views.base import OpenstacksViewSet


class ServersViewSet(OpenstacksViewSet, viewsets.ReadOnlyModelViewSet, mixins.UpdateModelMixin):
    """虛擬機管理頁面 (servers)."""

    swagger_tags = ['Openstack管理 - 虛擬機管理']
    swagger_generate_tag = 'openstack_servers'
    swagger_summaries = {
        'list': '獲取 - 虛擬機',
        'retrieve': '獲取 - 虛擬機 [詳情]',
        'refresh': '執行 - 虛擬機 [刷新]',
        'update': '編輯 - 虛擬機',
        'partial_update': '編輯 - 虛擬機 [PATCH]',
        'batch_reboot': '批量 - 虛擬機 [重啓]',
        'batch_rebuild': '批量 - 虛擬機 [鏡像重建]',
        'export': '導出 - 虛擬機',
        'export_choices': '獲取 - 虛擬機 [導出選單]',
        'volume_choices': '獲取 - 虛擬機 [掛載卷下拉選單]',
        'choices': {'get': '獲取 - 虛擬機 [下拉選單]'},
    }
    menu_action_key = 'openstacks:servers'
    queryset = (
        ServersModel.objects.select_related('region', 'project', 'image', 'flavor', 'zone', 'app')
        .prefetch_related('attach_vols', 'attach', 'ports', 'ports__security_groups')
        .all()
    )
    serializer_class = ServersSerializer
    serializer_action_classes = {
        'retrieve': ServersRetrieve,
        'choices': ServersChoices,
        'volume_choices': ServersVolumeChoices,
        'update': ServersUpdate,
        'partial_update': ServersUpdate,
        'batch_reboot': BatchServers,
        'batch_rebuild': BatchServers,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = ServersResource
    filterset_fields = ServersChoices.Meta.fields
    search_fields = [
        'name',
        'app__alias',
        'key_name',
        'metadata',
        'ip_address',
        'hypervisor_hostname',
    ]

    def perform_update(self, serializer):
        serializer.save()
        self.message = '編輯成功'

    def perform_refresh(self, request, *args, **kwargs):
        refresh_server_resource(**request.data)

    @action(methods=['GET'], detail=True)
    def volume_choices(self, request: Request, *args, **kwargs) -> Response:
        instance: ServersModel = self.get_object()
        queryset = VolumesModel.objects.filter(
            region=instance.region, project=instance.project, attachments__isnull=True
        )
        serializer = self.get_serializer({'attach_vols': queryset.values('id', 'name')})
        return Response(serializer.data)

    @action(methods=['POST'], detail=False, message='重啓成功，請等待虛擬機完成開機')
    def batch_reboot(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.batch_serializer(request, *args, **kwargs)
        for instance in serializer.validated_data['ids']:
            reboot(instance)

        return Response()

    @action(methods=['POST'], detail=False, message='重裝系統成功，請等待虛擬機完成開機')
    def batch_rebuild(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.batch_serializer(request, *args, **kwargs)
        for instance in serializer.validated_data['ids']:
            rebuild(instance)

        return Response()
