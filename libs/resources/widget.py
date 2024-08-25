from django.db.models import Choices
from import_export.widgets import (
    BooleanWidget,
    ForeignKeyWidget,
    ManyToManyWidget,
    Widget,
)
from rest_framework.serializers import ValidationError


class RowValidation(ValidationError):
    def __init__(self, detail: str = '', row_number=None) -> None:
        super().__init__(f'第{row_number}筆導入錯誤，' + detail if row_number else detail, None)


class ValueRequired(RowValidation):
    def __init__(self, detail: str = '', row_number=None) -> None:
        super().__init__(f'{detail}為必填項目, 不可為空', row_number)


class SAWidget(Widget):
    def clean(self, value, row=None, **kwargs):
        if isinstance(value, str):
            value = value.strip()
        return value


class SAManyToManyWidget(ManyToManyWidget):
    pass


class SABooleanWidget(BooleanWidget):
    TRUE_VALUES = ['是', '1', 1, True, 'true', 'TRUE', 'True']
    FALSE_VALUES = ['否', '0', 0, False, 'false', 'FALSE', 'False']


class SAForeignKeyWidget(ForeignKeyWidget, SAWidget):
    def __init__(self, **kwargs):
        self.extend_fields: dict = kwargs.pop('extend_fields', None)
        super().__init__(**kwargs)

    def clean(self, value, row=None, **kwargs):
        val = SAWidget().clean(value)
        if val:
            kw = {self.field: val}
            if self.extend_fields:
                kw.update({k: row.get(v) for k, v in self.extend_fields.items()})
            try:
                obj = self.get_queryset(value, row, **kwargs).get(**kw)
            except self.model.DoesNotExist:
                raise RowValidation(f'{val} 對象不存在', kwargs.get('row_number'))

            return obj


class SAChoicesWidget(SAWidget):
    def __init__(self, choices: Choices) -> None:
        self.choices = choices.choices

    def clean(self, value, row=None, **kwargs):
        value = super().clean(value, row=None, **kwargs)
        return next((k for k, v in self.choices if value == v), None)

    def render(self, value, obj=None):
        return dict(self.choices).get(value)


class TupleChoicesWidget(SAWidget):
    def __init__(self, choices: tuple) -> None:
        self.choices = choices

    def clean(self, value, row=None, **kwargs):
        value = super().clean(value, row=None, **kwargs)
        return next((k for k, v in self.choices if value == v), None)

    def render(self, value, obj=None):
        return dict(self.choices).get(value)
