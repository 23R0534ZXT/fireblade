# Kagarasu Host 0.10.1 qualification

## Investigation workflow

- Chromium exercises tagging a source row, filtering the investigation log and downloading
  the workbook. The API verifies that the same observation remains linked to its source
  row when changing from the combined layout to individual files.
- Incident intake is filled, exported to Word and reopened with the saved description.
  A synthetic case is erased and its HTML and Word records are opened outside its folder.
- The correlation fixture links process, file and network rows using a shared process
  identifier on the same host. A record from another machine, a record before process
  creation and an identifier in a different namespace are excluded. Chromium opens the
  original row from the correlation view.
- Four supplied Office templates were loaded privately and their resulting documents
  reopened with synthetic case data. The repository carries generated layouts and test
  fixtures only.

## Disk images

- A FAT E01 is navigated in Chromium, and a file is previewed, collected and downloaded.
  The original image hash remains unchanged.
- An NTFS E01 exposes `$Extend/$UsnJrnl:$J`. Its copy has the same SHA-256 as the bytes
  read from the image. The stream contains a synthetic USN v2 file-creation record that
  Dissect decodes after extraction. The packaged MFTECmd reader also completes the
  analysis of the extracted journal on the qualification container. [Fixture provenance](../../../../tests/data/ewf/PROVENANCE.md)

## Draft rewriting

A real local llama.cpp server running Qwen3 0.6B received synthetic French and English
drafts through the Host API. Both accepted rewrites preserved the source IP, host, time
and UTC marker. An unchanged proposal was rejected. Automated tests also reject a
proposal that substitutes an identifier and verify that the browser leaves the draft
intact until the analyst chooses **Use suggestion**.

## Boundaries

- Correlation supports compatible structured exports. Evidence that shares a timestamp
  alone is available through the analyst's tagged chronology. The correlation UI
  reports when the candidate cap is reached.
- The Office templates are mounted by the operator. Word destruction records carry
  verification results and signature fields. The record documents the applied erasure
  method and retains the storage limitations stated by the HTML certificate.
