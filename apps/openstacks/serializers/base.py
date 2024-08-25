from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from rest_framework import serializers

from libs.base.serializers import ChoicesField, SABaseSerializer


class RefreshSerializer(SABaseSerializer):
    id = serializers.CharField()
    region_id = serializers.CharField()

    class Meta:
        exclude = (*SABaseSerializer.Meta.exclude, 'region')


class ProjectRefreshSerializer(RefreshSerializer):
    project_id = serializers.CharField()

    class Meta:
        exclude = (*RefreshSerializer.Meta.exclude, 'project')


class BatchParamsSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        queryset = self.Meta.model.objects.all()
        self.fields['ids'].child = serializers.PrimaryKeyRelatedField(
            write_only=True, queryset=queryset, help_text='Object ID'
        )
        return super().__init__(*args, **kwargs)

    ids = serializers.ListField(child=serializers.CharField(), write_only=True, allow_empty=True)

    class Meta:
        fields = ['ids']


class RegionBaseChoices(serializers.Serializer):
    region = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('區域'))

    class Meta:
        fields = ['region']


class ProjectBaseChoices(RegionBaseChoices):
    project = ChoicesField(id_type=openapi.TYPE_STRING, help_text=_('項目'))

    class Meta:
        fields = ['project', *RegionBaseChoices.Meta.fields]
