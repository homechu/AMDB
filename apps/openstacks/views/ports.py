from rest_framework import mixins

from apps.openstacks.models.networks import PortsModel
from apps.openstacks.resouces import PortsResource
from apps.openstacks.serializers.networks import PortsChoices, PortsSerializer
from apps.openstacks.services.networks import refresh_port_resource
from apps.openstacks.views.base import OpenstacksViewSet


class PortsViewSet(OpenstacksViewSet, mixins.ListModelMixin):
    """接口管理頁面 (ports)"""

    swagger_tags = ['Openstack管理 - 接口管理']
    swagger_generate_tag = 'openstack_ports'
    swagger_summaries = {
        'list': '獲取 - 接口',
        'refresh': '執行 - 接口 [刷新]',
        'export': '導出 - 接口',
        'export_choices': '獲取 - 接口 [導出選單]',
        'choices': {'get': '獲取 - 接口 [下拉選單]'},
    }
    menu_action_key = 'openstacks:ports'
    queryset = (
        PortsModel.objects.select_related('region', 'project', 'device')
        .prefetch_related('fixed_ips', 'security_groups', 'address')
        .all()
    )
    serializer_class = PortsSerializer
    serializer_action_classes = {
        'choices': PortsChoices,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = PortsResource
    filterset_fields = PortsChoices.Meta.fields
    search_fields = [
        'status',
        'description',
        'device__name',
        'security_groups__name',
        'fixed_ips__name',
    ]

    def perform_refresh(self, request, *args, **kwargs):
        refresh_port_resource(**request.data)
