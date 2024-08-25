from django.db.models import OuterRef, Subquery
from django.forms.models import model_to_dict
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.openstacks.models.records import RecordsModel
from apps.openstacks.models.security_groups import RulesModel, SecurityGroupsModel
from apps.openstacks.resouces import RulesResource, SecurityGroupsResource
from apps.openstacks.serializers.security_groups import (
    BatchRules,
    RulesChoices,
    RulesCreateSerializer,
    RulesHistory,
    RulesSerializer,
    SecurityGroupsChoices,
    SecurityGroupsSerializer,
)
from apps.openstacks.services.security_groups import (
    add_rules,
    del_rules,
    refresh_rule_resource,
    refresh_securitygroup_resource,
)
from apps.openstacks.views.base import OpenstacksViewSet, perform_record


class SecurityGroupsViewSet(OpenstacksViewSet, mixins.ListModelMixin):
    swagger_tags = ['Openstack管理 - 安全組管理']
    swagger_generate_tag = 'openstack_securitygroups'
    swagger_summaries = {
        'list': '獲取 - 安全組',
        'refresh': '執行 - 安全組 [刷新]',
        'choices': {'get': '獲取 - 安全組 [下拉選單]'},
        'export': '導出 - 安全組',
        'export_choices': '獲取 - 安全組 [導出選單]',
    }
    queryset = SecurityGroupsModel.objects.select_related('region', 'project', 'region__idc').all()
    serializer_class = SecurityGroupsSerializer
    serializer_action_classes = {
        'choices': SecurityGroupsChoices,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = SecurityGroupsResource
    filterset_fields = SecurityGroupsChoices.Meta.fields
    search_fields = ['id', 'name', 'description']

    @property
    def choices_data(self):
        queryset = (
            SecurityGroupsModel.objects.exclude(name__in=['default'])
            .values_list('name', flat=True)
            .distinct()
        )
        return {'name': [{'id': i, 'name': i} for i in queryset]}

    def perform_refresh(self, request, *args, **kwargs):
        refresh_securitygroup_resource(**request.data)


class RulesViewSet(
    OpenstacksViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
):
    swagger_tags = ['Openstack管理 - 規則管理']
    swagger_generate_tag = 'openstack_rules'
    swagger_summaries = {
        'list': '獲取 - 規則',
        'defaultrules': '獲取 - 默認規則',
        'create': '創建 - 規則',
        'destroy': '刪除 - 規則',
        'batch_destroy': '批量刪除 - 規則',
        'refresh': '執行 - 規則 [刷新]',
        'choices': {'get': '獲取 - 規則 [下拉選單]'},
        'export': '導出 - 規則',
        'export_choices': '獲取 - 規則 [導出選單]',
        'history': '獲取 - 規則審計',
    }
    menu_action_key = 'openstacks:security_group_rule'
    queryset = (
        RulesModel.objects.select_related('region', 'security_group')
        .annotate(
            remote_group_name=Subquery(
                SecurityGroupsModel.objects.filter(id=OuterRef('remote_group_id')).values('name')
            )
        )
        .all()
    )
    records = RecordsModel.objects.filter(resource=menu_action_key)
    serializer_class = RulesSerializer
    serializer_action_classes = {
        'create': RulesCreateSerializer,
        'choices': RulesChoices,
        'batch_destroy': BatchRules,
        'history': RulesHistory,
        **OpenstacksViewSet.serializer_action_classes,
    }
    resource_class = RulesResource
    filterset_fields = ['security_group_id', 'protocol', 'ethertype', 'direction', 'region']
    search_fields = [
        'remote_ip_prefix',
        'port_range_min',
        'port_range_max',
        'protocol',
        'direction',
        'ethertype',
        'description',
    ]

    @perform_record(action_type='DELETE')
    def perform_destroy(self, instance: RulesModel):
        region = instance.region
        self.record_details['region'] = region
        self.record_details['resource_id'] = instance.security_group.id
        del_rules(region=region, id=instance.id)
        instance.update_by = self.request.user.username
        instance.delete()
        self.record_details['details'] = model_to_dict(instance)
        self.message = '規則已刪除'

    @perform_record(action_type='CREATE')
    def perform_create(self, serializer):
        kw = serializer.validated_data
        self.record_details['region'] = kw['region']
        self.record_details['resource_id'] = kw['security_group_id'] = kw['security_group'].id

        details = []
        remote_ip_prefix = kw['remote_ip_prefix']
        for ip in remote_ip_prefix or [kw['remote_group_id']]:
            kw['remote_ip_prefix'] = ip if kw['remote_ip_prefix'] else None
            kw['remote_group_id'] = kw['remote_group_id'] or None
            res = add_rules(**kw)
            _id = res['security_group_rule']['id']
            kw['remote_ip_prefix'] = ip if kw['remote_ip_prefix'] else ''
            kw['remote_group_id'] = kw['remote_group_id'] or ''
            details.append(
                RulesModel.objects.create(id=_id, create_by=self.request.user.username, **kw)
            )

        self.record_details['details'] = details
        self.message = '規則已新增'

    def perform_refresh(self, request, *args, **kwargs):
        refresh_rule_resource(**request.data)

    @action(methods=[], detail=False)
    def batch(self, request, *args, **kwargs) -> Response:
        pass

    @swagger_auto_schema(request_body=BatchRules)
    @batch.mapping.delete
    def batch_destroy(self, request, *args, **kwargs) -> Response:
        serializer = self.batch_serializer(request, *args, **kwargs)
        for instance in serializer.validated_data['ids']:
            self.perform_destroy(instance)

        self.message = '批量刪除成功'
        return Response()

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'security_group_id',
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description='安全組ID',
            ),
        ]
    )
    @action(['GET'], detail=False, filter_backends=None, pagination_class=None)
    def defaultrules(self, request, choices_data: dict = {}) -> Response:
        security_group_id = request.query_params.get('security_group_id')
        sg = SecurityGroupsModel.objects.get(pk=security_group_id)
        queryset = (
            SecurityGroupsModel.objects.filter(
                is_default=True, region=sg.region, project=sg.project
            )
            .first()
            .rules.all()
        )
        serializer = RulesSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'region',
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description='所屬區域ID',
                required=True,
            ),
        ]
    )
    @action(['GET'], detail=False, filter_backends=None, pagination_class=None)
    def choices(self, request, choices_data: dict = {}) -> Response:
        region = request.query_params.get('region')
        remote_group = (
            SecurityGroupsModel.objects.filter(region=region)
            .exclude(name__in=['default', 'null'])
            .exclude(project__name__in=['admin', 'service'])
            .values('id', 'name', 'project_id', 'project__name')
        )
        project = {i['project_id']: i['project__name'] for i in remote_group}
        return super().choices(
            request,
            choices_data={
                'remote_group': remote_group,
                'project': [{'id': k, 'name': v} for k, v in project.items()],
            },
        )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'security_group', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='安全組ID'
            ),
        ]
    )
    @action(['GET'], detail=False, filter_backends=[])
    def history(self, request, *args, **kwargs) -> Response:
        sg = SecurityGroupsModel.objects.get(id=request.query_params['security_group'])
        self.queryset = self.records.filter(region=sg.region, resource_id=sg.id).select_related(
            'region'
        )
        return super().list(self, request, *args, **kwargs)

    @property
    def is_paginated(self) -> bool:
        return self.action in ('history',)
