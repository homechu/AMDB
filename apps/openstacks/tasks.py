import typing as t

from datetime import datetime, timedelta

from celery import chain
from django.core.cache import cache
from django.db.models.fields.reverse_related import ManyToOneRel
from safedelete.config import HARD_DELETE

from apps.cmdb.models.idc import IDC, IDCType
from apps.openstacks.models.base import RegionModel
from apps.openstacks.services import (
    base,
    flavors,
    images,
    networks,
    security_groups,
    servers,
    volumes,
)
from libs.external.openstack import OpenStack
from main.celery import app
from main.settings import logger


@app.task  # type:ignore[misc]
def refresh_projects(idc: t.Union[IDC, int]) -> None:
    return base.refresh_projects(idc)


@app.task  # type:ignore[misc]
def refresh_regions(idc: t.Union[IDC, int]) -> None:
    return base.refresh_regions(idc)


@app.task  # type:ignore[misc]
def refresh_flavors(region: t.Union[RegionModel, str]) -> None:
    return flavors.refresh_flavors(region)


@app.task  # type:ignore[misc]
def refresh_images(region: t.Union[RegionModel, str]) -> None:
    return images.refresh_images(region)


@app.task  # type:ignore[misc]
def refresh_subnets(region: t.Union[RegionModel, str]) -> None:
    return networks.refresh_subnets(region)


@app.task  # type:ignore[misc]
def refresh_ports(region: t.Union[RegionModel, str]) -> None:
    return networks.refresh_ports(region)


@app.task  # type:ignore[misc]
def refresh_zones(region: t.Union[RegionModel, str]) -> None:
    return servers.refresh_zones(region)


@app.task  # type:ignore[misc]
def refresh_servergroups(region: t.Union[RegionModel, str]) -> None:
    return servers.refresh_servergroups(region)


@app.task  # type:ignore[misc]
def refresh_servers(region: t.Union[RegionModel, str]) -> None:
    return servers.refresh_servers(region)


@app.task  # type:ignore[misc]
def refresh_security_groups(region: t.Union[RegionModel, str]) -> None:
    return security_groups.refresh_security_groups(region)


@app.task  # type:ignore[misc]
def refresh_rules(region: t.Union[RegionModel, str]) -> None:
    return security_groups.refresh_rules(region)


@app.task  # type:ignore[misc]
def refresh_volumes(region: t.Union[RegionModel, str]) -> None:
    return volumes.refresh_volumes(region)


@app.task  # type:ignore[misc]
def refresh_volumeattach(region: t.Union[RegionModel, str]) -> None:
    return volumes.refresh_volumeattach(region)


@app.task  # type:ignore[misc]
def refresh_volumetype(region: t.Union[RegionModel, str]) -> None:
    return volumes.refresh_volumetype(region)


@app.task  # type:ignore[misc]
def sync_base_resource(idc) -> None:
    flow = refresh_regions.si(idc) | refresh_projects.si(idc)
    flow.apply_async()


@app.task  # type:ignore[misc]
def sync_resource() -> None:
    """刷新所有機房資源.

    Notice:
        任務有順序，會影響關聯.

    """
    for idc in IDC.active_objects.filter(type=IDCType.OPENSTACK, status=1):
        flow = chain()
        sync_base_resource.run(idc.id)
        idc.refresh_from_db()
        for region in idc.regionmodel_set.all():
            region = region.id
            flow |= refresh_flavors.si(region)
            flow |= refresh_images.si(region)
            flow |= refresh_security_groups.si(region)
            flow |= refresh_rules.si(region)
            flow |= refresh_zones.si(region)
            flow |= refresh_servergroups.si(region)
            flow |= refresh_subnets.si(region)
            flow |= refresh_volumetype.si(region)
            flow |= refresh_servers.si(region)
            flow |= refresh_volumes.si(region)
            flow |= refresh_ports.si(region)

        flow.apply_async()


@app.task  # type:ignore[misc]
def clean_openstack(expiration_days: datetime = datetime.now() - timedelta(days=30 * 6)):
    model = RegionModel
    model._safedelete_policy = HARD_DELETE
    model.deleted_objects.filter(is_deleted__lte=expiration_days).delete()
    for field in RegionModel._meta.get_fields():
        if isinstance(field, ManyToOneRel):
            model = field.related_model
            model._safedelete_policy = HARD_DELETE
            for obj in model.deleted_objects.filter(is_deleted__lte=expiration_days):
                logger.info(f'刪除Openstack過期訊息: {obj}')
                obj.delete()


@app.task  # type:ignore[misc]
def checkinfo():
    for idc in IDC.active_objects.filter(type=IDCType.OPENSTACK, status=1):
        data = {'status': 'running', 'detail': {}}
        try:
            OpenStack.from_idc(idc)
        except Exception as e:
            data['status'] = 'error'
            data['detail']['message'] = f'Openstack API 連接失敗: {e}'

        cache.set(f'vc:checkinfo:{idc.vcenterinfo.id}', data, 300)


@app.task  # type:ignore[misc]
def sync_resource_flow() -> None:
    flow = sync_resource.si() | clean_openstack.si() | checkinfo.si()
    flow.apply_async()


if __name__ == '__main__':
    idc = IDC.active_objects.get(name='SA_DEV')
    api = OpenStack.from_idc(idc)

    refresh_regions(idc)
    refresh_projects(idc)

    idc.refresh_from_db()
    region: RegionModel = idc.regionmodel_set.last()
    api = region.client()

    refresh_flavors(region)
    refresh_images(region)

    refresh_security_groups(region)
    refresh_rules(region)

    refresh_zones(region)
    refresh_servergroups(region)

    refresh_subnets(region)

    refresh_volumetype(region)
    refresh_volumes(region)

    refresh_servers(region)
    refresh_ports(region)
