import asyncio
import typing as t

from datetime import datetime
from functools import wraps

from dateutil import parser

from apps.cmdb.models.idc import IDC
from apps.openstacks.exceptions import OpenstackAPIException
from apps.openstacks.models.base import BaseModel, ProjectsModel, RegionModel
from apps.openstacks.models.security_groups import RulesModel, SecurityGroupsModel
from libs.external.openstack import OpenStack
from main.settings import logger


def opesntack_api_wraps(func):
    @wraps(func)
    def wrapper(region: t.Union[RegionModel, str], *args, **kwargs):
        project_id = kwargs['project'].id if kwargs.get('project') else None
        region = RegionModel.objects.get(pk=region) if isinstance(region, str) else region
        api: OpenStack = region.client(project_id)
        return func(region=region, api=api, *args, **kwargs)

    return wrapper


def refresh_wraps(model: BaseModel, idc_base=False) -> str:
    def _refresh_wraps(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if idc_base:
                _pk = kwargs.get('idc', args[0])
                kwargs['idc'] = IDC.objects.get(pk=_pk) if isinstance(_pk, int) else _pk
                api = OpenStack.from_idc(kwargs['idc'])
            else:
                _pk = kwargs.get('region', args[0])
                kwargs['region'] = RegionModel.objects.get(pk=_pk) if isinstance(_pk, str) else _pk
                api = kwargs['region'].client()

            ids_delete, bulks = func(api=api, **kwargs)
            if bulks:
                model.all_objects.bulk_create_or_update(bulks)

            if ids_delete:
                de_kwargs = {'pk__in': ids_delete.keys()}
                if idc_base:
                    de_kwargs['idc'] = _pk
                else:
                    de_kwargs['region'] = _pk

                model.all_objects.filter(**de_kwargs).delete()

            return f'{model._meta.verbose_name} Refresh Success: {datetime.now()}'

        return wrapper

    return _refresh_wraps


def sync_default_security_groups(region: RegionModel, api: OpenStack, project: str):
    result = api.security_groups(region)
    if not result.OK:
        raise OpenstackAPIException('獲取安全組失敗')

    admin_proj = api._projects['admin']
    project_id = api._projects[project]

    # 添加默認安全組
    sec_groups = result.data['security_groups']
    admin_default = next(
        (i for i in sec_groups if i['name'] == 'default' and i['project_id'] == admin_proj), None
    )
    default_group = next(
        (n for n in sec_groups if n['name'] == 'default' and n['project_id'] == project_id), None
    )
    if default_group and admin_default:
        SecurityGroupsModel.all_objects.update_or_create(
            defaults={
                'region_id': region.id,
                'project_id': default_group['project_id'],
                'name': default_group['name'],
                'description': default_group['description'],
                'create_time': parser.isoparse(default_group['created_at']).replace(tzinfo=None),
                'is_deleted': None,
            },
            id=default_group['id'],
        )
        for default_rule in admin_default['security_group_rules']:
            if default_rule['direction'] != 'ingress':
                continue

            kw = {
                'region': region,
                'security_group_id': default_group['id'],
                'remote_group_id': default_rule['remote_group_id'],
                'remote_ip_prefix': default_rule['remote_ip_prefix'],
                'port_range_min': default_rule['port_range_min'],
                'port_range_max': default_rule['port_range_max'],
                'ethertype': default_rule['ethertype'],
                'protocol': default_rule['protocol'],
                'direction': default_rule['direction'],
                'description': default_rule.get('description', ''),
            }
            logger.debug(f'增加安全組 {kw}')
            result = api.add_security_group_rules(**kw)
            if not result.OK:
                logger.error('同步默认安全组失败', extra={'data': kw})
            else:
                RulesModel.objects.create(**kw)
    else:
        logger.error(f'查無 {project if default_group else "admin"} 項目默認安全組')


def create_region_project(region: RegionModel, project: str):
    """檢查並創建 Openstack 項目, 需要 admin 權限.

    Args:
        project: 項目名稱.

    """
    api = region.client()
    if project.upper() in [i.upper() for i in api._projects.keys()]:
        return True, f'{project}项目已存在'

    roles_name = 'admin'

    # 獲得用戶列表
    users_result = api.get_users()
    if not users_result.OK:
        raise OpenstackAPIException('獲取用戶列表失敗')

    users_result = users_result.data['users']

    # 獲取規則ID
    roles_result = api.get_roles()
    if not roles_result.OK:
        raise OpenstackAPIException('獲取規則列表失敗')

    roles_result = roles_result.data['roles']

    # 創建項目
    result = api.create_project(project)
    if not result.OK:
        raise OpenstackAPIException(f'創建項目 {project} 失敗')

    project_id = result.data['project']['id']
    api._projects[project] = project_id

    # 賦予腳色權限
    user = next((i for i in users_result if i['name'] == api.username), dict())
    user_id = user.get('id')

    role = next((i for i in roles_result if i['name'] == roles_name), dict())
    role_id = role.get('id')

    if role_id:
        result = api.attach_user_role_project(project_id, user_id, role_id)
        if not result.OK:
            raise OpenstackAPIException(f'賦予權限 {project_id} 失敗')
    else:
        logger.error(f'項目 {project} 賦予權限失敗: 查無 admin 權限')

    # 配置默認計算配額
    result = api.get_compute_quota(region, api._projects['admin'])
    if not result.OK:
        raise OpenstackAPIException('獲取計算配額失敗')

    com_quota = result.data
    com_quota['quota_set'].pop('id')

    result = api.put_compute_quota(region, project_id, com_quota)
    if not result.OK:
        raise OpenstackAPIException('配置計算配額失敗')

    # 配置默認網路配額
    result = api.get_network_quota(region, api._projects['admin'])
    if not result.OK:
        raise OpenstackAPIException('獲取網路配額失敗')

    net_quota = result.data

    result = api.put_network_quota(region, project_id, net_quota)
    if not result.OK:
        raise OpenstackAPIException('配置網路配額失敗')

    sync_default_security_groups(region, api, project)
    return True, result


def refresh_resource(func, **filterkw):
    async def async_run(data, func) -> None:
        await asyncio.gather(*[func(i) for i in data])

    data = list(RegionModel.objects.filter(**filterkw))
    asyncio.run(async_run(data, func))


@refresh_wraps(RegionModel, True)
def refresh_regions(idc: t.Union[IDC, int], api: OpenStack):
    bulks = []
    id_mappings = RegionModel.all_objects.filter(idc=idc).in_bulk(field_name='id')
    for name, details in api.region.items():
        model_id = f'{idc}_{name}'
        if model_id in id_mappings:
            model = id_mappings.pop(model_id)
            if model.details != details:
                model.details = details
                bulks.append(model)
        else:
            model = RegionModel(id=model_id, name=name, idc=idc, details=details)
            bulks.append(model)

    return id_mappings, bulks


@refresh_wraps(ProjectsModel, True)
def refresh_projects(idc: t.Union[IDC, int], api: OpenStack):
    bulks = []
    id_mappings = ProjectsModel.all_objects.filter(idc=idc).in_bulk(field_name='id')
    for name, _id in api._projects.items():
        if _id in id_mappings:
            model = id_mappings.pop(_id)
            if model.name != name:
                model.name = name
                bulks.append(model)
        else:
            model = ProjectsModel(id=_id, idc=idc, name=name)
            bulks.append(model)

    return id_mappings, bulks
