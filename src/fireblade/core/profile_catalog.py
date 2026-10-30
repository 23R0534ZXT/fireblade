"""CSV field names and type metadata (2026-10-30).

No upstream parser code. See docs/development/PLUGINS.md for provenance.
"""

CATALOG = [
  {
    "name": "Boot",
    "signature": [
      "EntryPoint",
      "Signature",
      "BytesPerSector",
      "SectorsPerCluster",
      "ClusterSize",
      "ReservedSectors",
      "TotalSectors",
      "MftClusterBlockNumber",
      "MftMirrClusterBlockNumber",
      "MftEntrySize",
      "IndexEntrySize",
      "VolumeSerialNumberRaw",
      "VolumeSerialNumber",
      "VolumeSerialNumber32",
      "VolumeSerialNumber32Reverse",
      "SectorSignature",
      "SourceFile"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "EntryPoint",
      "Signature",
      "BytesPerSector",
      "SectorsPerCluster",
      "ClusterSize",
      "ReservedSectors",
      "TotalSectors",
      "MftClusterBlockNumber",
      "MftMirrClusterBlockNumber",
      "MftEntrySize",
      "IndexEntrySize",
      "VolumeSerialNumberRaw"
    ]
  },
  {
    "name": "Sds",
    "signature": [
      "Hash",
      "Id",
      "Offset",
      "OwnerSid",
      "GroupSid",
      "Control",
      "SaclAceCount",
      "UniqueSaclAceTypes",
      "DaclAceCount",
      "UniqueDaclAceTypes",
      "FileOffset",
      "SourceFile"
    ],
    "timestamp": [],
    "booleans": [
      "FromMirror"
    ],
    "columns": [
      "Hash",
      "Id",
      "Offset",
      "OwnerSid",
      "GroupSid",
      "Control",
      "SaclAceCount",
      "UniqueSaclAceTypes",
      "DaclAceCount",
      "UniqueDaclAceTypes",
      "FileOffset",
      "SourceFile"
    ]
  },
  {
    "name": "Sds",
    "signature": [
      "Hash",
      "Id",
      "Offset",
      "OwnerSid",
      "GroupSid",
      "Control",
      "SaclAceCount",
      "UniqueSaclAceTypes",
      "DaclAceCount",
      "UniqueDaclAceTypes",
      "FileOffset",
      "SourceFile",
      "FromMirror"
    ],
    "timestamp": [],
    "booleans": [
      "FromMirror"
    ],
    "columns": [
      "Hash",
      "Id",
      "Offset",
      "OwnerSid",
      "GroupSid",
      "Control",
      "SaclAceCount",
      "UniqueSaclAceTypes",
      "DaclAceCount",
      "UniqueDaclAceTypes",
      "FileOffset",
      "SourceFile"
    ]
  },
  {
    "name": "J",
    "signature": [
      "Name",
      "Extension",
      "EntryNumber",
      "SequenceNumber",
      "ParentEntryNumber",
      "ParentSequenceNumber",
      "ParentPath",
      "UpdateSequenceNumber",
      "UpdateTimestamp",
      "UpdateReasons",
      "FileAttributes",
      "OffsetToData",
      "SourceFile"
    ],
    "timestamp": [
      "UpdateTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Name",
      "Extension",
      "EntryNumber",
      "SequenceNumber",
      "ParentEntryNumber",
      "ParentSequenceNumber",
      "ParentPath",
      "UpdateSequenceNumber",
      "UpdateTimestamp",
      "UpdateReasons",
      "FileAttributes",
      "OffsetToData"
    ]
  },
  {
    "name": "MFTSourceFileResident",
    "signature": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory",
      "hasads",
      "isads",
      "si<fn",
      "useczeros",
      "copied",
      "siflags",
      "nametype",
      "created0x10",
      "created0x30",
      "lastmodified0x10",
      "lastmodified0x30",
      "lastrecordchange0x10",
      "lastrecordchange0x30",
      "lastaccess0x10",
      "lastaccess0x30",
      "updatesequencenumber",
      "logfilesequencenumber",
      "securityid",
      "objectidfiledroid",
      "loggedutilstream",
      "zoneidcontents",
      "sourcefile",
      "residentdatabase64",
      "residentdatahex",
      "residentdataascii"
    ],
    "timestamp": [
      "Created0x10",
      "Created0x30",
      "LastModified0x10",
      "LastModified0x30",
      "LastRecordChange0x10",
      "LastRecordChange0x30",
      "LastAccess0x10",
      "LastAccess0x30"
    ],
    "booleans": [
      "InUse",
      "IsDirectory",
      "HasAds",
      "IsAds",
      "Timestomped",
      "uSecZeros",
      "Copied"
    ],
    "columns": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory"
    ]
  },
  {
    "name": "MFTSourceFileResident",
    "signature": [
      "EntryNumber",
      "SequenceNumber",
      "InUse",
      "ParentEntryNumber",
      "ParentSequenceNumber",
      "ParentPath",
      "FileName",
      "Extension",
      "FileSize",
      "ReferenceCount",
      "ReparseTarget",
      "IsDirectory",
      "HasAds",
      "IsAds",
      "SI<FN",
      "uSecZeros",
      "Copied",
      "SiFlags",
      "NameType",
      "Created0x10",
      "Created0x30",
      "LastModified0x10",
      "LastModified0x30",
      "LastRecordChange0x10",
      "LastRecordChange0x30",
      "LastAccess0x10",
      "LastAccess0x30",
      "UpdateSequenceNumber",
      "LogfileSequenceNumber",
      "SecurityId",
      "ObjectIdFileDroid",
      "LoggedUtilStream",
      "ZoneIdContents",
      "SourceFile",
      "ResidentDataBase64",
      "ResidentDataHex",
      "ResidentDataASCII",
      "ParseErrors"
    ],
    "timestamp": [
      "Created0x10",
      "Created0x30",
      "LastModified0x10",
      "LastModified0x30",
      "LastRecordChange0x10",
      "LastRecordChange0x30",
      "LastAccess0x10",
      "LastAccess0x30"
    ],
    "booleans": [
      "InUse",
      "IsDirectory",
      "HasAds",
      "IsAds",
      "Timestomped",
      "uSecZeros",
      "Copied"
    ],
    "columns": [
      "EntryNumber",
      "SequenceNumber",
      "InUse",
      "ParentEntryNumber",
      "ParentSequenceNumber",
      "ParentPath",
      "FileName",
      "Extension",
      "FileSize",
      "ReferenceCount",
      "ReparseTarget",
      "IsDirectory"
    ]
  },
  {
    "name": "MFTSourceFile",
    "signature": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory",
      "hasads",
      "isads",
      "si<fn",
      "useczeros",
      "copied",
      "siflags",
      "nametype",
      "created0x10",
      "created0x30",
      "lastmodified0x10",
      "lastmodified0x30",
      "lastrecordchange0x10",
      "lastrecordchange0x30",
      "lastaccess0x10",
      "lastaccess0x30",
      "updatesequencenumber",
      "logfilesequencenumber",
      "securityid",
      "objectidfiledroid",
      "loggedutilstream",
      "zoneidcontents",
      "sourcefile"
    ],
    "timestamp": [
      "Created0x10",
      "Created0x30",
      "LastModified0x10",
      "LastModified0x30",
      "LastRecordChange0x10",
      "LastRecordChange0x30",
      "LastAccess0x10",
      "LastAccess0x30"
    ],
    "booleans": [
      "InUse",
      "IsDirectory",
      "HasAds",
      "IsAds",
      "Timestomped",
      "uSecZeros",
      "Copied"
    ],
    "columns": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory"
    ]
  },
  {
    "name": "MFTSourceFile",
    "signature": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory",
      "hasads",
      "isads",
      "si<fn",
      "useczeros",
      "copied",
      "siflags",
      "nametype",
      "created0x10",
      "created0x30",
      "lastmodified0x10",
      "lastmodified0x30",
      "lastrecordchange0x10",
      "lastrecordchange0x30",
      "lastaccess0x10",
      "lastaccess0x30",
      "updatesequencenumber",
      "logfilesequencenumber",
      "securityid",
      "objectidfiledroid",
      "loggedutilstream",
      "zoneidcontents",
      "sourcefile",
      "parseerrors"
    ],
    "timestamp": [
      "Created0x10",
      "Created0x30",
      "LastModified0x10",
      "LastModified0x30",
      "LastRecordChange0x10",
      "LastRecordChange0x30",
      "LastAccess0x10",
      "LastAccess0x30"
    ],
    "booleans": [
      "InUse",
      "IsDirectory",
      "HasAds",
      "IsAds",
      "Timestomped",
      "uSecZeros",
      "Copied"
    ],
    "columns": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory"
    ]
  },
  {
    "name": "MFT",
    "signature": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory",
      "hasads",
      "isads",
      "si<fn",
      "useczeros",
      "copied",
      "siflags",
      "nametype",
      "created0x10",
      "created0x30",
      "lastmodified0x10",
      "lastmodified0x30",
      "lastrecordchange0x10",
      "lastrecordchange0x30",
      "lastaccess0x10",
      "lastaccess0x30",
      "updatesequencenumber",
      "logfilesequencenumber",
      "securityid",
      "objectidfiledroid",
      "loggedutilstream",
      "zoneidcontents"
    ],
    "timestamp": [
      "Created0x10",
      "Created0x30",
      "LastModified0x10",
      "LastModified0x30",
      "LastRecordChange0x10",
      "LastRecordChange0x30",
      "LastAccess0x10",
      "LastAccess0x30"
    ],
    "booleans": [
      "InUse",
      "IsDirectory",
      "HasAds",
      "IsAds",
      "Timestomped",
      "uSecZeros",
      "Copied"
    ],
    "columns": [
      "entrynumber",
      "sequencenumber",
      "inuse",
      "parententrynumber",
      "parentsequencenumber",
      "parentpath",
      "filename",
      "extension",
      "filesize",
      "referencecount",
      "reparsetarget",
      "isdirectory"
    ]
  },
  {
    "name": "SBECmd",
    "signature": [
      "bagpath",
      "slot",
      "nodeslot",
      "mruposition",
      "absolutepath",
      "shelltype",
      "value",
      "childbags",
      "createdon",
      "modifiedon",
      "accessedon",
      "lastwritetime",
      "mftentry",
      "mftsequencenumber",
      "extensionblockcount",
      "firstinteracted",
      "lastinteracted",
      "hasexplored",
      "miscellaneous"
    ],
    "timestamp": [
      "CreatedOn",
      "ModifiedOn",
      "AccessedOn",
      "LastWriteTime",
      "FirstInteracted",
      "LastInteracted"
    ],
    "booleans": [
      "HasExplored"
    ],
    "columns": [
      "bagpath",
      "slot",
      "nodeslot",
      "mruposition",
      "absolutepath",
      "shelltype",
      "value",
      "childbags",
      "createdon",
      "modifiedon",
      "accessedon",
      "lastwritetime"
    ]
  },
  {
    "name": "RBCmd",
    "signature": [
      "SourceName",
      "FileType",
      "FileName",
      "FileSize",
      "DeletedOn"
    ],
    "timestamp": [
      "DeletedOn"
    ],
    "booleans": [
      "Removed"
    ],
    "columns": [
      "SourceName",
      "FileType",
      "FileName",
      "FileSize",
      "DeletedOn"
    ]
  },
  {
    "name": "RBCmd",
    "signature": [
      "SourceName",
      "FileType",
      "FileName",
      "FileSize",
      "DeletedOn",
      "Removed"
    ],
    "timestamp": [
      "DeletedOn"
    ],
    "booleans": [
      "Removed"
    ],
    "columns": [
      "SourceName",
      "FileType",
      "FileName",
      "FileSize",
      "DeletedOn",
      "Removed"
    ]
  },
  {
    "name": "PECmd",
    "signature": [
      "Note",
      "SourceFilename",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "ExecutableName",
      "Hash",
      "Size",
      "Version",
      "RunCount",
      "LastRun",
      "PreviousRun0",
      "PreviousRun1",
      "PreviousRun2",
      "PreviousRun3",
      "PreviousRun4",
      "PreviousRun5",
      "PreviousRun6",
      "Volume0Name",
      "Volume0Serial",
      "Volume0Created",
      "Volume1Name",
      "Volume1Serial",
      "Volume1Created",
      "Directories",
      "FilesLoaded",
      "ParsingError"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "LastRun",
      "PreviousRun0",
      "PreviousRun1",
      "PreviousRun2",
      "PreviousRun3",
      "PreviousRun4",
      "PreviousRun5",
      "PreviousRun6",
      "Volume0Created",
      "Volume1Created"
    ],
    "booleans": [
      "ParsingError",
      "PathValidated"
    ],
    "columns": [
      "Note",
      "SourceFilename",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "ExecutableName",
      "Hash",
      "Size",
      "Version",
      "RunCount",
      "LastRun",
      "PreviousRun0"
    ]
  },
  {
    "name": "PECmd",
    "signature": [
      "Note",
      "SourceFilename",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "ExecutableName",
      "FullPath",
      "PathValidated",
      "Hash",
      "Size",
      "Version",
      "RunCount",
      "LastRun",
      "PreviousRun0",
      "PreviousRun1",
      "PreviousRun2",
      "PreviousRun3",
      "PreviousRun4",
      "PreviousRun5",
      "PreviousRun6",
      "Volume0Name",
      "Volume0Serial",
      "Volume0Created",
      "Volume1Name",
      "Volume1Serial",
      "Volume1Created",
      "Directories",
      "FilesLoaded",
      "ParsingError"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "LastRun",
      "PreviousRun0",
      "PreviousRun1",
      "PreviousRun2",
      "PreviousRun3",
      "PreviousRun4",
      "PreviousRun5",
      "PreviousRun6",
      "Volume0Created",
      "Volume1Created"
    ],
    "booleans": [
      "ParsingError",
      "PathValidated"
    ],
    "columns": [
      "Note",
      "SourceFilename",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "ExecutableName",
      "FullPath",
      "PathValidated",
      "Hash",
      "Size",
      "Version",
      "RunCount"
    ]
  },
  {
    "name": "PECmdTimeline",
    "signature": [
      "RunTime",
      "ExecutableName"
    ],
    "timestamp": [
      "RunTime"
    ],
    "booleans": [
      "PathValidated"
    ],
    "columns": [
      "RunTime",
      "ExecutableName"
    ]
  },
  {
    "name": "PECmdTimeline",
    "signature": [
      "RunTime",
      "ExecutableName",
      "SourceFilename",
      "PathValidated"
    ],
    "timestamp": [
      "RunTime"
    ],
    "booleans": [
      "PathValidated"
    ],
    "columns": [
      "RunTime",
      "ExecutableName",
      "SourceFilename",
      "PathValidated"
    ]
  },
  {
    "name": "LECmd",
    "signature": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags",
      "DriveType",
      "VolumeSerialNumber",
      "VolumeLabel",
      "LocalPath",
      "NetworkPath",
      "CommonPath",
      "Arguments",
      "TargetIDAbsolutePath",
      "TargetMFTEntryNumber",
      "TargetMFTSequenceNumber",
      "MachineID",
      "MachineMACAddress",
      "MACVendor",
      "TrackerCreatedOn",
      "ExtraBlocksPresent"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "TrackerCreatedOn"
    ],
    "booleans": [],
    "columns": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags"
    ]
  },
  {
    "name": "LECmd",
    "signature": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags",
      "DriveType",
      "VolumeSerialNumber",
      "VolumeLabel",
      "LocalPath",
      "NetworkPath",
      "CommonPath",
      "Arguments",
      "TargetIDAbsolutePath",
      "TargetMFTEntryNumber",
      "TargetMFTSequenceNumber",
      "MachineID",
      "MachineMACAddress",
      "MACVendor",
      "TrackerCreatedOn",
      "ExtraBlocksPresent",
      "Name",
      "IconLocation",
      "ShowWindow",
      "EnvironmentVariables",
      "VolumeDroid",
      "FileDroid",
      "VolumeDroidBirth",
      "FileDroidBirth",
      "Anomalies"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "TrackerCreatedOn"
    ],
    "booleans": [],
    "columns": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags"
    ]
  },
  {
    "name": "JLECmdAuto",
    "signature": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "HasSps",
      "DestListVersion",
      "LastUsedEntryNumber",
      "MRU",
      "EntryNumber",
      "CreationTime",
      "LastModified",
      "Hostname",
      "MacAddress",
      "Path",
      "InteractionCount",
      "PinStatus",
      "FileBirthDroid",
      "FileDroid",
      "VolumeBirthDroid",
      "VolumeDroid",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags",
      "DriveType",
      "VolumeSerialNumber",
      "VolumeLabel",
      "LocalPath",
      "CommonPath",
      "TargetIDAbsolutePath",
      "TargetMFTEntryNumber",
      "TargetMFTSequenceNumber",
      "MachineID",
      "MachineMACAddress",
      "TrackerCreatedOn",
      "ExtraBlocksPresent",
      "Arguments",
      "Notes"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "CreationTime",
      "LastModified",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "TrackerCreatedOn"
    ],
    "booleans": [
      "HasSps"
    ],
    "columns": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "HasSps",
      "DestListVersion",
      "LastUsedEntryNumber",
      "MRU",
      "EntryNumber",
      "CreationTime"
    ]
  },
  {
    "name": "JLECmdAuto",
    "signature": [
      "User",
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "HasSps",
      "DestListVersion",
      "LastUsedEntryNumber",
      "MRU",
      "EntryNumber",
      "CreationTime",
      "LastModified",
      "Hostname",
      "MacAddress",
      "Path",
      "InteractionCount",
      "PinStatus",
      "FileBirthDroid",
      "FileDroid",
      "VolumeBirthDroid",
      "VolumeDroid",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags",
      "DriveType",
      "VolumeSerialNumber",
      "VolumeLabel",
      "LocalPath",
      "CommonPath",
      "TargetIDAbsolutePath",
      "TargetMFTEntryNumber",
      "TargetMFTSequenceNumber",
      "MachineID",
      "MachineMACAddress",
      "TrackerCreatedOn",
      "ExtraBlocksPresent",
      "Arguments",
      "Notes"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "CreationTime",
      "LastModified",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "TrackerCreatedOn"
    ],
    "booleans": [
      "HasSps"
    ],
    "columns": [
      "User",
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "HasSps",
      "DestListVersion",
      "LastUsedEntryNumber",
      "MRU",
      "EntryNumber"
    ]
  },
  {
    "name": "JLECmdCustom",
    "signature": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "EntryName",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags",
      "DriveType",
      "VolumeSerialNumber",
      "VolumeLabel",
      "LocalPath",
      "CommonPath",
      "TargetIDAbsolutePath",
      "TargetMFTEntryNumber",
      "TargetMFTSequenceNumber",
      "MachineID",
      "MachineMACAddress",
      "TrackerCreatedOn",
      "ExtraBlocksPresent",
      "Arguments"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "TrackerCreatedOn"
    ],
    "booleans": [],
    "columns": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "EntryName",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath"
    ]
  },
  {
    "name": "JLECmdCustom",
    "signature": [
      "User",
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "EntryName",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize",
      "RelativePath",
      "WorkingDirectory",
      "FileAttributes",
      "HeaderFlags",
      "DriveType",
      "VolumeSerialNumber",
      "VolumeLabel",
      "LocalPath",
      "CommonPath",
      "TargetIDAbsolutePath",
      "TargetMFTEntryNumber",
      "TargetMFTSequenceNumber",
      "MachineID",
      "MachineMACAddress",
      "TrackerCreatedOn",
      "ExtraBlocksPresent",
      "Arguments"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "TrackerCreatedOn"
    ],
    "booleans": [],
    "columns": [
      "User",
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "AppId",
      "AppIdDescription",
      "EntryName",
      "TargetCreated",
      "TargetModified",
      "TargetAccessed",
      "FileSize"
    ]
  },
  {
    "name": "EvtxECmd",
    "signature": [
      "RecordNumber",
      "EventRecordId",
      "TimeCreated",
      "EventId",
      "Level",
      "Provider",
      "Channel",
      "ProcessId",
      "ThreadId",
      "Computer",
      "ChunkNumber",
      "UserId",
      "MapDescription",
      "UserName",
      "RemoteHost",
      "PayloadData1",
      "PayloadData2",
      "PayloadData3",
      "PayloadData4",
      "PayloadData5",
      "PayloadData6",
      "ExecutableInfo",
      "HiddenRecord",
      "SourceFile",
      "Keywords",
      "ExtraDataOffset",
      "Payload"
    ],
    "timestamp": [
      "TimeCreated"
    ],
    "booleans": [
      "HiddenRecord"
    ],
    "columns": [
      "RecordNumber",
      "EventRecordId",
      "TimeCreated",
      "EventId",
      "Level",
      "Provider",
      "Channel",
      "ProcessId",
      "ThreadId",
      "Computer",
      "ChunkNumber",
      "UserId"
    ]
  },
  {
    "name": "EvtxECmd",
    "signature": [
      "RecordNumber",
      "EventRecordId",
      "TimeCreated",
      "EventId",
      "Level",
      "Provider",
      "Channel",
      "ProcessId",
      "ThreadId",
      "Computer",
      "ChunkNumber",
      "UserId",
      "MapDescription",
      "UserName",
      "RemoteHost",
      "PayloadData1",
      "PayloadData2",
      "PayloadData3",
      "PayloadData4",
      "PayloadData5",
      "PayloadData6",
      "ExecutableInfo",
      "HiddenRecord",
      "SourceFile",
      "Keywords",
      "ExtraDataOffset",
      "Payload",
      "RenderingInfo"
    ],
    "timestamp": [
      "TimeCreated"
    ],
    "booleans": [
      "HiddenRecord"
    ],
    "columns": [
      "RecordNumber",
      "EventRecordId",
      "TimeCreated",
      "EventId",
      "Level",
      "Provider",
      "Channel",
      "ProcessId",
      "ThreadId",
      "Computer",
      "ChunkNumber",
      "UserId"
    ]
  },
  {
    "name": "RecmdBatch",
    "signature": [
      "hivepath",
      "hivetype",
      "description",
      "category",
      "keypath",
      "valuename",
      "valuetype",
      "valuedata",
      "valuedata2",
      "valuedata3",
      "comment",
      "recursive",
      "deleted",
      "lastwritetimestamp",
      "plugindetailfile"
    ],
    "timestamp": [
      "LastWriteTimestamp"
    ],
    "booleans": [
      "Recursive",
      "Deleted"
    ],
    "columns": [
      "hivepath",
      "hivetype",
      "description",
      "category",
      "keypath",
      "valuename",
      "valuetype",
      "valuedata",
      "valuedata2",
      "valuedata3",
      "comment",
      "recursive"
    ]
  },
  {
    "name": "AppCompatCache",
    "signature": [
      "ControlSet",
      "CacheEntryPosition",
      "Path",
      "LastModifiedTimeUTC",
      "Executed",
      "Duplicate",
      "SourceFile"
    ],
    "timestamp": [
      "LastModifiedTimeUTC"
    ],
    "booleans": [
      "Duplicate",
      "FromSlack"
    ],
    "columns": [
      "ControlSet",
      "CacheEntryPosition",
      "Path",
      "LastModifiedTimeUTC",
      "Executed",
      "Duplicate",
      "SourceFile"
    ]
  },
  {
    "name": "AppCompatCache",
    "signature": [
      "ControlSet",
      "CacheEntryPosition",
      "Path",
      "LastModifiedTimeUTC",
      "Executed",
      "Duplicate",
      "SourceFile",
      "FromSlack"
    ],
    "timestamp": [
      "LastModifiedTimeUTC"
    ],
    "booleans": [
      "Duplicate",
      "FromSlack"
    ],
    "columns": [
      "ControlSet",
      "CacheEntryPosition",
      "Path",
      "LastModifiedTimeUTC",
      "Executed",
      "Duplicate",
      "SourceFile",
      "FromSlack"
    ]
  },
  {
    "name": "ActivityPackage",
    "signature": [
      "Id",
      "Platform",
      "Name",
      "AdditionalInformation",
      "Expires"
    ],
    "timestamp": [
      "Expires"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Platform",
      "Name",
      "AdditionalInformation",
      "Expires"
    ]
  },
  {
    "name": "Activity",
    "signature": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient",
      "ExpirationTime",
      "CreatedInCloud",
      "IsLocalOnly",
      "ETag",
      "PackageIdHash",
      "PlatformDeviceId",
      "DevicePlatform",
      "TimeZone"
    ],
    "timestamp": [
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedInCloud",
      "StartTime",
      "EndTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient"
    ],
    "booleans": [
      "IsLocalOnly"
    ],
    "columns": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime"
    ]
  },
  {
    "name": "Activity",
    "signature": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient",
      "ExpirationTime",
      "CreatedInCloud",
      "IsLocalOnly",
      "ETag",
      "PackageIdHash",
      "PlatformDeviceId",
      "DevicePlatform",
      "TimeZone",
      "AppActivityId",
      "ClipboardText"
    ],
    "timestamp": [
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedInCloud",
      "StartTime",
      "EndTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient"
    ],
    "booleans": [
      "IsLocalOnly"
    ],
    "columns": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime"
    ]
  },
  {
    "name": "ActivityOperation",
    "signature": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime",
      "LastModifiedTimeOnClient",
      "CreatedTime",
      "ExpirationTime",
      "OperationExpirationTime",
      "OperationOrder",
      "AppId",
      "OperationType",
      "Description",
      "PlatformDeviceId",
      "DevicePlatform",
      "TimeZone"
    ],
    "timestamp": [
      "StartTime",
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedTime",
      "EndTime",
      "LastModifiedTimeOnClient",
      "OperationExpirationTime"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime"
    ]
  },
  {
    "name": "ActivityOperation",
    "signature": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime",
      "LastModifiedTimeOnClient",
      "CreatedTime",
      "ExpirationTime",
      "OperationExpirationTime",
      "OperationOrder",
      "AppId",
      "OperationType",
      "Description",
      "PlatformDeviceId",
      "DevicePlatform",
      "TimeZone",
      "AppActivityId",
      "ClipboardText"
    ],
    "timestamp": [
      "StartTime",
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedTime",
      "EndTime",
      "LastModifiedTimeOnClient",
      "OperationExpirationTime"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "ActivityTypeOrg",
      "ActivityType",
      "Executable",
      "DisplayText",
      "ContentInfo",
      "Payload",
      "ClipboardPayload",
      "StartTime",
      "EndTime",
      "Duration",
      "LastModifiedTime"
    ]
  },
  {
    "name": "AmcacheParserPrograms",
    "signature": [
      "ProgramID",
      "LastWriteTimestamp",
      "ProgramName_0",
      "ProgramVersion_1",
      "VendorName_2",
      "InstallDateEpoch_a",
      "InstallDateEpoch_b",
      "LanguageCode_3",
      "InstallSource_6",
      "UninstallRegistryKey_7",
      "PathsList_d",
      "UnknownGuid_10",
      "UnknownGuid_12",
      "UninstallGuid_11",
      "UnknownDword_5",
      "UnknownDword_13",
      "UnknownDword_14",
      "UnknownDword_15",
      "UnknownBytes_16",
      "UnknownQWord_17",
      "UnknownDword_18",
      "UninstallGuid_f"
    ],
    "timestamp": [
      "LastWriteTimestamp",
      "InstallDateEpoch_a",
      "InstallDateEpoch_b"
    ],
    "booleans": [],
    "columns": [
      "ProgramID",
      "LastWriteTimestamp",
      "ProgramName_0",
      "ProgramVersion_1",
      "VendorName_2",
      "InstallDateEpoch_a",
      "InstallDateEpoch_b",
      "LanguageCode_3",
      "InstallSource_6",
      "UninstallRegistryKey_7",
      "PathsList_d",
      "UnknownGuid_10"
    ]
  },
  {
    "name": "AmcacheParserPrograms",
    "signature": [
      "ProgramID",
      "LastWriteTimestamp",
      "ProgramName_0",
      "ProgramVersion_1",
      "VendorName_2",
      "InstallDateEpoch_a",
      "UnknownGuid_10",
      "InstallDateEpoch_b",
      "LanguageCode_3",
      "UnknownGuid_12",
      "InstallSource_6",
      "UninstallGuid_11",
      "UninstallRegistryKey_7",
      "UnknownDword_5",
      "PathsList_d",
      "UnknownDword_13",
      "UnknownDword_14",
      "UnknownDword_15",
      "UnknownBytes_16",
      "UnknownQWord_17",
      "UnknownDword_18",
      "UninstallGuid_f"
    ],
    "timestamp": [
      "LastWriteTimestamp",
      "InstallDateEpoch_a",
      "InstallDateEpoch_b"
    ],
    "booleans": [],
    "columns": [
      "ProgramID",
      "LastWriteTimestamp",
      "ProgramName_0",
      "ProgramVersion_1",
      "VendorName_2",
      "InstallDateEpoch_a",
      "UnknownGuid_10",
      "InstallDateEpoch_b",
      "LanguageCode_3",
      "UnknownGuid_12",
      "InstallSource_6",
      "UninstallGuid_11"
    ]
  },
  {
    "name": "AmcacheParserFiles",
    "signature": [
      "ProgramName",
      "ProgramID",
      "VolumeID",
      "VolumeIDLastWriteTimestamp",
      "FileID",
      "FileIDLastWriteTimestamp",
      "SHA1",
      "FullPath",
      "FileExtension",
      "MFTEntryNumber",
      "MFTSequenceNumber",
      "FileSize",
      "FileVersionString",
      "FileVersionNumber",
      "FileDescription",
      "SizeOfImage",
      "PEHeaderHash",
      "PEHeaderChecksum",
      "BinProductVersion",
      "BinFileVersion",
      "LinkerVersion",
      "BinaryType",
      "IsLocal",
      "GuessProgramID",
      "Created",
      "LastModified",
      "LastModifiedStore",
      "LinkDate",
      "LanguageID",
      "ProductName",
      "CompanyName",
      "SwitchBackContext"
    ],
    "timestamp": [
      "VolumeIDLastWriteTimestamp",
      "FileIDLastWriteTimestamp",
      "Created",
      "LastModified",
      "LastModifiedStore",
      "LinkDate"
    ],
    "booleans": [],
    "columns": [
      "ProgramName",
      "ProgramID",
      "VolumeID",
      "VolumeIDLastWriteTimestamp",
      "FileID",
      "FileIDLastWriteTimestamp",
      "SHA1",
      "FullPath",
      "FileExtension",
      "MFTEntryNumber",
      "MFTSequenceNumber",
      "FileSize"
    ]
  },
  {
    "name": "AmcacheParserFiles",
    "signature": [
      "ProgramName",
      "ProgramID",
      "ProductName",
      "VolumeID",
      "CompanyName",
      "VolumeIDLastWriteTimestamp",
      "FileID",
      "FileIDLastWriteTimestamp",
      "SHA1",
      "FullPath",
      "FileExtension",
      "MFTEntryNumber",
      "MFTSequenceNumber",
      "FileSize",
      "FileVersionString",
      "FileVersionNumber",
      "FileDescription",
      "SwitchBackContext",
      "SizeOfImage",
      "PEHeaderHash",
      "PEHeaderChecksum",
      "BinProductVersion",
      "BinFileVersion",
      "LinkerVersion",
      "BinaryType",
      "IsLocal",
      "GuessProgramID",
      "Created",
      "LastModified",
      "LastModifiedStore",
      "LinkDate",
      "LanguageID"
    ],
    "timestamp": [
      "VolumeIDLastWriteTimestamp",
      "FileIDLastWriteTimestamp",
      "Created",
      "LastModified",
      "LastModifiedStore",
      "LinkDate"
    ],
    "booleans": [],
    "columns": [
      "ProgramName",
      "ProgramID",
      "ProductName",
      "VolumeID",
      "CompanyName",
      "VolumeIDLastWriteTimestamp",
      "FileID",
      "FileIDLastWriteTimestamp",
      "SHA1",
      "FullPath",
      "FileExtension",
      "MFTEntryNumber"
    ]
  },
  {
    "name": "AmcacheParserNewFiles",
    "signature": [
      "ApplicationName",
      "ProgramId",
      "FileKeyLastWriteTimestamp",
      "SHA1",
      "IsOsComponent",
      "FullPath",
      "Name",
      "FileExtension",
      "LinkDate",
      "ProductName",
      "Size",
      "Version",
      "ProductVersion",
      "LongPathHash",
      "BinaryType",
      "IsPeFile",
      "BinFileVersion",
      "BinProductVersion",
      "Usn",
      "Language",
      "Description"
    ],
    "timestamp": [
      "FileKeyLastWriteTimestamp",
      "LinkDate"
    ],
    "booleans": [
      "IsOsComponent",
      "IsPeFile"
    ],
    "columns": [
      "ApplicationName",
      "ProgramId",
      "FileKeyLastWriteTimestamp",
      "SHA1",
      "IsOsComponent",
      "FullPath",
      "Name",
      "FileExtension",
      "LinkDate",
      "ProductName",
      "Size",
      "Version"
    ]
  },
  {
    "name": "AmcacheParserNewFiles",
    "signature": [
      "ApplicationName",
      "ProgramId",
      "FileKeyLastWriteTimestamp",
      "SHA1",
      "IsOsComponent",
      "FullPath",
      "Name",
      "FileExtension",
      "LinkDate",
      "ProductName",
      "Size",
      "Version",
      "ProductVersion",
      "LongPathHash",
      "BinaryType",
      "IsPeFile",
      "BinFileVersion",
      "BinProductVersion",
      "Usn",
      "Language",
      "Description",
      "OriginalFileName"
    ],
    "timestamp": [
      "FileKeyLastWriteTimestamp",
      "LinkDate"
    ],
    "booleans": [
      "IsOsComponent",
      "IsPeFile"
    ],
    "columns": [
      "ApplicationName",
      "ProgramId",
      "FileKeyLastWriteTimestamp",
      "SHA1",
      "IsOsComponent",
      "FullPath",
      "Name",
      "FileExtension",
      "LinkDate",
      "ProductName",
      "Size",
      "Version"
    ]
  },
  {
    "name": "AmcacheParserNewFiles",
    "signature": [
      "ApplicationName",
      "ProgramId",
      "FileKeyLastWriteTimestamp",
      "SHA1",
      "IsOsComponent",
      "FullPath",
      "Name",
      "FileExtension",
      "LinkDate",
      "ProductName",
      "Size",
      "Version",
      "ProductVersion",
      "LongPathHash",
      "BinaryType",
      "IsPeFile",
      "BinFileVersion",
      "BinProductVersion",
      "Usn",
      "Language",
      "Description",
      "OriginalFileName",
      "Publisher",
      "Sha256",
      "KeyName",
      "AppxPackageFullName",
      "AppxPackageRelativeId"
    ],
    "timestamp": [
      "FileKeyLastWriteTimestamp",
      "LinkDate"
    ],
    "booleans": [
      "IsOsComponent",
      "IsPeFile"
    ],
    "columns": [
      "ApplicationName",
      "ProgramId",
      "FileKeyLastWriteTimestamp",
      "SHA1",
      "IsOsComponent",
      "FullPath",
      "Name",
      "FileExtension",
      "LinkDate",
      "ProductName",
      "Size",
      "Version"
    ]
  },
  {
    "name": "AmcacheParserNewDevicePnP",
    "signature": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "BusReportedDescription",
      "Class",
      "ClassGuid",
      "Compid",
      "ContainerId",
      "Description",
      "DriverId",
      "DriverPackageStrongName",
      "DriverName",
      "DriverVerDate",
      "DriverVerVersion",
      "Enumerator",
      "HWID",
      "Inf",
      "InstallState",
      "Manufacturer",
      "MatchingId",
      "Model",
      "ParentId",
      "ProblemCode",
      "Provider",
      "Service",
      "Stackid"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "DriverVerDate"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "BusReportedDescription",
      "Class",
      "ClassGuid",
      "Compid",
      "ContainerId",
      "Description",
      "DriverId",
      "DriverPackageStrongName",
      "DriverName",
      "DriverVerDate"
    ]
  },
  {
    "name": "AmcacheParserNewDevicePnP",
    "signature": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "BusReportedDescription",
      "Class",
      "ClassGuid",
      "Compid",
      "ContainerId",
      "Description",
      "DriverId",
      "DriverPackageStrongName",
      "DriverName",
      "DriverVerDate",
      "DriverVerVersion",
      "Enumerator",
      "HWID",
      "Inf",
      "InstallState",
      "Manufacturer",
      "MatchingId",
      "Model",
      "ParentId",
      "ProblemCode",
      "Provider",
      "Service",
      "Stackid",
      "DeviceState",
      "InstallDate",
      "FirstInstallDate",
      "ExtendedInfs",
      "UpperClassFilters",
      "LowerClassFilters",
      "UpperFilters",
      "LowerFilters",
      "DeviceInterfaceClasses",
      "LocationPaths"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "DriverVerDate"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "BusReportedDescription",
      "Class",
      "ClassGuid",
      "Compid",
      "ContainerId",
      "Description",
      "DriverId",
      "DriverPackageStrongName",
      "DriverName",
      "DriverVerDate"
    ]
  },
  {
    "name": "AmcacheParserDeviceContainer",
    "signature": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "Categories",
      "DiscoveryMethod",
      "FriendlyName",
      "Icon",
      "IsActive",
      "IsConnected",
      "IsMachineContainer",
      "IsNetworked",
      "IsPaired",
      "Manufacturer",
      "ModelId",
      "ModelName",
      "ModelNumber",
      "PrimaryCategory",
      "State"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp"
    ],
    "booleans": [
      "IsActive",
      "IsConnected",
      "IsMachineContainer",
      "IsNetworked",
      "IsPaired"
    ],
    "columns": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "Categories",
      "DiscoveryMethod",
      "FriendlyName",
      "Icon",
      "IsActive",
      "IsConnected",
      "IsMachineContainer",
      "IsNetworked",
      "IsPaired",
      "Manufacturer"
    ]
  },
  {
    "name": "AmcacheParserDriverPackage",
    "signature": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "Date",
      "Class",
      "Directory",
      "DriverInBox",
      "Hwids",
      "Inf",
      "Provider",
      "SubmissionId",
      "SYSFILE",
      "Version"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "Date"
    ],
    "booleans": [
      "DriverInBox"
    ],
    "columns": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "Date",
      "Class",
      "Directory",
      "DriverInBox",
      "Hwids",
      "Inf",
      "Provider",
      "SubmissionId",
      "SYSFILE",
      "Version"
    ]
  },
  {
    "name": "AmcacheParserDriverPackage",
    "signature": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "Date",
      "Class",
      "Directory",
      "DriverInBox",
      "Hwids",
      "Inf",
      "Provider",
      "SubmissionId",
      "SYSFILE",
      "Version",
      "ClassGuid",
      "DriverPackageStrongName",
      "FlightIds",
      "RecoveryIds",
      "IsActive"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "Date"
    ],
    "booleans": [
      "DriverInBox"
    ],
    "columns": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "Date",
      "Class",
      "Directory",
      "DriverInBox",
      "Hwids",
      "Inf",
      "Provider",
      "SubmissionId",
      "SYSFILE",
      "Version"
    ]
  },
  {
    "name": "AmcacheParserDriverBinary",
    "signature": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "DriverTimeStamp",
      "DriverLastWriteTime",
      "DriverName",
      "DriverInBox",
      "DriverIsKernelMode",
      "DriverSigned",
      "DriverCheckSum",
      "DriverCompany",
      "DriverId",
      "DriverPackageStrongName",
      "DriverType",
      "DriverVersion",
      "ImageSize",
      "Inf",
      "Product",
      "ProductVersion",
      "Service",
      "WdfVersion"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "DriverTimeStamp",
      "DriverLastWriteTime"
    ],
    "booleans": [
      "DriverInBox",
      "DriverIsKernelMode",
      "DriverSigned"
    ],
    "columns": [
      "KeyName",
      "KeyLastWriteTimestamp",
      "DriverTimeStamp",
      "DriverLastWriteTime",
      "DriverName",
      "DriverInBox",
      "DriverIsKernelMode",
      "DriverSigned",
      "DriverCheckSum",
      "DriverCompany",
      "DriverId",
      "DriverPackageStrongName"
    ]
  },
  {
    "name": "AmcacheParserNewShortcut",
    "signature": [
      "KeyName",
      "LnkName",
      "KeyLastWriteTimestamp"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "LnkName",
      "KeyLastWriteTimestamp"
    ]
  },
  {
    "name": "AmcacheParserNewShortcut",
    "signature": [
      "KeyName",
      "LnkName",
      "KeyLastWriteTimestamp",
      "ShortcutTargetPath",
      "ShortcutAumid",
      "ShortcutProgramId"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "LnkName",
      "KeyLastWriteTimestamp",
      "ShortcutTargetPath",
      "ShortcutAumid",
      "ShortcutProgramId"
    ]
  },
  {
    "name": "AmcacheParserNewProgram",
    "signature": [
      "ProgramId",
      "KeyLastWriteTimestamp",
      "Name",
      "Version",
      "Publisher",
      "InstallDateArpLastModified",
      "InstallDate",
      "InstallDateMsi",
      "OSVersionAtInstallTime",
      "InstallDateFromLinkFile",
      "BundleManifestPath",
      "HiddenArp",
      "InboxModernApp",
      "Language",
      "ManifestPath",
      "MsiPackageCode",
      "MsiProductCode",
      "PackageFullName",
      "ProgramInstanceId",
      "RegistryKeyPath",
      "RootDirPath",
      "Type",
      "Source",
      "StoreAppType",
      "UninstallString",
      "Manufacturer"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "InstallDateArpLastModified",
      "InstallDate",
      "InstallDateMsi",
      "InstallDateFromLinkFile",
      "MsiInstallDate"
    ],
    "booleans": [
      "HiddenArp",
      "InboxModernApp"
    ],
    "columns": [
      "ProgramId",
      "KeyLastWriteTimestamp",
      "Name",
      "Version",
      "Publisher",
      "InstallDateArpLastModified",
      "InstallDate",
      "InstallDateMsi",
      "OSVersionAtInstallTime",
      "InstallDateFromLinkFile",
      "BundleManifestPath",
      "HiddenArp"
    ]
  },
  {
    "name": "AmcacheParserNewProgram",
    "signature": [
      "ProgramId",
      "KeyLastWriteTimestamp",
      "Name",
      "Version",
      "Publisher",
      "InstallDateArpLastModified",
      "InstallDate",
      "InstallDateMsi",
      "OSVersionAtInstallTime",
      "InstallDateFromLinkFile",
      "BundleManifestPath",
      "HiddenArp",
      "InboxModernApp",
      "Language",
      "ManifestPath",
      "MsiPackageCode",
      "MsiProductCode",
      "PackageFullName",
      "ProgramInstanceId",
      "RegistryKeyPath",
      "RootDirPath",
      "Type",
      "Source",
      "StoreAppType",
      "UninstallString",
      "Manufacturer",
      "KeyName",
      "UserSid",
      "MsiInstallDate"
    ],
    "timestamp": [
      "KeyLastWriteTimestamp",
      "InstallDateArpLastModified",
      "InstallDate",
      "InstallDateMsi",
      "InstallDateFromLinkFile",
      "MsiInstallDate"
    ],
    "booleans": [
      "HiddenArp",
      "InboxModernApp"
    ],
    "columns": [
      "ProgramId",
      "KeyLastWriteTimestamp",
      "Name",
      "Version",
      "Publisher",
      "InstallDateArpLastModified",
      "InstallDate",
      "InstallDateMsi",
      "OSVersionAtInstallTime",
      "InstallDateFromLinkFile",
      "BundleManifestPath",
      "HiddenArp"
    ]
  },
  {
    "name": "NetworkUsage",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "BytesReceived",
      "BytesSent",
      "InterfaceLuid",
      "InterfaceType",
      "L2ProfileFlags",
      "L2ProfileId",
      "ProfileName"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "BytesReceived",
      "BytesSent"
    ]
  },
  {
    "name": "PushNotification",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "NetworkType",
      "NotificationType",
      "PayloadSize"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "NetworkType",
      "NotificationType"
    ]
  },
  {
    "name": "NetworkConnection",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "ConnectedTime",
      "ConnectStartTime",
      "InterfaceLuid",
      "InterfaceType",
      "L2ProfileFlags",
      "L2ProfileId",
      "ProfileName"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp",
      "ConnectStartTime"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "ConnectedTime",
      "ConnectStartTime"
    ]
  },
  {
    "name": "AppResourceUseInfo",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "BackgroundBytesRead",
      "BackgroundBytesWritten",
      "BackgroundContextSwitches",
      "BackgroundCycleTime",
      "BackgroundNumberOfFlushes",
      "BackgroundNumReadOperations",
      "BackgroundNumWriteOperations",
      "FaceTime",
      "ForegroundBytesRead",
      "ForegroundBytesWritten",
      "ForegroundContextSwitches",
      "ForegroundCycleTime",
      "ForegroundNumberOfFlushes",
      "ForegroundNumReadOperations",
      "ForegroundNumWriteOperations"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "BackgroundBytesRead",
      "BackgroundBytesWritten"
    ]
  },
  {
    "name": "UnknownD8F",
    "signature": [
      "Id",
      "Timestamp",
      "UserId",
      "AppId",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "StartTime",
      "EndTime",
      "Flags",
      "Duration"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp",
      "StartTime",
      "EndTime"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "UserId",
      "AppId",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "StartTime",
      "EndTime"
    ]
  },
  {
    "name": "Unknown312",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "EndTime",
      "DurationMs"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp",
      "EndTime"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "EndTime",
      "DurationMs"
    ]
  },
  {
    "name": "Unknown312",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "EndTime",
      "DurationMs",
      "InFocusS",
      "PsmForegroundS",
      "UserInputS",
      "KeyboardInputS",
      "MouseInputS",
      "DisplayRequiredS",
      "AudioInS",
      "AudioOutS"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp",
      "EndTime"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "EndTime",
      "DurationMs"
    ]
  },
  {
    "name": "EnergyUsage",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "IsLt",
      "ConfigurationHash",
      "EventTimestamp",
      "StateTransition",
      "ChargeLevel",
      "CycleCount",
      "DesignedCapacity",
      "FullChargedCapacity",
      "ActiveAcTime",
      "ActiveDcTime",
      "ActiveDischargeTime",
      "ActiveEnergy",
      "CsAcTime",
      "CsDcTime",
      "CsDischargeTime",
      "CsEnergy"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp",
      "EventTimestamp"
    ],
    "booleans": [
      "IsLt"
    ],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "IsLt",
      "ConfigurationHash"
    ]
  },
  {
    "name": "MFTFileListing",
    "signature": [
      "FullPath",
      "Extension",
      "IsDirectory",
      "FileSize",
      "Created0x10",
      "LastModified0x10"
    ],
    "timestamp": [
      "Created0x10",
      "LastModified0x10"
    ],
    "booleans": [
      "IsDirectory"
    ],
    "columns": [
      "FullPath",
      "Extension",
      "IsDirectory",
      "FileSize",
      "Created0x10",
      "LastModified0x10"
    ]
  },
  {
    "name": "SumChainedDb",
    "signature": [
      "Year",
      "FileName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Year",
      "FileName"
    ]
  },
  {
    "name": "SumSystemIdentInfo",
    "signature": [
      "CreationTime",
      "OsMajor",
      "OsMinor",
      "OsBuild"
    ],
    "timestamp": [
      "CreationTime"
    ],
    "booleans": [
      "OsDaylightInEffect"
    ],
    "columns": [
      "CreationTime",
      "OsMajor",
      "OsMinor",
      "OsBuild"
    ]
  },
  {
    "name": "SumSystemIdentInfo",
    "signature": [
      "CreationTime",
      "OsMajor",
      "OsMinor",
      "OsBuild",
      "SystemDnsHostName",
      "SystemDomainName",
      "SystemManufacturer",
      "SystemProductName",
      "SystemSerialNumber",
      "SystemSmbiosUuid",
      "OsSerialNumber",
      "OsLastBootUpTime",
      "OsCountryCode",
      "OsCurrentTimeZone",
      "OsDaylightInEffect",
      "OsProductType",
      "OsSuiteMask",
      "OsPlatformId",
      "ServicePackMajor",
      "ServicePackMinor",
      "PhysicalProcessorCount",
      "CoresPerPhysicalProcessor",
      "LogicalProcessorsPerPhysicalProcessor",
      "MaximumMemory"
    ],
    "timestamp": [
      "CreationTime"
    ],
    "booleans": [
      "OsDaylightInEffect"
    ],
    "columns": [
      "CreationTime",
      "OsMajor",
      "OsMinor",
      "OsBuild",
      "SystemDnsHostName",
      "SystemDomainName",
      "SystemManufacturer",
      "SystemProductName",
      "SystemSerialNumber",
      "SystemSmbiosUuid",
      "OsSerialNumber",
      "OsLastBootUpTime"
    ]
  },
  {
    "name": "SumRoleInfo",
    "signature": [
      "RoleGuid",
      "RoleName",
      "ProductName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "RoleGuid",
      "RoleName",
      "ProductName"
    ]
  },
  {
    "name": "SumRoleAccess",
    "signature": [
      "RoleGuid",
      "RoleDescription",
      "FirstSeen",
      "LastSeen",
      "SourceFile"
    ],
    "timestamp": [
      "FirstSeen",
      "LastSeen"
    ],
    "booleans": [],
    "columns": [
      "RoleGuid",
      "RoleDescription",
      "FirstSeen",
      "LastSeen",
      "SourceFile"
    ]
  },
  {
    "name": "SumClient",
    "signature": [
      "RoleGuid",
      "RoleDescription",
      "AuthenticatedUserName",
      "TotalAccesses",
      "InsertDate",
      "LastAccess",
      "IpAddress",
      "ClientName",
      "TenantId",
      "SourceFile"
    ],
    "timestamp": [
      "InsertDate",
      "LastAccess"
    ],
    "booleans": [],
    "columns": [
      "RoleGuid",
      "RoleDescription",
      "AuthenticatedUserName",
      "TotalAccesses",
      "InsertDate",
      "LastAccess",
      "IpAddress",
      "ClientName",
      "TenantId",
      "SourceFile"
    ]
  },
  {
    "name": "SumClientDetailed",
    "signature": [
      "Date",
      "Count",
      "DayNumber",
      "RoleGuid",
      "RoleDescription",
      "AuthenticatedUserName",
      "TotalAccesses",
      "InsertDate",
      "LastAccess",
      "IpAddress",
      "ClientName",
      "TenantId",
      "SourceFile"
    ],
    "timestamp": [
      "Date",
      "InsertDate",
      "LastAccess"
    ],
    "booleans": [],
    "columns": [
      "Date",
      "Count",
      "DayNumber",
      "RoleGuid",
      "RoleDescription",
      "AuthenticatedUserName",
      "TotalAccesses",
      "InsertDate",
      "LastAccess",
      "IpAddress",
      "ClientName",
      "TenantId"
    ]
  },
  {
    "name": "SumDnsInfo",
    "signature": [
      "HostName",
      "Address",
      "LastSeen",
      "SourceFile"
    ],
    "timestamp": [
      "LastSeen"
    ],
    "booleans": [],
    "columns": [
      "HostName",
      "Address",
      "LastSeen",
      "SourceFile"
    ]
  },
  {
    "name": "LogFile",
    "signature": [
      "Lsn",
      "TransactionId",
      "TransactionFirstLsn",
      "RedoOperation",
      "UndoOperation",
      "TargetEntryNumber",
      "TargetSequenceNumber",
      "TargetAttributeType",
      "TargetAttributeName",
      "TargetPath",
      "EntryNumber",
      "SequenceNumber",
      "FileName",
      "ParentEntryNumber",
      "ParentSequenceNumber",
      "ParentPath",
      "CreatedOn",
      "ContentModifiedOn",
      "RecordModifiedOn",
      "LastAccessedOn",
      "FileSize",
      "FileAttributes",
      "AttributeType",
      "Details",
      "PreviousLsn",
      "UndoNextLsn",
      "RecordType",
      "TargetAttribute",
      "TargetInferred",
      "TargetVcn",
      "Lcns",
      "RecordOffset",
      "AttributeOffset",
      "ClusterBlockOffset",
      "RedoLength",
      "UndoLength",
      "Truncated",
      "FileOffset",
      "SourceFile"
    ],
    "timestamp": [
      "CreatedOn",
      "ContentModifiedOn",
      "RecordModifiedOn",
      "LastAccessedOn"
    ],
    "booleans": [
      "TargetInferred",
      "Truncated"
    ],
    "columns": [
      "Lsn",
      "TransactionId",
      "TransactionFirstLsn",
      "RedoOperation",
      "UndoOperation",
      "TargetEntryNumber",
      "TargetSequenceNumber",
      "TargetAttributeType",
      "TargetAttributeName",
      "TargetPath",
      "EntryNumber",
      "SequenceNumber"
    ]
  },
  {
    "name": "SrumProcessorTime",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "ProcessorTime"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "ProcessorTime"
    ]
  },
  {
    "name": "SrumSizeInBytes",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "SizeInBytes"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "SizeInBytes"
    ]
  },
  {
    "name": "SrumTotalUsed",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "Total",
      "Used"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "Total",
      "Used"
    ]
  },
  {
    "name": "SrumNetworkBytes",
    "signature": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "BytesInBound",
      "BytesOutBound",
      "BytesTotal"
    ],
    "timestamp": [
      "Timestamp",
      "ExeTimestamp"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Timestamp",
      "ExeInfo",
      "ExeInfoDescription",
      "ExeTimestamp",
      "SidType",
      "Sid",
      "UserName",
      "UserId",
      "AppId",
      "BytesInBound",
      "BytesOutBound"
    ]
  },
  {
    "name": "SumVmInfo",
    "signature": [
      "VmGuid",
      "CreationTime",
      "LastSeenActive",
      "BiosGuid",
      "SerialNumber",
      "SourceFile"
    ],
    "timestamp": [
      "CreationTime",
      "LastSeenActive"
    ],
    "booleans": [],
    "columns": [
      "VmGuid",
      "CreationTime",
      "LastSeenActive",
      "BiosGuid",
      "SerialNumber",
      "SourceFile"
    ]
  },
  {
    "name": "AmcacheParserDeviceCensus",
    "signature": [
      "ItemKey",
      "Data",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Data",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryAcpiPhatHealthRecord",
    "signature": [
      "ItemKey",
      "AmHealthy",
      "DevicePathType",
      "DevicePathSubtype",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "AmHealthy",
      "DevicePathType",
      "DevicePathSubtype",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryAcpiPhatVersionElement",
    "signature": [
      "ItemKey",
      "VersionValue",
      "ProducerId",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "VersionValue",
      "ProducerId",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryApplicationAppV",
    "signature": [
      "ItemKey",
      "ProgramIds",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "ProgramIds",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryApplicationFramework",
    "signature": [
      "ItemKey",
      "Frameworks",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Frameworks",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryDeviceInterface",
    "signature": [
      "ItemKey",
      "Accelerometer3D",
      "ActivityDetection",
      "AmbientLight",
      "Barometer",
      "Custom",
      "FloorElevation",
      "GeomagneticOrientation",
      "GravityVector",
      "Gyrometer3D",
      "Humidity",
      "LinearAccelerometer",
      "Magnetometer3D",
      "Orientation",
      "Pedometer",
      "Proximity",
      "RelativeOrientation",
      "SimpleDeviceOrientation",
      "Temperature",
      "EnergyMeter",
      "HingeAngle",
      "PresenceCapabilities",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Accelerometer3D",
      "ActivityDetection",
      "AmbientLight",
      "Barometer",
      "Custom",
      "FloorElevation",
      "GeomagneticOrientation",
      "GravityVector",
      "Gyrometer3D",
      "Humidity",
      "LinearAccelerometer"
    ]
  },
  {
    "name": "AmcacheParserInventoryDeviceMediaClass",
    "signature": [
      "ItemKey",
      "Audio_RenderDriver",
      "Audio_CaptureDriver",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Audio_RenderDriver",
      "Audio_CaptureDriver",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryDevicePci",
    "signature": [
      "ItemKey",
      "IsTunneledDevice",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "IsTunneledDevice",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryDeviceSensor",
    "signature": [
      "ItemKey",
      "Manufacturer",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Manufacturer",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryDeviceUsbHubClass",
    "signature": [
      "ItemKey",
      "TotalUserConnectablePorts",
      "TotalUserConnectableTypeCPorts",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "TotalUserConnectablePorts",
      "TotalUserConnectableTypeCPorts",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryInstaller",
    "signature": [
      "ItemKey",
      "InstallerId",
      "InstallerName",
      "InstallerVersion",
      "InstallerPublisher",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "InstallerId",
      "InstallerName",
      "InstallerVersion",
      "InstallerPublisher",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryInstallerApplication",
    "signature": [
      "ItemKey",
      "ProgramId",
      "Name",
      "Version",
      "Publisher",
      "Language",
      "UninstallKey",
      "InstallerId",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "ProgramId",
      "Name",
      "Version",
      "Publisher",
      "Language",
      "UninstallKey",
      "InstallerId",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryInstallerApplicationFile",
    "signature": [
      "ItemKey",
      "InstallerId",
      "FilePath",
      "FileId",
      "ProgramId",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "InstallerId",
      "FilePath",
      "FileId",
      "ProgramId",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryMiscellaneous",
    "signature": [
      "ItemKey",
      "Exists",
      "Value",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Exists",
      "Value",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryMiscellaneousMemorySlotArrayInfo",
    "signature": [
      "ItemKey",
      "Slot",
      "Type",
      "TypeDetails",
      "Speed",
      "Capacity",
      "Model",
      "Manufacturer",
      "TotalWidth",
      "DataWidth",
      "MemoryErrorCorrection",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Slot",
      "Type",
      "TypeDetails",
      "Speed",
      "Capacity",
      "Model",
      "Manufacturer",
      "TotalWidth",
      "DataWidth",
      "MemoryErrorCorrection",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryMiscellaneousUUPInfo",
    "signature": [
      "ItemKey",
      "Identifier",
      "Version",
      "Source",
      "PreviousVersion",
      "LastActivatedVersion",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Identifier",
      "Version",
      "Source",
      "PreviousVersion",
      "LastActivatedVersion",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserInventoryMiscellaneousUser",
    "signature": [
      "ItemKey",
      "OriginalName",
      "Exists",
      "Value",
      "UserId",
      "StandardUserHash",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "OriginalName",
      "Exists",
      "Value",
      "UserId",
      "StandardUserHash",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserMare",
    "signature": [
      "ItemKey",
      "path",
      "programId",
      "flags",
      "far",
      "restore",
      "sdbentryguid",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "path",
      "programId",
      "flags",
      "far",
      "restore",
      "sdbentryguid",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserMareBackupApps",
    "signature": [
      "ItemKey",
      "Hash",
      "Aumids",
      "SidState",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "ItemKey",
      "Hash",
      "Aumids",
      "SidState",
      "LastModified"
    ]
  },
  {
    "name": "AmcacheParserMetadata",
    "signature": [
      "Database",
      "Name",
      "Value"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Database",
      "Name",
      "Value"
    ]
  },
  {
    "name": "RecmdAdobe",
    "signature": [
      "ProductName",
      "BatchKeyPath",
      "ProductVersion",
      "BatchValueName",
      "FullPath",
      "LastOpened",
      "FileName",
      "FileSize",
      "FileSource",
      "PageCount"
    ],
    "timestamp": [
      "LastOpened"
    ],
    "booleans": [],
    "columns": [
      "ProductName",
      "BatchKeyPath",
      "ProductVersion",
      "BatchValueName",
      "FullPath",
      "LastOpened",
      "FileName",
      "FileSize",
      "FileSource",
      "PageCount"
    ]
  },
  {
    "name": "RecmdAdobeTrustManager",
    "signature": [
      "Website",
      "BatchKeyPath",
      "UserChoice",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Website",
      "BatchKeyPath",
      "UserChoice",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdAppCompat",
    "signature": [
      "CacheEntryPosition",
      "BatchKeyPath",
      "ProgramName",
      "BatchValueName",
      "ModifiedTime",
      "Executed",
      "FromSlack"
    ],
    "timestamp": [
      "ModifiedTime"
    ],
    "booleans": [
      "FromSlack"
    ],
    "columns": [
      "CacheEntryPosition",
      "BatchKeyPath",
      "ProgramName",
      "BatchValueName",
      "ModifiedTime",
      "Executed",
      "FromSlack"
    ]
  },
  {
    "name": "RecmdAppCompatFlags",
    "signature": [
      "Executable",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Executable",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdAppCompatFlags2WinRAR",
    "signature": [
      "Path",
      "BatchKeyPath",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Path",
      "BatchKeyPath",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdAppPaths",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "FileName",
      "BatchValueName",
      "Path1",
      "Path2"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "FileName",
      "BatchValueName",
      "Path1",
      "Path2"
    ]
  },
  {
    "name": "RecmdApplicationSettingsContainer",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "ValueType",
      "BatchValueName",
      "Value",
      "Notes",
      "UTCTimestamp"
    ],
    "timestamp": [
      "UTCTimestamp"
    ],
    "booleans": [],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "ValueType",
      "BatchValueName",
      "Value",
      "Notes",
      "UTCTimestamp"
    ]
  },
  {
    "name": "RecmdAres",
    "signature": [
      "PropertyName",
      "BatchKeyPath",
      "PropertyValue",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "PropertyName",
      "BatchKeyPath",
      "PropertyValue",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdBamDam",
    "signature": [
      "Program",
      "BatchKeyPath",
      "ExecutionTime",
      "BatchValueName"
    ],
    "timestamp": [
      "ExecutionTime"
    ],
    "booleans": [],
    "columns": [
      "Program",
      "BatchKeyPath",
      "ExecutionTime",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdBluetoothBthPort",
    "signature": [
      "Name",
      "BatchKeyPath",
      "Address",
      "BatchValueName",
      "LastSeen"
    ],
    "timestamp": [
      "LastSeen"
    ],
    "booleans": [],
    "columns": [
      "Name",
      "BatchKeyPath",
      "Address",
      "BatchValueName",
      "LastSeen"
    ]
  },
  {
    "name": "RecmdCIDSizeMRU",
    "signature": [
      "Executable",
      "BatchKeyPath",
      "MRUPosition",
      "BatchValueName",
      "OpenedOn"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "Executable",
      "BatchKeyPath",
      "MRUPosition",
      "BatchValueName",
      "OpenedOn"
    ]
  },
  {
    "name": "RecmdDHCPNetworkHint",
    "signature": [
      "NetworkHint",
      "BatchKeyPath",
      "DHCPAddress",
      "BatchValueName",
      "DHCPServer",
      "DHCPDomain",
      "LeaseObtained",
      "LeaseExpires",
      "DefaultGateway",
      "Interface",
      "InterfaceSubkey"
    ],
    "timestamp": [
      "LeaseObtained",
      "LeaseExpires"
    ],
    "booleans": [],
    "columns": [
      "NetworkHint",
      "BatchKeyPath",
      "DHCPAddress",
      "BatchValueName",
      "DHCPServer",
      "DHCPDomain",
      "LeaseObtained",
      "LeaseExpires",
      "DefaultGateway",
      "Interface",
      "InterfaceSubkey"
    ]
  },
  {
    "name": "RecmdDeviceClasses",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "GuidFolder",
      "BatchValueName",
      "Type",
      "Name",
      "SerialNumber"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "GuidFolder",
      "BatchValueName",
      "Type",
      "Name",
      "SerialNumber"
    ]
  },
  {
    "name": "RecmdDsrmAdminLogonBehaviour",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "ValueData",
      "BatchValueName",
      "LastWriteTime",
      "PersistenceDetection"
    ],
    "timestamp": [
      "LastWriteTime"
    ],
    "booleans": [
      "PersistenceDetection"
    ],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "ValueData",
      "BatchValueName",
      "LastWriteTime",
      "PersistenceDetection"
    ]
  },
  {
    "name": "RecmdETW",
    "signature": [
      "LastWriteTimestamp",
      "BatchKeyPath",
      "Guid",
      "BatchValueName",
      "Provider",
      "Enabled",
      "EnabledProperty"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "LastWriteTimestamp",
      "BatchKeyPath",
      "Guid",
      "BatchValueName",
      "Provider",
      "Enabled",
      "EnabledProperty"
    ]
  },
  {
    "name": "RecmdFeatureUsage",
    "signature": [
      "KeyPath",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "Count"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "KeyPath",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "Count"
    ]
  },
  {
    "name": "RecmdFileExts",
    "signature": [
      "Extension",
      "BatchKeyPath",
      "OpensWithExecutables",
      "BatchValueName",
      "OpensWithProgramIDs",
      "UserChoice"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Extension",
      "BatchKeyPath",
      "OpensWithExecutables",
      "BatchValueName",
      "OpensWithProgramIDs",
      "UserChoice"
    ]
  },
  {
    "name": "RecmdFirewallRules",
    "signature": [
      "Action",
      "BatchKeyPath",
      "Active",
      "BatchValueName",
      "Dir",
      "Protocol",
      "LPort",
      "RPort",
      "Name",
      "Desc",
      "App"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Action",
      "BatchKeyPath",
      "Active",
      "BatchValueName",
      "Dir",
      "Protocol",
      "LPort",
      "RPort",
      "Name",
      "Desc",
      "App"
    ]
  },
  {
    "name": "RecmdFirstFolder",
    "signature": [
      "Executable",
      "BatchKeyPath",
      "FolderName",
      "BatchValueName",
      "MRUPosition",
      "OpenedOn"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "Executable",
      "BatchKeyPath",
      "FolderName",
      "BatchValueName",
      "MRUPosition",
      "OpenedOn"
    ]
  },
  {
    "name": "RecmdIconLayouts",
    "signature": [
      "Name",
      "BatchKeyPath",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Name",
      "BatchKeyPath",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdInventoryApplication",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Name",
      "BatchValueName",
      "Version",
      "Publisher",
      "Source",
      "RootDirPath",
      "UninstallString"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Name",
      "BatchValueName",
      "Version",
      "Publisher",
      "Source",
      "RootDirPath",
      "UninstallString"
    ]
  },
  {
    "name": "RecmdInventoryApplicationFile",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Path",
      "BatchValueName",
      "Name",
      "ProductName",
      "Publisher",
      "Version",
      "SHA1"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Path",
      "BatchValueName",
      "Name",
      "ProductName",
      "Publisher",
      "Version",
      "SHA1"
    ]
  },
  {
    "name": "RecmdInventoryApplicationShortcut",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Path",
      "BatchValueName"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Path",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdInventoryDeviceContainer",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "ModelName",
      "BatchValueName",
      "FriendlyName",
      "ModelNumber",
      "Manufacturer",
      "PrimaryCategory",
      "ModelID"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "ModelName",
      "BatchValueName",
      "FriendlyName",
      "ModelNumber",
      "Manufacturer",
      "PrimaryCategory",
      "ModelID"
    ]
  },
  {
    "name": "RecmdInventoryDevicePnp",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Model",
      "BatchValueName",
      "Manufacturer",
      "Description",
      "InstallDate",
      "ParentID",
      "MatchingID"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Model",
      "BatchValueName",
      "Manufacturer",
      "Description",
      "InstallDate",
      "ParentID",
      "MatchingID"
    ]
  },
  {
    "name": "RecmdInventoryDriverBinary",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "DriverLastWriteTime",
      "BatchValueName",
      "DriverCompany",
      "Product",
      "ProductVersion",
      "DriverName",
      "DriverVersion",
      "Path",
      "SHA1"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "DriverLastWriteTime",
      "BatchValueName",
      "DriverCompany",
      "Product",
      "ProductVersion",
      "DriverName",
      "DriverVersion",
      "Path",
      "SHA1"
    ]
  },
  {
    "name": "RecmdJumplistData",
    "signature": [
      "JumpListName",
      "BatchKeyPath",
      "ExecutedOn",
      "BatchValueName"
    ],
    "timestamp": [
      "ExecutedOn"
    ],
    "booleans": [],
    "columns": [
      "JumpListName",
      "BatchKeyPath",
      "ExecutedOn",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdKnownNetworks",
    "signature": [
      "FirstNetwork",
      "BatchKeyPath",
      "NetworkName",
      "BatchValueName",
      "NameType",
      "FirstConnectLOCAL",
      "LastConnectedLOCAL",
      "Managed",
      "DNSSuffix",
      "GatewayMacAddress",
      "ProfileGUID"
    ],
    "timestamp": [
      "FirstConnectLOCAL",
      "LastConnectedLOCAL"
    ],
    "booleans": [
      "Managed"
    ],
    "columns": [
      "FirstNetwork",
      "BatchKeyPath",
      "NetworkName",
      "BatchValueName",
      "NameType",
      "FirstConnectLOCAL",
      "LastConnectedLOCAL",
      "Managed",
      "DNSSuffix",
      "GatewayMacAddress",
      "ProfileGUID"
    ]
  },
  {
    "name": "RecmdLastVisitedMRU",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "Executable",
      "Directory",
      "OpenedOn"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "Executable",
      "Directory",
      "OpenedOn"
    ]
  },
  {
    "name": "RecmdLastVisitedPidlMRU",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "Executable",
      "AbsolutePath",
      "OpenedOn",
      "Details"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "Executable",
      "AbsolutePath",
      "OpenedOn",
      "Details"
    ]
  },
  {
    "name": "RecmdMare",
    "signature": [
      "Unknown",
      "BatchKeyPath",
      "Path",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Unknown",
      "BatchKeyPath",
      "Path",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdMountedDevices",
    "signature": [
      "DeviceName",
      "BatchKeyPath",
      "DeviceData",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "DeviceName",
      "BatchKeyPath",
      "DeviceData",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdNetworkAdapters",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "DriverDesc",
      "BatchValueName",
      "DriverDate",
      "DriverVersion",
      "ProviderName",
      "DeviceInstanceid"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "DriverDesc",
      "BatchValueName",
      "DriverDate",
      "DriverVersion",
      "ProviderName",
      "DeviceInstanceid"
    ]
  },
  {
    "name": "RecmdNetworkSettings",
    "signature": [
      "IPAddress",
      "BatchKeyPath",
      "SubnetMask",
      "BatchValueName",
      "DHCPSubnetMask",
      "DHCPServer",
      "DHCPNameServer",
      "DHCPIPAddress",
      "DHCPDefaultGateway",
      "LeaseObtainedTime",
      "LeaseTerminatesTime",
      "EnabledDHCP"
    ],
    "timestamp": [
      "LeaseObtainedTime",
      "LeaseTerminatesTime"
    ],
    "booleans": [
      "EnabledDHCP"
    ],
    "columns": [
      "IPAddress",
      "BatchKeyPath",
      "SubnetMask",
      "BatchValueName",
      "DHCPSubnetMask",
      "DHCPServer",
      "DHCPNameServer",
      "DHCPIPAddress",
      "DHCPDefaultGateway",
      "LeaseObtainedTime",
      "LeaseTerminatesTime",
      "EnabledDHCP"
    ]
  },
  {
    "name": "RecmdNetworkSetup2",
    "signature": [
      "ProtocolList",
      "BatchKeyPath",
      "Alias",
      "BatchValueName",
      "Description",
      "Type",
      "PermanentAddress",
      "CurrentAddress"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "ProtocolList",
      "BatchKeyPath",
      "Alias",
      "BatchValueName",
      "Description",
      "Type",
      "PermanentAddress",
      "CurrentAddress"
    ]
  },
  {
    "name": "RecmdOfficeMRU",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "LastOpened",
      "BatchValueName",
      "LastClosed",
      "FileName"
    ],
    "timestamp": [
      "LastOpened",
      "LastClosed"
    ],
    "booleans": [],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "LastOpened",
      "BatchValueName",
      "LastClosed",
      "FileName"
    ]
  },
  {
    "name": "RecmdOpenSaveMRU",
    "signature": [
      "Extension",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "MruPosition",
      "Filename",
      "OpenedOn"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "Extension",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "MruPosition",
      "Filename",
      "OpenedOn"
    ]
  },
  {
    "name": "RecmdOpenSavePidlMRU",
    "signature": [
      "Extension",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "MruPosition",
      "AbsolutePath",
      "OpenedOn",
      "Details"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "Extension",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "MruPosition",
      "AbsolutePath",
      "OpenedOn",
      "Details"
    ]
  },
  {
    "name": "RecmdProducts",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "DisplayName",
      "BatchValueName",
      "PackageName",
      "InstallDate",
      "Publisher",
      "Language",
      "InstallLocation",
      "InstallSource",
      "Comments"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "DisplayName",
      "BatchValueName",
      "PackageName",
      "InstallDate",
      "Publisher",
      "Language",
      "InstallLocation",
      "InstallSource",
      "Comments"
    ]
  },
  {
    "name": "RecmdProfileList",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "ProfileImagePath",
      "LastLogonTime",
      "LastLogoffTime"
    ],
    "timestamp": [
      "Timestamp",
      "LastLogonTime",
      "LastLogoffTime"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "ProfileImagePath",
      "LastLogonTime",
      "LastLogoffTime"
    ]
  },
  {
    "name": "RecmdRADAR",
    "signature": [
      "KeyName",
      "BatchKeyPath",
      "Filename",
      "BatchValueName",
      "LastDetectionTime"
    ],
    "timestamp": [
      "LastDetectionTime"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "BatchKeyPath",
      "Filename",
      "BatchValueName",
      "LastDetectionTime"
    ]
  },
  {
    "name": "RecmdRecentApps",
    "signature": [
      "KeyName",
      "BatchKeyPath",
      "AppId",
      "BatchValueName",
      "AppPath",
      "LastAccessed",
      "LaunchCount",
      "RecentDocs"
    ],
    "timestamp": [
      "LastAccessed"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "BatchKeyPath",
      "AppId",
      "BatchValueName",
      "AppPath",
      "LastAccessed",
      "LaunchCount",
      "RecentDocs"
    ]
  },
  {
    "name": "RecmdRecentDocs",
    "signature": [
      "Extension",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "TargetName",
      "LnkName",
      "MruPosition",
      "OpenedOn",
      "ExtensionLastOpened"
    ],
    "timestamp": [
      "OpenedOn",
      "ExtensionLastOpened"
    ],
    "booleans": [],
    "columns": [
      "Extension",
      "BatchKeyPath",
      "ValueName",
      "BatchValueName",
      "TargetName",
      "LnkName",
      "MruPosition",
      "OpenedOn",
      "ExtensionLastOpened"
    ]
  },
  {
    "name": "RecmdRunMRU",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "Executable",
      "OpenedOn"
    ],
    "timestamp": [
      "OpenedOn"
    ],
    "booleans": [],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "Executable",
      "OpenedOn"
    ]
  },
  {
    "name": "RecmdSAMBuiltin",
    "signature": [
      "GroupName",
      "BatchKeyPath",
      "Comment",
      "BatchValueName",
      "Users"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "GroupName",
      "BatchKeyPath",
      "Comment",
      "BatchValueName",
      "Users"
    ]
  },
  {
    "name": "RecmdSCSI",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Manufacturer",
      "BatchValueName",
      "Title",
      "SerialNumber",
      "DeviceName",
      "DiskId",
      "InitialTimestamp",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "timestamp": [
      "Timestamp",
      "InitialTimestamp",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Manufacturer",
      "BatchValueName",
      "Title",
      "SerialNumber",
      "DeviceName",
      "DiskId",
      "InitialTimestamp",
      "Installed",
      "FirstInstalled",
      "LastConnected"
    ]
  },
  {
    "name": "RecmdSWD",
    "signature": [
      "Type",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "Service",
      "DeviceDesc",
      "FriendlyName",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "timestamp": [
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "booleans": [],
    "columns": [
      "Type",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "Service",
      "DeviceDesc",
      "FriendlyName",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ]
  },
  {
    "name": "RecmdServices",
    "signature": [
      "Name",
      "BatchKeyPath",
      "Description",
      "BatchValueName",
      "DisplayName",
      "StartMode",
      "ServiceType",
      "NameKeyLastWrite",
      "ParametersKeyLastWrite",
      "Group",
      "ImagePath",
      "ServiceDLL",
      "RequiredPrivileges"
    ],
    "timestamp": [
      "NameKeyLastWrite",
      "ParametersKeyLastWrite"
    ],
    "booleans": [],
    "columns": [
      "Name",
      "BatchKeyPath",
      "Description",
      "BatchValueName",
      "DisplayName",
      "StartMode",
      "ServiceType",
      "NameKeyLastWrite",
      "ParametersKeyLastWrite",
      "Group",
      "ImagePath",
      "ServiceDLL"
    ]
  },
  {
    "name": "RecmdSevenZip",
    "signature": [
      "ArchiveName",
      "BatchKeyPath",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "ArchiveName",
      "BatchKeyPath",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdSevenZipCopyHistory",
    "signature": [
      "CopyPath",
      "BatchKeyPath",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "CopyPath",
      "BatchKeyPath",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdSevenZipFolderHistory",
    "signature": [
      "FolderPath",
      "BatchKeyPath",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "FolderPath",
      "BatchKeyPath",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdSevenZipPathHistory",
    "signature": [
      "ExtractionPath",
      "BatchKeyPath",
      "BatchValueName"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "ExtractionPath",
      "BatchKeyPath",
      "BatchValueName"
    ]
  },
  {
    "name": "RecmdSyscacheObjectTable",
    "signature": [
      "KeyPath",
      "BatchKeyPath",
      "ObjectId",
      "BatchValueName",
      "ObjectLru",
      "Usn",
      "UsnJournalId",
      "MftEntryNumber",
      "MftSequenceNumber",
      "Sha1",
      "AeProgramId",
      "LastWriteTime"
    ],
    "timestamp": [
      "LastWriteTime"
    ],
    "booleans": [],
    "columns": [
      "KeyPath",
      "BatchKeyPath",
      "ObjectId",
      "BatchValueName",
      "ObjectLru",
      "Usn",
      "UsnJournalId",
      "MftEntryNumber",
      "MftSequenceNumber",
      "Sha1",
      "AeProgramId",
      "LastWriteTime"
    ]
  },
  {
    "name": "RecmdTaskCache",
    "signature": [
      "Version",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "Path",
      "CreatedOn",
      "LastStart",
      "LastStop",
      "TaskState",
      "LastActionResult",
      "Source",
      "Description",
      "Command",
      "Arguments",
      "SecurityDescriptor",
      "Author"
    ],
    "timestamp": [
      "CreatedOn",
      "LastStart",
      "LastStop"
    ],
    "booleans": [],
    "columns": [
      "Version",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "Path",
      "CreatedOn",
      "LastStart",
      "LastStop",
      "TaskState",
      "LastActionResult",
      "Source",
      "Description"
    ]
  },
  {
    "name": "RecmdTaskFlowShellActivities",
    "signature": [
      "Position",
      "BatchKeyPath",
      "FullPath",
      "BatchValueName",
      "ExeName",
      "WindowTitle",
      "Other"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "Position",
      "BatchKeyPath",
      "FullPath",
      "BatchValueName",
      "ExeName",
      "WindowTitle",
      "Other"
    ]
  },
  {
    "name": "RecmdTaskband",
    "signature": [
      "LnkName",
      "BatchKeyPath",
      "Executable",
      "BatchValueName",
      "PinType"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "LnkName",
      "BatchKeyPath",
      "Executable",
      "BatchValueName",
      "PinType"
    ]
  },
  {
    "name": "RecmdTerminalServerClient",
    "signature": [
      "HostName",
      "BatchKeyPath",
      "Username",
      "BatchValueName",
      "MRUPosition",
      "LastModified"
    ],
    "timestamp": [
      "LastModified"
    ],
    "booleans": [],
    "columns": [
      "HostName",
      "BatchKeyPath",
      "Username",
      "BatchValueName",
      "MRUPosition",
      "LastModified"
    ]
  },
  {
    "name": "RecmdTimeZoneInfo",
    "signature": [
      "ValueName",
      "BatchKeyPath",
      "ValueData",
      "BatchValueName",
      "ValueDataRaw"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "ValueName",
      "BatchKeyPath",
      "ValueData",
      "BatchValueName",
      "ValueDataRaw"
    ]
  },
  {
    "name": "RecmdTrustedDocuments",
    "signature": [
      "EventType",
      "BatchKeyPath",
      "Timestamp",
      "BatchValueName",
      "FileName",
      "Username"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "EventType",
      "BatchKeyPath",
      "Timestamp",
      "BatchValueName",
      "FileName",
      "Username"
    ]
  },
  {
    "name": "RecmdTypedURLs",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Url",
      "BatchValueName",
      "Slack"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Url",
      "BatchValueName",
      "Slack"
    ]
  },
  {
    "name": "RecmdUSB",
    "signature": [
      "KeyName",
      "BatchKeyPath",
      "SerialNumber",
      "BatchValueName",
      "ParentidPrefix",
      "Service",
      "DeviceDesc",
      "FriendlyName",
      "DeviceName",
      "LocationInformation",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "timestamp": [
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "BatchKeyPath",
      "SerialNumber",
      "BatchValueName",
      "ParentidPrefix",
      "Service",
      "DeviceDesc",
      "FriendlyName",
      "DeviceName",
      "LocationInformation",
      "Installed",
      "FirstInstalled"
    ]
  },
  {
    "name": "RecmdUSBSTOR",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Manufacturer",
      "BatchValueName",
      "Title",
      "Version",
      "SerialNumber",
      "DeviceName",
      "DiskId",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "timestamp": [
      "Timestamp",
      "Installed",
      "FirstInstalled",
      "LastConnected",
      "LastRemoved"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Manufacturer",
      "BatchValueName",
      "Title",
      "Version",
      "SerialNumber",
      "DeviceName",
      "DiskId",
      "Installed",
      "FirstInstalled",
      "LastConnected"
    ]
  },
  {
    "name": "RecmdUnInstall",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "DisplayName",
      "DisplayVersion",
      "Publisher",
      "InstallDate",
      "InstallSource",
      "InstallLocation",
      "UninstallString"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "KeyName",
      "BatchValueName",
      "DisplayName",
      "DisplayVersion",
      "Publisher",
      "InstallDate",
      "InstallSource",
      "InstallLocation",
      "UninstallString"
    ]
  },
  {
    "name": "RecmdUserAccounts",
    "signature": [
      "ValidUserId",
      "BatchKeyPath",
      "BatchValueName",
      "UserId",
      "InvalidLoginCount",
      "TotalLoginCount",
      "CreatedOn",
      "LastLoginTime",
      "LastPasswordChange",
      "LastIncorrectPassword",
      "ExpiresOn",
      "UserName",
      "FullName",
      "PasswordHint",
      "Groups",
      "Comment",
      "UserComment",
      "HomeDirectory",
      "InternetUserName",
      "ResetData",
      "AccountDisabled",
      "HomeDirectoryRequired",
      "PasswordNotRequired",
      "TempDuplicateAccount",
      "NormalUserAccount",
      "MnsLogonAccount",
      "InterdomainTrustAccount",
      "WorkstationTrustAccount",
      "ServerTrustAccount",
      "PasswordDoesNotExpire",
      "AutoLocked"
    ],
    "timestamp": [
      "CreatedOn",
      "LastLoginTime",
      "LastPasswordChange",
      "LastIncorrectPassword",
      "ExpiresOn"
    ],
    "booleans": [
      "ValidUserId",
      "AccountDisabled",
      "HomeDirectoryRequired",
      "PasswordNotRequired",
      "TempDuplicateAccount",
      "NormalUserAccount",
      "MnsLogonAccount",
      "InterdomainTrustAccount",
      "WorkstationTrustAccount",
      "ServerTrustAccount",
      "PasswordDoesNotExpire",
      "AutoLocked"
    ],
    "columns": [
      "ValidUserId",
      "BatchKeyPath",
      "BatchValueName",
      "UserId",
      "InvalidLoginCount",
      "TotalLoginCount",
      "CreatedOn",
      "LastLoginTime",
      "LastPasswordChange",
      "LastIncorrectPassword",
      "ExpiresOn",
      "UserName"
    ]
  },
  {
    "name": "RecmdUserAssist",
    "signature": [
      "BatchKeyPath",
      "BatchValueName",
      "ProgramName",
      "RunCounter",
      "FocusCount",
      "FocusTime",
      "LastExecuted"
    ],
    "timestamp": [
      "LastExecuted"
    ],
    "booleans": [],
    "columns": [
      "BatchKeyPath",
      "BatchValueName",
      "ProgramName",
      "RunCounter",
      "FocusCount",
      "FocusTime",
      "LastExecuted"
    ]
  },
  {
    "name": "RecmdVolumeInfoCache",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "DriveName",
      "BatchValueName",
      "VolumeLabel",
      "DriveType"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "DriveName",
      "BatchValueName",
      "VolumeLabel",
      "DriveType"
    ]
  },
  {
    "name": "RecmdWindowsApp",
    "signature": [
      "KeyName",
      "BatchKeyPath",
      "DisplayName",
      "BatchValueName",
      "InstallTime",
      "PackageRootFolder"
    ],
    "timestamp": [
      "InstallTime"
    ],
    "booleans": [],
    "columns": [
      "KeyName",
      "BatchKeyPath",
      "DisplayName",
      "BatchValueName",
      "InstallTime",
      "PackageRootFolder"
    ]
  },
  {
    "name": "RecmdWindowsPortableDevices",
    "signature": [
      "Timestamp",
      "BatchKeyPath",
      "Device",
      "BatchValueName",
      "SerialNumber",
      "Guid",
      "FriendlyName"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "BatchKeyPath",
      "Device",
      "BatchValueName",
      "SerialNumber",
      "Guid",
      "FriendlyName"
    ]
  },
  {
    "name": "RecmdWordWheelQuery",
    "signature": [
      "SearchTerm",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "KeyName",
      "LastWriteTimestamp"
    ],
    "timestamp": [
      "LastWriteTimestamp"
    ],
    "booleans": [],
    "columns": [
      "SearchTerm",
      "BatchKeyPath",
      "MruPosition",
      "BatchValueName",
      "KeyName",
      "LastWriteTimestamp"
    ]
  },
  {
    "name": "I30",
    "signature": [
      "Offset",
      "FromSlack",
      "SelfMftEntry",
      "SelfMftSequence",
      "FileName",
      "Flags",
      "NameType",
      "ParentMftEntry",
      "ParentMftSequence",
      "CreatedOn",
      "ContentModifiedOn",
      "RecordModifiedOn",
      "LastAccessedOn",
      "PhysicalSize",
      "LogicalSize",
      "SourceFile"
    ],
    "timestamp": [
      "CreatedOn",
      "ContentModifiedOn",
      "RecordModifiedOn",
      "LastAccessedOn"
    ],
    "booleans": [
      "FromSlack"
    ],
    "columns": [
      "Offset",
      "FromSlack",
      "SelfMftEntry",
      "SelfMftSequence",
      "FileName",
      "Flags",
      "NameType",
      "ParentMftEntry",
      "ParentMftSequence",
      "CreatedOn",
      "ContentModifiedOn",
      "RecordModifiedOn"
    ]
  },
  {
    "name": "RecentFileCache",
    "signature": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "Filename"
    ],
    "timestamp": [
      "SourceCreated",
      "SourceModified",
      "SourceAccessed"
    ],
    "booleans": [],
    "columns": [
      "SourceFile",
      "SourceCreated",
      "SourceModified",
      "SourceAccessed",
      "Filename"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "cs(Referer)",
      "sc-status",
      "sc-substatus",
      "sc-win32-status",
      "time-taken",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "cs(Referer)",
      "sc-status"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "date",
      "time",
      "s-sitename",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "sc-status",
      "sc-substatus",
      "sc-win32-status",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "s-sitename",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "sc-status"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "date",
      "time",
      "s-sitename",
      "s-computername",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs-version",
      "cs(User-Agent)",
      "cs(Cookie)",
      "cs(Referer)",
      "cs-host",
      "sc-status",
      "sc-substatus",
      "sc-win32-status",
      "sc-bytes",
      "cs-bytes",
      "time-taken",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "s-sitename",
      "s-computername",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs-version"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "cs(Cookie)",
      "cs(Referer)",
      "sc-status",
      "sc-substatus",
      "sc-win32-status",
      "time-taken",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "cs(Cookie)",
      "cs(Referer)"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "sc-status",
      "sc-substatus",
      "sc-win32-status",
      "time-taken",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "sc-status",
      "sc-substatus"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "sc-status",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs(User-Agent)",
      "sc-status",
      "GeoCity"
    ]
  },
  {
    "name": "IisGeolocate",
    "signature": [
      "time",
      "s-sitename",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs-version",
      "cs(User-Agent)",
      "sc-status",
      "sc-substatus",
      "sc-win32-status",
      "GeoCity",
      "GeoCountry"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "time",
      "s-sitename",
      "s-ip",
      "cs-method",
      "cs-uri-stem",
      "cs-uri-query",
      "s-port",
      "cs-username",
      "c-ip",
      "cs-version",
      "cs(User-Agent)",
      "sc-status"
    ]
  },
  {
    "name": "SqleActivitiesCache",
    "signature": [
      "Id",
      "Payload",
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedInCloud",
      "StartTime",
      "EndTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient",
      "ActivityType",
      "IsLocalOnly",
      "ETag",
      "PackageIdHash",
      "PlatformDeviceId",
      "SourceFile"
    ],
    "timestamp": [
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedInCloud",
      "StartTime",
      "EndTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient"
    ],
    "booleans": [],
    "columns": [
      "Id",
      "Payload",
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedInCloud",
      "StartTime",
      "EndTime",
      "LastModifiedOnClient",
      "OriginalLastModifiedOnClient",
      "ActivityType",
      "IsLocalOnly",
      "ETag"
    ]
  },
  {
    "name": "SqleActivityPackageId",
    "signature": [
      "ActivityId",
      "Platform",
      "PackageName",
      "ExpirationTime",
      "SourceFile"
    ],
    "timestamp": [
      "ExpirationTime"
    ],
    "booleans": [],
    "columns": [
      "ActivityId",
      "Platform",
      "PackageName",
      "ExpirationTime",
      "SourceFile"
    ]
  },
  {
    "name": "SqleActivityOperation",
    "signature": [
      "OperationOrder",
      "AppId",
      "ActivityType",
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedTime",
      "EndTime",
      "LastModifiedOnClient",
      "PlatformDeviceId",
      "SourceFile"
    ],
    "timestamp": [
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedTime",
      "EndTime",
      "LastModifiedOnClient"
    ],
    "booleans": [],
    "columns": [
      "OperationOrder",
      "AppId",
      "ActivityType",
      "LastModifiedTime",
      "ExpirationTime",
      "CreatedTime",
      "EndTime",
      "LastModifiedOnClient",
      "PlatformDeviceId",
      "SourceFile"
    ]
  },
  {
    "name": "KapeCopyLog",
    "signature": [
      "CopiedTimestamp",
      "SourceFile",
      "DestinationFile",
      "FileSize",
      "SourceFileSha1",
      "DeferredCopy",
      "CreatedOnUtc",
      "ModifiedOnUtc",
      "LastAccessedOnUtc",
      "CopyDuration"
    ],
    "timestamp": [
      "CopiedTimestamp",
      "CreatedOnUtc",
      "ModifiedOnUtc",
      "LastAccessedOnUtc"
    ],
    "booleans": [
      "DeferredCopy"
    ],
    "columns": [
      "CopiedTimestamp",
      "SourceFile",
      "DestinationFile",
      "FileSize",
      "SourceFileSha1",
      "DeferredCopy",
      "CreatedOnUtc",
      "ModifiedOnUtc",
      "LastAccessedOnUtc",
      "CopyDuration"
    ]
  },
  {
    "name": "KapeSkipLog",
    "signature": [
      "SourceFile",
      "SourceFileSha1",
      "Reason"
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "SourceFile",
      "SourceFileSha1",
      "Reason"
    ]
  },
  {
    "name": "KapeTriage",
    "signature": [
      "datetimeutc",
      "eventtimesource",
      "hostname",
      "hostipaddress",
      "userid",
      "assessment",
      "eventtype",
      "eventdetails",
      "sdipaddress",
      "examinercomments",
      "md5",
      "eventaddedby",
      "dateadded",
      "rawevent"
    ],
    "timestamp": [
      "DateTimeUTC",
      "DateAdded"
    ],
    "booleans": [],
    "columns": [
      "datetimeutc",
      "eventtimesource",
      "hostname",
      "hostipaddress",
      "userid",
      "assessment",
      "eventtype",
      "eventdetails",
      "sdipaddress",
      "examinercomments",
      "md5",
      "eventaddedby"
    ]
  },
  {
    "name": "Sigcheck",
    "signature": [
      "path",
      "verified",
      "date",
      "publisher",
      "company",
      "description",
      "product",
      "product version",
      "file version",
      "machine type",
      "md5",
      "sha1",
      "pesha1",
      "pesha256",
      "sha256",
      "imp",
      "vt detection",
      "vt link"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [
      "Verified"
    ],
    "columns": [
      "path",
      "verified",
      "date",
      "publisher",
      "company",
      "description",
      "product",
      "product version",
      "file version",
      "machine type",
      "md5",
      "sha1"
    ]
  },
  {
    "name": "SigcheckTroy",
    "signature": [
      "path",
      "verified",
      "date",
      "publisher",
      "company",
      "description",
      "product",
      "product version",
      "file version",
      "machine type",
      "binary version",
      "original name",
      "internal name",
      "copyright",
      "comments",
      "entropy",
      "md5",
      "sha1",
      "pesha1",
      "pesha256",
      "sha256",
      "imp"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [
      "Verified"
    ],
    "columns": [
      "path",
      "verified",
      "date",
      "publisher",
      "company",
      "description",
      "product",
      "product version",
      "file version",
      "machine type",
      "binary version",
      "original name"
    ]
  },
  {
    "name": "Autoruns",
    "signature": [
      "time",
      "entry location",
      "entry",
      "enabled",
      "category",
      "profile",
      "description",
      "signer",
      "company",
      "image path",
      "version",
      "launch string",
      "md5",
      "sha-1",
      "pesha-1",
      "pesha-256",
      "sha-256",
      "imp",
      "pscomputername",
      "runspaceid",
      "psshowcomputername"
    ],
    "timestamp": [
      "Time"
    ],
    "booleans": [
      "Enabled"
    ],
    "columns": [
      "time",
      "entry location",
      "entry",
      "enabled",
      "category",
      "profile",
      "description",
      "signer",
      "company",
      "image path",
      "version",
      "launch string"
    ]
  },
  {
    "name": "MsftMft",
    "signature": [
      "segmentnumber\tinuse\treferencecount\tisdirectory\tisstream\tfilename\tfilesize\textension\tcreationtime0x10\tlastmodificationtime0x10\tlastchangetime0x10\tlastaccesstime0x10\tlastmodificationtime0x30\tcreationtime0x30\tlastchangetime0x30\tlastaccesstime0x30\tpath\tparentfrs\townerid\tsecurityid\thasea\tisreadonly\tishidden\tissystem\tisarchive\tisnormal\tistemporary\tissparse\tisreparsepoint\tiscompressed\tisoffline\tisnotcontentindexed\tisencrypted\tisintegritystream\tisvirtual\tisnoscrubdata\tisea\tloggedutilitystream\tsequencenumber\tparseerrormsg"
    ],
    "timestamp": [
      "CreationTime0x10",
      "LastModificationTime0x10",
      "LastChangeTime0x10",
      "LastAccessTime0x10",
      "LastModificationTime0x30",
      "CreationTime0x30",
      "LastChangeTime0x30",
      "LastAccessTime0x30"
    ],
    "booleans": [
      "InUse",
      "IsDirectory",
      "IsStream",
      "HasEA",
      "IsReadOnly",
      "IsHidden",
      "IsSystem",
      "IsArchive",
      "IsNormal",
      "IsTemporary",
      "IsSparse",
      "IsReparsePoint",
      "IsCompressed",
      "IsOffline",
      "IsNotContentIndexed",
      "IsEncrypted",
      "IsIntegrityStream",
      "IsVirtual",
      "IsNoScrubData",
      "IsEA"
    ],
    "columns": [
      "segmentnumber\tinuse\treferencecount\tisdirectory\tisstream\tfilename\tfilesize\textension\tcreationtime0x10\tlastmodificationtime0x10\tlastchangetime0x10\tlastaccesstime0x10\tlastmodificationtime0x30\tcreationtime0x30\tlastchangetime0x30\tlastaccesstime0x30\tpath\tparentfrs\townerid\tsecurityid\thasea\tisreadonly\tishidden\tissystem\tisarchive\tisnormal\tistemporary\tissparse\tisreparsepoint\tiscompressed\tisoffline\tisnotcontentindexed\tisencrypted\tisintegritystream\tisvirtual\tisnoscrubdata\tisea\tloggedutilitystream\tsequencenumber\tparseerrormsg"
    ]
  },
  {
    "name": "HayabusaStandard",
    "signature": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "RecordID",
      "Details",
      "ExtraFieldInfo"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "RecordID",
      "Details",
      "ExtraFieldInfo"
    ]
  },
  {
    "name": "HayabusaVerbose",
    "signature": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "MitreTactics",
      "MitreTags",
      "OtherTags",
      "RecordID",
      "Details",
      "ExtraFieldInfo",
      "RuleFile",
      "EvtxFile"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "MitreTactics",
      "MitreTags",
      "OtherTags",
      "RecordID",
      "Details",
      "ExtraFieldInfo"
    ]
  },
  {
    "name": "HayabusaSuperVerbose",
    "signature": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "RuleAuthor",
      "RuleModifiedDate",
      "Status",
      "RecordID",
      "Details",
      "ExtraFieldInfo",
      "MitreTactics",
      "MitreTags",
      "OtherTags",
      "Provider",
      "RuleCreationDate",
      "RuleFile",
      "EvtxFile"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "RuleAuthor",
      "RuleModifiedDate",
      "Status",
      "RecordID",
      "Details",
      "ExtraFieldInfo"
    ]
  },
  {
    "name": "HayabusaMinimal",
    "signature": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "RecordID",
      "Details"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Timestamp",
      "RuleTitle",
      "Level",
      "Computer",
      "Channel",
      "EventID",
      "RecordID",
      "Details"
    ]
  },
  {
    "name": "ChainsawSigma",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "count",
      "Event.System.Provider",
      "Event ID",
      "Record ID",
      "Computer",
      "Event Data"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "count",
      "Event.System.Provider",
      "Event ID",
      "Record ID",
      "Computer",
      "Event Data"
    ]
  },
  {
    "name": "ChainsawAntivirus",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "Threat Name",
      "Threat Path",
      "SHA1",
      "User",
      "Threat Type"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "Threat Name",
      "Threat Path",
      "SHA1",
      "User",
      "Threat Type"
    ]
  },
  {
    "name": "ChainsawAccountTampering",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User",
      "User SID",
      "Member SID"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User",
      "User SID",
      "Member SID"
    ]
  },
  {
    "name": "ChainsawCredentialAccess",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Computer",
      "User",
      "Service Name",
      "IP Address"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Computer",
      "User",
      "Service Name",
      "IP Address"
    ]
  },
  {
    "name": "ChainsawLateralMovement",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User",
      "Logon Type",
      "IP Address",
      "Process Name",
      "Process ID",
      "Interface Index",
      "Source Address",
      "Source Port",
      "Dest Address",
      "Dest Port"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User",
      "Logon Type",
      "IP Address",
      "Process Name",
      "Process ID",
      "Interface Index"
    ]
  },
  {
    "name": "ChainsawLateralMovementOld",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User",
      "Logon Type",
      "IP Address"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User",
      "Logon Type",
      "IP Address"
    ]
  },
  {
    "name": "ChainsawRDSPowerShellScript",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "Information"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "Information"
    ]
  },
  {
    "name": "ChainsawRDSWebAccess",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "IpAddress",
      "LogonType",
      "TargetUserName",
      "WorkstationName"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "IpAddress",
      "LogonType",
      "TargetUserName",
      "WorkstationName"
    ]
  },
  {
    "name": "ChainsawLogTampering",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User"
    ]
  },
  {
    "name": "ChainsawPowerShellEngineState",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "HostName",
      "HostVersion",
      "HostApplication",
      "PipelineId",
      "CommandName",
      "CommandType",
      "ScriptName",
      "CommandPath",
      "CommandLine"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "HostName",
      "HostVersion",
      "HostApplication",
      "PipelineId",
      "CommandName",
      "CommandType"
    ]
  },
  {
    "name": "ChainsawLoginAttacks",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "count",
      "Event ID",
      "User"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "count",
      "Event ID",
      "User"
    ]
  },
  {
    "name": "ChainsawIndicatorRemoval",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User Name",
      "Scheduled Task Name"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User Name",
      "Scheduled Task Name"
    ]
  },
  {
    "name": "ChainsawPersistence",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User Name",
      "Scheduled Task Name",
      "Domain Name",
      "Logon ID",
      "Parent Process Name",
      "Parent Process Command Line",
      "New Process Name",
      "New Process ID"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "User Name",
      "Scheduled Task Name",
      "Domain Name",
      "Logon ID",
      "Parent Process Name",
      "Parent Process Command Line"
    ]
  },
  {
    "name": "ChainsawRDPAttacks",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "event id",
      "computer",
      "ip address",
      "username",
      "provider",
      "logon type",
      "record id",
      "domain"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "event id",
      "computer",
      "ip address",
      "username",
      "provider",
      "logon type",
      "record id",
      "domain"
    ]
  },
  {
    "name": "ChainsawRasVPN",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Provider",
      "Computer",
      "Data"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Provider",
      "Computer",
      "Data"
    ]
  },
  {
    "name": "ChainsawServiceInstallation",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "Service Name",
      "Service File Name",
      "Service Type",
      "Service Start Type",
      "Service Account"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "Service Name",
      "Service File Name",
      "Service Type",
      "Service Start Type",
      "Service Account"
    ]
  },
  {
    "name": "ChainsawServiceTampering",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Username",
      "Computer",
      "Command",
      "Old Value",
      "New Value",
      "Service",
      "Old State",
      "New State",
      "SID",
      "Record ID",
      "Service Name",
      "Action"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Username",
      "Computer",
      "Command",
      "Old Value",
      "New Value",
      "Service",
      "Old State",
      "New State"
    ]
  },
  {
    "name": "ChainsawAppLocker",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "TargetUser",
      "FullFilePath"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Channel",
      "Computer",
      "TargetUser",
      "FullFilePath"
    ]
  },
  {
    "name": "ChainsawDefenseEvasion",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "Service Name",
      "Old Startup Type",
      "Current Startup Type"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "Event ID",
      "Record ID",
      "Computer",
      "Service Name",
      "Old Startup Type",
      "Current Startup Type"
    ]
  },
  {
    "name": "ChainsawMFT",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "FileNamePath",
      "StandardInfoLastModified0x10",
      "StandardInfoLastAccess0x10",
      "FileNameCreated0x30",
      "FileNameLastModified0x30",
      "FileNameLastAccess0x30",
      "FileSize",
      "IsADirectory",
      "IsDeleted",
      "HasAlternateDataStreams"
    ],
    "timestamp": [
      "Timestamp",
      "StandardInfoLastModified0x10",
      "StandardInfoLastAccess0x10",
      "FileNameCreated0x30",
      "FileNameLastModified0x30",
      "FileNameLastAccess0x30"
    ],
    "booleans": [
      "Directory",
      "Deleted",
      "HasAlternateDataStreams"
    ],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "FileNamePath",
      "StandardInfoLastModified0x10",
      "StandardInfoLastAccess0x10",
      "FileNameCreated0x30",
      "FileNameLastModified0x30",
      "FileNameLastAccess0x30",
      "FileSize",
      "IsADirectory",
      "IsDeleted"
    ]
  },
  {
    "name": "ChainsawMFTDataStreams",
    "signature": [
      "timestamp",
      "detections",
      "path",
      "FileNamePath",
      "StandardInfoLastModified0x10",
      "StandardInfoLastAccess0x10",
      "FileNameCreated0x30",
      "FileNameLastModified0x30",
      "FileNameLastAccess0x30",
      "FileSize",
      "IsADirectory",
      "IsDeleted",
      "HasAlternateDataStreams",
      "DataStreams"
    ],
    "timestamp": [
      "Timestamp",
      "StandardInfoLastModified0x10",
      "StandardInfoLastAccess0x10",
      "FileNameCreated0x30",
      "FileNameLastModified0x30",
      "FileNameLastAccess0x30"
    ],
    "booleans": [
      "Directory",
      "Deleted",
      "HasAlternateDataStreams"
    ],
    "columns": [
      "timestamp",
      "detections",
      "path",
      "FileNamePath",
      "StandardInfoLastModified0x10",
      "StandardInfoLastAccess0x10",
      "FileNameCreated0x30",
      "FileNameLastModified0x30",
      "FileNameLastAccess0x30",
      "FileSize",
      "IsADirectory",
      "IsDeleted"
    ]
  },
  {
    "name": "AnalyzeMft",
    "signature": [
      "record number",
      "good",
      "active",
      "record type",
      "sequence number",
      "parent file rec. #",
      "parent file rec. seq. #",
      "filename #1",
      "std info creation date",
      "std info modification date",
      "std info access date",
      "std info entry date",
      "fn info creation date",
      "fn info modification date",
      "fn info access date",
      "fn info entry date",
      "object id",
      "birth volume id",
      "birth object id",
      "birth domain id",
      "filename #2",
      "fn info creation date",
      "fn info modify date",
      "fn info access date",
      "fn info entry date",
      "filename #3",
      "fn info creation date",
      "fn info modify date",
      "fn info access date",
      "fn info entry date",
      "filename #4",
      "fn info creation date",
      "fn info modify date",
      "fn info access date",
      "fn info entry date",
      "standard information",
      "attribute list",
      "filename",
      "object id",
      "volume name",
      "volume info",
      "data",
      "index root",
      "index allocation",
      "bitmap",
      "reparse point",
      "ea information",
      "ea",
      "property set",
      "logged utility stream",
      "log/notes",
      "stf fn shift",
      "usec zero",
      "ads"
    ],
    "timestamp": [
      "StdInfoCreated",
      "StdInfoModified",
      "StdInfoAccessed",
      "StdInfoEntryDate",
      "FileNameCreated",
      "FileNameModified",
      "FileNameAccessed",
      "FileNameEntryDate",
      "FileNameCreated2",
      "FileNameModified2",
      "FileNameAccessed2",
      "FileNameEntryDate2",
      "FileNameCreated3",
      "FileNameModified3",
      "FileNameAccessed3",
      "FileNameEntryDate3",
      "FileNameCreated4",
      "FileNameModified4",
      "FileNameAccessed4",
      "FileNameEntryDate4"
    ],
    "booleans": [
      "Good",
      "Active",
      "StandardInformation",
      "AttributeList",
      "Filename",
      "ObjectId2",
      "VolumeName",
      "VolumeInfo",
      "Data",
      "IndexRoot",
      "IndexAllocation",
      "Bitmap",
      "ReparsePoint",
      "EaInformation",
      "Ea",
      "PropertySet",
      "LoggedUtilityStream",
      "StfFnShift",
      "uSecZero",
      "Ads"
    ],
    "columns": [
      "record number",
      "good",
      "active",
      "record type",
      "sequence number",
      "parent file rec. #",
      "parent file rec. seq. #",
      "filename #1",
      "std info creation date",
      "std info modification date",
      "std info access date",
      "std info entry date"
    ]
  },
  {
    "name": "BrowsingHistoryView251AndNewer",
    "signature": [
      "URL",
      "Title",
      "Visit Time",
      "Visit Count",
      "Visited From",
      "Visit Type",
      "Visit Duration",
      "Web Browser",
      "User Profile",
      "Browser Profile",
      "URL Length",
      "Typed Count",
      "History File",
      "Record ID"
    ],
    "timestamp": [
      "VisitTime"
    ],
    "booleans": [],
    "columns": [
      "URL",
      "Title",
      "Visit Time",
      "Visit Count",
      "Visited From",
      "Visit Type",
      "Visit Duration",
      "Web Browser",
      "User Profile",
      "Browser Profile",
      "URL Length",
      "Typed Count"
    ]
  },
  {
    "name": "BrowsingHistoryView250AndOlder",
    "signature": [
      "url",
      "title",
      "visit time",
      "visit count",
      "visited from",
      "visit type",
      "web browser",
      "user profile",
      "browser profile",
      "url length",
      "typed count",
      "history file",
      "record id"
    ],
    "timestamp": [
      "VisitTime"
    ],
    "booleans": [],
    "columns": [
      "url",
      "title",
      "visit time",
      "visit count",
      "visited from",
      "visit type",
      "web browser",
      "user profile",
      "browser profile",
      "url length",
      "typed count",
      "history file"
    ]
  },
  {
    "name": "CrowdStrikeEvent",
    "signature": [
      "timestamp",
      "treeid",
      "patternid",
      "parent process id",
      "process id",
      "event",
      "file loaded/executed",
      "domain",
      "destip",
      "file accessed/written",
      "usersid_readable",
      "username",
      "attributes",
      "aid"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "timestamp",
      "treeid",
      "patternid",
      "parent process id",
      "process id",
      "event",
      "file loaded/executed",
      "domain",
      "destip",
      "file accessed/written",
      "usersid_readable",
      "username"
    ]
  },
  {
    "name": "ShimcacheParser",
    "signature": [
      "last modified",
      "last update",
      "path",
      "file size",
      "exec flag"
    ],
    "timestamp": [
      "LastModified",
      "LastUpdate"
    ],
    "booleans": [
      "Executed"
    ],
    "columns": [
      "last modified",
      "last update",
      "path",
      "file size",
      "exec flag"
    ]
  },
  {
    "name": "ShimcacheVolatility",
    "signature": [
      "order",
      "last modified",
      "last update",
      "exec flag",
      "file size",
      "file path"
    ],
    "timestamp": [
      "LastModified",
      "LastUpdate"
    ],
    "booleans": [
      "Executed"
    ],
    "columns": [
      "order",
      "last modified",
      "last update",
      "exec flag",
      "file size",
      "file path"
    ]
  },
  {
    "name": "DensityScout",
    "signature": [
      "("
    ],
    "timestamp": [],
    "booleans": [],
    "columns": [
      "("
    ]
  },
  {
    "name": "VanillaWindowsReference",
    "signature": [
      "directoryname",
      "name",
      "fullname",
      "length",
      "creationtimeutc",
      "lastaccesstimeutc",
      "lastwritetimeutc",
      "attributes",
      "md5",
      "sha256",
      "sddl"
    ],
    "timestamp": [
      "CreationTimeUtc",
      "LastAccessTimeUtc",
      "LastWriteTimeUtc"
    ],
    "booleans": [],
    "columns": [
      "directoryname",
      "name",
      "fullname",
      "length",
      "creationtimeutc",
      "lastaccesstimeutc",
      "lastwritetimeutc",
      "attributes",
      "md5",
      "sha256",
      "sddl"
    ]
  },
  {
    "name": "EVTXETWResources",
    "signature": [
      "Event ID",
      "Event Version",
      "Level",
      "Channel",
      "Task",
      "Opcode",
      "Keyword",
      "Windows",
      "Version",
      "Edition",
      "Date",
      "Build",
      "Event Message",
      "Event Fields"
    ],
    "timestamp": [
      "Date"
    ],
    "booleans": [],
    "columns": [
      "Event ID",
      "Event Version",
      "Level",
      "Channel",
      "Task",
      "Opcode",
      "Keyword",
      "Windows",
      "Version",
      "Edition",
      "Date",
      "Build"
    ]
  },
  {
    "name": "ConvertPSHistoryToCSV",
    "signature": [
      "User",
      "CommandIndex",
      "Command",
      "ExecutionTimestamp",
      "File"
    ],
    "timestamp": [
      "ExecutionTimestamp"
    ],
    "booleans": [],
    "columns": [
      "User",
      "CommandIndex",
      "Command",
      "ExecutionTimestamp",
      "File"
    ]
  },
  {
    "name": "PeScan",
    "signature": [
      "compiled",
      "time-UTC",
      "created",
      "time-UTC",
      "access",
      "time-UTC",
      "modify",
      "time-UTC",
      "size",
      "type",
      "cpu",
      "linker",
      "code size",
      "init data",
      "uninit data",
      "image ver",
      "subsys ver",
      "min OS",
      "entry rva",
      "entryfaddr",
      "imagebase",
      "cert",
      "chksum",
      "md5",
      "company",
      "file",
      "rating",
      "notes",
      "PEiD",
      "symbol file"
    ],
    "timestamp": [
      "CompiledTime",
      "CreatedTime",
      "AccessedTime",
      "ModifiedTime"
    ],
    "booleans": [
      "Signed",
      "CheckSum"
    ],
    "columns": [
      "compiled",
      "time-UTC",
      "created",
      "time-UTC",
      "access",
      "time-UTC",
      "modify",
      "time-UTC",
      "size",
      "type",
      "cpu",
      "linker"
    ]
  },
  {
    "name": "Wisp",
    "signature": [
      "mft entry",
      "mft seq",
      "parent mft",
      "seqnum",
      "type",
      "file mdate",
      "time-UTC",
      "file adate",
      "time-UTC",
      "mftdate",
      "time-UTC",
      "file cdate",
      "time-UTC",
      "dir/file",
      "size resv",
      "size used",
      "flags",
      "name",
      "slack comment"
    ],
    "timestamp": [
      "AccessedTime",
      "ModifiedTime",
      "CreatedTime",
      "RecordChangedTime"
    ],
    "booleans": [],
    "columns": [
      "mft entry",
      "mft seq",
      "parent mft",
      "seqnum",
      "type",
      "file mdate",
      "time-UTC",
      "file adate",
      "time-UTC",
      "mftdate",
      "time-UTC",
      "file cdate"
    ]
  },
  {
    "name": "ForensicTimeline",
    "signature": [
      "DateTime",
      "TimestampInfo",
      "ArtifactName",
      "Tool",
      "Description",
      "DataDetails",
      "DataPath",
      "FileExtension",
      "EventId",
      "User",
      "Computer",
      "FileSize",
      "IPAddress",
      "SourceAddress",
      "DestinationAddress",
      "SHA1",
      "Count",
      "EvidencePath",
      "RawData"
    ],
    "timestamp": [
      "DateTime"
    ],
    "booleans": [],
    "columns": [
      "DateTime",
      "TimestampInfo",
      "ArtifactName",
      "Tool",
      "Description",
      "DataDetails",
      "DataPath",
      "FileExtension",
      "EventId",
      "User",
      "Computer",
      "FileSize"
    ]
  },
  {
    "name": "PsortTimeline",
    "signature": [
      "datetime",
      "timestamp_desc",
      "source",
      "source_long",
      "message",
      "parser",
      "display_name",
      "tag"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "datetime",
      "timestamp_desc",
      "source",
      "source_long",
      "message",
      "parser",
      "display_name",
      "tag"
    ]
  },
  {
    "name": "SuperTimeline",
    "signature": [
      "date",
      "time",
      "timezone",
      "macb",
      "source",
      "sourcetype",
      "type",
      "user",
      "host",
      "short",
      "desc",
      "version",
      "filename",
      "inode",
      "notes",
      "format",
      "extra"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "time",
      "timezone",
      "macb",
      "source",
      "sourcetype",
      "type",
      "user",
      "host",
      "short",
      "desc",
      "version"
    ]
  },
  {
    "name": "MacTime",
    "signature": [
      "date",
      "size",
      "type",
      "mode",
      "uid",
      "gid",
      "meta",
      "file name"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "date",
      "size",
      "type",
      "mode",
      "uid",
      "gid",
      "meta",
      "file name"
    ]
  },
  {
    "name": "KapeMiniTimeline",
    "signature": [
      "Time",
      "Type",
      "ComputerName",
      "User/Source",
      "Message"
    ],
    "timestamp": [
      "Timestamp"
    ],
    "booleans": [],
    "columns": [
      "Time",
      "Type",
      "ComputerName",
      "User/Source",
      "Message"
    ]
  }
]

