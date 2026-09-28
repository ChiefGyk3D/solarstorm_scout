"""
The forecaster against a fake engine: cleanup, fitting, the agreement checks,
and above all that every failure means "no briefing", never an exception.
"""

import pytest

from solarstorm_scout import forecaster as module
from solarstorm_scout.forecaster import (
    SPACE_WEATHER_PROFILE,
    SpaceWeatherForecaster,
    build_prompt,
    clean_reply,
    contradictions,
    describe_data,
    fit_to_budget,
)

GOOD = ('Good evening, operators! The Sun is behaving with the solar flux at 145 and a '
        'K-index of 2, so the bands are wide open. Point your antennas toward 20m and 17m for DX.')


class FakeEngine:
    """Stands in for hypeman's LLMManager."""

    def __init__(self, replies=None, available=True, auth=True):
        self.replies = list(replies or [])
        self.available = available
        self.auth = auth
        self.prompts = []
        self.enabled = False
        self.enable_deduplication = True
        self.primary = None
        self.fallbacks = []
        self.guardrail_issues = []

    def authenticate(self):
        self.enabled = self.auth
        return self.auth

    def is_available(self):
        return self.available

    def generate(self, prompt, max_tokens=None):
        self.prompts.append(prompt)
        if not self.replies:
            return None
        return self.replies.pop(0)

    def apply_guardrails(self, message, **kwargs):
        if self.guardrail_issues:
            return None, list(self.guardrail_issues)
        return message, []

    def status(self):
        return {'enabled': self.enabled}


@pytest.fixture
def make(monkeypatch):
    def _make(replies=None, **kwargs):
        engine = FakeEngine(replies, **kwargs)
        monkeypatch.setattr(module, 'LLMManager', lambda profile: engine)
        forecaster = SpaceWeatherForecaster()
        assert forecaster.engine is engine
        return forecaster, engine
    return _make


class TestCleanReply:
    def test_strips_chatter_quotes_markdown_hashtags_urls(self):
        raw = ('Here\'s your briefing:\n"**Good evening!** The Sun is quiet. '
               'Try 20m. #HamRadio https://swpc.noaa.gov"')
        assert clean_reply(raw) == 'Good evening! The Sun is quiet. Try 20m.'

    def test_folds_lines_and_bullets(self):
        assert clean_reply('- Quiet Sun.\n- Bands open.\n\n  Try 40m.') == 'Quiet Sun. Bands open. Try 40m.'

    def test_leading_label_removed(self):
        assert clean_reply('Briefing: The Sun is quiet.') == 'The Sun is quiet.'

    def test_quote_closing_after_a_hashtag_is_removed(self):
        assert clean_reply('"The Sun is quiet. Try 20m." #HamRadio') == 'The Sun is quiet. Try 20m.'

    def test_plain_text_untouched(self):
        assert clean_reply(GOOD) == GOOD


class TestFitToBudget:
    def test_short_enough_is_returned_as_is(self):
        assert fit_to_budget(GOOD, 400) == GOOD

    def test_cuts_at_a_sentence_end(self):
        text = 'First sentence here. Second sentence here! Third one goes past the budget?'
        fitted = fit_to_budget(text, 45)
        assert fitted == 'First sentence here. Second sentence here!'

    def test_no_sentence_end_early_enough_means_none(self):
        assert fit_to_budget('word ' * 60, 100) is None
        assert fit_to_budget('Short. ' + 'x' * 200, 100) is None

    def test_empty_is_none(self):
        assert fit_to_budget('', 100) is None


class TestContradictions:
    def test_agreeing_text_passes(self, data):
        assert contradictions(GOOD, data) == []

    def test_wrong_k_index(self, data):
        assert contradictions('The K-index is 5 tonight.', data)
        assert contradictions('Kp sits at 4.', data)
        assert contradictions('K index of 2 today.', data) == []

    def test_wrong_sfi_and_a_index(self, data):
        assert contradictions('Solar flux at 180 today.', data)
        assert contradictions('SFI 145 keeps the high bands open.', data) == []
        assert contradictions('The A-index reads 40.', data)
        assert contradictions('Kp is holding at a comfortable 3.', data)
        assert contradictions('solar flux coming in at 145 today', data) == []

    def test_wrong_flare_class(self, data):
        assert contradictions('An M-class flare just went off!', data)
        assert contradictions('X2.1 flare in progress.', data)
        assert contradictions('B-class background, nothing to worry about.', data) == []

    def test_negated_flare_class_is_allowed(self, data):
        assert contradictions('No M-class flares today, the Sun is calm.', data) == []
        assert contradictions('We are free of any X-class activity.', data) == []

    def test_wrong_noaa_scale(self, data):
        assert contradictions('A G2 geomagnetic storm is underway.', data)
        assert contradictions('Scales read R0 S0 G0 across the board.', data) == []
        assert contradictions('No G1 storming expected.', data) == []

    def test_missing_data_is_not_checked(self, data):
        data['k_index'] = 'N/A'
        data['xray_class'] = 'N/A'
        assert contradictions('K-index 7 and an X-class flare.', data) == []


class TestPrompt:
    def test_describe_lists_every_reading_and_skips_gaps(self, data):
        text = describe_data(data)
        for needle in ('SFI): 145', 'K-index: 2', 'A-index 13', 'B4.2', 'R0 S0 G0',
                       '20m, 17m, 15m, 12m', '12 GW', 'Moderate (Day)'):
            assert needle in text
        assert '🟡' not in text

        data['aurora_power'] = 'N/A'
        data['xray_class'] = 'N/A'
        text = describe_data(data)
        assert 'Aurora' not in text and 'X-ray' not in text and 'N/A' not in text

    def test_strict_prompt_adds_rules_and_keeps_budget(self, data):
        loose = build_prompt(data, 240)
        strict = build_prompt(data, 240, strict=True)
        assert '240 characters maximum' in loose
        assert 'STRICT' not in loose and 'STRICT' in strict
        assert 'no hashtags' in loose.lower()

    def test_profile_rejects_invented_events(self):
        import re
        for text in ('A CME is expected to arrive tonight at 8pm', 'watch sunspot AR 4123',
                     'solar wind at 600 km/s', 'better conditions on Tuesday'):
            assert any(re.search(p, text, re.IGNORECASE) for p in SPACE_WEATHER_PROFILE.hallucination_patterns), text
        assert not any(re.search(p, GOOD, re.IGNORECASE) for p in SPACE_WEATHER_PROFILE.hallucination_patterns)


class TestBriefing:
    def test_disabled_llm_means_none_and_no_calls(self, make, data):
        forecaster, engine = make([GOOD], auth=False)
        assert forecaster.authenticate() is False
        assert forecaster.briefing(data, 240, 'bluesky') is None
        assert engine.prompts == []

    def test_happy_path(self, make, data):
        forecaster, engine = make([GOOD])
        assert forecaster.authenticate() is True
        assert engine.enable_deduplication is False
        assert forecaster.briefing(data, 400, 'mastodon') == GOOD
        assert len(engine.prompts) == 1

    def test_same_budget_generates_once(self, make, data):
        forecaster, engine = make([GOOD, 'Different text.'])
        forecaster.authenticate()
        assert forecaster.briefing(data, 240, 'bluesky') == forecaster.briefing(data, 240, 'mastodon')
        assert len(engine.prompts) == 1

    def test_unavailable_provider_means_none(self, make, data):
        forecaster, engine = make([GOOD], available=False)
        forecaster.authenticate()
        assert forecaster.briefing(data, 240, 'bluesky') is None
        assert engine.prompts == []

    def test_empty_reply_means_none(self, make, data):
        forecaster, _ = make([])
        forecaster.authenticate()
        assert forecaster.briefing(data, 240, 'bluesky') is None

    def test_contradiction_triggers_one_strict_retry(self, make, data):
        forecaster, engine = make(['The K-index is 6 and rising.', GOOD])
        forecaster.authenticate()
        assert forecaster.briefing(data, 400, 'mastodon') == GOOD
        assert len(engine.prompts) == 2
        assert 'STRICT' in engine.prompts[1]

    def test_two_bad_replies_means_none(self, make, data):
        forecaster, engine = make(['An M-class flare erupted!', 'Kp 5 storm levels.'])
        forecaster.authenticate()
        assert forecaster.briefing(data, 400, 'mastodon') is None
        assert len(engine.prompts) == 2

    def test_guardrail_rejection_means_none(self, make, data):
        forecaster, engine = make([GOOD, GOOD])
        forecaster.authenticate()
        engine.guardrail_issues = ['Contains forbidden words: insane']
        assert forecaster.briefing(data, 400, 'mastodon') is None

    def test_overlong_reply_is_fitted_or_dropped(self, make, data):
        long_reply = GOOD + ' And now a very long ramble about antennas that runs past any budget.'
        forecaster, _ = make([long_reply])
        forecaster.authenticate()
        result = forecaster.briefing(data, len(GOOD) + 10, 'mastodon')
        assert result == GOOD

    def test_engine_exception_is_swallowed(self, make, data):
        forecaster, engine = make([GOOD])
        forecaster.authenticate()

        def explode(*a, **k):
            raise RuntimeError('ollama on fire')

        engine.generate = explode
        assert forecaster.briefing(data, 240, 'bluesky') is None

    def test_tiny_budget_skips_generation(self, make, data):
        forecaster, engine = make([GOOD])
        forecaster.authenticate()
        assert forecaster.briefing(data, 50, 'bluesky') is None
        assert engine.prompts == []
