"""Versioned, source-specific diagnostic binding; never a tolerance waiver.

REV10 strict verification remains unchanged. Only the two independently observed
alternate representations below are admitted as source-correspondence evidence.
Every geometric operation must continue to use the exact REV05 cached WKB.
"""
import hashlib
import math
from shapely import from_wkb, get_coordinates, to_wkb
from .crop_attachment_diagnostic import _decode
from .native_inventory import steps

VERSION = 'c02-pinned-circle-binding/1'
SOURCE = '850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0'
PINS = {
    SOURCE+':bytes:1651778:1651902': {
        'site': 'R005',
        'fragment': '0033df8920a6b6a450fcd93cd536f53df76f7e10a6ab926c05697ff3286c0f6e',
        'cached': 'a7573e64aac495cc0458c602883169a85c534d2c0be1bb1e7deca7d2e994d5b6',
        'alternate': 'edcc2283570d77137172b9dd18195d34ba5a32d08248dcb029d55487b19a628f',
        'center': ('0x1.46dd2f1a9fbe7p+4', '-0x1.96147ae147ae1p+3'),
        'end': ('0x1.48dd0fa58f712p+4', '-0x1.96147ae147ae1p+3'),
        'cached_y': '-0x1.925b7e7a40915p+3',
        'alternate_y': '-0x1.925b7e7a40914p+3',
    },
    SOURCE+':bytes:1652641:1652766': {
        'site': 'R006',
        'fragment': 'd4c5f157c170fca3e046259dcd2b73938dd7aed60c4c517e6b67786e3cdc1c61',
        'cached': 'b90e180ef500d177ae919d6cb92ee6aeddc534f9f67cdbc1994b93ed8fd3b591',
        'alternate': 'fddba4ef4de4563c5ac85542b43deeec68c5f27543b82b4da4e7fd7683c57a74',
        'center': ('0x1.51c28f5c28f5cp+4', '-0x1.98fdf3b645a1dp+3'),
        'end': ('0x1.53c26fe718a87p+4', '-0x1.98fdf3b645a1dp+3'),
        'cached_y': '-0x1.9544f74f3e851p+3',
        'alternate_y': '-0x1.9544f74f3e850p+3',
    },
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def verify_representation(source_id, fragment, kind, attrs, cached_blob, native_blob):
    """Check one exact pinned source and return evidence, never replacement bytes."""
    if source_id not in PINS:
        raise ValueError('SOURCE_NOT_PINNED')
    p = PINS[source_id]
    if sha(fragment) != p['fragment'] or sha(cached_blob) != p['cached']:
        raise ValueError('SOURCE_OR_CACHE_HASH_MISMATCH')
    if (kind != 'gr_circle' or list(map(str, attrs.get('layer', []))) != ['F.Cu']
            or list(map(str, attrs.get('fill', []))) != ['yes']):
        raise ValueError('PINNED_CIRCLE_SEMANTICS_CHANGED')
    center, end = (tuple(map(float, attrs[key])) for key in ('center', 'end'))
    radius = math.dist(center, end)
    if (tuple(v.hex() for v in center) != p['center']
            or tuple(v.hex() for v in end) != p['end']
            or radius.hex() != '0x1.ffe08aefb2b00p-4' or steps(radius) != 63):
        raise ValueError('PINNED_BUFFER_INPUT_CHANGED')
    digest = sha(native_blob)
    if digest not in (p['cached'], p['alternate']):
        raise ValueError('UNLISTED_RECONSTRUCTION_HASH')
    cached, native = map(from_wkb, (cached_blob, native_blob))
    a, b = get_coordinates(cached).tolist(), get_coordinates(native).tolist()
    if len(a) != 253 or len(b) != 253:
        raise ValueError('PINNED_COORDINATE_COUNT_CHANGED')
    differences = [(i, av, bv) for i, (av, bv) in enumerate(zip(a, b, strict=True)) if av != bv]
    if digest == p['cached']:
        if cached_blob != native_blob or differences:
            raise ValueError('CANONICAL_BYTES_CHANGED')
        status = 'CANONICAL_EXACT'
    else:
        if (len(differences) != 1 or differences[0][0] != 174
                or differences[0][1][0] != differences[0][2][0]
                or differences[0][1][1].hex() != p['cached_y']
                or differences[0][2][1].hex() != p['alternate_y']):
            raise ValueError('PINNED_VERTEX_DIFFERENCE_CHANGED')
        status = 'PINNED_ALTERNATE_REPRESENTATION'
    return dict(version=VERSION, status=status, source_id=source_id,
                source_fragment_sha256=sha(fragment), authoritative_wkb_sha256=p['cached'],
                reconstructed_wkb_sha256=digest, coordinate_count=253,
                differences=[dict(index=i, cached_hex=[v.hex() for v in av],
                                  reconstructed_hex=[v.hex() for v in bv]) for i, av, bv in differences],
                geometry_authority='EXACT_REV05_CACHED_WKB_ONLY', acceptance='NONE')


def bind_pinned_circle(source, source_id, cached_blob):
    """Decode unchanged source, verify its observed representation, keep cache."""
    if sha(source) != SOURCE or source_id not in PINS:
        raise ValueError('SOURCE_NOT_PINNED')
    _, (record,) = _decode(source, (source_id,))
    kind, attrs, native, _ = record
    start, end = map(int, source_id.rsplit(':', 2)[1:])
    evidence = verify_representation(source_id, source[start:end], kind, attrs,
                                     cached_blob, to_wkb(native))
    return cached_blob, evidence
