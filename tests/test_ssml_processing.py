import sys
import types
import importlib.util
import importlib.machinery
from pathlib import Path


def load_ssml_module():
    sys.modules['boto3'] = types.SimpleNamespace(client=lambda *a, **k: None)
    sys.modules['botocore.exceptions'] = types.SimpleNamespace(BotoCoreError=Exception, ClientError=Exception)
    path = Path(__file__).resolve().parents[1] / 'pipeline_support' / 'ssml_processing.py'
    loader = importlib.machinery.SourceFileLoader('ssml_module', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_split_ssml_basic():
    ssml_mod = load_ssml_module()
    ssml = '<speak>Hello <break/>world <p>test</p></speak>'
    chunks = ssml_mod.split_ssml(ssml, max_chunk_size=30)
    assert len(chunks) == 2
    assert all(c.startswith('<speak>') and c.endswith('</speak>') for c in chunks)
