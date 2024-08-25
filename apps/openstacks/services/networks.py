import typing as t

from asgiref.sync import sync_to_async
from django.db.models import Model

from apps.openstacks.models.networks import AddressThrough, PortsModel, SubnetsModel
from apps.openstacks.models.servers import ServersModel
from apps.openstacks.serializers.networks import (
    PortsRefreshSerializer,
    SubnetsRefreshSerializer,
)
from apps.openstacks.services.base import RegionModel, refresh_resource, refresh_wraps
from libs.external.openstack import OpenStack
from main.settings import logger


@refresh_wraps(SubnetsModel)
def refresh_subnets(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    id_mappings = SubnetsModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.subnets(region.name).data['subnets']:
        logger.debug(f'Subnet Item: {item}')
        item['region_id'] = region.id
        item['project_id'] = item['project_id']
        ser = SubnetsRefreshSerializer(data=item)
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
            model = SubnetsModel(**ser.validated_data)
            bulks.append(model)

    return id_mappings, bulks


@refresh_wraps(PortsModel)
def refresh_ports(region: t.Union[RegionModel, str], api: OpenStack):
    Port_sec_model: Model = PortsModel.security_groups.through
    port_sec_bulks = []
    port_sec_id_mappings = Port_sec_model.objects.filter(portsmodel__region=region)
    port_sec_id_mappings = {
        p.portsmodel_id + p.securitygroupsmodel_id: p.id for p in port_sec_id_mappings
    }
    server_bulks = []
    server_mapping = ServersModel.all_objects.filter(region=region).in_bulk(field_name='id')
    addr_bulks = []
    addr_id_mappings = AddressThrough.all_objects.filter(region=region).in_bulk(field_name='id')
    bulks = []
    id_mappings = PortsModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.ports(region.name).data['ports']:
        logger.debug(f'Ports Item: {item}')
        item['region_id'] = region.id

        if item['project_id'] not in api._projects.values():
            logger.warning(f"Port:{item['id']} is not in projects")
            continue

        if item['device_id'] not in server_mapping:
            logger.warning(f'Server not found for port {item["device_id"]}')
            item['device_id'] = None

        ser = PortsRefreshSerializer(data=item)
        ser.is_valid(True)

        for ips in item.get('fixed_ips', []):
            ip_address = ips['ip_address']
            model_id = f'{region.id}_{ip_address}'
            kw = {
                'id': model_id,
                'ip_address': ip_address,
                'region_id': region.id,
                'subnet_id': ips['subnet_id'],
                'port_id': item['id'],
            }
            if model_id in addr_id_mappings:
                is_update = False
                model = addr_id_mappings.pop(model_id)
                for attr, value in kw.items():
                    if getattr(model, attr) != value:
                        setattr(model, attr, value)
                        is_update = True

                if is_update:
                    addr_bulks.append(model)
            else:
                addr_bulks.append(AddressThrough(**kw))

            if item['device_id'] in server_mapping:
                server_mapping[item['device_id']].ip_address = ip_address
                server_bulks.append(server_mapping[item['device_id']])

        for sg_id in item.get('security_groups', []):
            mapping_id = item['id'] + sg_id
            if mapping_id in port_sec_id_mappings:
                port_sec_id_mappings.pop(mapping_id)
            else:
                port_sec_bulks.append(
                    Port_sec_model(portsmodel_id=item['id'], securitygroupsmodel_id=sg_id)
                )

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
            bulks.append(PortsModel(**ser.validated_data))

    PortsModel.all_objects.bulk_create_or_update(bulks)
    PortsModel.all_objects.filter(region=region, id__in=id_mappings.keys()).delete()

    Port_sec_model.objects.bulk_create(port_sec_bulks, batch_size=1000)
    Port_sec_model.objects.filter(
        portsmodel__region=region, id__in=port_sec_id_mappings.values()
    ).delete()

    AddressThrough.all_objects.bulk_create_or_update(addr_bulks)
    AddressThrough.all_objects.filter(region=region, id__in=addr_id_mappings.keys()).delete()

    ServersModel.all_objects.bulk_update(server_bulks, fields=['ip_address'], batch_size=1000)
    return [], []


def refresh_port_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_subnets(item)
        refresh_ports(item)

    refresh_resource(func, **filterkw)
