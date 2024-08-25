from django.db import models
from django.utils.translation import gettext_lazy as _
from safedelete.models import SafeDeleteAllManager

from apps.cmdb.models.app import Module, ProductLine
from apps.cmdb.models.idc import IDC
from libs.base.models import SafeBaseModel
from libs.external.openstack import OpenStack


class CustomAllManager(SafeDeleteAllManager):
    def bulk_create_or_update(self, bulks: list):
        _new, _old = [b for b in bulks if not b.create_time], [b for b in bulks if b.create_time]
        self.bulk_create(_new, batch_size=200)
        self.bulk_update(
            _old,
            fields=[f.name for f in self.model._meta.fields if not f.primary_key],
            batch_size=200,
        )


class BaseModel(SafeBaseModel):
    all_objects = CustomAllManager()
    id = models.CharField('OpenstackID', max_length=255, primary_key=True)

    class Meta:
        abstract = True


class IDCBase(BaseModel):
    idc = models.ForeignKey(
        IDC, models.SET_NULL, null=True, limit_choices_to={'type': 3}, verbose_name=_('虛擬機房')
    )

    class Meta:
        abstract = True


class RegionModel(IDCBase):
    def _default():
        return {}

    name = models.CharField(_('區域名稱'), max_length=50)
    details = models.JSONField(default=_default)

    def __str__(self):
        return self.name

    def client(self, project_id: str = ''):
        return OpenStack.from_idc(self.idc, project_id)

    class Meta:
        verbose_name = _('區域')


class ProjectsModel(IDCBase):
    name = models.CharField(_('項目名稱'), max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('項目')


class OpenstacksRegionBase(BaseModel):
    region = models.ForeignKey(RegionModel, models.CASCADE, verbose_name=_('所屬區域'))

    class Meta:
        abstract = True


class OpenstacksProjectBase(OpenstacksRegionBase):
    project = models.ForeignKey(ProjectsModel, models.CASCADE, verbose_name=_('所屬項目'))

    class Meta:
        abstract = True


class OpenstacksWithPerm(OpenstacksRegionBase):
    product_perm = models.ManyToManyField(ProductLine, default=None)
    module_perm = models.ManyToManyField(Module, default=None)

    class Meta:
        abstract = True
