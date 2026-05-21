import importlib.util
import pathlib


def _load_llm_module():
    p = pathlib.Path(__file__).resolve().parents[1] / 'llm-agent' / 'main.py'
    spec = importlib.util.spec_from_file_location('llm_agent_main', p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_build_output_shape():
    mod = _load_llm_module()
    out = mod.build_output('abc', 'text')
    assert out['id'] == 'abc'
    assert out['llm_summary'] == 'text'
