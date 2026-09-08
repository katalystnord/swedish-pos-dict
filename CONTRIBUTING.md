# Contributing

This repo tracks the Swedish POS/morphology dictionary piece of a broader
effort to bring Swedish up to par in LanguageTool. See
`implementation-plan.md` in the notes repo for the full phased plan.

## Setup

```bash
git clone --recurse-submodules https://github.com/katalystnord/swedish-pos-dict.git
cd swedish-pos-dict
poetry install --with dev,test
```

You'll also need the `unmunch` Hunspell binary on your `PATH`, and a local
clone of [`katalystnord/languagetool`](https://github.com/katalystnord/languagetool)
with `LT_HOME` pointing at it (see `dict_tools/README.md` for why).

## Versioning

Semantic versioning, same scheme as `portuguese-pos-dict`:

- **major**: breaking changes that require LT code changes to consume
- **minor**: new content (words, forms) added
- **patch**: fixes to existing entries (typos, wrong tags)

## Workflow

1. Branch off `main`.
2. Make your change to the source data under `data/`.
3. Run the build scripts in `dict_tools/scripts/` to confirm the dictionary
   still compiles.
4. Open a PR. Once merged and tagged, the new version needs to be picked up
   by `katalystnord/languagetool`'s `pom.xml` before it's actually usable.
