# data

Source lexicon files for the Swedish tagger dictionary, in the format
`dict_tools/scripts/build_tagger_dicts.py` expects.

Not populated yet, this is Phase 2 of the plan (converting SALDO's LMF/XML
export into per-lexeme source rows). See `implementation-plan.md` in the
notes repo.

## ngram-source

Phase 4 (n-gram confusion data). Raw corpus text for building the n-gram
counts LanguageTool's `ConfusionProbabilityRule` uses.

Source: Swedish Wikipedia dump, `svwiki-latest-pages-articles.xml.bz2` from
`https://dumps.wikimedia.org/svwiki/latest/`, CC BY-SA 4.0. Chosen over
Kubhist (historical newspaper Swedish, wrong register and era for modern
confusion pairs like dig/mig/sig vs dej/mej/sej) and over CC-100/mC4 (kept
as a fallback if more volume or a more colloquial register is needed later).

Pipeline: wikiextractor to plain text, sentence-split, tokenize, then
LanguageTool's own n-gram index builder over 1/2/3-grams. Not committed to
git, regenerate by re-downloading and re-running the pipeline; the built
binary index doesn't live in git either, it gets hosted on the LT server
directly (`lt.katalyst.now`).
