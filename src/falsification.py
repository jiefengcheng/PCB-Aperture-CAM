"""Deliberately corrupt copies of native Gerbers; never touch assets."""
from pathlib import Path
import shutil
from .validator import evaluate, sha

def falsify(before, candidate, output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    definitions=[
        ('shifted_aperture','F_Mask','X19500000','X19600000','fixed_reference','FAIL'),
        ('disconnected_n1','F_Cu','X20000000Y-21550000D02*\nX20000000Y-23000000D01*','', 'connectivity','FAIL'),
        ('bridge','F_Cu','M02*','D11*\nX20000000Y-24000000D02*\nX23000000Y-24000000D01*\nM02*','no_short','FAIL'),
        ('protected_p3','F_Cu','X23000000Y-20000000D03*','X23300000Y-20000000D03*','scope','FAIL'),
        ('insufficient_exposure','F_Cu','X20050000Y-20000000D03*','X20350000Y-20000000D03*','exposure','FAIL'),
        ('wrong_polarity','F_Mask','FilePolarity,Negative','FilePolarity,Positive','coverage','NOT_ESTABLISHED'),
        ('mirroring','F_Cu','%LPD*%','%LPD*%\n%LMX*%','coverage','NOT_ESTABLISHED'),
        ('macro','F_Cu','%LPD*%','%LPD*%\n%AMUNQUALIFIED*1,1,1,0,0*%','coverage','NOT_ESTABLISHED'),
        ('clear_image','F_Cu','%LPD*%','%LPC*%','coverage','NOT_ESTABLISHED'),
        ('inch_units','F_Cu','%MOMM*%','%MOIN*%','coverage','NOT_ESTABLISHED'),
        ('unknown_command','F_Cu','M02*','G999*\nM02*','coverage','NOT_ESTABLISHED'),
        ('narrow_neck','F_Cu','%ADD11C,0.250000*%','%ADD11C,0.100000*%','connectivity','FAIL'),
        ('clearance','F_Cu','M02*','D11*\nX20000000Y-24000000D02*\nX22700000Y-24000000D01*\nM02*','clearance','FAIL'),
    ]
    results=[]
    for name,layer,old,new,key,expected in definitions:
        dest=output/name
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(candidate,dest)
        file=dest/('coupon-'+layer+'.gbr'); text=file.read_text()
        if old not in text: raise AssertionError('mutation anchor absent: '+name)
        file.write_text(text.replace(old,new))
        result=evaluate(before,dest)
        actual=next((c['status'] for c in result['checks'] if c['id']==key),None)
        results.append({'name':name,'check':key,'expected':expected,'actual':actual,
                        'status':'PASS' if actual==expected and result['overall']!='PASS' else 'FAIL',
                        'mutated_file':str(file),'sha256':sha(file),'report':result})
    return results
