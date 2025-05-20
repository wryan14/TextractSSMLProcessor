import os
import sys
import types
import importlib.util
import importlib.machinery
from pathlib import Path


def load_utils_module():
    sys.modules['openai'] = types.ModuleType('openai')
    class DummyCompletions:
        def create(self, *a, **k):
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='translated'))])
    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()
    class DummyClient:
        def __init__(self, api_key=None):
            self.chat = DummyChat()
    sys.modules['openai'].OpenAI = DummyClient

    sys.modules['nltk'] = types.SimpleNamespace(sent_tokenize=lambda text: [s + '.' for s in text.split('. ') if s])
    import xml.etree.ElementTree as ET
    sys.modules['lxml'] = types.SimpleNamespace(etree=ET)
    sys.modules['bs4'] = types.SimpleNamespace(BeautifulSoup=lambda html, parser: None)
    sys.modules['werkzeug.utils'] = types.SimpleNamespace(secure_filename=lambda x: x)
    sys.modules['flask'] = types.SimpleNamespace(current_app=types.SimpleNamespace(config={'PROCESSED_FOLDER':'.','LATIN_FOLDER':'.'}))

    os.environ['OPENAI_API_KEY'] = 'dummy'
    path = Path(__file__).resolve().parents[1] / 'textract_ssml_processor' / 'utils.py'
    loader = importlib.machinery.SourceFileLoader('utils_module', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_generate_ssml_request():
    utils = load_utils_module()
    result = utils.generate_ssml_request('hello')
    assert 'Text to format:' in result


def test_chunk_text():
    utils = load_utils_module()
    chunks = utils.chunk_text('Sentence one. Sentence two.', max_chunk_size=15)
    assert len(chunks) == 2
    assert chunks[0].startswith('Sentence')


def test_safe_format_text_with_gpt(monkeypatch):
    utils = load_utils_module()
    monkeypatch.setattr(utils, 'clean_and_enhance_ssml_with_gpt', lambda x: x + ' cleaned')
    monkeypatch.setattr(utils, 'validate_ssml_with_gpt', lambda x: '<speak>' + x + '</speak>')
    monkeypatch.setattr(utils, 'smooth_text_for_youtube', lambda x: x + ' smooth')
    validated, smooth = utils.safe_format_text_with_gpt('data', 'English')
    assert validated == '<speak>translated cleaned</speak>'
    assert smooth == '<speak>translated cleaned</speak> smooth'
