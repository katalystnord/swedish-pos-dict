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

Bootstrapped, not yet populated. Converting SALDO's LMF/XML export into the
tagger-dict source format is the next step. Track progress in
`implementation-plan.md` in the notes repo.

## License

Code in this repo (scripts, build config) is LGPL-2.1-or-later, matching
LanguageTool itself, see [COPYING.txt](COPYING.txt). The underlying SALDO
data carries its own CC BY 4.0 license, see [NOTICE.md](NOTICE.md).
