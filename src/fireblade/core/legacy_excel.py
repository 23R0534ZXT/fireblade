"""Legacy BIFF XLS reading, no Excel automation and no macro execution."""
import csv
from contextlib import contextmanager
from pathlib import Path
import tempfile

import xlrd


def sheet_names(source):
    book = xlrd.open_workbook(str(source), on_demand=True)
    try:
        return book.sheet_names()
    finally:
        book.release_resources()


@contextmanager
def csv_from_sheet(source, sheet, directory, check_cancelled):
    book, temporary = None, None
    try:
        book = xlrd.open_workbook(str(source), on_demand=True)
        page = book.sheet_by_name(sheet)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', dir=directory, suffix='.csv', delete=False) as out:
            temporary = Path(out.name)
            writer = csv.writer(out)
            for number in range(page.nrows):
                if number % 128 == 0:
                    check_cancelled()
                values = []
                for cell in page.row(number):
                    value = cell.value
                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        value = ''
                    elif cell.ctype == xlrd.XL_CELL_DATE:
                        value = xlrd.xldate.xldate_as_datetime(value, book.datemode).isoformat(' ')
                    elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                        value = 'TRUE' if value else 'FALSE'
                    elif cell.ctype == xlrd.XL_CELL_NUMBER and value.is_integer():
                        value = str(int(value))
                    elif cell.ctype == xlrd.XL_CELL_ERROR:
                        value = xlrd.error_text_from_code.get(value, '#ERROR')
                    values.append(value)
                if number == 0 and (not values or not any(values)):
                    raise ValueError("La première ligne doit contenir des noms de colonnes")
                writer.writerow(values)
        yield temporary
    finally:
        if book:
            book.release_resources()
        if temporary:
            temporary.unlink(missing_ok=True)
