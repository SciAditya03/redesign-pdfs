import json
from pathlib import Path

def test_mextropic_benchmark_fixture():
    p=Path(__file__).parents[1]/'examples'/'mextropic'/'content.json'
    data=json.loads(p.read_text(encoding='utf-8'))
    assert len(data['cats']) == 19
    assert sum(len(c['items']) for c in data['cats']) == 102
    assert all(item.get('name') and item.get('desc') for c in data['cats'] for item in c['items'])
