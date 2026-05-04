
from docsync.cache import FileCache


def test_cache_roundtrip(tmp_path):
    c = FileCache(tmp_path / "c.json")
    k = FileCache.key_for("hello")
    assert c.get(k) is None
    c.set(k, {"x": 1})
    c2 = FileCache(tmp_path / "c.json")
    assert c2.get(k) == {"x": 1}
