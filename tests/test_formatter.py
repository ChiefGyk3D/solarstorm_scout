"""Thread layout: numbering, limits, hashtags, and the optional briefing post."""

import pytest

from solarstorm_scout.formatter import (
    BRIEFING_HEADER,
    briefing_char_budget,
    char_limit_for,
    format_thread_posts,
    get_post_stats,
)


@pytest.mark.parametrize('platform', ['bluesky', 'mastodon'])
class TestDataThread:
    def test_five_posts_numbered_out_of_five(self, data, platform):
        posts = format_thread_posts(data, platform)
        assert len(posts) == 5
        for index, post in enumerate(posts, start=1):
            assert f"({index}/5)" in post['text'].split('\n', 1)[0]

    def test_every_post_fits_its_platform(self, data, platform):
        for post in format_thread_posts(data, platform):
            assert len(post['text']) <= char_limit_for(platform)

    def test_hashtags_present_and_hamradio_toggles(self, data, platform):
        with_tag = format_thread_posts(data, platform, include_hamradio=True)
        without = format_thread_posts(data, platform, include_hamradio=False)
        for post in with_tag:
            assert '#SolarStormScout' in post['text'] and '#HamRadio' in post['text']
        for post in without:
            assert '#SolarStormScout' in post['text'] and '#HamRadio' not in post['text']

    def test_images_on_the_right_posts(self, data, platform):
        posts = format_thread_posts(data, platform)
        assert [bool(p['image_url']) for p in posts] == [False, False, True, True, True]
        assert posts[4]['image_url'] == 'GENERATE_CHART'
        assert all(p['alt_text'] for p in posts if p['image_url'])


@pytest.mark.parametrize('platform', ['bluesky', 'mastodon'])
class TestBriefingPost:
    def test_briefing_opens_the_thread_and_renumbers(self, data, platform):
        briefing = 'The Sun is quiet, the bands are open. Try 20m and 17m for DX.'
        posts = format_thread_posts(data, platform, briefing=briefing)
        assert len(posts) == 6
        assert posts[0]['text'].startswith(f"{BRIEFING_HEADER} (1/6)")
        assert briefing in posts[0]['text']
        assert posts[0]['image_url'] is None
        for index, post in enumerate(posts, start=1):
            assert f"({index}/6)" in post['text'].split('\n', 1)[0]
        assert '(1/5)' not in ''.join(p['text'] for p in posts)

    def test_briefing_at_full_budget_fits(self, data, platform):
        for include_hamradio in (True, False):
            budget = briefing_char_budget(platform, include_hamradio)
            assert budget > 100
            briefing = 'x' * budget
            posts = format_thread_posts(data, platform, include_hamradio, briefing)
            assert len(posts[0]['text']) <= char_limit_for(platform)

    def test_no_briefing_means_no_change(self, data, platform):
        assert format_thread_posts(data, platform, briefing=None) == format_thread_posts(data, platform)
        assert format_thread_posts(data, platform, briefing='') == format_thread_posts(data, platform)


def test_budget_is_tighter_with_hamradio():
    assert briefing_char_budget('bluesky', True) < briefing_char_budget('bluesky', False)
    assert briefing_char_budget('mastodon', True) > briefing_char_budget('bluesky', True)


def test_unknown_platform_uses_the_tight_limit():
    assert char_limit_for('threads') == 300


def test_post_stats_count_and_limit(data):
    posts = format_thread_posts(data, 'mastodon', briefing='Quiet Sun today.')
    stats = get_post_stats(posts, 'mastodon')
    assert stats['count'] == 6
    assert stats['limit'] == 500
    assert all(p['remaining'] >= 0 for p in stats['posts'])
