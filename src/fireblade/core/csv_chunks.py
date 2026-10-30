"""Bound CSV ingestion queries without splitting quoted or multiline records."""
import csv
from pathlib import Path
import tempfile


CHUNK_BYTES = 16 * 1024 * 1024


class _Utf8Writer:
    def __init__(self, output):
        self.output, self.bytes_written = output, 0

    def write(self, value):
        data = value.encode('utf-8')
        self.output.write(data)
        self.bytes_written += len(data)
        return len(value)


def csv_chunks(source, headers, delimiter, directory, byte_limit, check_cancelled):
    # Native read_csv -> CREATE TABLE can retain a query's string arena even
    # after table pages spill. A fresh native query for each bounded file frees
    # that arena; all queries still belong to the caller's single transaction.
    csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))
    with tempfile.TemporaryDirectory(prefix='.fireblade-import-', dir=directory) as temporary:
        chunk = Path(temporary) / 'records.csv'
        with Path(source).open(encoding='utf-8-sig', newline='') as incoming:
            reader = csv.reader(incoming, delimiter=delimiter, quotechar='"',
                                doublequote=True, strict=True)
            next((record for record in reader if record), None)  # Native-normalized headers supplied separately.
            done = False
            while not done:
                check_cancelled()
                count = 0
                with chunk.open('wb') as outgoing:
                    sink = _Utf8Writer(outgoing)
                    writer = csv.writer(sink)
                    writer.writerow(headers)
                    for record in reader:
                        if not record:
                            continue
                        if len(record) != len(headers):
                            raise ValueError(f'CSV incohérent à la ligne physique {reader.line_num} : '
                                             f'{len(record)} colonnes au lieu de {len(headers)}')
                        writer.writerow(record)
                        count += 1
                        if count % 256 == 0:
                            check_cancelled()
                        # Byte counting avoids flushing/seeking for every row,
                        # and a wide row cannot overshoot by another 255 rows.
                        if sink.bytes_written >= byte_limit:
                            break
                    else:
                        done = True
                if count:
                    yield chunk, count
