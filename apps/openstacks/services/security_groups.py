import typing as t

from asgiref.sync import sync_to_async

from apps.openstacks.exceptions import OpenstackAPIException
from apps.openstacks.models.base import ProjectsModel, RegionModel
from apps.openstacks.models.security_groups import RulesModel, SecurityGroupsModel
from apps.openstacks.serializers.security_groups import (
    RulesRefreshSerializer,
    SecurityGroupsModelRefresh,
)
from apps.openstacks.services.base import (
    opesntack_api_wraps,
    refresh_resource,
    refresh_wraps,
)
from libs.external.openstack import OpenStack
from main.settings import logger


@refresh_wraps(SecurityGroupsModel)
def refresh_security_groups(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    project_id_mappings = ProjectsModel.all_objects.in_bulk(field_name='id')
    id_mappings = SecurityGroupsModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.security_groups(region.name).data['security_groups']:
        logger.debug(f'Security Group Item: {item}')
        item['region_id'] = region.id
        item['project_id'] = item['project_id']
        if item['project_id'] not in project_id_mappings:
            continue

        ser = SecurityGroupsModelRefresh(data=item)
        ser.is_valid(True)
        if item['id'] in id_mappings:
            is_update = None
            model = id_mappings.pop(item['id'])
            for attr, value in ser.validated_data.items():
                if getattr(model, attr) != value:
                    setattr(model, attr, value)
                    is_update = True

            if is_update:
                bulks.append(model)
        else:
            model = SecurityGroupsModel(**ser.validated_data)
            bulks.append(model)

    return id_mappings, bulks


@refresh_wraps(RulesModel)
def refresh_rules(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    sg_id_mappings = SecurityGroupsModel.all_objects.filter(region=region).in_bulk(field_name='id')
    id_mappings = RulesModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.security_group_rules(region.name).data['security_group_rules']:
        logger.debug(f'Rule Item: {item}')
        item['region_id'] = region.id
        if item['security_group_id'] not in sg_id_mappings:
            logger.warning(f'Invalid security group id: {item["security_group_id"]}')
            continue

        ser = RulesRefreshSerializer(data=item)
        ser.is_valid(True)

        if item['id'] in id_mappings:
            is_update = None
            model = id_mappings.pop(item['id'])
            for attr, value in ser.validated_data.items():
                if getattr(model, attr) != value:
                    setattr(model, attr, value)
                    is_update = True

            if is_update:
                bulks.append(model)
        else:
            bulks.append(RulesModel(**ser.validated_data))

    return id_mappings, bulks


@opesntack_api_wraps
def del_rules(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    res = api.del_security_group_rules(region, kwargs['id'])
    logger.debug(f'Deleted Rule:{res.OK}:{kwargs}')
    if not res.OK:
        raise OpenstackAPIException(res.data)

    return res.data


@opesntack_api_wraps
def add_rules(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    res = api.add_security_group_rules(**kwargs)
    logger.debug(f'Added Rule:{res.OK}:{kwargs}')
    if not res.OK:
        raise OpenstackAPIException(res.data)

    return res.data


def refresh_securitygroup_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_security_groups(item)

    refresh_resource(func, **filterkw)


def refresh_rule_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_rules(item)

    refresh_resource(func, **filterkw)
