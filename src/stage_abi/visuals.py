"""Exact geometry-derived SVGs for common-frame ABI comparisons."""
import html

def comparison_svg(copper,delta,viewport,*,title):
 x,y,x2,y2=viewport;w=x2-x;h=y2-y
 if w<=0 or h<=0:raise ValueError('POSITIVE_VIEWPORT_REQUIRED')
 base=copper.svg(scale_factor=min(w,h)/500,fill_color='#ec4261',opacity=1)
 add='' if delta.is_empty else delta.svg(scale_factor=min(w,h)/500,fill_color='#20bba7',opacity=1)
 return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" width="1200" height="900"><title>{html.escape(title)}</title><desc>Exact finite copper. Teal is actual added or removed copper. Display x=x,y=y in the declared source frame, mm; no hidden coordinate inversion.</desc><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#071722"/>{base}{add}</svg>').encode()
