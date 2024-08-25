from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.openstacks.models.base import OpenstacksWithPerm


class ImagesModel(OpenstacksWithPerm):
    name = models.CharField(_('鏡像名稱'), max_length=50)
    status = models.CharField(_('狀態'), blank=True, max_length=50)
    visibility = models.CharField(_('可見度'), blank=True, max_length=50)
    container_format = models.CharField(_('容器格式'), blank=True, max_length=255)
    disk_format = models.CharField(_('硬碟格式'), blank=True, max_length=255)
    os_distro = models.CharField(_('操作系統'), blank=True, max_length=255)
    enable = models.BooleanField(_('啓用'), default=True)
    is_win = models.BooleanField(_('是否為Windows'), default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('鏡像')
