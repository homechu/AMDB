from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.cmdb.models.app import App
from apps.openstacks.models.base import OpenstacksProjectBase, OpenstacksRegionBase
from apps.openstacks.models.flavors import FlavorsModel
from apps.openstacks.models.images import ImagesModel


class ZonesModel(OpenstacksRegionBase):
    STATUS_CHOICES = [('enabled', '啓用'), ('disabled', '禁用')]
    STATE_CHOICES = [('up', '運行中'), ('down', '關閉')]

    def _default():
        return []

    name = models.CharField(_('可用區名稱'), max_length=50, default='')
    total_ram = models.PositiveIntegerField(_('總共內存'), default=0)
    available_ram = models.PositiveIntegerField(_('可用內存'), default=0)
    available_disk = models.PositiveIntegerField(_('可用容量'), default=0)
    virtual_num = models.PositiveIntegerField(_('已創建虛擬機數量'), default=0)
    status = models.CharField(_('可用狀態'), choices=STATUS_CHOICES, max_length=50, default='')
    state = models.CharField(_('運行狀態'), choices=STATE_CHOICES, max_length=50, default='')
    hypervisors = models.JSONField(_('實體主機訊息'), default=_default)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = _('可用區')
        unique_together = ('region', 'name')


class ServerGroupsModel(OpenstacksRegionBase):
    name = models.CharField(_('名稱'), max_length=50)

    class Meta:
        verbose_name = _('主機羣組')


class ServersModel(OpenstacksProjectBase):
    STATUS_CHOICES = [
        ('ACTIVE', '運行中'),
        ('SHUTOFF', '關機'),
        ('BUILD', '構建中'),
        ('REBUILD', '重建中'),
        ('REBOOT', '重啓中'),
        ('ERROR', '錯誤'),
        ('DELETE', '刪除'),
    ]

    def _default():
        return {}

    name = models.CharField(_('主機名'), max_length=50)
    key_name = models.CharField(_('Keypair Name'), max_length=20, null=True)
    app = models.ForeignKey(App, models.SET_NULL, null=True, default=None, verbose_name=_('業務'))
    metadata = models.JSONField(_('元數據'), default=_default, blank=True)
    status = models.CharField(_('狀態'), choices=STATUS_CHOICES, max_length=20, null=True)
    ip_address = models.GenericIPAddressField(_('IP地址'), null=True, default=None)
    image = models.ForeignKey(ImagesModel, models.SET_NULL, null=True, verbose_name=_('鏡像'))
    flavor = models.ForeignKey(FlavorsModel, models.SET_NULL, null=True, verbose_name=_('規格'))
    zone = models.ForeignKey(ZonesModel, models.SET_NULL, null=True, verbose_name=_('可用區'))
    hypervisor_hostname = models.CharField(_('硬件名稱'), max_length=128, blank=True, default='')

    class Meta:
        verbose_name = _('虛擬機')
