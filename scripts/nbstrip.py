#!/usr/bin/env python3
"""Strip outputs and machine-specific metadata from Jupyter notebooks.

Used two ways:

  git clean filter   cat notebook.ipynb | python3 scripts/nbstrip.py
  manual cleanup     python3 scripts/nbstrip.py --inplace draft/draft.ipynb

Notebook outputs are the easiest way to leak something from this project:
they embed local filesystem paths, scraped league data and anything a cell
happened to print. The clean filter means the working copy keeps its outputs
while the committed blob never has them.

Standard library only, so it works as a filter without extra dependencies.
"""

import json
import sys

# Per-cell metadata that records when and where a cell ran.
CELL_METADATA_NOISE = ('execution', 'ExecuteTime', 'collapsed', 'scrolled')


def strip(nb):
    """Clear outputs and machine-specific metadata. Idempotent."""
    for cell in nb.get('cells', []):
        if cell.get('cell_type') == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
        metadata = cell.get('metadata')
        if isinstance(metadata, dict):
            for key in CELL_METADATA_NOISE:
                metadata.pop(key, None)

    # kernelspec.metadata.interpreter.hash identifies the machine that ran it.
    kernelspec = nb.get('metadata', {}).get('kernelspec')
    if isinstance(kernelspec, dict):
        kernelspec.pop('metadata', None)
    nb.get('metadata', {}).pop('vscode', None)

    return nb


def dumps(nb):
    """Serialize the way nbformat does, so the bytes are stable run to run."""
    return json.dumps(nb, indent=1, sort_keys=True, ensure_ascii=False) + '\n'


def main():
    args = sys.argv[1:]

    if args and args[0] == '--inplace':
        for path in args[1:]:
            with open(path, encoding='utf-8') as handle:
                nb = json.load(handle)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(dumps(strip(nb)))
            print(f"stripped {path}", file=sys.stderr)
        return 0

    # Filter mode. If anything goes wrong, pass the input through untouched
    # rather than let git store a corrupted notebook.
    raw = sys.stdin.read()
    try:
        sys.stdout.write(dumps(strip(json.loads(raw))))
    except Exception as exc:  # noqa: BLE001 - never break a commit
        print(f"nbstrip: passing through unchanged ({exc})", file=sys.stderr)
        sys.stdout.write(raw)
    return 0


if __name__ == '__main__':
    sys.exit(main())
