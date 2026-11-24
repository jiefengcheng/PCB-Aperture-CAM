# Large-copper 0.2.0 source baseline

`source.gbr` is the exact 532,869-byte positive-copper Gerber used for the
qualified 0.2.0 trimming reproduction. This is the file referred to as
“source.bgr” in the delivery request; its actual Gerber extension is `.gbr`.
The owner explicitly requested its inclusion in the GitHub handoff on
2026-11-24. The original local intake file remains unchanged.

SHA-256: `207a51318f103190a4d61e76f4a0457fcfd11fd3db560c9439dd2f5f460f9b90`.

This is the input baseline for developing/reproducing the trimming process.
It is not a corrected manufacturing export or production approval. This addition
does not assign a new license to the supplied board artwork.

`reference.json` records the tested Mac result, environment, historical hashes
and unresolved findings. The expected generic result is **356 corrected,
77 unresolved, 24 ignored**, with 895 changed contributions among 17,849 source
occurrences. It covers the 46 previously reviewed removal witnesses and includes
additional discoveries. The older 46-case result is a different reference.

Verify input bytes with no third-party dependencies:

```sh
python3 -B tools/check_large_copper_baseline.py
```

Add `--parse` in the pinned environment to exercise the existing source parser.
A source-intake PASS is explicitly **not** trimming, geometry parity or display
qualification. See the [reproduction guide](../../reproduction/large_copper_0.2.0/README.md).
