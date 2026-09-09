"""Converts SALDOM (SALDO's morphology component) into LanguageTool's tagger
dictionary source format: TAB-separated (inflected form, lemma, DSSO/SUC-style
tag), one line per reading, matching the format already used by the existing
languagetool-language-modules/sv/.../swedish.dict (verified by decompiling it
with morfologik.tools.DictDecompile and cross-checking known words).

Deliberately conservative: an msd pattern that isn't in MSD_MAP is skipped and
counted, not guessed at. Compound-internal forms (SALDO msd "c", "cm", "ci",
"sms") are always skipped, they're stems for compound-building, not words a
person would encounter standalone.

Coverage as of this version: core nn/vb/av/ab/pn/pm/kn/pp/sn/in/nl forms,
plus subjunctive verb forms (VB:...:KONJ) and adjective/participle genitive
forms (...:GEN), both newly-introduced tag categories with no precedent in
the pre-existing dictionary (purely additive, nothing queries them yet).
Also covers SALDO's genuinely dual-gender nouns ("v"-class paradigms,
paradigm string doesn't fix a gender): singular indefinite forms are
gender-neutral in Swedish surface form, so both UTR and NEU readings are
emitted; singular definite forms are classified per-form by their own
ending (-en/-et is unambiguous); plural forms (where the paradigm has any)
are classified by positional pairing against singular indefinite, see
_convert_dual_gender_noun. A small residue (~1% of dual-gender entries,
mostly Latin-derived grammar terms like "aktivum"/"perfektum" with two
competing singular spellings) can't be paired unambiguously and stays
unmapped rather than guessed at.

License note: SALDOM data is CC BY 4.0, Språkbanken Text, University of
Gothenburg. See ../NOTICE.md for the attribution this requires downstream.
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
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
    # Present participles (löpande, skrivande): invariant in Swedish, no
    # gender/number inflection, confirmed against real existing entries
    # (abdikerande, absorberande, ... all bare VB:PREPC, no subdivisions).
    "pres_part nom": "VB:PREPC",
    # Genitive forms below (:GEN suffix) and subjunctive mood (:KONJ) have no
    # precedent anywhere in the existing dictionary, there was nothing to
    # verify a tag pattern against, so these are new tag names, not
    # rediscovered ones. Purely additive: nothing in the current rule set
    # queries these tags, so adding them can't change any existing behavior,
    # only make more (rare) word forms recognizable at all. Added 2026-09-09
    # per explicit request to complete this rather than leave it skipped.
    "pres_part gen": "VB:PREPC:GEN",
    "pret_part indef sg u gen": "VB:PPC:UTR:GEN",
    "pret_part indef sg n gen": "VB:PPC:NEU:GEN",
    "pret_part indef pl gen": "VB:PPC:PLU:GEN",
    "pret_part def sg no_masc gen": "VB:PPC:PLU:GEN",
    "pret_part def sg masc gen": "VB:PPC:PLU:GEN",
    "pret_part def pl gen": "VB:PPC:PLU:GEN",
    "pres konj aktiv": "VB:PRS:KONJ",
    "pres konj s-form": "VB:PRS:KONJ:PF",
    "pret konj aktiv": "VB:PRT:KONJ",
    "pret konj s-form": "VB:PRT:KONJ:PF",
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
    # Genitive adjective forms: same situation as VB's :GEN tags above, no
    # existing precedent, purely additive new tag names. Follows the same
    # nom-side collapsing already used above (def sg no_masc/def pl -> BF).
    "pos indef sg u gen": "JJ:PU:GEN",
    "pos indef sg n gen": "JJ:PN:GEN",
    "pos indef pl gen": "JJ:P:GEN",
    "pos def sg no_masc gen": "JJ:BF:GEN",
    "pos def sg masc gen": "JJ:M:GEN",
    "pos def pl gen": "JJ:BF:GEN",
    "komp gen": "JJ:K:GEN",
    "super indef gen": "JJ:S:GEN",
    "super def no_masc gen": "JJ:S:BF:NM:GEN",
    "super def masc gen": "JJ:S:BF:M:GEN",
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


def noun_gender_from_ending(form: str, msd: str) -> str | None:
    """For nouns whose paradigm doesn't fix a gender (SALDO's 'v'-class,
    irregular/dual-gender declensions, e.g. paradigm nn_vv_test): each
    definite-singular form's own ending is still an unambiguous Swedish
    morphological marker (-en/-ens = utrum, -et/-ets = neutrum), verified
    against real dual-gender entries like "ziqqurat" (ziqquraten vs.
    ziqquratet, both genuinely attested for the same lemma). Only used for
    the two definite-singular msds; indefinite and plural forms don't carry
    an equally reliable per-form signal, those are handled separately by
    _convert_dual_gender_noun's positional pairing instead.
    """
    if msd == "sg def nom":
        if form.endswith("en"):
            return "UTR"
        if form.endswith("et"):
            return "NEU"
    elif msd == "sg def gen":
        if form.endswith("ens"):
            return "UTR"
        if form.endswith("ets"):
            return "NEU"
    return None


# Noun msd slots whose plural forms need positional pairing rather than a
# per-form signal, for dual-gender ("v"-class) nouns. SALDO can attest
# several competing plural spellings for the same slot (e.g. sudoku's "pl
# indef nom" is sudokun/sudokus/sudokusar/sudokur/sudoku), where exactly the
# spelling identical to "sg indef nom" is the neuter reading (a Swedish
# neuter noun ending in a consonant has an indefinite plural identical to
# its indefinite singular) and every other spelling at that position is a
# valid utrum reading. Verified against saldom.xml samples spanning all
# "*v_*" paradigm families (0v/3v/4v/6v/vv).
_DUAL_GENDER_PLURAL_MSDS = ("pl indef nom", "pl indef gen", "pl def nom", "pl def gen")


def _convert_dual_gender_noun(lemma: str, forms: list[tuple[str, str]],
                               stats: Counter) -> list[Reading]:
    by_msd: dict[str, list[str]] = defaultdict(list)
    for form, raw_msd in forms:
        msd = normalize_msd(raw_msd)
        if msd in SKIP_MSD_TOKENS:
            stats["skipped_compound_form"] += 1
            continue
        by_msd[msd].append(form)

    out: list[Reading] = []

    # sg indef nom/gen: one shared spelling in SALDO, grammatical under
    # either gender ("en ziqqurat" and "ett ziqqurat" are both attested
    # Swedish), so both readings get emitted for the same form.
    for msd in ("sg indef nom", "sg indef gen"):
        base = NN_MSD_MAP[msd]
        for form in by_msd.get(msd, []):
            out.append(Reading(form=form, lemma=lemma, tag=f"{base}:UTR"))
            out.append(Reading(form=form, lemma=lemma, tag=f"{base}:NEU"))

    # sg def nom/gen: each form's own ending is an unambiguous gender marker.
    for msd in ("sg def nom", "sg def gen"):
        base = NN_MSD_MAP[msd]
        for form in by_msd.get(msd, []):
            form_gender = noun_gender_from_ending(form, msd)
            if form_gender:
                out.append(Reading(form=form, lemma=lemma, tag=f"{base}:{form_gender}"))
            else:
                stats["skipped_nn_unknown_gender"] += 1

    # Plural forms: positional pairing against "pl indef nom", whose own
    # per-position gender is fixed by matching each spelling against the
    # (single, shared) "sg indef nom" form. Requires exactly one sg-indef-nom
    # spelling; a handful of entries (mostly Latin-derived grammar terms
    # like "aktivum"/"perfektum" with two competing singular spellings) have
    # none or several, and stay unmapped rather than guessed at. Each of the
    # four plural msds is checked independently against "pl indef nom"'s
    # length, so a length mismatch in one (observed for a few informal
    # loanwords, e.g. "sudoku") only drops that one slot, not all four.
    base_indef_forms = by_msd.get("sg indef nom", [])
    pl_indef_nom = by_msd.get("pl indef nom", [])
    if pl_indef_nom and len(base_indef_forms) == 1:
        position_genders = ["NEU" if f == base_indef_forms[0] else "UTR" for f in pl_indef_nom]
        for msd in _DUAL_GENDER_PLURAL_MSDS:
            base = NN_MSD_MAP[msd]
            plural_forms = by_msd.get(msd, [])
            if len(plural_forms) != len(position_genders):
                stats["skipped_nn_unknown_gender"] += len(plural_forms)
                continue
            for form, form_gender in zip(plural_forms, position_genders):
                out.append(Reading(form=form, lemma=lemma, tag=f"{base}:{form_gender}"))
    else:
        for msd in _DUAL_GENDER_PLURAL_MSDS:
            stats["skipped_nn_unknown_gender"] += len(by_msd.get(msd, []))

    return out


def convert_entry(pos: str, paradigm: str, lemma: str, forms: list[tuple[str, str]],
                   stats: Counter) -> list[Reading]:
    """forms: list of (writtenForm, msd) for one LexicalEntry."""
    gender = noun_gender_from_paradigm(paradigm) if pos == "nn" else None

    if pos == "nn" and gender is None:
        return _convert_dual_gender_noun(lemma, forms, stats)

    out: list[Reading] = []
    for form, raw_msd in forms:
        msd = normalize_msd(raw_msd)
        if msd in SKIP_MSD_TOKENS:
            stats["skipped_compound_form"] += 1
            continue

        tag = None
        if pos == "nn":
            # gender is always known here: dual-gender ("v"-class) entries
            # returned via _convert_dual_gender_noun above already.
            base = NN_MSD_MAP.get(msd)
            if base:
                tag = f"{base}:{gender}"
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
