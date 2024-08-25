import operator
import typing

from functools import reduce

from django.conf import settings
from django.core.exceptions import FieldError, ValidationError
from django.db.models import Q
from django.db.models.fields import DateTimeField
from rest_framework.filters import OrderingFilter

from libs.tool import get_attr_list

if typing.TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.views import APIView

from rest_framework.filters import SearchFilter as rest_framework_SearchFilter


class SearchFilter(rest_framework_SearchFilter):
    old_param = 'search_filter'

    def get_search_terms(self, request):
        """
        Search terms are set by a ?search=... query parameter,
        and may be comma and/or whitespace delimited.
        """
        params = request.query_params.get(self.search_param, '') or request.query_params.get(
            self.old_param, ''
        )
        params = params.replace('\x00', '')  # strip null characters
        params = params.replace(',', ' ')
        return params.split()


class BaseFilter:
    page_params = ['page', 'page_size']

    def filter_queryset(self, request, queryset, view):
        """
        過濾函數
        """
        if hasattr(request, 'filter_query_params'):
            _params = request.filter_query_params
        elif hasattr(request, 'query_params'):
            _params = request.query_params
        else:
            _params = request.GET

        params = {k: v for k, v in _params.items()}
        search = params.pop('search', None) or params.pop('search_filter', None)
        like = params.pop('like', False)
        order_by = params.get('order_by')
        ordering = params.pop('ordering', view.ordering)
        desc = params.pop('desc', False)

        # 優先讀取order_by, 若沒有則讀取desc
        if order_by and ordering:
            _order = {'descend': '-'}.get(ordering, '')
            ordering = f'{_order}{order_by}'
        elif ordering:
            _order = '-' if desc else ''
            ordering = f'{_order}{ordering}'

        like = True if str(like).lower() in [1, 'true'] else False

        if search:
            query = Q()
            for col in view.search_fields:
                # 兼容choices
                _choices = get_attr_list(queryset, ['model', col, 'field', 'choices'])
                if _choices:
                    _choices = {v: k for k, v in dict(_choices).items()}
                    value = _choices.get(search)
                    if value:
                        filter = {f'{col}': value}
                    else:
                        filter = {}
                else:
                    filter = {f'{col}__icontains': search}

                query |= Q(**filter)
            queryset = queryset.filter(query)

        for key, val in params.items():
            if key in self.page_params:
                continue
            # 範圍查詢
            if key in view.range_fields:
                try:
                    start, end = val.split(',')
                    filter = {
                        f'{key}__gte': start,
                        f'{key}__lt': end,
                    }
                    queryset = queryset.filter(**filter)
                except:
                    msg = f'範圍查詢 {key} 格式錯誤'
                    raise Exception(msg)
            # 模糊查詢
            elif key in view.fuzzy_search and like:
                try:
                    filter = {f'{key}__contains': val}
                    queryset = queryset.filter(**filter)
                except:
                    msg = f'模糊查詢 {key} 格式錯誤'
                    raise Exception(msg)
            # 多選查詢
            elif key in view.multiple_fields:
                key = view.multiple_fields[key] if isinstance(view.multiple_fields, dict) else key
                vals = val.split(',')
                try:
                    filter = {f'{key}__in': vals}
                    queryset = queryset.filter(**filter)
                except:
                    msg = f'多選查詢 {key} 格式錯誤'
                    raise Exception(msg)
            # 篩選查詢
            elif key in view.filter_fields:
                try:
                    filter = {key: val}
                    queryset = queryset.filter(**filter)
                except ValidationError as e:
                    continue

                except FieldError as e:
                    msg = f'{key} 查詢參數錯誤'
                    raise Exception(msg)

                except:
                    msg = f'不支援 {key} 查詢'
                    raise Exception(msg)

        if ordering:
            queryset = queryset.order_by(ordering)

        return queryset


class RangeFilter:
    def filter_queryset(self, request: 'Request', queryset: 'QuerySet', view: 'APIView'):
        range_fields = getattr(view, 'range_fields', None)
        if range_fields == '__all__':
            range_fields = [
                i for i in view.queryset.model._meta.get_fields() if isinstance(i, DateTimeField)
            ]

        params = request.query_params
        if not range_fields or not any(f in params.keys() for f in range_fields):
            return queryset

        conditions = []
        for field in range_fields:
            val = params.get(field)
            if val:
                start, end = val.split(',')
                filter = {
                    f'{field}__gte': start,
                    f'{field}__lt': end,
                }
                conditions.append(Q(**filter))

        if conditions:
            queryset = queryset.filter(reduce(operator.and_, conditions))

        return queryset


class SAOrderingFilter(OrderingFilter):
    ordering_fields = '__all__'

    def get_ordering(self, request, queryset, view):
        """
        兼容舊版排序接口參數 order_by ordering.
        """
        old_cend = settings.REST_FRAMEWORK.get('ORDERING_CEND_PARAM')
        old_cend = request.query_params.get(old_cend, '')

        params = request.query_params.get(self.ordering_param, '')
        if params or old_cend:
            if old_cend:
                params = f'-{old_cend}' if params in 'descending' else old_cend

            fields = [param.strip() for param in params.split(',')]
            ordering = self.remove_invalid_fields(queryset, fields, view, request)
            if ordering:
                return ordering

        # No ordering was included, or all the ordering fields were invalid
        return self.get_default_ordering(view)
