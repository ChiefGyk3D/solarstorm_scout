# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
The on-air forecaster: an LLM reads the numbers like a radio weatherperson.

Every run already fetches the solar flux, K-index, absorption, aurora power
and X-ray flux. This module hands those numbers to hypeman-social's LLM
manager (a local Ollama box by default, Gemini if configured) and asks for
a short spoken-style briefing to open the thread with: what the Sun did,
what it means for the bands, which ones to try.

The rule that shapes everything here: the briefing is optional and the data
is not. Any problem — the LLM switched off, the server down, a reply that
mentions a flare class or K-index the data does not show, a reply that will
not fit — means the thread goes out exactly as it always has, without the
briefing. Nothing in here can fail the run.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from hypeman_social.llm import ContentProfile, LLMManager

logger = logging.getLogger(__name__)

#: Domain vocabulary for the guardrails. hypeman's own profiles cover video,
#: stream and repository announcements; this one names the details a small
#: model invents when asked to talk about space weather it cannot see. It
#: lives here rather than in hypeman because the patterns get tuned against
#: whatever the model on the local box actually says, and that should not
#: wait for a library release.
SPACE_WEATHER_PROFILE = ContentProfile(
    name='space-weather',
    content_noun='forecast',
    generic_phrases=[
        'stay tuned',
        'check it out',
        'as always',
        'happy hunting',
        'get on the air',
        'keep an eye',
    ],
    hallucination_patterns=[
        # Events the NOAA feeds this bot reads say nothing about.
        r'coronal\s+mass\s+ejection',
        r'\bcmes?\b',
        r'\bproton\s+(?:event|storm)',
        r'\bsolar\s+wind',
        r'\bbz\b',
        r'\d+\s*km/s',
        r'\bsunspot\s+(?:group\s+|region\s+)?(?:ar\s*)?\d{3,}',
        r'\bar\s?\d{4}\b',
        r'\bhalo\b',
        # Timing the data does not carry: clock times, days, arrival forecasts.
        r'\d{1,2}:\d{2}\s*(?:am|pm|utc|z)\b',
        r'\b\d{1,2}\s*(?:am|pm)\b',
        r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'(?:expected|forecast|predicted|due)\s+to\s+(?:hit|arrive|impact|strike|reach)',
        r'\bin\s+the\s+next\s+\d+\s+(?:hours?|days?)',
        r'\b(?:tonight|tomorrow)\s+at\b',
    ],
)

#: Words a weatherperson uses that the bands do not know: header lines and
#: model chatter that wrap the actual briefing.
_META_PATTERNS = [
    r'^(?:here\'?s|okay,? here\'?s|alright,? here\'?s|sure,? here\'?s|here you go|sure thing|certainly)[^:\n]*:\s*',
    r'^(?:here\'?s|here you go|sure thing|certainly)[,!.]?\s+',
    r'^(?:briefing|forecast|report|post|output|script)\s*:\s*',
    r'^\*\*[^*\n]{0,60}\*\*\s*:?\s*',
]

_NEGATIONS = re.compile(
    r'\b(?:no|not|non|without|zero|free\s+of|absence\s+of|nothing\s+above|below|under|'
    r'stayed\s+out\s+of|short\s+of|never|any)\b',
    re.IGNORECASE,
)

# The words a weatherperson puts between a reading's name and its value:
# "K-index is holding at 2", "solar flux coming in at 145", "Kp reads 3".
_VERBS = (
    r'(?:\s+(?:is|was|of|at|to|a|an|the|reads?|reading|sits?|sitting|holds?|holding|hovering|'
    r'parked|steady|currently|now|today|tonight|around|near|about|roughly|value|level|'
    r'coming\s+in|up|down|only|just|still|comfortable|healthy|low|quiet))*'
)
_K_INDEX = re.compile(
    r'\bkp?(?:[- ]?index)?' + _VERBS + r'\s*[=:]?\s*(\d)\b',
    re.IGNORECASE,
)
_A_INDEX = re.compile(
    r'\ba[- ]?index' + _VERBS + r'\s*[=:]?\s*(\d{1,3})\b',
    re.IGNORECASE,
)
_SFI = re.compile(
    r'(?:\bsfi\b|solar\s+flux(?:\s+index)?)' + _VERBS + r'\s*[=:]?\s*(\d{2,3})\b',
    re.IGNORECASE,
)
_FLARE_CLASS = re.compile(
    r'\b([abcmx])(?:\d+(?:\.\d+)?)?[- ]class\b|\b([abcmx])(\d(?:\.\d)?)\s+(?:flare|event|level)',
    re.IGNORECASE,
)
_NOAA_SCALE = re.compile(r'\b([rsg])([0-5])\b', re.IGNORECASE)


class SpaceWeatherForecaster:
    """
    Generates the opening briefing through hypeman's LLM manager.

    Holds an LLMManager so the provider plumbing — Ollama, Gemini,
    reconnection, opt-in failover, retries — is the library's problem and
    the same across the daemons. What is SolarStorm Scout's own is the
    prompt, the read of the numbers, and the checks that the reply agrees
    with them.
    """

    def __init__(self):
        self.engine = LLMManager(profile=SPACE_WEATHER_PROFILE)
        self.enabled = False
        self._cache: dict[int, str | None] = {}

    def authenticate(self) -> bool:
        """
        Bring up the configured provider(s).

        Returns False when LLM_ENABLE is off or no provider constructs. A
        provider that is merely down right now still returns True — hypeman
        keeps the configuration and retries on the next availability check.
        """
        if not self.engine.authenticate():
            self.enabled = False
            return False

        self.enabled = True

        # Each run is a fresh process, so the recently-posted cache never
        # spans runs; within a run the Bluesky and Mastodon versions of the
        # same forecast are supposed to agree, so a near-duplicate is the
        # goal, not a defect.
        self.engine.enable_deduplication = False
        for provider in [self.engine.primary, *self.engine.fallbacks]:
            if provider is not None:
                provider.enable_deduplication = False
        return True

    def is_available(self) -> bool:
        """True if a provider can generate right now. May heal a downed one."""
        return self.enabled and self.engine.is_available()

    def status(self) -> dict:
        """Provider state, for logs."""
        return self.engine.status()

    # ─────────────────────────────────────────────────────────────────────
    # Generation
    # ─────────────────────────────────────────────────────────────────────

    def briefing(self, data: dict, max_chars: int, platform: str = 'generic') -> str | None:
        """
        Write the on-air briefing for this run's data, or None.

        Args:
            data: The dict from spaceweather.fetch_space_weather_data().
            max_chars: Room left in the post after the header and hashtags.
            platform: 'bluesky' or 'mastodon', for hypeman's per-network checks.

        Returns:
            Briefing text that fits max_chars and agrees with the data, or
            None when the LLM is off, unreachable, or produced nothing usable.
            None always means "post the thread without it"; it never means
            "do not post".
        """
        if not self.enabled:
            return None
        if max_chars < 80:
            logger.info(f"ℹ️  Skipping briefing: only {max_chars} characters of room")
            return None

        # Both networks ask for the same budget more often than not; one
        # generation serves them both and keeps the thread consistent.
        if max_chars in self._cache:
            return self._cache[max_chars]

        result = None
        try:
            result = self._generate(data, max_chars, platform)
        except Exception as e:  # noqa: BLE001  # the briefing is optional; the thread is not
            logger.error(f"✗ Briefing generation failed: {type(e).__name__}: {e}")

        self._cache[max_chars] = result
        return result

    def _generate(self, data: dict, max_chars: int, platform: str) -> str | None:
        if not self.engine.is_available():
            logger.warning("⚠ LLM not available; posting without the briefing")
            return None

        max_tokens = max_chars // 2 + 30

        for strict in (False, True):
            prompt = build_prompt(data, max_chars, strict=strict)
            raw = self.engine.generate(prompt, max_tokens=max_tokens)
            if not raw:
                logger.warning("⚠ LLM returned nothing; posting without the briefing")
                return None

            text = clean_reply(raw)
            text = fit_to_budget(text, max_chars)
            if not text:
                logger.warning(
                    f"⚠ Briefing did not fit {max_chars} characters"
                    + (", retrying with a stricter prompt" if not strict else "")
                )
                continue

            issues = contradictions(text, data)
            if not issues:
                text, guard_issues = self.engine.apply_guardrails(
                    text,
                    title='space weather',
                    username='',
                    platform=platform,
                    char_limit=max_chars,
                    expected_hashtag_count=0,
                )
                issues = guard_issues if not text else []

            if not issues and text:
                logger.info(f"✨ Briefing ready ({len(text)} chars): {text[:70]}...")
                return text

            preview = '; '.join(issues[:3])
            logger.warning(
                f"⚠ Briefing rejected ({preview})"
                + (", retrying with a stricter prompt" if not strict else "")
            )

        logger.warning("⚠ No usable briefing this run; posting the data thread on its own")
        return None


# ─────────────────────────────────────────────────────────────────────────
# Pure helpers — no state, easy to test
# ─────────────────────────────────────────────────────────────────────────

def _num(value) -> float | None:
    """The value as a number, or None for the 'N/A' the fetcher leaves behind."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def describe_data(data: dict) -> str:
    """
    Lay the run's numbers out as plain lines for the prompt.

    Anything the fetcher could not get is left out rather than shown as
    N/A, so the model is never tempted to comment on a gap.
    """
    lines = []

    sfi = _num(data.get('solar_flux'))
    if sfi is not None:
        lines.append(f"- Solar flux index (SFI): {int(sfi)}")

    k = _num(data.get('k_index'))
    if k is not None:
        a = _num(data.get('a_index'))
        a_part = f", A-index {int(a)}" if a is not None else ''
        if k <= 2:
            mood = 'geomagnetic field quiet'
        elif k <= 3:
            mood = 'geomagnetic field unsettled'
        elif k == 4:
            mood = 'geomagnetic field active'
        else:
            mood = 'geomagnetic storm in progress'
        lines.append(f"- K-index: {int(k)}{a_part} ({mood})")

    fof2 = _num(data.get('fof2'))
    muf = _num(data.get('muf_dx'))
    if fof2 is not None and muf is not None:
        lines.append(f"- Estimated foF2 {fof2:.1f} MHz, MUF for DX about {muf:.0f} MHz")

    absorption = data.get('d_region_absorption')
    if absorption and absorption != 'N/A':
        lines.append(f"- D-layer absorption: {_strip_emoji(str(absorption))}")

    conditions = data.get('propagation_conditions')
    if conditions and conditions != 'N/A':
        lines.append(f"- Overall HF conditions: {_strip_emoji(str(conditions))}")

    bands = data.get('band_conditions') or {}
    if bands:
        band_text = ', '.join(f"{name} {info.get('quality', '?')}" for name, info in bands.items())
        lines.append(f"- Band by band: {band_text}")

    best = data.get('best_bands_now')
    if best and best != 'N/A':
        lines.append(f"- Best bands right now: {best}")

    aurora = _num(data.get('aurora_power'))
    if aurora is not None:
        if aurora >= 100:
            aurora_note = 'strong aurora, visible to mid-latitudes'
        elif aurora >= 50:
            aurora_note = 'moderate aurora at high latitudes'
        elif aurora >= 20:
            aurora_note = 'minor aurora near the poles'
        else:
            aurora_note = 'aurora quiet'
        lines.append(f"- Aurora hemispheric power: {aurora:.0f} GW ({aurora_note})")

    xray = data.get('xray_class')
    if xray and xray != 'N/A':
        letter = str(xray)[0].upper()
        flare_note = {
            'X': 'major flare in progress, HF blackouts likely',
            'M': 'medium flare, some HF degradation on the sunlit side',
            'C': 'small flare, minimal impact',
        }.get(letter, 'background level, no flares')
        lines.append(f"- GOES X-ray flux: {xray} ({flare_note})")

    scales = [f"{name}{data.get(key)}" for name, key in (('R', 'r_scale'), ('S', 's_scale'), ('G', 'g_scale'))
              if data.get(key) not in (None, 'N/A')]
    if scales:
        lines.append(f"- NOAA scales: {' '.join(scales)} (0 means none)")

    return '\n'.join(lines)


def build_prompt(data: dict, max_chars: int, strict: bool = False) -> str:
    """
    The prompt, tuned for small local models: explicit data, explicit
    rules, and the exact ways they tend to go wrong spelled out.
    """
    now = datetime.now(UTC).strftime('%H:%M UTC')
    sentences = '2 or 3 sentences' if max_chars >= 350 else '2 short sentences'

    rules = f"""RULES:
- Use ONLY the numbers and conditions listed above. Do not add anything the report does not say.
- No times, dates, days of the week, sunspot numbers, CMEs, solar wind, or predictions about later.
- Mention only the current X-ray level; do not talk about other flare classes.
- Plain text only: no hashtags, no URLs, no headings, no quotation marks, no bullet points, no preamble.
- {max_chars} characters maximum, {sentences}, at most one emoji.
- Output only the words you would say on the air."""

    if strict:
        rules += f"""
- STRICT: the previous attempt broke these rules. Shorter this time: well under {max_chars} characters.
- STRICT: every number you say must appear in the report above, exactly.
- STRICT: no emoji at all, no hashtags at all, nothing before or after the briefing."""

    return f"""You are the on-air space weather forecaster for an amateur radio show. Read the current HF propagation report to the operators listening, in the warm, plain-spoken voice of a radio weatherperson.

CURRENT REPORT ({now}):
{describe_data(data)}

STYLE: friendly and conversational, a little personality, ham-radio audience (bands, DX, QSOs). Say what the Sun is doing, what it means for the bands, and which bands to try. Sound like a person on the radio, not a table of numbers.

{rules}

Briefing:"""


def _strip_emoji(text: str) -> str:
    """Drop pictographs and variation selectors, keeping the words."""
    return re.sub(
        r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF️‍]',
        '', text,
    ).strip()


def clean_reply(raw: str) -> str:
    """
    Turn a model reply into the briefing text itself.

    Strips the chatter models wrap answers in, quotation marks, markdown,
    hashtags (the thread adds its own) and any URL, then folds the result
    into one paragraph.
    """
    text = raw.strip()
    for pattern in _META_PATTERNS:
        text = re.sub(pattern, '', text, count=1, flags=re.IGNORECASE)
    text = text.strip().strip('"\'“”').strip()
    text = re.sub(r'\*\*|__|`', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?<!\w)#\w+', '', text)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = ' '.join(text.split())
    # A quote that closed after a hashtag or link is only exposed now.
    return text.strip().strip('"\'“”').strip()


def fit_to_budget(text: str, max_chars: int) -> str | None:
    """
    Make the briefing fit, or admit it cannot.

    A reply that runs long is cut at the last sentence end inside the
    budget, because a briefing that stops mid-word sounds like a dropped
    call. When no sentence end leaves at least 40% of the budget, the reply
    is unusable and None asks for another attempt.
    """
    if not text:
        return None
    if len(text) <= max_chars:
        return text

    head = text[:max_chars]
    cut = max(head.rfind('. '), head.rfind('! '), head.rfind('? '),
              head.rfind('.'), head.rfind('!'), head.rfind('?'))
    if cut < int(max_chars * 0.4):
        return None
    return head[:cut + 1].strip()


def _negated(text: str, start: int) -> bool:
    """True if a negation sits within a few words before position start."""
    window = text[max(0, start - 40):start]
    return bool(_NEGATIONS.search(window))


def contradictions(text: str, data: dict) -> list[str]:
    """
    Numbers the briefing states that disagree with the data.

    The guardrails catch invented *kinds* of detail; this catches invented
    *values*: a K-index of 5 when it is 2, an M-class flare when the flux
    says B, a G2 storm when the scale reads G0. Mentions the model negates
    ("no M-class flares today") are left alone. Values the fetcher did not
    get are not checked, since there is nothing to check against.
    """
    issues: list[str] = []

    k = _num(data.get('k_index'))
    if k is not None:
        for match in _K_INDEX.finditer(text):
            if int(match.group(1)) != int(k):
                issues.append(f"says K-index {match.group(1)}, data says {int(k)}")
                break

    a = _num(data.get('a_index'))
    if a is not None:
        for match in _A_INDEX.finditer(text):
            if int(match.group(1)) != int(a):
                issues.append(f"says A-index {match.group(1)}, data says {int(a)}")
                break

    sfi = _num(data.get('solar_flux'))
    if sfi is not None:
        for match in _SFI.finditer(text):
            if int(match.group(1)) != int(sfi):
                issues.append(f"says SFI {match.group(1)}, data says {int(sfi)}")
                break

    xray = data.get('xray_class')
    if xray and xray != 'N/A':
        actual = str(xray)[0].upper()
        for match in _FLARE_CLASS.finditer(text):
            letter = (match.group(1) or match.group(2)).upper()
            if letter != actual and not _negated(text, match.start()):
                issues.append(f"says {letter}-class, data says {actual}-class ({xray})")
                break

    for name, key in (('R', 'r_scale'), ('S', 's_scale'), ('G', 'g_scale')):
        actual_scale = _num(data.get(key))
        if actual_scale is None:
            continue
        for match in _NOAA_SCALE.finditer(text):
            if match.group(1).upper() != name:
                continue
            if int(match.group(2)) != int(actual_scale) and not _negated(text, match.start()):
                issues.append(f"says {name}{match.group(2)}, data says {name}{int(actual_scale)}")
                break

    return issues
