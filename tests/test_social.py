"""Posting the thread through hypeman platforms, with the network faked."""

import asyncio

from solarstorm_scout import social as module
from solarstorm_scout.formatter import BRIEFING_HEADER, DRAP_IMAGE_URL
from solarstorm_scout.social import ImageCache, SocialMediaManager

PNG = b'\x89PNG\r\n\x1a\n' + b'chart'


class FakePlatform:
    """Records what a hypeman SocialPlatform would have been asked to post."""

    def __init__(self, name='Fake', fail_at=None, auth=True):
        self.name = name
        self.posts = []
        self.fail_at = fail_at
        self.auth = auth

    def authenticate(self):
        return self.auth

    def safe_post(self, message, reply_to_id=None, stream_data=None):
        self.posts.append({'text': message, 'reply_to_id': reply_to_id, 'stream_data': stream_data})
        if self.fail_at == len(self.posts):
            return None
        return f'{self.name}-{len(self.posts)}'


class FakeImages(ImageCache):
    def __init__(self, table):
        super().__init__()
        self.table = table
        self.requests = []

    async def get(self, image_url):
        self.requests.append(image_url)
        return self.table.get(image_url)


def run(coro):
    return asyncio.run(coro)


class TestPostThread:
    def test_replies_chain_and_images_ride_along(self, data):
        manager = SocialMediaManager()
        platform = FakePlatform('Bluesky')
        images = FakeImages({module.GENERATE_CHART: PNG, DRAP_IMAGE_URL: b'map'})
        posts = module.format_thread_posts(data, 'bluesky')

        assert run(manager.post_thread(platform, posts, images)) is True
        assert [p['reply_to_id'] for p in platform.posts] == [None, 'Bluesky-1', 'Bluesky-2', 'Bluesky-3', 'Bluesky-4']
        # D-RAP map and chart attached with alt text; aurora (not in the table) left off.
        assert platform.posts[2]['stream_data']['images'][0]['data'] == b'map'
        assert 'Absorption' in platform.posts[2]['stream_data']['images'][0]['alt']
        assert platform.posts[3]['stream_data'] is None
        assert platform.posts[4]['stream_data']['images'][0]['data'] == PNG
        assert platform.posts[0]['stream_data'] is None

    def test_failure_mid_thread_stops_and_reports(self, data):
        manager = SocialMediaManager()
        platform = FakePlatform('Mastodon', fail_at=2)
        posts = module.format_thread_posts(data, 'mastodon')
        assert run(manager.post_thread(platform, posts, FakeImages({}))) is False
        assert len(platform.posts) == 2


class TestPostToAll:
    def test_briefing_source_is_asked_per_platform_and_images_shared(self, data, monkeypatch):
        monkeypatch.setattr(module, 'ImageCache', lambda session=None: FakeImages({}))
        manager = SocialMediaManager()
        bsky, masto = FakePlatform('Bluesky'), FakePlatform('Mastodon')
        assert manager.add_platform('bluesky', bsky) and manager.add_platform('mastodon', masto)
        asked = []

        def briefing_source(payload, max_chars, platform):
            asked.append((max_chars, platform))
            return 'Quiet Sun, open bands.' if platform == 'mastodon' else None

        results = run(manager.post_to_all(data, include_hamradio=False, briefing_source=briefing_source))
        assert results == {'Bluesky': True, 'Mastodon': True}
        assert [p for _, p in asked] == ['bluesky', 'mastodon']
        assert asked[0][0] < asked[1][0]
        assert len(bsky.posts) == 5 and len(masto.posts) == 6
        assert masto.posts[0]['text'].startswith(BRIEFING_HEADER)

    def test_one_platform_failing_does_not_block_the_other(self, data, monkeypatch):
        manager = SocialMediaManager()
        broken, fine = FakePlatform('Bluesky'), FakePlatform('Mastodon')
        manager.add_platform('bluesky', broken)
        manager.add_platform('mastodon', fine)

        def explode(*a, **k):
            raise RuntimeError('boom')

        broken.safe_post = explode
        monkeypatch.setattr(module, 'ImageCache', lambda session=None: FakeImages({}))
        results = run(manager.post_to_all(data))
        assert results == {'Bluesky': False, 'Mastodon': True}

    def test_failed_authentication_is_not_added(self):
        manager = SocialMediaManager()
        assert manager.add_platform('bluesky', FakePlatform(auth=False)) is False
        assert manager.add_platform('nope') is False
        assert manager.get_platform_count() == 0


class TestConfigureAll:
    def test_nothing_enabled(self, monkeypatch):
        manager = SocialMediaManager()
        assert manager.configure_all() == []

    def test_enabled_platforms_are_constructed(self, monkeypatch):
        monkeypatch.setenv('MASTODON_ENABLE_POSTING', 'true')
        monkeypatch.setattr(module, 'PLATFORM_CLASSES', {'mastodon': lambda: FakePlatform('Mastodon')})
        manager = SocialMediaManager()
        assert manager.configure_all() == ['Mastodon']


class TestImageCache:
    def test_downloads_once_and_remembers_misses(self, monkeypatch):
        calls = []

        async def fake_download(url, session=None):
            calls.append(url)
            return b'img' if 'good' in url else None

        monkeypatch.setattr(module, 'download_image', fake_download)
        cache = ImageCache()
        assert run(cache.get('https://x/good.png')) == b'img'
        assert run(cache.get('https://x/good.png')) == b'img'
        assert run(cache.get('https://x/bad.png')) is None
        assert run(cache.get('https://x/bad.png')) is None
        assert calls == ['https://x/good.png', 'https://x/bad.png']

    def test_chart_is_rendered_via_renderer(self, monkeypatch):
        import io

        async def fake_plot(period):
            return io.BytesIO(PNG)

        monkeypatch.setattr(module, 'plot_xray_flux', fake_plot)
        assert run(ImageCache().get(module.GENERATE_CHART)) == PNG
