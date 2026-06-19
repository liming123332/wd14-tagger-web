from pathlib import Path
import pytest
from backend.tagger.models_spec import MODEL_SPECS, DEFAULT_MODEL_KEY, is_downloaded, ModelSpec


def test_seven_models_present():
    assert set(MODEL_SPECS.keys()) == {
        "wd14", "wd3", "wd_vit_v3", "wd_eva_v3", "wd_conv_v3", "ddb", "e621"
    }
    assert DEFAULT_MODEL_KEY == "wd14"


def test_each_spec_has_required_fields():
    for key, spec in MODEL_SPECS.items():
        assert spec.key == key
        assert spec.label  # 非空
        assert spec.folder
        assert "model.onnx" in spec.files  # 第二个文件 csv 或 txt
        assert spec.prep in ("bgr_wd", "ddb")
        assert spec.tag_source in ("csv", "txt")


def test_ddb_uses_txt_and_ddb_prep():
    s = MODEL_SPECS["ddb"]
    assert s.tag_source == "txt"
    assert "tags.txt" in s.files
    assert s.prep == "ddb"


def test_wd_models_use_csv_and_bgr():
    for key in ("wd14", "wd3", "wd_vit_v3", "wd_eva_v3", "wd_conv_v3", "e621"):
        s = MODEL_SPECS[key]
        assert s.tag_source == "csv"
        assert "selected_tags.csv" in s.files
        assert s.prep == "bgr_wd"


def test_is_downloaded_true_when_all_files_exist(tmp_path):
    root = tmp_path / "models"
    s = MODEL_SPECS["wd14"]
    d = root / s.folder
    d.mkdir(parents=True)
    for name in s.files:
        (d / name).write_text("x")
    assert is_downloaded("wd14", root) is True


def test_is_downloaded_false_when_missing(tmp_path):
    root = tmp_path / "models"
    root.mkdir()
    # 目录都没有
    assert is_downloaded("wd14", root) is False
    # 只有部分文件
    d = root / MODEL_SPECS["wd14"].folder
    d.mkdir()
    (d / "model.onnx").write_text("x")  # 缺 csv
    assert is_downloaded("wd14", root) is False


def test_is_downloaded_unknown_key_raises(tmp_path):
    with pytest.raises(KeyError):
        is_downloaded("nope", tmp_path)
