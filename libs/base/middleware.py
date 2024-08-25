import json
import re
import time

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve

from apps.management.tasks.audit import create_audit


def mask_sensitive_data(data, mask_api_parameters=False):
    """
    Hides sensitive keys specified in sensitive_keys settings.
    Loops recursively over nested dictionaries.

    When the mask_api_parameters parameter is set, the function will
    instead iterate over sensitive_keys and remove them from an api
    URL string.
    """
    SENSITIVE_KEYS = settings.AUDIT_REST_FRAMEWORK['SENSITIVE_KEYS']

    if type(data) is not dict:
        if mask_api_parameters and type(data) is str:
            for sensitive_key in SENSITIVE_KEYS:
                data = re.sub(
                    '({}=)(.*?)($|&)'.format(sensitive_key),
                    '\g<1>******\g<3>'.format(sensitive_key.upper()),
                    data,
                )
        if type(data) is list:
            data = [mask_sensitive_data(item) for item in data]
        return data

    for key, value in data.items():
        if key in SENSITIVE_KEYS:
            data[key] = "******"

        if type(value) is dict:
            data[key] = mask_sensitive_data(data[key])

        if type(value) is list:
            data[key] = [mask_sensitive_data(item) for item in data[key]]

    return data


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.AUDIT_REST_FRAMEWORK = getattr(settings, 'AUDIT_REST_FRAMEWORK')

    def __call__(self, request):
        if not self.AUDIT_REST_FRAMEWORK:
            return self.get_response(request)

        start_time = time.time()
        url_name = resolve(request.path_info).url_name
        namespace = resolve(request.path_info).namespace

        if namespace == 'admin':
            return self.get_response(request)

        if f'{namespace}:{url_name}' in self.AUDIT_REST_FRAMEWORK.get('SKIP_URL_NAMESPACE', []):
            return self.get_response(request)

        try:
            request_data = json.loads(request.body) if request.body else ''
        except:
            request_data = ''

        # Code to be executed for each request before
        # the view (and later middleware) are called.
        response = self.get_response(request)
        method = request.method

        # Log only registered methods if available.
        LOGGER_METHODS = self.AUDIT_REST_FRAMEWORK.get('LOGGER_METHODS', [])
        if LOGGER_METHODS and method not in LOGGER_METHODS:
            return response

        if response.get('content-type') in (
            'application/json',
            'application/vnd.api+json',
            'application/gzip',
            'application/octet-stream',
        ):
            if response.get('content-type') == 'application/gzip':
                response_body = 'GZIP Archive'
            elif response.get('content-type') == 'application/octet-stream':
                response_body = 'Binary File'
            elif getattr(response, 'streaming', False):
                response_body = 'Streaming'
            else:
                if type(response.content) is bytes:
                    response_body = json.loads(response.content.decode())
                else:
                    response_body = json.loads(response.content)

            auth = 3
            sso: str = request.COOKIES.get('sso', '')
            if sso.startswith('WEB'):
                auth = 1
            elif sso.startswith('API'):
                auth = 2

            try:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                else:
                    ip = request.META.get('REMOTE_ADDR')
            except:
                ip = None

            sensitive_response = mask_sensitive_data(response_body)
            data = {
                'user': request.user.username if request.user != AnonymousUser else '',
                'ip': ip,
                'auth': auth,
                'method': method,
                'url': mask_sensitive_data(request.get_full_path(), mask_api_parameters=True),
                'body': json.dumps(mask_sensitive_data(request_data)),
                'response': json.dumps(sensitive_response),
                'resp_code': sensitive_response.get('code') or response.status_code,
                'resp_time': sensitive_response.get('time') or start_time - time.time(),
                'resp_message': sensitive_response.get('message') or '',
            }
            if settings.CURRENT_ENV == 'LOCAL':
                create_audit.run(**data)
            else:
                create_audit.delay(**data)
        else:
            return response

        return response
