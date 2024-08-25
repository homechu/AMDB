from django.db import models
from django.utils.translation import gettext_lazy as _
from safedelete import HARD_DELETE

from apps.openstacks.models.base import OpenstacksProjectBase, OpenstacksRegionBase
from apps.openstacks.models.security_groups import SecurityGroupsModel
from apps.openstacks.models.servers import ServersModel


class SubnetsModel(OpenstacksProjectBase):
    # 暫時不做關聯
    network_id = models.CharField(_('網路ID'), max_length=50)
    name = models.CharField(_('子網名稱'), max_length=100)
    cidr = models.CharField(_('子網網段'), max_length=20)
    total_ips = models.PositiveSmallIntegerField(_('IP總數'))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('子網')


class PortsModel(OpenstacksProjectBase):
    fixed_ips = models.ManyToManyField(
        SubnetsModel, through='AddressThrough', verbose_name=_('IP地址')
    )
    device = models.ForeignKey(
        ServersModel, models.SET_NULL, null=True, related_name='ports', verbose_name=_('服務器ID')
    )
    security_groups = models.ManyToManyField(SecurityGroupsModel, verbose_name=_('安全組'))
    status = models.CharField(_('狀態'), max_length=20)
    description = models.CharField(_('備註'), blank=True, max_length=255)

    class Meta:
        verbose_name = _('接口')


class AddressThrough(OpenstacksRegionBase):
    _safedelete_policy = HARD_DELETE

    subnet = models.ForeignKey(SubnetsModel, models.CASCADE, related_name='address')
    port = models.ForeignKey(PortsModel, models.CASCADE, related_name='address')
    ip_address = models.GenericIPAddressField(_('IP地址'), null=True, default=None)

    def __str__(self):
        return self.ip_address

    class Meta:
        verbose_name = _('地址')
