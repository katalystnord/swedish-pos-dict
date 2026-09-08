"""Converts SALDOM (SALDO's morphology component) into LanguageTool's tagger
dictionary source format: TAB-separated (inflected form, lemma, DSSO/SUC-style
tag), one line per reading, matching the format already used by the existing
languagetool-language-modules/sv/.../swedish.dict (verified by decompiling it
with morfologik.tools.DictDecompile and cross-checking known words).

Deliberately conservative: an msd pattern that isn't in MSD_MAP is skipped and
counted, not guessed at. Compound-internal forms (SALDO msd "c", "cm", "ci",
"sms") are always skipped, they're stems for compound-building, not words a
person would encounter standalone.

Coverage as of this version: core nn/vb/av/ab/pn/pm/kn/pp/sn/in/nl forms.
Not yet covered (skipped, not silently wrong): subjunctive verb forms
(pres/pret konj), present participles, adjective genitive forms, all rare
enough that leaving them out is safer than guessing a tag that doesn't
exist elsewhere in the dictionary.

License note: SALDOM data is CC BY 4.0, Språkbanken Text, University of
Gothenburg. See ../NOTICE.md for the attribution this requires downstream.
"""
import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

# Compound-internal / non-standalone form markers, always skip.
SKIP_MSD_TOKENS = {"c", "cm", "ci", "sms"}

# Paradigm string gender marker -> DSSO gender tag, for "nn" (noun).
# SALDO paradigm names encode declension+gender as a digit+letter right
# after "nn_", e.g. nn_3u_salong (declension 3, utrum), nn_6n_departement
# (declension 6, neutrum). Verified against several dozen samples.
PARADIGM_GENDER_RE = re.compile(r"^nn_\d*([un])[a-z]?_")


def noun_gender_from_paradigm(paradigm: str) -> str | None:
    m = PARADIGM_GENDER_RE.match(paradigm)
    if not m:
        return None
    return "UTR" if m.group(1) == "u" else "NEU"


# --- msd -> DSSO tag maps, per core POS. Each is normalized-msd -> tag. -----

NN_MSD_MAP = {
    "sg indef nom": "NN:OF:SIN:NOM",
    "sg indef gen": "NN:OF:SIN:GEN",
    "sg def nom": "NN:BF:SIN:NOM",
    "sg def gen": "NN:BF:SIN:GEN",
    "pl indef nom": "NN:OF:PLU:NOM",
    "pl indef gen": "NN:OF:PLU:GEN",
    "pl def nom": "NN:BF:PLU:NOM",
    "pl def gen": "NN:BF:PLU:GEN",
}

VB_MSD_MAP = {
    "pres ind aktiv": "VB:PRS",
    "pres ind s-form": "VB:PRS:PF",
    "pret ind aktiv": "VB:PRT",
    "pret ind s-form": "VB:PRT:PF",
    "imper": "VB:IMP",
    "inf aktiv": "VB:INF",
    "inf s-form": "VB:INF:PF",
    "sup aktiv": "VB:SUP",
    "sup s-form": "VB:SUP:PF",
    # Past participles (perfekt particip) inflect like adjectives. Verified
    # against the existing dict's "två" entry: tvådd/VB:PPC:UTR,
    # tvådda/VB:PPC:PLU, tvått/VB:PPC:NEU. Definite forms aren't separately
    # attested there, Swedish weak-declension definite forms coincide with
    # the plural surface form, so they're folded into :PLU rather than left
    # unmapped; genitive participle forms are rare enough to skip rather
    # than guess a tag pattern with no precedent in the existing dictionary.
    "pret_part indef sg u nom": "VB:PPC:UTR",
    "pret_part indef sg n nom": "VB:PPC:NEU",
    "pret_part indef pl nom": "VB:PPC:PLU",
    "pret_part def sg no_masc nom": "VB:PPC:PLU",
    "pret_part def sg masc nom": "VB:PPC:PLU",
    "pret_part def pl nom": "VB:PPC:PLU",
}

AV_MSD_MAP = {
    "pos indef sg u nom": "JJ:PU",
    "pos indef sg n nom": "JJ:PN",
    "pos indef pl nom": "JJ:P",
    "pos def sg no_masc nom": "JJ:BF",
    "pos def sg masc nom": "JJ:M",
    "pos def pl nom": "JJ:BF",
    "komp nom": "JJ:K",
    "super indef nom": "JJ:S",
    "super def no_masc nom": "JJ:S:BF:NM",
    "super def masc nom": "JJ:S:BF:M",
}

# Categories where every non-skipped form just gets the bare POS tag,
# no further subdivision in the existing dictionary (verified: AB, PN, KN,
# PP, SN, IN all appear unsubdivided in the decompiled swedish.dict).
BARE_TAG_POS = {"ab": "AB", "pn": "PN", "kn": "KN", "pp": "PP", "sn": "SN", "in": "IN"}

# Most proper nouns are invariant ("nom"/"gen" only, e.g. Sverige/Sveriges),
# but some (personal names, countable place-name-like proper nouns) decline
# with the full noun sg/pl indef/def scheme. The existing dictionary only
# distinguishes NOM/GEN for proper nouns either way, so number/definiteness
# collapses into that same two-way split rather than inventing new tags.
PM_MSD_MAP = {
    "nom": "PM:NOM",
    "gen": "PM:GEN",
    "sg indef nom": "PM:NOM",
    "sg indef gen": "PM:GEN",
    "sg def nom": "PM:NOM",
    "sg def gen": "PM:GEN",
    "pl indef nom": "PM:NOM",
    "pl indef gen": "PM:GEN",
    "pl def nom": "PM:NOM",
    "pl def gen": "PM:GEN",
}

# nl (numeral): "nom num u" / "nom num n" -> NL, gender not distinguished
# in the existing dict's tagging of numerals (kept simple deliberately).
NL_MSD_PREFIX = "nom num"


@dataclass
class Reading:
    form: str
    lemma: str
    tag: str


def normalize_msd(msd: str) -> str:
    """Strips SALDO's compound-slot position suffix, e.g. 'gen 1:2-3' -> 'gen'."""
    return re.sub(r"\s+\d+:\d+-\d+$", "", msd).strip()


def convert_entry(pos: str, paradigm: str, lemma: str, forms: list[tuple[str, str]],
                   stats: Counter) -> list[Reading]:
    """forms: list of (writtenForm, msd) for one LexicalEntry."""
    out: list[Reading] = []
    gender = noun_gender_from_paradigm(paradigm) if pos == "nn" else None

    for form, raw_msd in forms:
        msd = normalize_msd(raw_msd)
        if msd in SKIP_MSD_TOKENS:
            stats["skipped_compound_form"] += 1
            continue

        tag = None
        if pos == "nn":
            base = NN_MSD_MAP.get(msd)
            if base and gender:
                tag = f"{base}:{gender}"
            elif base and not gender:
                stats["skipped_nn_unknown_gender"] += 1
                continue
        elif pos == "vb":
            tag = VB_MSD_MAP.get(msd)
        elif pos == "av":
            tag = AV_MSD_MAP.get(msd)
        elif pos == "pm":
            tag = PM_MSD_MAP.get(msd)
        elif pos == "nl":
            if msd.startswith(NL_MSD_PREFIX):
                tag = "NL"
        elif pos in BARE_TAG_POS:
            tag = BARE_TAG_POS[pos]

        if tag is None:
            stats[f"unmapped:{pos}:{msd}"] += 1
            continue

        out.append(Reading(form=form, lemma=lemma, tag=tag))
    return out


def iter_lexical_entries(xml_path: Path):
    """Streams LexicalEntry elements without loading the whole 254MB file."""
    context = etree.iterparse(str(xml_path), events=("end",), tag="LexicalEntry")
    for _, elem in context:
        yield elem
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]


def parse_entry(elem) -> tuple[str, str, str, list[tuple[str, str]]] | None:
    lemma_el = elem.find("Lemma/FormRepresentation")
    if lemma_el is None:
        return None
    feats = {f.get("att"): f.get("val") for f in lemma_el.findall("feat")}
    pos = feats.get("partOfSpeech")
    lemma = feats.get("writtenForm")
    paradigm = feats.get("paradigm", "")
    if not pos or not lemma:
        return None

    forms = []
    for wf in elem.findall("WordForm"):
        wf_feats = {f.get("att"): f.get("val") for f in wf.findall("feat")}
        form = wf_feats.get("writtenForm")
        msd = wf_feats.get("msd")
        if form and msd:
            forms.append((form, msd))
    return pos, lemma, paradigm, forms


def convert(xml_path: Path, out_path: Path) -> Counter:
    stats: Counter = Counter()
    seen: set[tuple[str, str, str]] = set()
    core_pos = set(BARE_TAG_POS) | {"nn", "vb", "av", "pm", "nl"}

    with out_path.open("w", encoding="utf-8", newline="\n") as out:
        for i, elem in enumerate(iter_lexical_entries(xml_path)):
            parsed = parse_entry(elem)
            if parsed is None:
                continue
            pos, lemma, paradigm, forms = parsed
            stats["entries_seen"] += 1
            if pos not in core_pos:
                stats["skipped_non_core_pos"] += 1
                continue
            for reading in convert_entry(pos, paradigm, lemma, forms, stats):
                key = (reading.form, reading.lemma, reading.tag)
                if key in seen:
                    continue
                seen.add(key)
                out.write(f"{reading.form}\t{reading.lemma}\t{reading.tag}\n")
                stats["readings_written"] += 1
            if i and i % 20000 == 0:
                print(f"  ...{i} entries processed", file=sys.stderr)
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True, help="Path to saldom.xml")
    ap.add_argument("--output", type=Path, required=True, help="Output TSV path")
    ap.add_argument("--stats-top", type=int, default=25,
                     help="How many top unmapped-msd patterns to print")
    args = ap.parse_args()

    stats = convert(args.input, args.output)

    print("\n=== Conversion summary ===")
    for key in ("entries_seen", "skipped_non_core_pos", "readings_written",
                "skipped_compound_form", "skipped_nn_unknown_gender"):
        print(f"{key}: {stats.get(key, 0)}")

    unmapped = Counter({k: v for k, v in stats.items() if k.startswith("unmapped:")})
    total_unmapped = sum(unmapped.values())
    print(f"total unmapped readings: {total_unmapped}")
    print(f"\nTop {args.stats_top} unmapped msd patterns (fix these next):")
    for k, v in unmapped.most_common(args.stats_top):
        print(f"  {v:>8}  {k}")


if __name__ == "__main__":
    main()
