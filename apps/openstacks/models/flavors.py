from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.openstacks.models.base import OpenstacksWithPerm


class FlavorsModel(OpenstacksWithPerm):
    name = models.CharField(_('規格名稱'), max_length=255)
    vcpus = models.PositiveSmallIntegerField(_('核心數'))
    ram = models.PositiveIntegerField(_('內存大小(MiB)'))
    disk = models.PositiveIntegerField(_('磁盤大小(GiB)'))
    enable = models.BooleanField(_('啓用'), default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('規格')
