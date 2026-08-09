"""存储与哈希单测（本地后端，零外依赖）。"""

from __future__ import annotations

from servevo_audit.storage import LocalStorage, compute_hash, json_bytes


def test_local_storage_roundtrip(tmp_path):
    st = LocalStorage(root=tmp_path)
    data = b"hello servevo"
    key = "test/data.txt"
    info = st.upload(data, key)
    assert info["sha256"] == compute_hash(data)
    assert st.download(key) == data
    assert st.exists(key)
    st.delete(key)
    assert not st.exists(key)


def test_local_storage_path_traversal_blocked(tmp_path):
    st = LocalStorage(root=tmp_path)
    try:
        st.upload(b"x", "../../evil.txt")
        assert False, "应拒绝路径穿越"
    except ValueError:
        pass


def test_generate_key_safe():
    key = LocalStorage.generate_key("audit", "我 的 报告.md")
    assert key.startswith("audit/")
    assert not any(c in key for c in " ")
    assert key.endswith(".md")


def test_json_bytes_valid():
    assert json_bytes({"a": 1}) == b'{\n  "a": 1\n}'