# E01 fixture

`image.E01` is the single-segment EWF sample published in the `dissect.evidence`
repository (`tests/_data/ewf/single/image.E01`, commit
`b2d1ac23288a0a77b1e6158b2dfcad0c945c5d2d`), fetched from
`https://media.githubusercontent.com/media/fox-it/dissect.evidence/<commit>/tests/_data/ewf/single/image.E01`.

SHA-256 `fbc3da213475f9692be6bf00fb68eb87adaab3195c204f21ea42efc3b2b35097`, 13 344 bytes.

The payload is a 4 MiB pattern with no partition table and no filesystem: the
fixture qualifies **container decoding** (EWF headers, chunk table, decompression),
not the reading of a filesystem inside an E01. A filesystem-bearing image would
have to be acquired from a real medium to qualify that step.

## Synthetic navigable FAT image

`synthetic-fat.E01` wraps the FAT12 test filesystem produced by
`tests/core/test_disk.py::fat_image` in EnCase 6 EWF. It contains one synthetic
authentication log at `/VAR/LOG/AUTH.LOG`.

Generated with libewf's `ewfacquirestream -q -c best -t synthetic-fat < fat.img`.
SHA-256 of the E01 file
`32c533946f392a0e0a531be970c445b5f518e7a3e78230f50a4467d7bb26ddad`.

## Synthetic NTFS journal stream

`synthetic-ntfs.E01` wraps a 48 MiB volume formatted with `mkntfs -F -Q`.
`ntfscp` placed a separate synthetic placeholder in `/$Extend/$UsnJrnl` and a
96-byte USN_RECORD_V2 in its named `$J` stream. The record is a file creation
(`0x100`) for `synthetic-file.txt`, with file reference 42 and parent 5. The
image was encoded with `ewfacquirestream -q -c best`.

SHA-256 of the E01 file
`b20744ec9561e2a5b40541dd395ba6bdd86b0a60bb4715d95725acb0871888fa`.
