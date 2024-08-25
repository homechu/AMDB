import typing as t

from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from IPy import IP
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from apps.openstacks.models.records import RecordsModel
from apps.openstacks.models.security_groups import RulesModel, SecurityGroupsModel
from apps.openstacks.serializers.base import (
    BatchParamsSerializer,
    ProjectBaseChoices,
    ProjectRefreshSerializer,
    RefreshSerializer,
    RegionBaseChoices,
)
from libs.base.serializers import ChoicesField, SABaseSerializer


class SecurityGroupsChoices(ProjectBaseChoices):
    name = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('區域'))

    class Meta:
        fields = ['name', *ProjectBaseChoices.Meta.fields]


class SecurityGroupsModelRefresh(ProjectRefreshSerializer):
    def to_internal_value(self, data: t.Any) -> t.Any:
        if data['name'] == 'default':
            data['is_default'] = True

        return super().to_internal_value(data)

    class Meta(ProjectRefreshSerializer.Meta):
        model = SecurityGroupsModel


class SecurityGroupsSerializer(SABaseSerializer):
    idc_display = serializers.CharField(source='region.idc.name', read_only=True)
    region_display = serializers.CharField(source='region.name', read_only=True)
    project_display = serializers.CharField(source='project.name', read_only=True)

    class Meta(SABaseSerializer.Meta):
        model = SecurityGroupsModel


class RulesRefreshSerializer(RefreshSerializer):
    remote_ip_prefix = serializers.CharField(allow_null=True, allow_blank=True, default=None)
    security_group_id = serializers.CharField(allow_null=True, allow_blank=True, default='')

    def to_internal_value(self, data: t.Any) -> t.Any:
        data['protocol'] = (data['protocol'] or 'ANY').upper()
        data['remote_ip_prefix'] = data['remote_ip_prefix'] or ''
        data['remote_group_id'] = data['remote_group_id'] or ''
        data['description'] = data['description'] or ''
        return super().to_internal_value(data)

    class Meta(RefreshSerializer.Meta):
        model = RulesModel
        exclude = (*RefreshSerializer.Meta.exclude, 'security_group')


class RemoteIPPrefixsField(serializers.CharField):
    def to_internal_value(self, value: str) -> str:
        try:
            value: IP = IP(value, make_net=True)
        except Exception:
            raise ParseError(f'{value}:IP格式不合法')

        return value


class RulesSerializer(SABaseSerializer):
    class Meta(SABaseSerializer.Meta):
        model = RulesModel


class RulesCreateSerializer(RulesSerializer):
    id = serializers.CharField(read_only=True)
    remote_ip_prefix = serializers.ListField(
        child=RemoteIPPrefixsField(), allow_empty=True, default=[], write_only=True
    )
    remote_group_id = serializers.CharField(allow_null=True, default='')

    def to_internal_value(self, data: t.Any) -> t.Any:
        if all((data['remote_ip_prefix'], data['remote_group_id'])):
            return ParseError('IP段和遠端組ID不能同時存在')

        if not data['remote_ip_prefix'] and not data['remote_ip_prefix']:
            raise ParseError('缺少IP段或遠端組ID')

        self.security_group = SecurityGroupsModel.objects.get(pk=data['security_group'])
        self.rules = self.security_group.rules.filter(is_deleted__isnull=True)
        self.check_filter = {
            'port_range_min': data['port_range_min'],
            'port_range_max': data['port_range_max'],
            'direction': data['direction'],
            'protocol': data['protocol'],
        }
        return super().to_internal_value(data)

    def validate_security_group(self, value: t.AnyStr) -> t.AnyStr:
        if value.is_default:
            raise ParseError('默認安全組不允許修改')

        return value

    def validate_remote_group_id(self, value: t.AnyStr) -> t.AnyStr:
        if not value:
            return value

        self.check_filter['remote_group_id'] = value
        if self.rules.filter(**self.check_filter).exists():
            raise ParseError('安全組規則已存在')

        remote_group = SecurityGroupsModel.objects.filter(
            region=self.security_group.region, pk=value
        )
        if not remote_group.exists():
            raise ParseError('遠端組ID不存在')

    def validate_remote_ip_prefix(self, values: t.List) -> t.List:
        if not values:
            return values

        rules = self.rules.values_list('remote_ip_prefix', flat=True)
        for v in values:
            if len(v) == 1:
                for ip in rules:
                    over = v.overlaps(IP(ip, make_net=True))
                    if over == 1:
                        raise ParseError(f'預新增IP段與{ip}規則存在重疊')
                    elif over == -1:
                        raise ParseError(f'預新增IP段與{ip}規則存在交集')
            else:
                self.check_filter['remote_ip_prefix'] = v.strNormal()
                if self.rules.filter(**self.check_filter).exists():
                    raise ParseError('安全組規則已存在')

        return [v.strNormal() for v in values]

    def validate_protocol(self, value: t.AnyStr) -> t.AnyStr:
        if value == 'ANY' and (
            self.initial_data['port_range_max'] or self.initial_data['port_range_min']
        ):
            raise ParseError('指定端口時無法使用ANY協議')

        return value

    def to_representation(self, instance: t.Any) -> t.Any:
        return {}


class RulesChoices(RegionBaseChoices):
    project = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('項目'))
    remote_group = ChoicesField(
        id_type=openapi.TYPE_STRING,
        help_text=_('遠端安全組'),
        extra_properties={
            'project_id': {'type': openapi.TYPE_STRING},
            'project__name': {'type': openapi.TYPE_STRING},
        },
    )
    protocol = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('協議'))
    ethertype = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('網絡類型'))
    direction = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('方向'))

    class Meta:
        fields = ['project', 'protocol', 'ethertype', 'direction', *RegionBaseChoices.Meta.fields]


class RulesHistory(SABaseSerializer):
    region_display = serializers.CharField(source='region.name')
    create_by = serializers.CharField(help_text=_('操作人'))

    class Meta:
        model = RecordsModel
        exclude = ['resource', 'resource_id', *SABaseSerializer.Meta.exclude]


class BatchRules(BatchParamsSerializer):
    class Meta(BatchParamsSerializer.Meta):
        model = RulesModel
