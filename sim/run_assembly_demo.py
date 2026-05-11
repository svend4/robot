import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import json
from pathlib import Path
from adapters.generic_oem_adapter import to_oem_request
from sim.fake_middleware_endpoint import send_request

def main():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root/'examples/etd.assembly.precision/execution_contract.json').read_text())
    res = send_request(to_oem_request(contract, 'assembly_station_a'))
    print(res)
    raise SystemExit(0 if res['accepted'] else 1)
if __name__ == '__main__': main()
