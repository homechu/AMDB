from rest_framework import mixins
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.openstacks.models.images import ImagesModel
from apps.openstacks.resouces import ImagesResource
from apps.openstacks.serializers.images import (
    ImagesChoices,
    ImagesSerializer,
    ImagesUpdate,
)
from apps.openstacks.services.images import refresh_image_resource
from apps.openstacks.views.base import OpenstacksViewSet


class ImagesViewSet(OpenstacksViewSet, ReadOnlyModelViewSet, mixins.UpdateModelMixin):
    """鏡像管理頁面 (images)"""

    swagger_tags = ['Openstack管理 - 鏡像管理']
    swagger_generate_tag = 'openstack_images'
    swagger_summaries = {
        'list': '獲取 - 鏡像',
        'retrieve': '獲取 - 鏡像 [詳情]',
        'refresh': '執行 - 鏡像 [刷新]',
        'update': '編輯 - 鏡像',
        'partial_update': '編輯 - 鏡像 [PATCH]',
        'export': '導出 - 鏡像',
        'export_choices': '獲取 - 鏡像 [導出選單]',
        'choices': {'get': '獲取 - 鏡像 [下拉選單]'},
    }
    menu_action_key = 'openstacks:images'
    queryset = ImagesModel.objects.select_related('region').all()
    serializer_class = ImagesSerializer
    serializer_action_classes = {
        'retrieve': ImagesSerializer,
        'choices': ImagesChoices,
        'update': ImagesUpdate,
        'partial_update': ImagesUpdate,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = ImagesResource
    filterset_fields = ImagesChoices.Meta.fields
    search_fields = ['name', 'visibility', 'container_format', 'os_distro']

    def perform_update(self, serializer):
        self.message = '編輯成功'
        serializer.save()

    def perform_refresh(self, request, *args, **kwargs):
        refresh_image_resource(**request.data)
