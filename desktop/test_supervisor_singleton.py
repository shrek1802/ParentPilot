#!/usr/bin/env python3
"""Headless regression for duplicate ParentPilot child UI starts."""
import fcntl
import importlib.util
import os
from pathlib import Path
import tempfile

source = Path(__file__).with_name('max_desktop_supervisor.py')
spec = importlib.util.spec_from_file_location('parentpilot_supervisor', source)
sup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sup)
with tempfile.TemporaryDirectory() as temp:
    sup.LOCK_PATH = Path(temp) / 'supervisor.lock'
    first = sup.acquire_singleton()
    assert first is not None, 'First supervisor could not start'
    assert sup.acquire_singleton() is None, 'Second supervisor must not start'
    assert sup.supervise() == 0, 'Duplicate must exit harmlessly without launching child'
    fcntl.flock(first, fcntl.LOCK_UN)
    os.close(first)
    third = sup.acquire_singleton()
    assert third is not None, 'A legitimate subsequent login must be allowed'
    fcntl.flock(third, fcntl.LOCK_UN)
    os.close(third)
print('PASS: exactly one child supervisor; duplicates exit and future login can restart')
