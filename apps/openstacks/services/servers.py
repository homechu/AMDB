import typing as t

from asgiref.sync import sync_to_async

from apps.cmdb.models.app import App
from apps.openstacks.exceptions import OpenstackAPIException
from apps.openstacks.models.base import RegionModel
from apps.openstacks.models.flavors import FlavorsModel
from apps.openstacks.models.images import ImagesModel
from apps.openstacks.models.servers import ServerGroupsModel, ServersModel, ZonesModel
from apps.openstacks.serializers.servers import ServersRefreshSerializer
from apps.openstacks.services.base import refresh_resource, refresh_wraps
from libs.external.openstack import OpenStack
from main.settings import logger


@refresh_wraps(ZonesModel)
def refresh_zones(region: t.Union[RegionModel, str], api: OpenStack):
    hypervisor = dict()
    for item in api.os_hypervisors_detail(region.name).data['hypervisors']:
        item.pop('cpu_info', None)
        hypervisor[item['hypervisor_hostname']] = item

    bulks = []
    id_mappings = ZonesModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.os_availability_zone_detail(region.name).data['availabilityZoneInfo']:
        model_id = f"{region.id}_{item['zoneName']}"

        info_dict = {'state': 'up', 'virtual_num': 0, 'available_ram': 0, 'available_disk': 0}
        for i in item['hosts']:
            if i in hypervisor:
                item['hosts'][i]['hypervisor'] = hypervisor[i]
                if hypervisor[i]['state'] != 'up':
                    info_dict['state'] = 'down'

                info_dict['virtual_num'] += hypervisor[i].get('running_vms', 0)
                info_dict['available_ram'] += hypervisor[i].get('free_ram_mb', 0)
                info_dict['available_disk'] += hypervisor[i].get('free_disk_gb', 0)
            else:
                item['hosts'][i]['hypervisor'] = {}

        kw = {
            'id': model_id,
            'name': item['zoneName'].lower(),
            'region': region,
            'hypervisors': item['hosts'],
            'status': 'enabled' if item['zoneState'].get('available') else 'disabled',
        }
        kw.update(info_dict)
        if kw['id'] in id_mappings:
            is_update = False
            model = id_mappings.pop(model_id)
            for attr, value in kw.items():
                if getattr(model, attr) != value:
                    setattr(model, attr, value)
                    is_update = True

            if is_update:
                bulks.append(model)

        else:
            model = ZonesModel(**kw)
            bulks.append(model)

    return id_mappings, bulks


@refresh_wraps(ServerGroupsModel)
def refresh_servergroups(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    id_mappings = ServerGroupsModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.os_server_groups(region.name, **{'all_projects': True}).data['server_groups']:
        kw = {
            'id': item['id'],
            'name': item['name'],
            'region': region,
        }
        if item['id'] in id_mappings:
            is_update = False
            model = id_mappings.pop(item['id'])
            for attr, value in kw.items():
                if getattr(model, attr) != value:
                    setattr(model, attr, value)
                    is_update = True

            if is_update:
                bulks.append(model)

        else:
            model = ServerGroupsModel(**kw)
            bulks.append(model)

    return id_mappings, bulks


@refresh_wraps(ServersModel)
def refresh_servers(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    """更新虛擬機資訊"""
    app_mappings = {i[1].lower(): i[0] for i in App.active_objects.values_list('id', 'alias')}
    flavor_mapping = FlavorsModel.objects.values_list('id', flat=True)
    image_mapping = ImagesModel.objects.values_list('id', flat=True)
    zone_name_mappings = dict(
        ZonesModel.all_objects.filter(region=region).values_list('name', 'id')
    )
    bulks = []
    id_mappings = ServersModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.servers_detail(region.name, **kwargs).data['servers']:
        logger.debug(f'Server Item: {item}')
        item['region_id'] = region.id
        item['zone_id'] = zone_name_mappings.get(item['OS-EXT-AZ:availability_zone'])
        item['app_id'] = app_mappings.get(item['metadata'].get('apps', '').lower())

        item['image_id'] = item['image'].get('id') if item['image'] else None
        if item['image_id'] not in image_mapping:
            logger.warning(f"Invalid Image id: {item['image_id']}")
            item['image_id'] = None

        item['flavor_id'] = item['flavor'].get('id') if item['flavor'] else None
        if item['flavor_id'] not in flavor_mapping:
            logger.warning(f"Invalid Flavor id: {item['flavor_id']}")
            item['flavor_id'] = None

        ser = ServersRefreshSerializer(data=item)
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
            model = ServersModel(**ser.validated_data)
            bulks.append(model)

    return id_mappings, bulks


def refresh_server_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_zones(item)
        refresh_servergroups(item)
        refresh_servers(item)

    refresh_resource(func, **filterkw)


def rebuild(instance: ServersModel):
    api: OpenStack = instance.region.client()
    rebuild_data = {'name': instance.name, 'imageRef': instance.image.id}
    logger.info(f'{instance.name}重装系统: {rebuild_data}')
    result = api.action_server(instance.region.name, instance.id, 'rebuild', rebuild_data)
    if not result.OK:
        raise OpenstackAPIException(result.data)

    instance.status = 'REBUILD'
    instance.save()


def reboot(instance: ServersModel, _type: str = 'SOFT'):
    api: OpenStack = instance.region.client()
    logger.info(f'{instance.name}重起系统: {_type}')
    result = api.action_server(instance.region.name, instance.id, 'reboot', body={'type': _type})
    if not result.OK:
        raise OpenstackAPIException(result.data)

    instance.status = 'REBOOT'
    instance.save()
