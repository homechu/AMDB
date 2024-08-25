import typing as t

from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import exception_handler as default_exception_handler


def exception_handler(exc: Exception, context: t.Any) -> t.Optional[Response]:
    response = default_exception_handler(exc, context)
    view = context['view']

    if response is None or getattr(view, 'message', None) is not None:
        return response

    message = f'發生 {response.status_code} 錯誤'
    if isinstance(response.data, dict):
        if isinstance(exc, exceptions.ValidationError):  # 處理 Serializer 驗證錯誤
            message = [f'{", ".join(v)}' for v in response.data.values()]
            message = f'栏位错误: {", ".join(message)}'

        else:
            message = getattr(exc, 'message', response.data.get('detail', message))

    view.message = message
    return response


class ValidationMessage(APIException):
    status_code = HTTP_400_BAD_REQUEST
    default_detail = _('Invalid input.')
    default_code = 'invalid'

    def __init__(self, message=None):
        self.detail = {'detail': message}


class DirectReturn504(Exception):
    """
    Data body was str.
    """

    def __init__(self, *args, **kwargs):  # real signature unknown
        pass


class DirectReturn500(Exception):
    """
    Data body was str.
    """

    def __init__(self, *args, **kwargs):  # real signature unknown
        pass
