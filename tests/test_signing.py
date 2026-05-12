"""Tests for scripts/sign_package.py and scripts/verify_signature.py."""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Add scripts/ to path so imports work without installing
_SCRIPTS = ROOT / 'scripts'
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from nacl.signing import SigningKey

from sign_package import sign_package, _package_digest
from verify_signature import verify_package


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def keypair(tmp_path):
    """Generate a fresh Ed25519 keypair in tmp_path and return (signing_key_path, verify_key_path)."""
    sk = SigningKey.generate()
    sk_path = tmp_path / 'test_signing.hex'
    vk_path = tmp_path / 'test_verify.hex'
    sk_path.write_text(sk.encode().hex())
    vk_path.write_text(sk.verify_key.encode().hex())
    return sk_path, vk_path


@pytest.fixture
def signed_pkg(tmp_path, keypair):
    """Copy etd.pickplace.basic to tmp_path and return (pkg_path, sk_path)."""
    sk_path, _ = keypair
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'etd.pickplace.basic'
    shutil.copytree(src, dst)
    sign_package(dst, sk_path)
    return dst, sk_path


# ── sign_package ──────────────────────────────────────────────────────────────

def test_sign_creates_sig_file(tmp_path, keypair):
    sk_path, _ = keypair
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg'
    shutil.copytree(src, dst)
    sig_path = sign_package(dst, sk_path)
    assert sig_path.exists()
    assert sig_path.name == 'package.sig'


def test_sig_file_has_required_fields(signed_pkg):
    pkg, _ = signed_pkg
    doc = json.loads((pkg / 'package.sig').read_text())
    for field in ('algorithm', 'digest_algorithm', 'signed_files', 'signature', 'verify_key'):
        assert field in doc, f'Missing field: {field}'


def test_sig_algorithm_is_ed25519(signed_pkg):
    pkg, _ = signed_pkg
    doc = json.loads((pkg / 'package.sig').read_text())
    assert doc['algorithm'] == 'ed25519'
    assert doc['digest_algorithm'] == 'sha256'


def test_sig_signature_is_64_bytes_hex(signed_pkg):
    pkg, _ = signed_pkg
    doc = json.loads((pkg / 'package.sig').read_text())
    assert len(bytes.fromhex(doc['signature'])) == 64


def test_sig_verify_key_is_32_bytes_hex(signed_pkg):
    pkg, _ = signed_pkg
    doc = json.loads((pkg / 'package.sig').read_text())
    assert len(bytes.fromhex(doc['verify_key'])) == 32


def test_sig_signed_files_lists_known_files(signed_pkg):
    pkg, _ = signed_pkg
    doc = json.loads((pkg / 'package.sig').read_text())
    assert 'manifest.yaml' in doc['signed_files']
    assert 'skill.json' in doc['signed_files']


# ── verify_package ────────────────────────────────────────────────────────────

def test_verify_signed_package_returns_true(signed_pkg):
    pkg, _ = signed_pkg
    assert verify_package(pkg) is True


def test_verify_with_explicit_pub_key(tmp_path, keypair):
    sk_path, vk_path = keypair
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg2'
    shutil.copytree(src, dst)
    sign_package(dst, sk_path)
    assert verify_package(dst, pub_key_path=vk_path) is True


def test_verify_missing_sig_file_returns_false(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'unsigned'
    shutil.copytree(src, dst)
    assert verify_package(dst) is False


def test_verify_tampered_file_returns_false(signed_pkg):
    pkg, _ = signed_pkg
    # Modify manifest.yaml after signing
    manifest = (pkg / 'manifest.yaml').read_text()
    (pkg / 'manifest.yaml').write_text(manifest + '\n# tampered\n')
    assert verify_package(pkg) is False


def test_verify_wrong_public_key_returns_false(tmp_path, keypair):
    sk_path, _ = keypair
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg3'
    shutil.copytree(src, dst)
    sign_package(dst, sk_path)
    # Generate a different keypair
    different_sk = SigningKey.generate()
    wrong_vk_path = tmp_path / 'wrong_vk.hex'
    wrong_vk_path.write_text(different_sk.verify_key.encode().hex())
    assert verify_package(dst, pub_key_path=wrong_vk_path) is False


def test_verify_sig_doc_missing_verify_key_returns_false(tmp_path, keypair):
    sk_path, _ = keypair
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'pkg_nokey'
    shutil.copytree(src, dst)
    sign_package(dst, sk_path)
    # Strip verify_key from sig doc, and pass a nonexistent pub_key_path
    sig_doc = json.loads((dst / 'package.sig').read_text())
    sig_doc.pop('verify_key', None)
    (dst / 'package.sig').write_text(json.dumps(sig_doc))
    # pub_key_path points to a nonexistent file → falls back to sig_doc verify_key (now empty)
    assert verify_package(dst, pub_key_path=tmp_path / 'no_such_key.hex') is False


# ── sign + verify round-trip for all 8 packages ───────────────────────────────

_ALL_PKGS = [
    'etd.pickplace.basic',
    'etd.assembly.precision',
    'etd.inspect.vision',
    'etd.cobot.safeassist',
    'etd.atlas.humanoid_walkfetch',
    'etd.hyundai.wia_welding',
    'etd.hyundai.mobed_transport',
    'etd.hyundai.vest_exoskeleton',
]


@pytest.mark.parametrize('pkg_name', _ALL_PKGS)
def test_sign_verify_roundtrip(tmp_path, keypair, pkg_name):
    sk_path, _ = keypair
    src = ROOT / 'examples' / pkg_name
    dst = tmp_path / pkg_name
    shutil.copytree(src, dst)
    sign_package(dst, sk_path)
    assert verify_package(dst) is True


# ── _package_digest determinism ───────────────────────────────────────────────

def test_package_digest_is_deterministic():
    pkg = ROOT / 'examples' / 'etd.pickplace.basic'
    d1 = _package_digest(pkg)
    d2 = _package_digest(pkg)
    assert d1 == d2
    assert len(d1) == 32  # SHA-256


def test_package_digest_differs_between_packages():
    pick = ROOT / 'examples' / 'etd.pickplace.basic'
    asm  = ROOT / 'examples' / 'etd.assembly.precision'
    assert _package_digest(pick) != _package_digest(asm)


# ── generic_oem_adapter ───────────────────────────────────────────────────────

from adapters.generic_oem_adapter import to_oem_request


def test_oem_request_nominal():
    req = to_oem_request({'arm_mode': 'torque_assist', 'speed': 0.5}, station_id='weld_station_a')
    assert req['request_type'] == 'skill_intent'
    assert req['station_id'] == 'weld_station_a'
    assert req['bounded'] is True
    assert req['payload']['arm_mode'] == 'torque_assist'


def test_oem_request_default_station():
    req = to_oem_request({'arm_mode': 'passive'})
    assert req['station_id'] == 'unknown'


def test_oem_request_rejects_servo_torque():
    with pytest.raises(ValueError, match='unsafe'):
        to_oem_request({'servo_torque': 120.0})


def test_oem_request_rejects_collision_disable():
    with pytest.raises(ValueError, match='unsafe'):
        to_oem_request({'collision_disable': True})


def test_oem_request_rejects_emergency_stop_override():
    with pytest.raises(ValueError, match='unsafe'):
        to_oem_request({'emergency_stop_override': True})


def test_oem_request_empty_payload_allowed():
    req = to_oem_request({})
    assert req['bounded'] is True
    assert req['payload'] == {}


# ── generate_keypair ──────────────────────────────────────────────────────────

from generate_keypair import generate


def test_generate_creates_key_files(tmp_path):
    generate(tmp_path / 'keys')
    assert (tmp_path / 'keys' / 'etd_signing_key.hex').exists()
    assert (tmp_path / 'keys' / 'etd_verify_key.hex').exists()


def test_generate_private_key_is_32_bytes_hex(tmp_path):
    generate(tmp_path / 'keys')
    raw = bytes.fromhex((tmp_path / 'keys' / 'etd_signing_key.hex').read_text())
    assert len(raw) == 32


def test_generate_public_key_is_32_bytes_hex(tmp_path):
    generate(tmp_path / 'keys')
    raw = bytes.fromhex((tmp_path / 'keys' / 'etd_verify_key.hex').read_text())
    assert len(raw) == 32


def test_generate_private_key_permissions(tmp_path):
    import stat
    generate(tmp_path / 'keys')
    mode = (tmp_path / 'keys' / 'etd_signing_key.hex').stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_generate_keypair_is_usable_for_signing(tmp_path):
    generate(tmp_path / 'keys')
    sk_path = tmp_path / 'keys' / 'etd_signing_key.hex'
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dst = tmp_path / 'etd.pickplace.basic'
    shutil.copytree(src, dst)
    sign_package(dst, sk_path)
    assert verify_package(dst) is True


def test_generate_creates_output_dir_if_absent(tmp_path):
    nested = tmp_path / 'a' / 'b' / 'c'
    assert not nested.exists()
    generate(nested)
    assert nested.exists()


def test_generate_keys_are_different(tmp_path):
    out1 = tmp_path / 'keys1'
    out2 = tmp_path / 'keys2'
    generate(out1)
    generate(out2)
    sk1 = (out1 / 'etd_signing_key.hex').read_text()
    sk2 = (out2 / 'etd_signing_key.hex').read_text()
    assert sk1 != sk2


# ── release_package._zip_dir ──────────────────────────────────────────────────

import zipfile as _zipfile
from release_package import _zip_dir


def test_zip_dir_creates_zip_file(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dest = tmp_path / 'test_pkg.zip'
    _zip_dir(src, dest)
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_zip_dir_contains_expected_files(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dest = tmp_path / 'test_pkg.zip'
    _zip_dir(src, dest)
    with _zipfile.ZipFile(dest, 'r') as z:
        names = z.namelist()
    assert any('manifest.yaml' in n for n in names)
    assert any('skill.json' in n for n in names)


def test_zip_dir_excludes_pycache(tmp_path):
    src = ROOT / 'examples' / 'etd.pickplace.basic'
    dest = tmp_path / 'test_pkg.zip'
    _zip_dir(src, dest)
    with _zipfile.ZipFile(dest, 'r') as z:
        names = z.namelist()
    assert not any('__pycache__' in n for n in names)
    assert not any(n.endswith('.pyc') for n in names)
