import typing as t

from datetime import datetime
from typing import Any

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from rest_framework import serializers
from rest_framework.utils import model_meta
from selfpackage.django import contexts


class BatchParams(serializers.Serializer):
    id = serializers.ListField(child=serializers.IntegerField())


class BatchUpdateParams(BatchParams):
    data = serializers.JSONField()


class BaseTimeSerializer(serializers.ModelSerializer):
    """Serializer 基類"""

    update_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', required=False)
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', required=False)


class BaseSerializer(BaseTimeSerializer):
    """Serializer 基類"""

    is_deleted = serializers.BooleanField(required=False)


class ExportChoicesSerializer(serializers.Serializer[t.Any]):
    id = serializers.CharField(help_text='導出ID')
    name = serializers.CharField(help_text='導出字段')


class ChoiceFiled(serializers.CharField):
    """
    針對 Choice 類型處理，讀取序列化，寫入原值
    """

    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        return super().to_representation(value)

    def get_attribute(self, instance):
        field_name = self.field_name
        choices = dict(instance.CHOICES[field_name])
        value = getattr(instance, field_name)
        return choices.get(value, value)


class BooleanField(serializers.BooleanField):
    """
    針對 Boolean 類型處理，轉為中文
    """

    def to_internal_value(self, data):
        try:
            if data in self.TRUE_VALUES:
                return '是'
            elif data in self.FALSE_VALUES:
                return '否'
            elif data in self.NULL_VALUES and self.allow_null:
                return None
        except TypeError:  # Input is an unhashable type
            pass
        self.fail('invalid', input=data)

    def to_representation(self, value):
        if value in self.TRUE_VALUES:
            return '是'
        elif value in self.FALSE_VALUES:
            return '否'
        if value in self.NULL_VALUES and self.allow_null:
            return None
        return bool(value)


class ChoicesField(serializers.ListField):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        kwargs['child'] = serializers.JSONField()

        # 動態配置 Meta Class 避免欄位間互相影響
        class Meta:
            swagger_schema_fields = {
                'type': openapi.TYPE_ARRAY,
                'items': {
                    'type': openapi.TYPE_OBJECT,
                    'properties': dict(
                        {
                            'id': {'type': kwargs.pop('id_type', openapi.TYPE_STRING)},
                            'name': {'type': openapi.TYPE_STRING},
                        },
                        **kwargs.pop('extra_properties', {}),
                    ),
                },
            }

        setattr(self, 'Meta', Meta)
        super().__init__(*args, **kwargs)


class CurrentUserDefault(serializers.CurrentUserDefault):
    def __call__(self, serializer_field):
        context = serializer_field.context
        return (
            context['request'].user.username if 'request' in context else context.get('username')
        )


class SABaseCreateSerializer(serializers.ModelSerializer):
    create_by = serializers.HiddenField(
        default=serializers.CreateOnlyDefault(CurrentUserDefault()),
        help_text=_('創建者'),
    )
    update_by = serializers.HiddenField(
        default=CurrentUserDefault(),
        help_text=_('更新者'),
    )


class SABaseSerializer(serializers.ModelSerializer):
    create_by = serializers.CharField(required=False, read_only=True, help_text=_('創建者'))
    update_by = serializers.CharField(required=False, read_only=True, help_text=_('更新者'))
    update_time = serializers.DateTimeField(
        format='%Y-%m-%d %H:%M:%S', required=False, read_only=True, help_text=_('更新時間')
    )
    create_time = serializers.DateTimeField(
        format='%Y-%m-%d %H:%M:%S', required=False, read_only=True, help_text=_('創建時間')
    )

    class Meta:
        exclude = ('is_deleted', 'deleted_by_cascade', 'identifier')

    def create(self, validated_data: Any) -> Any:
        request = contexts.request.get()
        if request is not None:
            validated_data['create_by'] = validated_data['update_by'] = request.user.username

        return super().create(validated_data)

    def update(self, instance: Any, validated_data: Any) -> Any:
        request = contexts.request.get()
        if request is not None:
            validated_data['update_by'] = request.user.username

        return super().update(instance, validated_data)


class BatchUpdateSerializer(serializers.ListSerializer):
    def update(self, instance: QuerySet, validated_data: t.List[t.Dict[str, t.Any]]) -> t.Any:
        allow_ids = set(
            instance.filter(id__in=[d['instance'].id for d in validated_data]).values_list(
                'id', flat=True
            )
        )
        objs = []
        writable_fields = ['update_time', 'update_by']
        for datum in validated_data:
            obj = datum.pop('instance')
            info = model_meta.get_field_info(obj)
            if obj.id not in allow_ids:
                continue

            m2m_fields = []
            for attr, value in datum.items():
                if attr in info.relations and info.relations[attr].to_many:
                    m2m_fields.append((attr, value))
                else:
                    writable_fields.append(attr)
                    setattr(obj, attr, value)

            request = contexts.request.get()
            obj.update_time = datetime.now()
            obj.update_by = request.user.username if request is not None else 'system'
            for attr, value in m2m_fields:
                field = getattr(obj, attr)
                field.set(value)

            objs.append(obj)

        instance.model.objects.bulk_update(objs, set(writable_fields))
        return objs
