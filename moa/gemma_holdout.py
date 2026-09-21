"""Single pinned Gemma GGUF study using the bounded local holdout runner."""

from .comparison import ROOT
from .local_holdout import LocalStudy, ModelSpec, main as local_main

STUDY = LocalStudy(
    models=(ModelSpec('gemma4-12b-gguf', 'gemma4:12b-it-q4_K_M',
                      '4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c'),),
    protocol=ROOT / 'docs' / 'gemma-holdout-v0.7.md',
    inventory=ROOT / 'receipts' / 'v0.7-gemma-gguf' / 'inventory.json',
)


def main(argv=None):
    return local_main(argv, study=STUDY)


if __name__ == '__main__':
    raise SystemExit(main())
