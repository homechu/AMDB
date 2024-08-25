import typing as t

from asgiref.sync import sync_to_async

from apps.openstacks.models.base import RegionModel
from apps.openstacks.models.images import ImagesModel
from apps.openstacks.serializers.images import ImagesRefreshSerializer
from apps.openstacks.services.base import refresh_resource, refresh_wraps
from libs.external.openstack import OpenStack
from main.settings import logger


@refresh_wraps(ImagesModel)
def refresh_images(region: t.Union[RegionModel, str], api: OpenStack):
    system = set()
    bulks = []
    id_mappings = ImagesModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.images(region.name).data['images']:
        logger.debug(f'Image Item: {item}')
        item['region_id'] = region.id
        ser = ImagesRefreshSerializer(data=item)
        ser.is_valid(True)

        if item['name'] not in system:
            system.add(item['name'])

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
            model = ImagesModel(**ser.validated_data)
            bulks.append(model)

    vc = region.idc.vcenterinfo
    if set(vc.system or []) ^ system:
        vc.system = list(system)
        vc.save()

    return id_mappings, bulks


def refresh_image_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_images(item)

    refresh_resource(func, **filterkw)
