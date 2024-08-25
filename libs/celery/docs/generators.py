import typing as t

from drf_yasg.generators import OpenAPISchemaGenerator as _OpenAPISchemaGenerator


class OpenAPISchemaGenerator(_OpenAPISchemaGenerator):  # type: ignore[misc]
    def determine_path_prefix(self, paths: t.Any) -> str:
        return '/'
