from django.db import models
from django.utils.translation import gettext_lazy as _
from selfpackage.django.models.fields import (
    AutoUUIDField,
    CreatedTimestampField,
    UpdatedTimestampField,
)
from safedelete import SOFT_DELETE_CASCADE, models as safedelete_models


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class BaseModel(models.Model):
    """
    Model 基類

    CHOICES = {
        'status': [(1, '使用'), (2, '廢棄')]
    }
    FOREIGN = {
        'user': (User, ['username'])
    }
    MANY2MANY = {
        'group': (Group, ['name'])
    }
    説明：
        User: User Model
        username: 序列化時預計顯示值，
    choices 顯示內容:
        單一值顯示，{'id': 1, 'name': username}
        多值則依list字段顯示
    """

    objects = ActiveManager()
    all_objects = models.Manager()

    CHOICES = {}
    FOREIGN = {}
    MANY2MANY = {}

    create_time = models.DateTimeField(verbose_name='創建時間', auto_now_add=True, null=True)
    update_time = models.DateTimeField(verbose_name='更新時間', auto_now=True, null=True)
    create_by = models.CharField(max_length=64, default='', blank=True, verbose_name='創建人')
    update_by = models.CharField(max_length=64, default='', blank=True, verbose_name='修改人')
    is_deleted = models.BooleanField(default=False, blank=True, verbose_name='已刪除')

    class Meta:
        abstract = True

    @classmethod
    def get_source(cls, key):
        if key in cls.CHOICES:
            return 'get_{}_display'.format(key)
        if key in cls.FOREIGN:
            source = cls.FOREIGN[key][1]
            if isinstance(source, list) or isinstance(source, tuple):
                return '{}.{}'.format(key, source[0])
            else:
                return '{}.{}'.format(key, source)
        return None


class SafeBaseModel(safedelete_models.SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    identifier = AutoUUIDField(unique=True, verbose_name=_('識別碼'))
    create_time = CreatedTimestampField(db_index=True, verbose_name='創建時間')
    update_time = UpdatedTimestampField(db_index=True, verbose_name='更新時間')
    create_by = models.CharField(max_length=255, null=True, verbose_name=_('創建者'))
    update_by = models.CharField(max_length=255, null=True, verbose_name=_('編輯者'))

    class Meta:
        abstract = True
