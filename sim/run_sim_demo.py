import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import json
from pathlib import Path
from adapters.generic_oem_adapter import to_oem_request
from sim.fake_middleware_endpoint import send_request
from sim.event_replay import replay

def main():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root/'examples/etd.pickplace.basic/execution_contract.json').read_text())
    req = to_oem_request(contract, station_id='logistics_cell_a')
    res = send_request(req)
    events = replay(['skill.started','primitive.entered','skill.completed'],
                    'etd.pickplace.basic', min_severity='debug')
    print({'middleware': res, 'events': len(events)})
    raise SystemExit(0 if res['accepted'] and len(events) == 3 else 1)
if __name__ == '__main__': main()
