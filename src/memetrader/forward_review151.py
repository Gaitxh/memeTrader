"""Low-priority, bounded project reports; never fits or changes trading policy."""
import asyncio
import json
import os
import subprocess
import sys
from .models import iso, parse_time, utcnow


async def generate(root, minutes):
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == 'nt' else 0
    child = await asyncio.create_subprocess_exec(sys.executable,
        str(root / 'scripts' / 'deep_cycle_report.py'), '--minutes', str(minutes),
        '--label', 'daily' if minutes == 1440 else 'two_hour', cwd=str(root),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=flags)
    try:
        stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=120)
    except (asyncio.CancelledError, TimeoutError):
        if child.returncode is None:
            child.kill()
        await child.wait()
        raise
    if child.returncode != 0:
        raise RuntimeError('forward review failed: ' + stderr.decode('utf-8', errors='replace')[-1200:])
    return json.loads(stdout.decode('utf-8'))


async def run(runtime):
    # No overlapping runs, no main-thread SQLite scans; exit lane gets startup priority.
    delay = 60
    while not runtime._stop.is_set():
        try:
            await asyncio.wait_for(runtime._stop.wait(), timeout=delay)
            return
        except TimeoutError:
            pass
        now = utcnow()
        prior = runtime.store.get_kv('forward-review151', {}) or {}
        due = prior.get('completed_at')
        if due and (now - parse_time(due)).total_seconds() < 7200:
            delay = max(60, 7200 - (now - parse_time(due)).total_seconds())
            continue
        try:
            report = await generate(runtime.root, 120)
            daily = prior.get('daily_at')
            if not daily or (now - parse_time(daily)).total_seconds() >= 86400:
                prior['daily_report'] = await generate(runtime.root, 1440)
                prior['daily_at'] = iso(utcnow())
            prior.update(status='ok', completed_at=iso(utcnow()), report=report,
                         interval_seconds=7200, policy_mutations=False, extra_market_requests=0)
            prior.pop('error', None)
            delay = 7200
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            prior.update(status='error', attempted_at=iso(now), error=str(exc)[:1500])
            delay = 120
        runtime.store.set_kv('forward-review151', prior)
