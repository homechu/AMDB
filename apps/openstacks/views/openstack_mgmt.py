from apps.cmdb.models.idc import IDC, IDCType
from apps.cmdb.views.idc_api import IdcRoomInfoViewSet


class OpenstackMgmtViewSet(IdcRoomInfoViewSet):
    queryset = (
        IDC.active_objects.filter(type=IDCType.OPENSTACK)
        .select_related('physical_region', 'vcenterinfo')
        .prefetch_related('saltmaster_set', 'isp', 'product')
        .all()
    )
    swagger_tags = ['Openstack管理 - 機房(資源池)管理']
    swagger_generate_tag = 'openstackmgmt'
