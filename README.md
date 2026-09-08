# swedish-pos-dict

Source data and build tooling for a Swedish part-of-speech / morphology
dictionary for [LanguageTool](https://languagetool.org/), following the same
`<language>-pos-dict` convention as
[german-pos-dict](https://github.com/languagetool-org/german-pos-dict),
[english-pos-dict](https://github.com/languagetool-org/english-pos-dict),
[french-pos-dict](https://github.com/languagetool-org/french-pos-dict),
[dutch-pos-dict](https://github.com/languagetool-org/dutch-pos-dict), and
[portuguese-pos-dict](https://github.com/languagetool-org/portuguese-pos-dict).

Not affiliated with or endorsed by LanguageTool; this is an independent effort
by [Katalyst Nord](https://github.com/katalystnord), built to be mergeable
upstream in the same shape LanguageTool's own tooling expects.

## Why this exists

LanguageTool's Swedish support is thin (roughly 29 grammar rules, a sparse
spelling dictionary, no maintainer since at least 2023). The full background
and source citations live in
[`swedish-grammar-landscape.md`](https://github.com/katalystnord/LT-Swedish-grammer)
(the sibling notes repo). This repo is the POS/morphology dictionary piece of
that effort; see also
[`katalystnord/languagetool`](https://github.com/katalystnord/languagetool)
(fork, `sv-improvements` branch) for the grammar rules and module code.

## Data source

Built from [SALDO](https://spraakbanken.gu.se/en/resources/saldo) (Swedish
Associative Thesaurus v2), a lexical-semantic resource for modern Swedish from
Språkbanken Text, University of Gothenburg, licensed
**CC BY 4.0** (commercial use permitted with attribution). SALDO's own license
is separate from this repo's code license, see [NOTICE.md](NOTICE.md) for the
attribution this requires.

## Structure

Mirrors the `dict_tools`-based repos rather than the older bespoke-script
repos (`german-pos-dict` predates `dictionary-tools`; `portuguese-pos-dict`
is the up-to-date reference):

- `dict_tools/` — git submodule pointing to
  [`languagetool-org/dictionary-tools`](https://github.com/languagetool-org/dictionary-tools),
  the shared build scripts (`build_tagger_dicts.py`, `build_spelling_dicts.py`).
- `data/` — source lexicon files derived from SALDO, in the format
  `build_tagger_dicts.py` expects. Not populated yet, see Status below.

## Status

First pass done: `sv_dict/saldo_convert.py` converts SALDOM's full-form
morphology into the tagger-dict source format (mapping SALDO's own tagset
onto the existing DSSO/SUC-style tags), `sv_dict/merge_sources.py` combines
it with the dictionary already shipping in the fork. Result:
`data/generated/combined_tagger_source.tsv`, 295,476 existing entries plus
547,957 new ones from SALDO, currently what
[`katalystnord/languagetool`](https://github.com/katalystnord/languagetool)'s
`sv-improvements` branch actually ships as `swedish.dict`.

Known gaps, left for a future pass rather than guessed at: adjective and
participle genitive forms, present participles, and subjunctive mood verb
forms, none of these have an established tag pattern in the existing
dictionary to map onto yet. Also open: the ~2.5% of noun paradigms that are
genuinely dual-gender (SALDO's "v"-class irregular paradigms), gender there
varies per surface form rather than being fixed by the noun, so needs an
ending-based heuristic rather than the current paradigm-name lookup.

To reproduce: download `saldo_tagger_source.tsv`'s inputs per the URLs in
`NOTICE.md`/this README's Data source section into `data/saldo-source/`
(gitignored, large), then `poetry run python sv_dict/saldo_convert.py
--input data/saldo-source/saldom.xml --output data/generated/saldo_tagger_source.tsv`.

Track progress in `implementation-plan.md` in the notes repo.

## License

Code in this repo (scripts, build config) is LGPL-2.1-or-later, matching
LanguageTool itself, see [COPYING.txt](COPYING.txt). The underlying SALDO
data carries its own CC BY 4.0 license, see [NOTICE.md](NOTICE.md).
