from django.db import models
from django.utils.translation import gettext_lazy as _
from safedelete import HARD_DELETE

from apps.openstacks.models.base import OpenstacksProjectBase, OpenstacksRegionBase
from apps.openstacks.models.servers import ServersModel


class VolumeTypeModel(OpenstacksRegionBase):
    name = models.CharField(_('類型名稱'), max_length=50)
    description = models.CharField(_('類型描述'), max_length=1024)
    is_public = models.BooleanField(_('公共類型'), default=False)

    class Meta:
        verbose_name = _('卷類型')


class VolumesModel(OpenstacksProjectBase):
    STATUS_CHOICES = [
        ('available', '可用'),
        ('in-use', '使用中'),
        ('deleting', '刪除中'),
    ]

    def _default():
        return {}

    name = models.CharField(_('名稱'), default='', blank=True, max_length=50)
    size = models.PositiveIntegerField(_('磁盤大小(GiB)'))
    volume_type = models.CharField(_('類型'), max_length=255)
    status = models.CharField(_('狀態'), choices=STATUS_CHOICES, max_length=20)
    attachments = models.ManyToManyField(
        ServersModel,
        related_name='attach_vols',
        through='VolumesAttachments',
        verbose_name=_('已綁定服務器'),
    )
    description = models.CharField(_('描述'), default='', blank=True, max_length=255)

    # 創建的來源資訊
    volume_image_metadata = models.JSONField(_('元數據'), default=_default, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('卷')


class VolumesAttachments(OpenstacksRegionBase):
    _safedelete_policy = HARD_DELETE

    server = models.ForeignKey(ServersModel, models.SET_NULL, null=True, related_name='attach')
    volume = models.ForeignKey(VolumesModel, models.SET_NULL, null=True, related_name='attach')
    attached_at = models.DateTimeField(_('綁定時間'), null=True)
    device = models.CharField(_('檔案系統'), default='', blank=True, max_length=255)

    def __str__(self) -> str:
        return f'{self.server} - {self.volume}'

    class Meta:
        verbose_name = _('綁定卷')
