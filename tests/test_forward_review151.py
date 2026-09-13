import asyncio
from pathlib import Path
import pytest
from memetrader import forward_review151 as review


def test_report_subprocess_is_bounded_and_read_only(monkeypatch):
    seen = {}
    class Child:
        returncode = 0
        async def communicate(self):
            return b'{"json":"report.json"}', b''
    async def start(*args, **kw):
        seen.update(args=args, kw=kw)
        return Child()
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', start)
    assert asyncio.run(review.generate(Path('.'), 120)) == {'json': 'report.json'}
    assert '--minutes' in seen['args'] and '120' in seen['args']
    assert '--config' not in seen['args']


def test_report_failure_is_not_success(monkeypatch):
    class Child:
        returncode = 1
        async def communicate(self):
            return b'', b'query interrupted'
    async def start(*args, **kw):
        return Child()
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', start)
    with pytest.raises(RuntimeError, match='query interrupted'):
        asyncio.run(review.generate(Path('.'), 120))
