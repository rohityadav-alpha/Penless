"""Quick smoke test — starts the server and hits the main endpoints."""

import sys, time, tempfile, shutil, urllib.request, json
sys.path.insert(0, '.')

from config import PenlessSettings
from server.flask_app import FlaskServer

tmp = tempfile.mkdtemp()
settings = PenlessSettings(shared_folder=tmp, port=18080)
server = FlaskServer(settings)
server.start()
time.sleep(2.0)

all_pass = True

# /api/status
try:
    with urllib.request.urlopen('http://127.0.0.1:18080/api/status', timeout=5) as r:
        data = json.loads(r.read())
    assert data['status'] == 'running'
    assert data['port'] == 18080
    assert data['pinRequired'] == False
    print(f"  PASS  /api/status  -> status={data['status']}, port={data['port']}")
except Exception as e:
    print(f"  FAIL  /api/status  -> {e}")
    all_pass = False

# /api/files
try:
    with urllib.request.urlopen('http://127.0.0.1:18080/api/files', timeout=5) as r:
        data = json.loads(r.read())
    assert 'currentPath' in data
    assert 'folders' in data
    assert 'files' in data
    print(f"  PASS  /api/files   -> folders={len(data['folders'])}, files={len(data['files'])}")
except Exception as e:
    print(f"  FAIL  /api/files   -> {e}")
    all_pass = False

# /api/logs
try:
    with urllib.request.urlopen('http://127.0.0.1:18080/api/logs', timeout=5) as r:
        data = json.loads(r.read())
    assert 'entries' in data
    print(f"  PASS  /api/logs    -> {len(data['entries'])} entries")
except Exception as e:
    print(f"  FAIL  /api/logs    -> {e}")
    all_pass = False

# index.html
try:
    with urllib.request.urlopen('http://127.0.0.1:18080/', timeout=5) as r:
        html = r.read().decode()
    assert 'Penless' in html
    print(f"  PASS  / (index)    -> {len(html)} bytes")
except Exception as e:
    print(f"  FAIL  / (index)    -> {e}")
    all_pass = False

server.stop()
shutil.rmtree(tmp, ignore_errors=True)

print()
if all_pass:
    print("All tests passed!")
else:
    print("Some tests failed.")
    sys.exit(1)
