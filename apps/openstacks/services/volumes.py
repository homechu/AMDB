import typing as t

from asgiref.sync import sync_to_async

from apps.openstacks.exceptions import OpenstackAPIException
from apps.openstacks.models.base import RegionModel
from apps.openstacks.models.volumes import (
    VolumesAttachments,
    VolumesModel,
    VolumeTypeModel,
)
from apps.openstacks.serializers.volumes import (
    VolumesAttachmentsRefresh,
    VolumesRefreshSerializer,
    VolumesTypeRefreshSerializer,
)
from apps.openstacks.services.base import (
    opesntack_api_wraps,
    refresh_resource,
    refresh_wraps,
)
from libs.external.openstack import OpenStack
from main.settings import logger


@refresh_wraps(VolumesModel)
def refresh_volumes(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    volumeattach = {'attachments': []}
    id_mappings = VolumesModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.volumes(region.name).data['volumes']:
        logger.debug(f'Volume Item: {item}')
        item['region_id'] = region.id
        item['project_id'] = item['os-vol-tenant-attr:tenant_id']
        item['name'] = item['name'] or item['id']
        ser = VolumesRefreshSerializer(data=item)
        ser.is_valid(True)

        volumeattach['attachments'] += item.get('attachments', [])
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
            model = VolumesModel(**ser.validated_data)
            bulks.append(model)

    # For API v3.13
    _new, _old = [b for b in bulks if not b.create_time], [b for b in bulks if b.create_time]
    VolumeTypeModel.objects.bulk_create(_new, batch_size=200)
    refresh_volumeattach(region, volumeattach=volumeattach)

    return id_mappings, _old


@refresh_wraps(VolumeTypeModel)
def refresh_volumetype(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    id_mappings = VolumeTypeModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.volume_types(region.name).data['volume_types']:
        item['region_id'] = region.id
        ser = VolumesTypeRefreshSerializer(data=item)
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
            model = VolumeTypeModel(**ser.validated_data)
            bulks.append(model)

    return id_mappings, bulks


@refresh_wraps(VolumesAttachments)
def refresh_volumeattach(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    """刷新卷绑定

    Note:
        Everything except for Complete attachment is new as of the 3.27 microversion. Complete attachment is new as of the 3.44 microversion.

    """
    bulks = []
    id_mappings = VolumesAttachments.all_objects.filter(region=region).in_bulk(field_name='id')
    res = kwargs.get('volumeattach', api.volumes_attachments(region).data)
    if 'itemNotFound' in str(res)[:15]:
        return [], []

    for item in res['attachments']:
        item['region_id'] = region.id
        ser = VolumesAttachmentsRefresh(data=item)
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
            model = VolumesAttachments(**ser.validated_data)
            bulks.append(model)

    return id_mappings, bulks


def refresh_volume_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_volumetype(item)
        refresh_volumes(item)
        # API v3.27 only.
        # refresh_volumeattach(item)

    refresh_resource(func, **filterkw)


@opesntack_api_wraps
def add_volumes(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    res = api.add_volumes(
        region,
        kwargs['project'],
        kwargs['size'],
        kwargs['volume_type'],
        kwargs['description'],
        kwargs.get('name'),
    )
    if not res.OK:
        raise OpenstackAPIException(res.data)

    return res.data


@opesntack_api_wraps
def del_volumes(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    res = api.del_volumes(region, kwargs['project'], kwargs['id'])
    if not res.OK:
        raise OpenstackAPIException(res.data)

    return res.data


@opesntack_api_wraps
def del_attachments(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    res = api.del_server_os_volume_attachments(region, kwargs['server_id'], kwargs['volume_id'])
    if not res.OK:
        raise OpenstackAPIException(res.data)

    return res.data


@opesntack_api_wraps
def add_attachments(region: t.Union[RegionModel, str], api: OpenStack, *args, **kwargs):
    res = api.add_server_os_volume_attachments(region, kwargs['server_id'], kwargs['volume_id'])
    if not res.OK:
        raise OpenstackAPIException(res.data)

    return res.data
