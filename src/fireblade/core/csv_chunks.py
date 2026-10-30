"""Bound CSV ingestion queries without splitting quoted or multiline records."""
import csv
from pathlib import Path
import tempfile


CHUNK_BYTES = 16 * 1024 * 1024


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
                with chunk.open('w', encoding='utf-8', newline='') as outgoing:
                    writer = csv.writer(outgoing)
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
                            if outgoing.tell() >= byte_limit:
                                break
                    else:
                        done = True
                if count:
                    yield chunk, count
