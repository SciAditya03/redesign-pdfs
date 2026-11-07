"""Procedural scientific imagery for the Mextropic catalogue (numpy + Pillow)."""
import numpy as np, math, os
from PIL import Image, ImageDraw, ImageFilter
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets'); os.makedirs(OUT,exist_ok=True)
rng=np.random.default_rng(7)
NAVY=(7,27,53); MID=(11,16,32); BLUE=(23,105,255); CYAN=(40,188,229); LAV=(166,155,255); OFF=(244,247,251)
_cache={}
def sprite(r,col):
    key=(r,col)
    if key in _cache: return _cache[key]
    s=2*r+3; y,x=np.mgrid[-r-1:r+2,-r-1:r+2].astype(float); d=np.hypot(x,y)/r
    z=np.sqrt(np.clip(1-d**2,0,1)); nx,ny=x/r,y/r
    L=np.array([-0.5,-0.6,0.62]); L/=np.linalg.norm(L)
    diff=np.clip(nx*L[0]+ny*L[1]+z*L[2],0,1)
    h=L+np.array([0,0,1]); h/=np.linalg.norm(h)
    spec=np.clip(nx*h[0]+ny*h[1]+z*h[2],0,1)**40
    shade=0.22+0.85*diff
    rgb=np.stack([np.array(col)[i]*shade+255*spec*0.55 for i in range(3)],-1)
    rim=(1-z)**2*0.35
    rgb=rgb+np.array(col)[None,None,:]*rim[...,None]*0.0
    a=np.clip((1-d)*r,0,1)
    arr=np.dstack([np.clip(rgb,0,255),a*255]).astype(np.uint8)
    im=Image.fromarray(arr,'RGBA'); _cache[key]=im; return im
def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))
def render(beads,W,H,bg,glow=0.55,blur_far=5,blur_mid=1.6):
    """beads: (x,y,z,r,col). z in [-1,1], larger = nearer."""
    beads=sorted(beads,key=lambda b:b[2])
    layers=[Image.new('RGBA',(W,H),(0,0,0,0)) for _ in range(3)]
    for x,y,z,r,col in beads:
        li=0 if z<-0.35 else (1 if z<0.25 else 2)
        r=max(2,int(round(r))); sp=sprite(r,col)
        fade=0.55+0.45*(z+1)/2
        if fade<0.99:
            sp=sp.copy(); a=np.array(sp); a[...,:3]=(a[...,:3]*fade).astype(np.uint8); sp=Image.fromarray(a,'RGBA')
        layers[li].alpha_composite(sp,(int(x-r-1),int(y-r-1))) if 0<=x-r-1<W-2*r-3 and 0<=y-r-1<H-2*r-3 else _safe(layers[li],sp,int(x-r-1),int(y-r-1))
    far=layers[0].filter(ImageFilter.GaussianBlur(blur_far)); mid=layers[1].filter(ImageFilter.GaussianBlur(blur_mid)); near=layers[2]
    base=bg.convert('RGBA')
    comp=Image.new('RGBA',(W,H)); 
    allm=Image.new('RGBA',(W,H),(0,0,0,0))
    for l in (layers[0],layers[1],layers[2]): allm.alpha_composite(l)
    g=allm.filter(ImageFilter.GaussianBlur(28)); ga=np.array(g).astype(float); ga[...,3]=ga[...,3]*glow
    glowim=Image.fromarray(ga.astype(np.uint8),'RGBA')
    base.alpha_composite(glowim)
    for l in (far,mid,near): base.alpha_composite(l)
    return base.convert('RGB')
def _safe(layer,sp,x,y):
    W,H=layer.size; w,h=sp.size
    x0,y0=max(0,x),max(0,y); x1,y1=min(W,x+w),min(H,y+h)
    if x1<=x0 or y1<=y0: return
    layer.alpha_composite(sp.crop((x0-x,y0-y,x1-x,y1-y)),(x0,y0))
def vgrad(W,H,top,bot):
    t=np.linspace(0,1,H)[:,None,None]; a=np.array(top)[None,None,:]; b=np.array(bot)[None,None,:]
    return Image.fromarray((a+(b-a)*t).repeat(W,1).astype(np.uint8),'RGB')
def radial_glow(img,cx,cy,rad,col,strength):
    W,H=img.size; y,x=np.mgrid[0:H,0:W]; d=np.hypot(x-cx,y-cy)/rad
    g=np.exp(-d**2*2.2)*strength; a=np.array(img).astype(float)
    a+=g[...,None]*np.array(col)[None,None,:]; return Image.fromarray(np.clip(a,0,255).astype(np.uint8))
def bezier(P,n):
    t=np.linspace(0,1,n)[:,None]; P=[np.array(p,float) for p in P]
    return (1-t)**3*P[0]+3*(1-t)**2*t*P[1]+3*(1-t)*t**2*P[2]+t**3*P[3]

# ---------- 1. COVER: particle double helix ----------
def cover():
    W,H=1654,2339
    bg=vgrad(W,H,MID,NAVY); bg=radial_glow(bg,W*0.78,H*0.55,W*0.7,(14,50,140),0.9); bg=radial_glow(bg,W*0.3,H*1.0,W*0.6,(60,40,150),0.35)
    pts=bezier([(0.12*W,1.12*H),(0.95*W,0.98*H),(1.2*W,0.52*H),(0.78*W,-0.12*H)],1400)
    d=np.gradient(pts,axis=0); T=d/np.linalg.norm(d,axis=1)[:,None]; N=np.stack([-T[:,1],T[:,0]],1)
    seg=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]; L=seg[-1]
    R=0.115*W; pitch=0.23*H; beads=[]
    step=0.0105*W
    for u in np.arange(0,L,step):
        i=np.searchsorted(seg,u); i=min(i,len(pts)-1); phi=2*math.pi*u/pitch
        for k,ph in enumerate((0,math.pi)):
            z=math.sin(phi+ph); off=math.cos(phi+ph)*R; sc=1+0.32*z
            x,y=pts[i]+N[i]*off
            t=(u/L); col=lerp((200,226,255),(120,175,255),0.5+0.5*z) if k==0 else lerp((150,205,245),(90,150,255),0.5+0.5*z)
            beads.append((x,y,z,0.0145*W*sc,col))
    for u in np.arange(0,L,pitch/11):
        i=min(np.searchsorted(seg,u),len(pts)-1); phi=2*math.pi*u/pitch
        za=math.sin(phi); zb=-za; xa,ya=pts[i]+N[i]*math.cos(phi)*R; xb,yb=pts[i]-N[i]*math.cos(phi)*R
        for j,f in enumerate(np.linspace(0.1,0.9,7)):
            x=xa+(xb-xa)*f; y=ya+(yb-ya)*f; z=za+(zb-za)*f
            col=lerp(CYAN,LAV,f) if f<0.5 else lerp(LAV,CYAN,(f-0.5)*2)
            col=lerp(col,(255,255,255),0.15)
            beads.append((x,y,z*0.9,0.0072*W*(1+0.3*z),col))
    render(beads,W,H,bg,glow=0.6).save(f'{OUT}/cover.jpg',quality=90)

# ---------- 2. PROTEOMICS: protein chain ----------
def catmull(P,n):
    P=np.array(P,float); out=[]
    P=np.vstack([P[0],P,P[-1]])
    for i in range(1,len(P)-2):
        for t in np.linspace(0,1,n,endpoint=False):
            p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
            out.append(0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t**2+(-p0+3*p1-3*p2+p3)*t**3))
    return np.array(out)
def protein():
    W,H=1654,1560
    bg=vgrad(W,H,MID,NAVY); bg=radial_glow(bg,W*0.55,H*0.5,W*0.55,(20,60,160),0.8); bg=radial_glow(bg,W*0.85,H*0.2,W*0.35,(80,60,190),0.4)
    ctrl=[]
    r2=np.random.default_rng(11)
    for i in range(16):
        a=i/16*2*math.pi*1.6; ctrl.append((math.cos(a)*(1.7+0.5*math.sin(i*1.3)),math.sin(a*1.2)*1.2+0.3*math.cos(i),math.sin(a+i*0.7)*1.6))
    base=catmull(ctrl,150)
    d=np.gradient(base,axis=0); T=d/np.linalg.norm(d,axis=1)[:,None]
    ref=np.array([0,1,0.2]); n=len(base); Nn=np.zeros_like(base); Bn=np.zeros_like(base)
    v=np.cross(T[0],ref); v/=np.linalg.norm(v)
    for i in range(n):
        v=v-np.dot(v,T[i])*T[i]; v/=np.linalg.norm(v); Nn[i]=v; Bn[i]=np.cross(T[i],v)
    pos=np.zeros_like(base); rad=np.zeros(n)
    for i in range(n):
        helixness=0.5+0.5*math.sin(i/n*2*math.pi*3.1)
        hr=0.42*helixness**0.7; ph=i*0.26
        pos[i]=base[i]+hr*(math.cos(ph)*Nn[i]+math.sin(ph)*Bn[i])
    # rotate + project
    ay,ax=0.5,0.35
    Ry=np.array([[math.cos(ay),0,math.sin(ay)],[0,1,0],[-math.sin(ay),0,math.cos(ay)]])
    Rx=np.array([[1,0,0],[0,math.cos(ax),-math.sin(ax)],[0,math.sin(ax),math.cos(ax)]])
    q=pos@Ry.T@Rx.T; q-=q.mean(0); sc=W*0.138
    beads=[]
    zmax=np.abs(q[:,2]).max()
    for i in range(n):
        z=q[i,2]/zmax; persp=1+0.18*z
        x=W*0.55+q[i,0]*sc*persp; y=H*0.57+q[i,1]*sc*persp
        t=i/n; col=lerp(CYAN,BLUE,min(1,t*2)) if t<0.5 else lerp(BLUE,LAV,(t-0.5)*2)
        col=lerp(col,(255,255,255),0.12+0.12*z)
        beads.append((x,y,z,W*0.0068*persp,col))
    # ligand spheres
    for k in range(7):
        a=r2.uniform(0,2*math.pi); x=W*0.52+math.cos(a)*W*r2.uniform(0.38,0.47); y=H*0.5+math.sin(a)*H*r2.uniform(0.3,0.45); z=r2.uniform(-0.8,0.9)
        beads.append((x,y,z,W*r2.uniform(0.008,0.017),lerp(LAV,(255,255,255),0.3)))
    render(beads,W,H,bg,glow=0.5).save(f'{OUT}/proteomics.jpg',quality=90)

# ---------- 3. MICROSCOPY ----------
def microscopy(W=760,H=3040,name='intro_side.jpg',seed=3):
    r=np.random.default_rng(seed); yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
    dapi=np.zeros((H,W),np.float32); act=np.zeros_like(dapi); mk=np.zeros_like(dapi)
    cells=[(r.uniform(0,W),r.uniform(0,H)) for _ in range(int(46*W*H/(900*1900)))]
    for cx,cy in cells:
        rx,ry=r.uniform(34,60),r.uniform(30,52); th=r.uniform(0,math.pi)
        c,s=math.cos(th),math.sin(th); xr=(xx-cx)*c+(yy-cy)*s; yr=-(xx-cx)*s+(yy-cy)*c
        d=np.sqrt((xr/rx)**2+(yr/ry)**2)
        dapi+=np.exp(-d**4*1.2)*r.uniform(0.7,1.1)
        act+=np.exp(-((xr/(rx*3.1))**2+(yr/(ry*3.1))**2)*1.6)*0.35
        mk+=np.exp(-((xr/(rx*1.9))**2+(yr/(ry*1.9))**2)*3.0)*0.6*(d>0.9)
    # fibres
    fib=Image.new('L',(W,H),0); dr=ImageDraw.Draw(fib)
    for cx,cy in cells:
        for _ in range(int(r.integers(10,18))):
            a=r.uniform(0,2*math.pi); l=r.uniform(90,260); pts=[(cx,cy)]
            for k in range(1,7):
                a+=r.normal(0,0.28); pts.append((cx+math.cos(a)*l*k/6,cy+math.sin(a)*l*k/6))
            dr.line(pts,fill=int(r.integers(90,200)),width=2)
    fib=np.array(fib.filter(ImageFilter.GaussianBlur(1.3)),np.float32)/255
    tex=lambda s: np.array(Image.fromarray((r.random((H//4,W//4))*255).astype(np.uint8)).resize((W,H),Image.BICUBIC).filter(ImageFilter.GaussianBlur(s)),np.float32)/255
    dapi=dapi*(0.7+0.6*tex(2)); act=act*(0.6+0.8*tex(3))+fib*0.9; mk=mk*(0.5+tex(1.5))
    pun=np.zeros((H,W),np.float32)
    for _ in range(int(900*W*H/(900*1900))): pun[int(r.integers(0,H)),int(r.integers(0,W))]=r.uniform(0.6,1)
    pun=np.array(Image.fromarray((pun*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2)),np.float32)/255*8
    out=np.zeros((H,W,3),np.float32)
    for ch,col,g in ((dapi,BLUE,1.25),(act*0.7,CYAN,0.8),(mk+pun,LAV,0.9)):
        out+=np.clip(ch,0,1.2)[...,None]*np.array(col)[None,None,:]*g
    out=255*(1-np.exp(-out/200*0.9)); out+=np.array(MID)[None,None,:]*0.9
    vig=1-0.4*(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2)**1.2
    Image.fromarray(np.clip(out*vig[...,None],0,255).astype(np.uint8)).save(f'{OUT}/{name}',quality=90)

# ---------- 4. WAVE (contents band) ----------
def wave():
    W,H=1654,430
    bg=vgrad(W,H,MID,MID); bg=radial_glow(bg,W*0.5,H*0.6,W*0.6,(18,55,150),0.6)
    beads=[]
    rows=34; cols=230
    for j in range(rows):
        v=j/(rows-1)
        for i in range(cols):
            u=i/(cols-1); x=-60+u*(W+120)
            amp=95*math.sin(u*5.0+v*2.6)+45*math.sin(u*11+v*5)
            y=H*0.62+amp*(0.35+0.9*v)-v*140+ math.sin(u*3+1.2)*30
            z=math.sin(u*5+v*2.6)
            t=0.5+0.5*math.sin(u*3+v*2)
            col=lerp(BLUE,CYAN,t) if v<0.6 else lerp(LAV,CYAN,t*0.6)
            beads.append((x,y,z*0.8,2.2+2.3*v,col))
    render(beads,W,H,bg,glow=0.7,blur_far=2.5,blur_mid=0.8).save(f'{OUT}/wave.jpg',quality=90)

# ---------- 5. TOMOGRAPHY STACK (clinical imaging header) ----------
def tomo():
    W,H=1654,600
    bg=vgrad(W,H,MID,NAVY); bg=radial_glow(bg,W*0.72,H*0.5,W*0.45,(20,70,170),0.8)
    img=bg.convert('RGBA'); r=np.random.default_rng(5)
    n=11; sw,sh=540,150
    for k in range(n):
        cx=W*0.79+(k-n/2)*20; cy=H*0.74-k*34
        tile=np.zeros((sh*2,sw*2),np.float32); yy,xx=np.mgrid[0:sh*2,0:sw*2]
        d=np.hypot((xx-sw)/sw,(yy-sh)/sh)
        ring=(np.sin(d*18+k*0.7)*0.5+0.5)*np.exp(-d**2*1.8)
        blob=np.exp(-(((xx-sw*0.8)/70)**2+((yy-sh*1.1)/32)**2))+np.exp(-(((xx-sw*1.2)/60)**2+((yy-sh*0.9)/30)**2))
        noise=np.array(Image.fromarray((r.random((sh//3,sw//3))*255).astype(np.uint8)).resize((sw*2,sh*2),Image.BICUBIC),np.float32)/255
        v=np.clip(ring*0.5+blob*0.9+noise*0.25*np.exp(-d**2),0,1)
        mask=(d<1.0).astype(np.float32); edge=np.exp(-((d-0.985)/0.012)**2)
        base_col=np.array(CYAN if k!=7 else LAV,np.float32)
        rgb=v[...,None]*base_col[None,None,:]*0.9+np.array(BLUE)[None,None,:]*0.25*mask[...,None]
        a=(mask*(0.30+0.5*v)*(0.55 if k!=7 else 0.85)+edge*0.9)*255
        rgb=rgb+edge[...,None]*np.array(CYAN)[None,None,:]*0.9
        tl=Image.fromarray(np.dstack([np.clip(rgb,0,255),np.clip(a,0,255)]).astype(np.uint8),'RGBA')
        tl=tl.resize((sw,sh),Image.LANCZOS); img.alpha_composite(tl,(int(cx-sw/2),int(cy-sh/2)))
    img=img.convert('RGB').filter(ImageFilter.GaussianBlur(0.4)); img.save(f'{OUT}/tomography.jpg',quality=90)

def finish():
    im=Image.open(f'{OUT}/proteomics.jpg'); W,H=im.size
    im=im.crop((0,50,W,50+1440)); a=np.array(im).astype(float); h=a.shape[0]
    ramp=np.clip((np.arange(h)-h*0.74)/(h*0.26),0,1)**1.4
    a=a*(1-ramp)[:,None,None]+np.array(NAVY)[None,None,:]*ramp[:,None,None]
    Image.fromarray(a.astype(np.uint8)).save(f'{OUT}/opener_proteomics.jpg',quality=92)
    Image.open(f'{OUT}/wave.jpg').crop((0,110,1654,370)).save(f'{OUT}/contents_band.jpg',quality=92)
    Image.open(f'{OUT}/tomography.jpg').crop((0,30,1654,570)).save(f'{OUT}/clinical_band.jpg',quality=92)

if __name__=='__main__':
    import sys
    sel=sys.argv[1:] or ['cover','protein','microscopy','wave','tomo','finish']
    for f in [globals()[n] for n in sel]: f(); print('done',f.__name__)
