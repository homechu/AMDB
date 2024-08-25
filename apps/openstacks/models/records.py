from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.openstacks.models.base import RegionModel
from libs.base.models import SafeBaseModel


class RecordsModel(SafeBaseModel):
    ACTION_CHOICES = [('CREATE', '創建'), ('UPDATE', '更新'), ('DELETE', '刪除')]

    def _default():
        return {}

    region = models.ForeignKey(RegionModel, models.CASCADE, verbose_name=_('所屬區域'))
    action_type = models.CharField(_('操作'), max_length=20, choices=ACTION_CHOICES)
    resource = models.CharField(_('資源名稱'), db_index=True, max_length=255)
    resource_id = models.CharField(_('資源ID'), db_index=True, max_length=255, default='')
    details = models.JSONField(_('詳情'), default=_default)
    status = models.CharField(_('狀態'), max_length=20, default='SUCCESS')

    class Meta:
        verbose_name = _('紀錄')
        ordering = ['-create_time']
