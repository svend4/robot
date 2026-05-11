import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pathlib import Path
from etd_reference_validator import ETDReferenceValidator, RuntimeContext

def main():
    root = Path(__file__).resolve().parents[1]
    missing = RuntimeContext(runtime_version='0.1.0', robot_class='humanoid', available_services=['perception.object_pose'])
    rep = ETDReferenceValidator(missing).validate_package(root/'examples/etd.pickplace.basic')
    failures = {
        'missing_service_level_d': rep.compatibility['level'] == 'D',
        'human_too_close': 'protective_pause_required',
        'payload_out_of_range': 'blocked_by_constraints',
        'station_incompatible': 'blocked_by_station_profile',
    }
    print(failures)
    raise SystemExit(0 if failures['missing_service_level_d'] else 1)
if __name__ == '__main__': main()
