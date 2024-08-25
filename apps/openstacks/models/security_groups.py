from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.openstacks.models.base import OpenstacksProjectBase, OpenstacksRegionBase


class SecurityGroupsModel(OpenstacksProjectBase):
    name = models.CharField(_('安全組名稱'), max_length=255)
    description = models.CharField(_('描述'), default='', blank=True, max_length=500)
    is_default = models.BooleanField(_('是否為默認安全組'), default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('安全組')


class RulesModel(OpenstacksRegionBase):
    DIRECTION_CHOICES = [('ingress', '入口'), ('egress', '出口')]
    PROTOCOL_CHOICES = [('TCP', 'TCP'), ('UDP', 'UDP'), ('ICMP', 'ICMP'), ('ANY', 'ANY')]
    ETHERTYPE_CHOICES = [('IPv4', 'IPv4'), ('IPv6', 'IPv6')]

    security_group = models.ForeignKey(
        SecurityGroupsModel, models.CASCADE, related_name='rules', verbose_name=_('所屬安全組')
    )
    remote_ip_prefix = models.GenericIPAddressField(_('IP段'), default=None, blank=True, null=True)
    # 暫時不做關聯
    remote_group_id = models.CharField(_('遠端組ID'), default='', blank=True, max_length=100)
    port_range_min = models.PositiveIntegerField(_('起始端口'), default=None, null=True)
    port_range_max = models.PositiveIntegerField(_('結束端口'), default=None, null=True)
    protocol = models.CharField(_('協議'), choices=PROTOCOL_CHOICES, max_length=20, default='ANY')
    direction = models.CharField(_('方向'), choices=DIRECTION_CHOICES, max_length=20)
    ethertype = models.CharField(_('類型'), choices=ETHERTYPE_CHOICES, default='IPv4', max_length=20)
    description = models.CharField(_('描述'), default='', blank=True, max_length=500)

    class Meta:
        verbose_name = _('安全規則')
