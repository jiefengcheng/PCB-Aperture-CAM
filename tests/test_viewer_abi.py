"""Viewer publication custody, holes, unsupported semantics and atomic failure."""
import json
import pytest
from src.viewer_abi.publisher import publish, read_current, import_gerber


def gerber(tmp_path, x='1000000', extra=''):
    path = tmp_path / ('source-' + x + '.gbr')
    path.write_text('G04 synthetic viewer test, not native export*\n%FSLAX46Y46*%\n%MOMM*%\n'
                    '%TF.FileFunction,Copper,L1,Top*%\n%TF.FilePolarity,Positive*%\n'
                    '%ADD10C,1.0X0.4*%\nD10*\nX' + x + 'Y2000000D03*\n' + extra + 'M02*\n')
    return path


def test_publish_hole_and_source_custody(tmp_path):
    source = gerber(tmp_path)
    raw = source.read_bytes()
    manifest, scene = publish(tmp_path / 'viewer', [source])
    assert scene['status'] == 'Preview'
    assert scene['objects'][0]['path'].count('M ') == 2  # aperture hole preserved
    assert scene['objects'][0]['bounds']['y'] == pytest.approx(-2.5)
    assert scene['sources'][0]['layer'] == 'Copper.L1.Top'
    assert source.read_bytes() == raw
    assert read_current(tmp_path / 'viewer')[0] == manifest


def test_revision_parent_and_affected_include_removed_location(tmp_path):
    root = tmp_path / 'viewer'
    _, first = publish(root, [gerber(tmp_path)])
    manifest, second = publish(root, [gerber(tmp_path, '4000000')])
    assert second['parentRevision'] == first['revision']
    assert second['objects'][0]['id'] == first['objects'][0]['id']
    assert second['objects'][0]['sourceID'] != first['objects'][0]['sourceID']
    assert second['affected']['x'] == pytest.approx(.5)
    assert second['affected']['width'] == pytest.approx(4)
    assert manifest['previousPayload']


def test_failed_import_does_not_replace_manifest(tmp_path):
    root = tmp_path / 'viewer'
    source = gerber(tmp_path)
    publish(root, [source])
    before = (root / 'current.json').read_bytes()
    source.write_text(source.read_text().replace('M02*', '%LPC*%\nX4000000Y2000000D03*\nM02*'))
    with pytest.raises(ValueError, match='CLEAR_OPERATIONS'):
        publish(root, [source])
    assert (root / 'current.json').read_bytes() == before


def test_tampered_payload_rejected_without_republication(tmp_path):
    root = tmp_path / 'viewer'
    source = gerber(tmp_path)
    manifest, _ = publish(root, [source])
    (root / 'snapshots' / manifest['payload']).write_text('{}')
    before = (root / 'current.json').read_bytes()
    with pytest.raises(ValueError, match='CHECKSUM'):
        publish(root, [source])
    assert (root / 'current.json').read_bytes() == before
    assert not (root / '.publish.lock').exists()


def test_duplicate_layer_and_unknown_role_rejected(tmp_path):
    source = gerber(tmp_path)
    with pytest.raises(ValueError, match='DUPLICATE_LAYER'):
        publish(tmp_path / 'viewer', [source, source])
    source.write_text(source.read_text().replace('Copper,L1,Top', 'Legend,Top'))
    with pytest.raises(ValueError, match='ROLE_REQUIRED'):
        import_gerber(source)


def test_missing_eof_and_units_fail_closed(tmp_path):
    source = gerber(tmp_path)
    good = source.read_text()
    source.write_text(good.replace('M02*', ''))
    with pytest.raises(Exception, match='M02 EOF'):
        import_gerber(source)
    source.write_text(good.replace('%MOMM*%', '%MOIN*%'))
    with pytest.raises(Exception, match='MM46'):
        import_gerber(source)


def test_publisher_lock_prevents_racing_parent(tmp_path):
    root = tmp_path / 'viewer'; root.mkdir()
    (root / '.publish.lock').write_text('retained producer lock')
    with pytest.raises(FileExistsError):
        publish(root, [gerber(tmp_path)])
    assert (root / '.publish.lock').read_text() == 'retained producer lock'


def test_mask_regions_with_unavailable_attributes_are_explicit_preview(tmp_path):
    path = tmp_path / 'mask.gbr'
    path.write_text('G04 synthetic mask region*\n%FSLAX46Y46*%\n%MOMM*%\n'
                    '%TF.FileFunction,Soldermask,Top*%\n%TF.FilePolarity,Negative*%\n'
                    'G01*\nG36*\nX1000000Y1000000D02*\nX2000000Y1000000D01*\n'
                    'X2000000Y2000000D01*\nX1000000Y2000000D01*\nX1000000Y1000000D01*\nG37*\nM02*\n')
    _, scene = publish(tmp_path / 'viewer', [path])
    assert scene['objects'][0]['kind'] == 'Region'
    assert scene['objects'][0]['attributes'] == {}
    assert scene['status'] == 'Preview'
    assert any('unavailable attributes remain empty' in s for s in scene['limitations'])
