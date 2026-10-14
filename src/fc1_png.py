"""Read RGB8 non-interlaced PNG for the already acquired FC-1 reference only.
No Gerber parsing or image editing. Reject all other PNG representations.
"""
import struct, zlib

def read_rgb8(path):
    b=path.read_bytes()
    if b[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('PNG signature')
    pos=8;payload=b'';header=None
    while pos<len(b):
        size=struct.unpack('>I',b[pos:pos+4])[0];kind=b[pos+4:pos+8];data=b[pos+8:pos+8+size]
        crc=struct.unpack('>I',b[pos+8+size:pos+12+size])[0]
        if zlib.crc32(kind+data)&0xffffffff!=crc: raise ValueError('PNG CRC')
        if kind==b'IHDR':header=struct.unpack('>IIBBBBB',data)
        elif kind==b'IDAT':payload+=data
        pos+=12+size
        if kind==b'IEND':break
    w,h,depth,color,comp,filt,interlace=header
    if (depth,color,comp,filt,interlace)!=(8,2,0,0,0):raise ValueError('FC-1 expects RGB8 non-interlaced PNG')
    raw=zlib.decompress(payload);stride=w*3
    if len(raw)!=(stride+1)*h:raise ValueError('PNG size')
    rows=[];last=bytearray(stride);offset=0
    for _ in range(h):
        mode=raw[offset];scan=bytearray(raw[offset+1:offset+1+stride]);offset+=stride+1
        for i in range(stride):
            left=scan[i-3] if i>=3 else 0;up=last[i];ul=last[i-3] if i>=3 else 0
            if mode==0:p=0
            elif mode==1:p=left
            elif mode==2:p=up
            elif mode==3:p=(left+up)//2
            elif mode==4:
                v=left+up-ul;dist=[abs(v-left),abs(v-up),abs(v-ul)];p=(left,up,ul)[dist.index(min(dist))]
            else:raise ValueError('PNG filter')
            scan[i]=(scan[i]+p)&255
        rows.append(bytes(scan));last=scan
    return w,h,rows

def orange_components(path):
    w,h,rows=read_rgb8(path)
    cells={(x,y) for y,row in enumerate(rows) for x in range(w) if row[3*x]>200 and 40<row[3*x+1]<180 and row[3*x+2]<100}
    remaining=set(cells);components=[]
    while remaining:
        seed=min(remaining);remaining.remove(seed);todo=[seed];group=[]
        while todo:
            p=todo.pop();group.append(p);x,y=p
            for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if q in remaining:remaining.remove(q);todo.append(q)
        components.append({'pixels':len(group),'centroid':[sum(x for x,y in group)/len(group),sum(y for x,y in group)/len(group)],'bounds':[min(x for x,y in group),min(y for x,y in group),max(x for x,y in group),max(y for x,y in group)]})
    return w,h,cells,components
