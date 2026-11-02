"""Qualified Gerber curves retain vector identity and explicit native frame."""
import xml.etree.ElementTree as ET
import pytest
from src.render_abi.board_gerber_svg import gerber_svg
from src.render_abi.view import crop_svg,verify_svg_view


def source(path,role='Copper,L1,Top',polarity='Positive',clear=False):
    path.write_text('G04 native curve display coupon*\n%FSLAX46Y46*%\n%MOMM*%\n'
                    f'%TF.FileFunction,{role}*%\n%TF.FilePolarity,{polarity}*%\n'
                    '%TF.SameCoordinates,Original*%\n%ADD10C,0.300000*%\nD10*\n'
                    +('%LPC*%\n'if clear else'')+'X1000000Y2000000D03*\nM02*\n')


def test_real_qualified_gerber_flash_stays_a_true_svg_circle(tmp_path):
    g=tmp_path/'board.gbr';source(g);before=g.read_bytes();svg=tmp_path/'display.svg';facts=gerber_svg(g,svg)
    root=ET.fromstring(svg.read_bytes());group=root[0];circle=group[0]
    assert group.attrib==dict(transform='scale(1 -1)')
    assert circle.tag.endswith('circle')and float(circle.attrib['cx'])==1 and float(circle.attrib['cy'])==2 and float(circle.attrib['r'])==.15
    assert g.read_bytes()==before and facts['source_edited']is False and facts['source_objects']==1
    tile=tmp_path/'tile.svg';crop_svg(svg,tile,[.5,-2.5,1.5,-1.5],[500,500]);verify_svg_view(tile,[.5,-2.5,1.5,-1.5],[500,500])
    assert ET.fromstring(tile.read_bytes())[-1][0].attrib==circle.attrib
    with pytest.raises(FileExistsError):gerber_svg(g,svg)


@pytest.mark.parametrize('kwargs,error',[(dict(role='Copper,L2,Bot'),'RENDER_FCU_ROLE'),(dict(polarity='Negative'),'RENDER_FCU_ROLE'),(dict(clear=True),'RENDER_CLEAR_POLARITY')])
def test_wrong_role_or_clear_display_never_silently_passes(tmp_path,kwargs,error):
    g=tmp_path/'board.gbr';source(g,**kwargs);out=tmp_path/'display.svg'
    with pytest.raises(ValueError,match=error):gerber_svg(g,out)
    assert not out.exists()
