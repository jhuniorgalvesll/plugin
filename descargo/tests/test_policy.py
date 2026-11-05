import pytest

from descargo.core import policy


@pytest.mark.parametrize("url", [
    "https://www.netflix.com/watch/80100172",
    "https://www.disneyplus.com/video/abc",
    "https://open.spotify.com/track/xyz",
    "https://www.udemy.com/course/python/learn/lecture/1",
    "https://www.amazon.com/gp/video/detail/B0123",
    "https://www.amazon.es/gp/video/detail/B0123",
    "https://www.linkedin.com/learning/curso-x",
    "https://onlyfans.com/someone",
    "https://www.patreon.com/posts/123",
    "https://play.max.com/video/watch/1",
    "https://vimeo.com/ondemand/pelicula",
])
def test_paid_urls_blocked(url):
    assert policy.is_paid_url(url)
    with pytest.raises(policy.BlockedContentError):
        policy.check_url(url)


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.facebook.com/reel/123",
    "https://www.instagram.com/reel/abc/",
    "https://www.tiktok.com/@user/video/123",
    "https://vimeo.com/76979871",
    "https://www.amazon.com/dp/B0123",           # tienda, no Prime Video
    "https://www.linkedin.com/posts/video-123",  # publicación, no cursos
    "https://example.com/video.mp4",
    "https://notnetflix.com/video",
])
def test_free_urls_allowed(url):
    assert not policy.is_paid_url(url)
    policy.check_url(url)


def test_drm_and_premium_info_blocked():
    with pytest.raises(policy.BlockedContentError):
        policy.check_info({"formats": [{"has_drm": True}, {"has_drm": True}]})
    with pytest.raises(policy.BlockedContentError):
        policy.check_info({"availability": "premium_only"})
    with pytest.raises(policy.BlockedContentError):
        policy.check_info({"webpage_url": "https://www.netflix.com/title/1"})
    policy.check_info({"formats": [{"has_drm": True}, {"has_drm": False}], "availability": "public"})


def test_error_messages_detected():
    assert policy.blocked_reason_from_error("ERROR: This video is DRM protected") == policy.DRM_MESSAGE
    assert policy.blocked_reason_from_error("Join this channel to get access to members-only content")
    assert policy.blocked_reason_from_error("HTTP Error 404") is None
