import typing as t

from django.utils.encoding import smart_str
from rest_framework import renderers


class PlainTextRenderer(renderers.BaseRenderer):
    media_type = 'text/plain'
    format = 'txt'

    def render(
        self,
        data: t.Any,
        accepted_media_type: t.Optional[str] = None,
        renderer_context: t.Optional[t.Mapping[str, t.Any]] = None,
    ) -> t.Any:
        kwargs = {}
        if self.charset:
            kwargs.update({'encoding': self.charset})

        return smart_str(data, **kwargs)


class JSONIndentRenderer(renderers.JSONRenderer):
    json_indent = 4

    def render(
        self,
        data: t.Any,
        accepted_media_type: t.Optional[str] = None,
        renderer_context: t.Optional[t.Mapping[str, t.Any]] = None,
    ) -> t.Any:
        renderer_context = renderer_context or {}
        renderer_context.setdefault('indent', self.json_indent)  # type: ignore[attr-defined]  # noqa: E501
        return super().render(data, accepted_media_type, renderer_context)
