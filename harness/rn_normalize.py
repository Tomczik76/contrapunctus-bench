"""Canonical Python port of the engine's Scala RN normalizer.

SINGLE SOURCE OF TRUTH for Roman-numeral canonicalisation on the
Python side of the cross-engine benchmark. Every competitor scorer
(`music21_comparison.py`, `augnet_comparison.py` via its
music21_comparison import, `analysisgnn_comparison.py` via
`augnet_vs_ours_diff.py`) must import `normalize` from THIS module —
never define a local copy.

Why this module exists (2026-06-09 fairness audit): the benchmark
scored OUR engine through the Scala normalizer but scored the three
competitor engines through two independently-drifted Python copies.
Three drifts all inflated our relative exact-tier number:

  1. The tonicization-slash keep-charset was missing lowercase `v`/`n`
     (`'IViINFGCS'`), so `/v`, `/vi`, `/vii` targets lost their slash
     for competitors only — `V7/V` and `V7/v` normalized to DIFFERENT
     strings, and every slash-dependent tier expansion broke.
  2. `Ger65` / `Ger7` → `Ger6` collapse (Scala canonicaliseAug6) was
     absent, so competitor Ger-convention answers missed at exact.
  3. The `#vii` → `vii` strip (Scala does it at the EXACT tier,
     no-slash forms only) was instead a broader interpretive-tier
     rule, so DCML-style `#vii°` cost competitors exact hits.

This port mirrors the Scala implementation rule-for-rule, including
its processing ORDER (brackets → alteration suffix → inversion
shorthand → aug6 canonicalisation → #vii strip) and its quirks (the
`/o` half-diminished advance assumes the `o` is adjacent to the
slash, exactly like the Scala `i += 2`).

Parity is enforced by `test_rn_normalize_parity.py` against the
committed fixture `rn_normalize_fixture.json` (every distinct raw RN
label in the corpus, normalized by the engine's Scala normalizer; the
fixture is regenerated in the private engine repo by a fixture-dump
utility whenever the Scala side changes):

    python3 harness/test_rn_normalize_parity.py     # or: make test

Run the parity test after ANY edit here (the engine maintainer runs it
after any engine-side normalizer change too).
"""

import re

DIGIT_MAP = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
}

# Mirrors the engine-side isRomanLetter (Scala): tonicization-target
# detection after a slash. Intentionally generous — only distinguishes
# "tonicization slash" from "figured-bass slash". Includes BOTH cases
# of i/v (DCML writes `/V`, Bach's own WTC analysis writes `/v`) and
# N/n plus the aug6 shorthand initials.
_ROMAN_LETTERS = frozenset('IViVvNnFGC')  # == {'I','V','i','v','N','n','F','G','C'}


def _next_non_space(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def _is_digit_or_end(s: str, idx: int) -> bool:
    return idx >= len(s) or s[idx].isdigit() or s[idx] in DIGIT_MAP


def _strip_bracket_modifiers(s: str) -> str:
    """`V7[no3][add4]` → `V7` (rntxt figured-bass alteration brackets)."""
    return re.sub(r'\[[^\]]*\]', '', s)


_ALTERATION_SUFFIX = re.compile(r'^(.+?)([#b]\d)$')


def _strip_alteration_suffix(s: str) -> str:
    """`viio64b3` → `viio64` (bare-suffix alteration form)."""
    m = _ALTERATION_SUFFIX.match(s)
    return m.group(1) if m else s


def _expand_inversion_shorthand(s: str) -> str:
    """`V2` → `V42`; `viio63` → `viio6` (figured-bass shorthand)."""
    if s.endswith('2') and not s.endswith('42'):
        before = len(s) - 2
        if before >= 0 and not s[before].isdigit():
            return s[:-1] + '42'
        return s
    if s.endswith('63'):
        return s[:-1]
    return s


_AUG6_PREFIX = re.compile(r'^(It|Fr|Ger|Sw)\+')


def _canonicalise_aug6(s: str) -> str:
    """Strip the decorative `+` after aug6 names; canonicalise the
    German figure-form variants (`Ger65`, `Ger7` → `Ger6`) and the
    French (`Fr6` → `Fr43`). Mirrors Scala canonicaliseAug6 incl. the
    chord/target split (preserves `Ger65/vi` → `Ger6/vi`)."""
    idx = s.rfind('/')
    chord, target = (s, '') if idx == -1 else (s[:idx], s[idx:])
    stripped = _AUG6_PREFIX.sub(r'\1', chord, count=1)
    canonical = {'Fr6': 'Fr43', 'Ger65': 'Ger6', 'Ger7': 'Ger6'}.get(stripped, stripped)
    return canonical + target


def _strip_local_sharp_viio(s: str) -> str:
    """`#vii*` → `vii*` for LOCAL-key forms only (the caller applies
    this on the no-slash branch only — secondary forms like
    `#viio65/ii` keep the chromatic marker, exactly like Scala)."""
    return s[1:] if s.startswith('#vii') else s


def normalize(rn):
    """Canonicalise an RN string from any engine/annotation format.

    Rule-for-rule mirror of the engine's Scala `normalize`:
      - Unicode super/subscript digits → ASCII
      - `°` → `o`; `♯`/`♭` → `#`/`b`; `⁺` → `+`; `Δ` elided
      - `/o<digit-or-end>` → `ø` (half-diminished shorthand)
      - slash before a roman-letterish char → tonicization (kept);
        any other slash (figured bass `V4/3`) → dropped
      - post-pass on the chord side: strip `[..]` brackets, strip
        bare `#3`/`b5`-style alteration suffixes, `*2`→`*42`,
        `*63`→`*6`, aug6 canonicalisation, `#vii`→`vii` (no-slash
        only); tonicization target lowercased.
    """
    if not rn:
        return rn
    s_in = rn.strip()
    if not s_in:
        return s_in

    out = []
    i = 0
    n = len(s_in)
    while i < n:
        c = s_in[i]
        if c in DIGIT_MAP:
            out.append(DIGIT_MAP[c])
            i += 1
        elif c == '°':
            out.append('o')
            i += 1
        elif c == '♯':
            out.append('#')
            i += 1
        elif c == '♭':
            out.append('b')
            i += 1
        elif c == '⁺':
            out.append('+')
            i += 1
        elif c == 'Δ':
            i += 1
        elif c == '/':
            j = _next_non_space(s_in, i + 1)
            nxt = s_in[j] if j < n else None
            if nxt == 'o' and _is_digit_or_end(s_in, i + 2):
                # Half-diminished shorthand `/o7` → `ø7`. The `i + 2`
                # advance assumes the `o` is adjacent to the slash —
                # same assumption as the Scala implementation.
                out.append('ø')
                i += 2
            elif nxt is not None and nxt in _ROMAN_LETTERS:
                out.append('/')
                i += 1
            else:
                i += 1
        else:
            out.append(c)
            i += 1

    return _post_process(''.join(out))


def _post_process(s: str) -> str:
    idx = s.rfind('/')
    if idx == -1:
        return _strip_local_sharp_viio(
            _canonicalise_aug6(
                _expand_inversion_shorthand(
                    _strip_alteration_suffix(_strip_bracket_modifiers(s)))))
    chord = s[:idx]
    target = s[idx + 1:]
    chord = _canonicalise_aug6(
        _expand_inversion_shorthand(
            _strip_alteration_suffix(_strip_bracket_modifiers(chord))))
    return f"{chord}/{target.lower()}"


def rntxt_beats_per_measure(time_sig):
    """rntxt beats per measure for a time-signature string.

    Shared by the music21 + AnalysisGNN aligners. Matches the Scala
    `rntxtBeatsPerMeasure` for all plain meters; additionally maps the
    `slow`/`fast` prefixed compound meters the way the rntxt corpus
    uses them (e.g. `fast 6/8` counts 2 dotted-quarter beats — the
    Scala fallback strips the prefix and returns the numerator, a
    known small divergence for the rare prefixed-TS files)."""
    ts = (time_sig or '4/4').strip().lower()
    mapping = {
        'c': 4, '4/4': 4, 'cut': 2, '2/2': 2,
        '3/4': 3, '2/4': 2, '3/8': 3, '6/8': 2,
        '9/8': 3, '12/8': 4,
        'slow 6/8': 6, 'fast 6/8': 2,
        'slow 3/8': 3, 'fast 3/8': 1,
        'slow 12/8': 12, 'fast 12/8': 4,
    }
    if ts in mapping:
        return mapping[ts]
    stripped = ts.replace('slow', '').replace('fast', '').strip()
    parts = stripped.split('/')
    if len(parts) == 2:
        try:
            return int(parts[0])
        except ValueError:
            return 4
    return 4
