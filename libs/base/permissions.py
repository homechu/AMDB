from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from main.settings import PERMISSION_SA_ROLES


class CMDBPermission(BasePermission):
    message = None

    def has_permission(self, request: Request, view: APIView) -> bool:
        view.current_user = request.user
        if isinstance(view.current_user, AnonymousUser):
            self.message = '認證過期, 請登入認證'
            return False

        data = request.user.user_permission
        if isinstance(data['role'], QuerySet) and not data['role'].exists():
            self.message = '錯誤原因: 您沒有被配置角色權限, 請聯繫管理員'
            return False

        return True

    def has_object_permission(self, request: Request, view: Request, obj) -> bool:
        if set(PERMISSION_SA_ROLES) & set(request.user.user_permission['rolename']):
            return True
