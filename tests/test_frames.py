from __future__ import annotations

from pathlib import Path

import frames


def touch(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"jpg")
    return path


def test_merge_fills_gaps_between_sparse_scenes(tmp_path):
    scenes = [(touch(tmp_path, "scene_1.jpg"), 4.0), (touch(tmp_path, "scene_2.jpg"), 300.0)]
    even = [(touch(tmp_path, f"even_{i}.jpg"), at) for i, at in enumerate([50.0, 150.0, 290.0, 450.0])]
    merged = frames.merge(scenes, even, gap=25.0)
    assert [at for _, at in merged] == [4.0, 50.0, 150.0, 300.0, 450.0]
    assert not (tmp_path / "even_2.jpg").exists()  # 290 s is covered by the scene at 300 s


def test_sample_spreads_over_the_whole_video_and_deletes_the_rest(tmp_path):
    shots = [(touch(tmp_path, f"f{i:02d}.jpg"), float(i)) for i in range(30)]
    kept = frames.sample(shots, 6)
    assert [at for _, at in kept] == [0.0, 6.0, 12.0, 17.0, 23.0, 29.0]
    assert len(list(tmp_path.glob("*.jpg"))) == 6
    assert frames.sample(shots[:3], 6) == shots[:3]


def test_sample_follows_time_not_clustered_scene_changes(tmp_path):
    busy = [(touch(tmp_path, f"busy{i:02d}.jpg"), float(i)) for i in range(20)]  # 20 cuts in 20 s
    slow = [(touch(tmp_path, f"slow{i}.jpg"), at) for i, at in enumerate([300.0, 600.0, 900.0])]
    kept = frames.sample(busy + slow, 5)
    assert [at for _, at in kept] == [0.0, 19.0, 300.0, 600.0, 900.0]


def test_prune_removes_only_old_frame_folders(tmp_path):
    import os

    old, fresh = tmp_path / "frames" / "old", tmp_path / "frames" / "fresh"
    for folder in (old, fresh):
        folder.mkdir(parents=True)
    os.utime(old, (0, 0))
    os.utime(tmp_path / "frames", (0, 0))
    frames.prune(tmp_path / "frames")
    assert not old.exists() and fresh.exists() and (tmp_path / "frames").exists()


def test_clock():
    assert frames.clock(75.9) == "01:15" and frames.clock(3725) == "1:02:05"
