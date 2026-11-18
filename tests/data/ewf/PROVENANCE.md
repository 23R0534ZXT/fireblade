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
