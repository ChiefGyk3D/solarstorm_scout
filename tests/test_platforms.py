"""The 0.2.0 shim: images and token-only Mastodon auth, against fake clients."""

from types import SimpleNamespace

import pytest

from solarstorm_scout import platforms as module
from solarstorm_scout.platforms import BlueskyPlatform, MastodonPlatform, images_in, sniff_image_mime

PNG = b'\x89PNG\r\n\x1a\n' + b'chart'


@pytest.fixture
def shim_active(monkeypatch):
    """Exercise the shim's own code path regardless of the installed hypeman."""
    monkeypatch.setattr(module, 'LIBRARY_HAS_IMAGES', False)


class TestHelpers:
    def test_sniff(self):
        assert sniff_image_mime(PNG) == 'image/png'
        assert sniff_image_mime(b'\xff\xd8\xffx') == 'image/jpeg'
        assert sniff_image_mime(b'?') == 'image/png'

    def test_images_in_drops_garbage_and_caps(self):
        entries = [{'data': PNG, 'alt': str(i)} for i in range(6)] + [None, {'alt': 'no data'}]
        resolved = images_in({'images': entries})
        assert [i['alt'] for i in resolved] == ['0', '1', '2', '3']
        assert resolved[0]['mime_type'] == 'image/png'
        assert images_in(None) == [] and images_in({}) == []


class FakeBuilder:
    def __init__(self):
        self.parts = []

    def text(self, v):
        self.parts.append(('text', v))

    def tag(self, display, tag):
        self.parts.append(('tag', tag))


class FakeModels:
    class AppBskyEmbedImages:
        @staticmethod
        def Main(images):
            return SimpleNamespace(images=images)

        @staticmethod
        def Image(alt, image):
            return SimpleNamespace(alt=alt, image=image)

    class AppBskyFeedPost:
        @staticmethod
        def ReplyRef(parent, root):
            return SimpleNamespace(parent=parent, root=root)

    @staticmethod
    def create_strong_ref(post):
        return SimpleNamespace(uri=post.uri, cid='cid')


class FakeBskyClient:
    def __init__(self):
        self.sent = []
        self.parent = SimpleNamespace(uri='at://post/parent', record=SimpleNamespace(reply=None))
        self.app = SimpleNamespace(bsky=SimpleNamespace(feed=SimpleNamespace(
            get_posts=lambda params: SimpleNamespace(posts=[self.parent]))))

    def upload_blob(self, data):
        return SimpleNamespace(blob=SimpleNamespace(size=len(data)))

    def send_post(self, builder, reply_to=None, embed=None):
        self.sent.append({'builder': builder, 'reply_to': reply_to, 'embed': embed})
        return SimpleNamespace(uri=f'at://post/{len(self.sent)}')


@pytest.fixture
def bsky(monkeypatch, shim_active):
    monkeypatch.setattr(module._bluesky, 'models', FakeModels)
    monkeypatch.setattr(module._bluesky, 'client_utils', SimpleNamespace(TextBuilder=FakeBuilder))
    platform = BlueskyPlatform()
    platform.enabled = platform.authenticated = True
    platform.client = FakeBskyClient()
    return platform


class TestBlueskyShim:
    def test_images_embed_with_alt_and_thread(self, bsky):
        uri = bsky.post('X-ray #SolarStormScout', reply_to_id='at://post/parent',
                        stream_data={'images': [{'data': PNG, 'alt': 'chart'}]})
        assert uri == 'at://post/1'
        sent = bsky.client.sent[0]
        assert sent['embed'].images[0].alt == 'chart'
        assert sent['reply_to'].root.uri == 'at://post/parent'
        assert ('tag', 'SolarStormScout') in sent['builder'].parts

    def test_no_images_defers_to_library(self, bsky, monkeypatch):
        called = []
        monkeypatch.setattr(module._bluesky.BlueskyPlatform, 'post',
                            lambda self, *a, **k: called.append(a) or 'at://lib')
        assert bsky.post('plain text') == 'at://lib'
        assert called

    def test_upload_failure_still_posts_text(self, bsky):
        bsky.client.upload_blob = lambda data: (_ for _ in ()).throw(RuntimeError('down'))
        assert bsky.post('t', stream_data={'images': [{'data': PNG, 'alt': 'a'}]}) == 'at://post/1'
        assert bsky.client.sent[0]['embed'] is None


class FakeMastodon:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.uploads = []
        self.statuses = []

    def media_post(self, media_file, mime_type=None, description=None):
        self.uploads.append((media_file, mime_type, description))
        return {'id': f'm{len(self.uploads)}'}

    def status_post(self, message, in_reply_to_id=None, media_ids=None):
        self.statuses.append((message, in_reply_to_id, media_ids))
        return {'id': 42}


@pytest.fixture
def masto_env(monkeypatch, shim_active):
    monkeypatch.setenv('MASTODON_ENABLE_POSTING', 'true')
    monkeypatch.setenv('MASTODON_ACCESS_TOKEN', 'tok')
    monkeypatch.setenv('MASTODON_API_BASE_URL', 'https://m.example')
    monkeypatch.delenv('MASTODON_CLIENT_ID', raising=False)
    monkeypatch.delenv('MASTODON_CLIENT_SECRET', raising=False)
    monkeypatch.setattr(module._mastodon, 'Mastodon', FakeMastodon)
    monkeypatch.setattr(module._mastodon, 'MASTODON_AVAILABLE', True)


class TestMastodonShim:
    def test_token_only_auth(self, masto_env):
        platform = MastodonPlatform()
        assert platform.authenticate() is True
        assert platform.client.kwargs == {'access_token': 'tok', 'api_base_url': 'https://m.example'}

    def test_client_pair_passed_when_both_set(self, masto_env, monkeypatch):
        monkeypatch.setenv('MASTODON_CLIENT_ID', 'cid')
        monkeypatch.setenv('MASTODON_CLIENT_SECRET', 'sec')
        platform = MastodonPlatform()
        assert platform.authenticate() is True
        assert platform.client.kwargs['client_id'] == 'cid'

    def test_missing_token_fails(self, masto_env, monkeypatch):
        monkeypatch.delenv('MASTODON_ACCESS_TOKEN')
        assert MastodonPlatform().authenticate() is False

    def test_images_uploaded_from_bytes(self, masto_env):
        platform = MastodonPlatform()
        platform.authenticate()
        assert platform.post('X-ray', reply_to_id='7',
                             stream_data={'images': [{'data': PNG, 'alt': 'chart'}]}) == '42'
        assert platform.client.uploads == [(PNG, 'image/png', 'chart')]
        assert platform.client.statuses == [('X-ray', '7', ['m1'])]

    def test_no_images_defers_to_library(self, masto_env, monkeypatch):
        platform = MastodonPlatform()
        platform.authenticate()
        monkeypatch.setattr(module._mastodon.MastodonPlatform, 'post', lambda self, *a, **k: '99')
        assert platform.post('plain') == '99'
