from io import BytesIO

from openpyxl import Workbook
from tablib.formats._xlsx import XLSXFormat


class ExportFormat(XLSXFormat):
    @classmethod
    def export_set(cls, dataset, freeze_panes=True, formatter=None, resource_class=None):
        """Returns XLSX representation of Dataset."""
        wb = Workbook()
        ws = wb.worksheets[0]
        ws.title = str(dataset.title) if dataset.title else "Tablib Dataset"
        cls.dset_sheet(dataset, ws, freeze_panes=freeze_panes)

        if formatter:
            formatter(ws, resource_class)

        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()
