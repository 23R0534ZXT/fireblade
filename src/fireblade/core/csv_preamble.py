"""Recognize documented tool metadata only before a matching CSV header."""
import csv

HEADERS = {
    'pescan - ': 'compiled,time-UTC,created,time-UTC,access,time-UTC,modify,time-UTC,size,type,cpu,linker,code size,init data,uninit data,image ver,subsys ver,min OS,entry rva,entryfaddr,imagebase,cert,chksum,md5,company,file,rating,notes,PEiD,symbol file',
    'wisp - ': 'mft entry,mft seq,parent mft,seqnum,type,file mdate,time-UTC,file adate,time-UTC,mftdate,time-UTC,file cdate,time-UTC,dir/file,size resv,size used,flags,name,slack comment',
}


def preamble_lines(stream):
    first = stream.readline(65536)
    if not first.endswith(('\n','\r')):
        return 0
    if first.startswith('#TYPE '):
        return 1
    for prefix, header in HEADERS.items():
        if first.startswith(prefix):
            lines = [stream.readline(65536) for _ in range(4)]
            if any(not line.endswith(('\n','\r')) for line in lines[:3]):
                return 0
            try:
                actual = next(csv.reader([lines[-1]], strict=True))
            except (csv.Error, StopIteration):
                return 0
            if [x.strip().casefold() for x in actual] == header.casefold().split(','):
                return 4
    return 0
