import logging
import typing as t
import tablib

from datetime import datetime
from io import BytesIO
from tempfile import NamedTemporaryFile
from django.db.models import ManyToManyField, Model
from django.http import FileResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from import_export import resources
from openpyxl import Workbook
from rest_framework import parsers, serializers, status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from libs.resources.format import ExportFormat

_MT = t.TypeVar('_MT', bound=Model)


if t.TYPE_CHECKING:
    from rest_framework.generics import UsesQuerySet


logger = logging.getLogger(__name__)


class ChoicesMixin:
    @action(['get'], detail=False, filter_backends=None, pagination_class=None)
    def choices(self: 'UsesQuerySet[_MT]', request: Request, choices_data: dict = {}) -> Response:
        data = getattr(self, 'choices_data', choices_data)
        model_class = self.get_queryset().model

        ser_class = self.get_serializer_class()
        ser_fields = list(getattr(ser_class.Meta, 'fields', []))
        for field in model_class._meta.fields + getattr(model_class._meta, 'many_to_many', ()):
            if (ser_fields and field.name not in ser_fields) or field.name in data:
                continue

            if field.choices:
                data[field.name] = [{'id': k, 'name': v} for k, v in field.choices]
                continue

            # TODO: 將關聯的資料移到序列化，進而優化查詢
            if field.is_relation and field.related_model or isinstance(field, ManyToManyField):
                data[field.name] = [
                    {'id': k, 'name': str(v)} for k, v in field.get_choices(include_blank=0)
                ]
                continue

        for field in set(ser_fields) - set(data.keys()):
            try:
                model_class._meta.get_field(field)
            except Exception:
                continue

            data[field] = [
                {'id': o, 'name': o}
                for o in set(model_class.objects.values_list(field, flat=True))
            ]

        serializer = self.get_serializer(data)
        return Response(serializer.data)


class GetSerializerClassMixin:
    action: str
    serializer_action_classes: t.Dict[str, t.Type[BaseSerializer[t.Any]]] = {}

    def get_serializer_class(self) -> t.Type[BaseSerializer[t.Any]]:
        """
        Get serializer class.

        A class which inhertis this mixins should have variable
        `serializer_action_classes`.
        Look for serializer class in self.serializer_action_classes, which
        should be a dict mapping action name (key) to serializer class (value),
        i.e.:
        class SampleViewSet(viewsets.ViewSet):
            serializer_class = DocumentSerializer
            serializer_action_classes = {
               'upload': UploadDocumentSerializer,
               'download': DownloadDocumentSerializer,
            }
            @action
            def upload:
                ...
        If there's no entry for that action then just fallback to the regular
        get_serializer_class lookup: self.serializer_class, DefaultSerializer.
        """
        return self.serializer_action_classes.get(
            self.action,
            super().get_serializer_class(),  # type: ignore[misc]
        )


class ExportchoicesMixin:
    class File(serializers.Serializer):
        file = serializers.FileField()
        dry_run = serializers.BooleanField()

    class ExportParams(serializers.Serializer):
        ids = serializers.ListField(
            help_text=_('導出IDs, 不帶參數默認依照篩選導出(逗號分隔)'),
            default=[],
            child=serializers.CharField(trim_whitespace=True),
        )
        export_include = serializers.ListField(
            help_text=_('帶參數時, 會依照字串篩選欄位(逗號分隔)'),
            default=[],
            child=serializers.CharField(trim_whitespace=True),
        )

        def validate_ids(self, attrs: t.List[str]) -> t.List:
            return [int(n) for i in attrs for n in i.split(',')]

        def validate_export_include(self, attrs: t.List[str]) -> t.List:
            return [n for i in attrs for n in i.split(',')]

    @swagger_auto_schema(
        request_body=File,
        responses={
            status.HTTP_200_OK: openapi.Schema(
                type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)
            )
        },
        manual_parameters=[
            openapi.Parameter(
                name='file', in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=True
            )
        ],
    )
    @action(
        methods=['post'],
        detail=False,
        url_path='import',
        parser_classes=[parsers.FormParser, parsers.MultiPartParser, parsers.FileUploadParser],
        filter_backends=None,
        pagination_class=None,
    )
    def import_handle(self, request: Request):
        """導入數據.

        TODO:
            - 發送郵件訊息至AMDB MANGER與操作人
            - 郵件訊息 包含 result.diff_header, 與 row.diff

        """
        dry_run = request.data.get('dry_run')
        dataset = tablib.Dataset()
        dataset.load(request.FILES['file'])
        model_class = self.get_queryset().model
        resource_class: resources.ModelResource = getattr(
            self, 'resource_class', resources.modelresource_factory(model=model_class)
        )()
        result = resource_class.import_data(
            dataset,
            dry_run=False if dry_run == 'false' else True,
            raise_errors=True,
            username=request.user.username,
        )

        result.diff_headers = [resource_class.get_verbose(h) for h in result.diff_headers]

        self.message = '導入成功'
        return Response(result.totals)

    @swagger_auto_schema(
        responses={status.HTTP_200_OK: openapi.Schema(type=openapi.TYPE_FILE)},
        query_serializer=ExportParams,
    )
    @action(['get'], detail=False, pagination_class=None)
    def export(self, request: Request) -> Response:
        """導出數據."""
        serializer = self.ExportParams(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        export_include = serializer.validated_data['export_include']

        queryset = self.get_queryset()
        model_class = queryset.model
        verbose_name = model_class._meta.verbose_name

        resource_class: resources.ModelResource = getattr(
            self, 'resource_class', resources.modelresource_factory(model=model_class)
        )
        dataset = resource_class().export(
            queryset=self.filter_queryset(queryset.filter(pk__in=ids) if ids else queryset),
            export_include=export_include,
        )
        dataset.title = verbose_name

        io = ExportFormat.export_set(
            dataset, formatter=resource_class.xlformatter, resource_class=resource_class
        )
        response = FileResponse(
            BytesIO(io),
            filename=f'{verbose_name}_{datetime.now().strftime("%Y%m%d%H")}.xlsx',
            as_attachment=True,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        return response

    @action(['get'], detail=False, filter_backends=None, pagination_class=None)
    def export_choices(self: 'UsesQuerySet[_MT]', request: Request) -> Response:
        """獲取導出篩選訊息."""
        model_class = self.get_queryset().model
        resource_class: resources.ModelResource = getattr(
            self, 'resource_class', resources.modelresource_factory(model=model_class)
        )
        column_map = getattr(resource_class, 'COLUMN_MAP', {})
        for i in getattr(resource_class._meta, 'export_order', resource_class.fields.keys()):
            if i not in column_map:
                column_map[i] = model_class._meta.get_field(i).verbose_name

        serializer = self.get_serializer(
            [{'id': k, 'name': v} for k, v in column_map.items()], many=True
        )
        return Response(serializer.data)

    def save_virtual_workbook(self, wb: Workbook) -> t.BinaryIO:
        with NamedTemporaryFile() as tmp:
            wb.save(tmp.name)
            tmp.seek(0)
            return tmp.read()


class BatchMixin:
    def batch_destroy(self: GenericAPIView, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for instance in serializer.validated_data['ids']:
            self.check_object_permissions(request, instance)

        for instance in serializer.validated_data['ids']:
            self.perform_destroy(instance)

        self.message = '批量刪除成功'
        return Response(status=200)

    def batch_update(self: GenericAPIView, request: Request) -> Response:
        serializer = self.get_serializer(self.get_queryset(), data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        for data in serializer.validated_data:
            self.check_object_permissions(request, data['instance'])

        serializer.save()
        self.message = '批量更新成功'
        return Response(status=200)
