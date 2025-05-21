import os
import sys
import types
import importlib.util
import importlib.machinery
from pathlib import Path


def load_run_module(tmp_path):
    config = types.SimpleNamespace(
        PROCESSED_FOLDER=str(tmp_path / "processed"),
        CHUNKS_FOLDER=str(tmp_path / "chunks"),
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
        LATIN_FOLDER=str(tmp_path / "latin"),
        AUDIO_OUTPUT_FOLDER=str(tmp_path / "audio"),
        SUBTITLE_OUTPUT=str(tmp_path / "subtitles"),
    )
    sys.modules['config'] = types.SimpleNamespace(Config=config)
    sys.modules['textract_ssml_processor'] = types.SimpleNamespace(create_app=lambda: None)

    path = Path(__file__).resolve().parents[1] / 'run.py'
    loader = importlib.machinery.SourceFileLoader('run_module', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module, config


def test_create_directories(tmp_path):
    run_mod, cfg = load_run_module(tmp_path)
    run_mod.create_directories()
    for d in [
        cfg.PROCESSED_FOLDER,
        cfg.CHUNKS_FOLDER,
        cfg.UPLOAD_FOLDER,
        cfg.LATIN_FOLDER,
        cfg.AUDIO_OUTPUT_FOLDER,
        cfg.SUBTITLE_OUTPUT,
    ]:
        assert os.path.isdir(d)
