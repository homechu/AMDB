import typing as t

from asgiref.sync import sync_to_async

from apps.openstacks.models.base import RegionModel
from apps.openstacks.models.flavors import FlavorsModel
from apps.openstacks.serializers.flavors import FlavorsRefreshSerializer
from apps.openstacks.services.base import refresh_resource, refresh_wraps
from libs.external.openstack import OpenStack
from main.settings import logger


@refresh_wraps(FlavorsModel)
def refresh_flavors(region: t.Union[RegionModel, str], api: OpenStack):
    bulks = []
    id_mappings = FlavorsModel.all_objects.filter(region=region).in_bulk(field_name='id')
    for item in api.flavors(region.name).data['flavors']:
        logger.debug(f'Flavor Item: {item}')
        item['region_id'] = region.id
        ser = FlavorsRefreshSerializer(data=item)
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
            bulks.append(FlavorsModel(**ser.validated_data))

    return id_mappings, bulks


def refresh_flavor_resource(region: str = None):
    filterkw = dict()
    if region:
        filterkw['id'] = region

    @sync_to_async(thread_sensitive=False)
    def func(item):
        refresh_flavors(item)

    refresh_resource(func, **filterkw)
