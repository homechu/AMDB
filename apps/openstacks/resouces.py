from import_export.fields import Field

from apps.cmdb.models.app import App
from apps.openstacks.models import (
    AddressThrough,
    FlavorsModel,
    ImagesModel,
    PortsModel,
    ProjectsModel,
    RegionModel,
    RulesModel,
    SecurityGroupsModel,
    ServersModel,
    VolumesModel,
    ZonesModel,
)
from libs.resources.resource import BaseResource
from libs.resources.widget import (
    SABooleanWidget,
    SAForeignKeyWidget,
    SAManyToManyWidget,
)


class Base(BaseResource):
    region = Field(attribute='region', widget=SAForeignKeyWidget(model=RegionModel, field='name'))

    class Meta(BaseResource.Meta):
        exclude = (*BaseResource.Meta.exclude, 'create_time', 'create_by')


class ProjectBase(Base):
    project = Field(
        attribute='project', widget=SAForeignKeyWidget(model=ProjectsModel, field='name')
    )


class EnableBase(Base):
    enable = Field(attribute='enable', widget=SABooleanWidget())


class ServersResource(ProjectBase):
    COLUMN_MAP = {'attach_vols': '已綁定卷', 'security_groups': '已連接安全組'}

    app = Field(attribute='app', widget=SAForeignKeyWidget(model=App, field='alias'))
    image = Field(attribute='image', widget=SAForeignKeyWidget(model=ImagesModel, field='name'))
    flavor = Field(attribute='flavor', widget=SAForeignKeyWidget(model=FlavorsModel, field='name'))
    zone = Field(attribute='zone', widget=SAForeignKeyWidget(model=ZonesModel, field='name'))
    attach_vols = Field(
        attribute='attach_vols', widget=SAManyToManyWidget(model=VolumesModel, field='name')
    )
    security_groups = Field(attribute='security_groups')

    def dehydrate_security_groups(self, obj):
        security_groups = [o.name for port in obj.ports.all() for o in port.security_groups.all()]
        return ','.join(security_groups)

    class Meta(Base.Meta):
        model = ServersModel
        export_order = (
            'region',
            'project',
            'name',
            'app',
            'ip_address',
            'status',
            'attach_vols',
            'security_groups',
            'image',
            'flavor',
            'zone',
            'key_name',
            'hypervisor_hostname',
            'metadata',
        )


class SecurityGroupsResource(ProjectBase):
    is_default = Field(attribute='is_default', widget=SABooleanWidget())

    class Meta(Base.Meta):
        model = SecurityGroupsModel
        export_order = (
            'region',
            'project',
            'name',
            'is_default',
            'description',
        )


class RulesResource(Base):
    security_group = Field(
        attribute='security_group',
        widget=SAForeignKeyWidget(model=SecurityGroupsModel, field='name'),
    )

    def dehydrate_remote_group_id(self, obj):
        try:
            value = SecurityGroupsModel.objects.get(id=obj.remote_group_id)
        except SecurityGroupsModel.DoesNotExist:
            return obj.remote_group_id

        return value.name

    class Meta(Base.Meta):
        model = RulesModel
        export_order = (
            'region',
            'security_group',
            'ethertype',
            'protocol',
            'direction',
            'remote_ip_prefix',
            'remote_group_id',
            'port_range_min',
            'port_range_max',
            'description',
        )


class VolumesResource(ProjectBase):
    attachments = Field(
        attribute='attachments', widget=SAManyToManyWidget(model=ServersModel, field='name')
    )

    class Meta:
        model = VolumesModel
        exclude = (*Base.Meta.exclude, 'volume_image_metadata')
        export_order = (
            'region',
            'project',
            'name',
            'volume_type',
            'size',
            'status',
            'attachments',
            'description',
        )


class FlavorsResource(EnableBase):
    class Meta:
        model = FlavorsModel
        exclude = (*Base.Meta.exclude, 'product_perm', 'module_perm')
        export_order = (
            'region',
            'name',
            'vcpus',
            'ram',
            'disk',
        )


class ImagesResource(EnableBase):
    is_win = Field(attribute='is_win', widget=SABooleanWidget())

    class Meta(Base.Meta):
        model = ImagesModel
        export_order = (
            'region',
            'name',
            'status',
            'visibility',
            'container_format',
            'disk_format',
            'os_distro',
        )


class PortsResource(ProjectBase):
    COLUMN_MAP = {'device': '已連接服務器', 'security_groups': '已連接安全組'}

    fixed_ips = Field(
        attribute='address', widget=SAManyToManyWidget(model=AddressThrough, field='ip_address')
    )
    device = Field(attribute='device__name')

    class Meta(Base.Meta):
        model = PortsModel
        export_order = (
            'region',
            'project',
            'fixed_ips',
            'device',
            'security_groups',
            'status',
            'description',
        )
