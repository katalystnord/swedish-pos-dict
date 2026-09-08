"""Merges the existing LanguageTool swedish.dict (decompiled to TSV) with the
new SALDO-derived TSV, producing a combined source file for POSDictionaryBuilder.

Existing entries always win on conflict (same form+lemma, different tag):
they're the currently-shipping, presumably-reviewed data. SALDO only adds
(form, lemma, tag) triples not already present under any tag for that
form+lemma pair, and words entirely new to the dictionary.

Input files use different separators (existing dump: '+', SALDO output: TAB)
since that's what each tool naturally produces; both are read here and the
existing dump's '+' is a real separator, not incidental, so we don't try to
unify the on-disk format, just parse both correctly.
"""
import argparse
from pathlib import Path


def read_existing(path: Path) -> list[tuple[str, str, str]]:
    """Reads a morfologik DictDecompile dump: LEMMA+FORM+TAG per line.

    Verified empirically, not assumed: built an isolated dictionary from a
    known (form, lemma, tag) = (fåren, får, NN:BF:PLU:NOM:NEU) row and
    decompiled it back; the dump line came out "får+fåren+NN:BF:PLU:NOM:NEU",
    lemma first. Getting this backwards (form+lemma+tag) silently swaps form
    and lemma for every entry where they differ, which POSDictionaryBuilder
    happily compiles without complaint, it only surfaces as wrong readings
    at tagger runtime (confirmed: querying "får" returned "fåren" as a stem
    with this bug in place).
    """
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("+")
            if len(parts) != 3:
                # A small number of entries contain a literal '+' in the
                # word itself; for those the split produces >3 parts.
                # Rejoin defensively: tag is always the last field, the
                # form (2nd column) the second-to-last.
                if len(parts) > 3:
                    lemma = "+".join(parts[:-2])
                    form, tag = parts[-2], parts[-1]
                    parts = [lemma, form, tag]
                else:
                    continue
            lemma, form, tag = parts
            rows.append((form, lemma, tag))
    return rows


def read_saldo(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            rows.append(tuple(parts))
    return rows


def merge(existing: list[tuple[str, str, str]], saldo: list[tuple[str, str, str]]):
    existing_set = set(existing)
    # Anything already covered for this exact (form, lemma) pair, regardless
    # of tag, so we don't add a second, possibly-wrong reading SALDO
    # produced for a pair the existing dictionary already handles.
    existing_form_lemma = {(f, l) for f, l, _ in existing}

    added = []
    for row in saldo:
        form, lemma, tag = row
        if row in existing_set:
            continue
        if (form, lemma) in existing_form_lemma:
            continue
        added.append(row)
        existing_form_lemma.add((form, lemma))

    return existing, added


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--existing", type=Path, required=True,
                     help="Decompiled existing swedish.dict (+ separated)")
    ap.add_argument("--saldo", type=Path, required=True,
                     help="saldo_convert.py output (TAB separated)")
    ap.add_argument("--output", type=Path, required=True,
                     help="Combined TSV, TAB separated, for POSDictionaryBuilder")
    args = ap.parse_args()

    existing = read_existing(args.existing)
    saldo = read_saldo(args.saldo)
    existing_rows, added_rows = merge(existing, saldo)

    with args.output.open("w", encoding="utf-8", newline="\n") as out:
        for form, lemma, tag in existing_rows:
            out.write(f"{form}\t{lemma}\t{tag}\n")
        for form, lemma, tag in added_rows:
            out.write(f"{form}\t{lemma}\t{tag}\n")

    print(f"existing entries kept:  {len(existing_rows)}")
    print(f"new entries from SALDO: {len(added_rows)}")
    print(f"total:                  {len(existing_rows) + len(added_rows)}")


if __name__ == "__main__":
    main()
