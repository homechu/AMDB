from functools import wraps

from django.db.models import QuerySet
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from apps.openstacks.models.records import RecordsModel
from libs.base.permissions import CMDBPermission
from libs.base.serializers import ExportChoicesSerializer
from libs.mixins import (
    BatchMixin,
    ChoicesMixin,
    ExportchoicesMixin,
    GetSerializerClassMixin,
)
from main.settings import PERMISSION_SA_ROLES


def perform_record(action_type):
    def decorator(func):
        @wraps(func)
        def wrapper(self: 'OpenstacksViewSet', *args, **kwargs):
            kw = {
                'create_by': self.request.user,
                'action_type': action_type,
                'resource': getattr(self, 'menu_action_key', ''),
            }
            try:
                res = func(self, *args, **kwargs)
                kw.update(self.record_details)
            except Exception as e:
                kw.update(self.record_details)
                kw.update({'details': str(e), 'status': 'FAIL'})
                raise
            finally:
                RecordsModel.objects.create(**kw)

            return res

        return wrapper

    return decorator


class OpenstacksPermission(CMDBPermission):
    message = '您無權進行操作，請聯繫產品、業務運維負責人'

    def has_permission(self, request, view):
        permission = request.user.user_permission
        if not set(PERMISSION_SA_ROLES) & set(permission['rolename']):
            view.queryset = view.queryset.filter(product_id__in=permission['products'])

        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view: views.APIView, obj) -> bool:
        permission = request.user.user_permission
        if set(PERMISSION_SA_ROLES) & set(permission['rolename']):
            return True

        key = getattr(view, 'menu_action_key', None)
        # API統一給SSO管理
        if not request.user.is_api:
            menu_perm: QuerySet = permission['menu']
            if not menu_perm.filter(key2=f"{key}:{view.action}").exists():
                raise PermissionDenied('您沒有接口權限，請聯繫管理員')

        return (
            super().has_object_permission(request, view, obj)
            or obj.product_id in permission['products']
            or obj.person.filter(name=request.user.username, is_deleted=False).exists()
            or obj.product.person.filter(name=request.user.username, is_deleted=False).exists()
        )


class OpenstacksViewSet(
    BatchMixin, ChoicesMixin, GetSerializerClassMixin, ExportchoicesMixin, viewsets.GenericViewSet
):
    message = None
    permission_classes = [OpenstacksPermission]
    serializer_action_classes = {'export_choices': ExportChoicesSerializer}
    range_fields = ['create_time', 'update_time']
    ordering = ['-id']

    record_details = {}

    def import_handle(self):
        pass

    def batch_serializer(self, request: Request, *args, **kwargs) -> Serializer:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for instance in serializer.validated_data['ids']:
            self.check_object_permissions(request, instance)

        return serializer

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'region': openapi.Schema(type=openapi.TYPE_STRING)},
        )
    )
    @action(methods=['POST'], detail=False, serializer_class=Serializer)
    def refresh(self, request, *args, **kwargs):
        func = getattr(self, 'perform_refresh', None)
        if func:
            func(request, *args, **kwargs)
        else:
            self.message = '刷新功能未定義'

        self.message = '刷新成功'
        return Response()
