from rest_framework import mixins
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.openstacks.models.flavors import FlavorsModel
from apps.openstacks.resouces import FlavorsResource
from apps.openstacks.serializers.flavors import (
    FlavorsChoices,
    FlavorsSerializer,
    FlavorsUpdate,
)
from apps.openstacks.services.flavors import refresh_flavor_resource
from apps.openstacks.views.base import OpenstacksViewSet


class FlavorsViewSet(OpenstacksViewSet, ReadOnlyModelViewSet, mixins.UpdateModelMixin):
    """規格管理頁面 (flavors)"""

    swagger_tags = ['Openstack管理 - 規格管理']
    swagger_generate_tag = 'openstack_flavors'
    swagger_summaries = {
        'list': '獲取 - 規格',
        'retrieve': '獲取 - 規格 [詳情]',
        'refresh': '執行 - 規格 [刷新]',
        'update': '編輯 - 規格',
        'partial_update': '編輯 - 規格 [PATCH]',
        'export': '導出 - 規格',
        'export_choices': '獲取 - 規格 [導出選單]',
        'choices': {'get': '獲取 - 規格 [下拉選單]'},
    }
    menu_action_key = 'openstacks:flavors'
    queryset = FlavorsModel.objects.select_related('region').all()
    serializer_class = FlavorsSerializer
    serializer_action_classes = {
        'retrieve': FlavorsSerializer,
        'choices': FlavorsChoices,
        'update': FlavorsUpdate,
        'partial_update': FlavorsUpdate,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = FlavorsResource
    filterset_fields = FlavorsChoices.Meta.fields
    search_fields = ['name', 'vcpus', 'ram', 'disk']

    def perform_update(self, serializer):
        self.message = '編輯成功'
        serializer.save()

    def perform_refresh(self, request, *args, **kwargs):
        refresh_flavor_resource(**request.data)
