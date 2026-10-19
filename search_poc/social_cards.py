"""First-party DEBE social campaign graphics, served as Instagram-ready PNGs.

All creatives are original typography and abstract vector illustrations:
no third-party logos or borrowed car photography.
"""
from functools import lru_cache
from io import BytesIO
from math import sin, pi
import os
from PIL import Image, ImageDraw, ImageFont

W,H=1080,1350
WHITE=(245,250,255)
MUTED=(168,194,222)
BLUE=(126,183,255)
CYAN=(103,226,217)
DARK=(9,20,36)
CREATIVES={
    "search": {
        "kicker":"DEBE  /  PESQUISA AUTOMÓVEL",
        "headline":("O CARRO CERTO","SEM ABRIR","10 SITES."),
        "subtitle":("Pesquisa carros de várias fontes","numa só experiência."),
        "kind":"search",
        "cta":"EXPERIMENTA O DEBE SEARCH",
    },
    "checklist":{
        "kicker":"ANTES DE COMPRAR UM USADO",
        "headline":("5 COISAS","QUE NÃO PODES","IGNORAR."),
        "subtitle":("O preço é só o início.","Compra com informação."),
        "kind":"checklist",
        "cta":"GUARDA ESTA CHECKLIST",
    },
    "analyse":{
        "kicker":"DEBE SEARCH  +  DEBE ANÁLISE",
        "headline":("ENCONTRA.","ANALISA.","DECIDE."),
        "subtitle":("Da pesquisa de anúncios à avaliação","dos pontos fortes e riscos."),
        "kind":"analyse",
        "cta":"DESCOBRE AS DUAS FERRAMENTAS",
    },
    "a5":{
        "kicker":"PESQUISA POR MOTORIZAÇÃO",
        "headline":("AUDI A5","E-HYBRID?","VÊ A VERSÃO."),
        "subtitle":("Avant ou Limousine? A escolha certa","começa com o filtro certo."),
        "kind":"a5",
        "cta":"PESQUISA A5 E-HYBRID NO DEBE",
    },
}

def f(size,bold=False):
    root="/usr/share/fonts/truetype/dejavu"
    paths=[
        root+("/DejaVuSans-Bold.ttf" if bold else "/DejaVuSans.ttf"),
        "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
    ]
    for p in paths:
        try:return ImageFont.truetype(p,size)
        except (OSError,ValueError):continue
    return ImageFont.load_default()


def gradient():
    im=Image.new("RGB",(W,H))
    px=im.load()
    for y in range(H):
        v=y/(H-1)
        for x in range(W):
            xfactor=0.025*sin(x*0.007+y*0.002)
            px[x,y]=(
                int(9+8*v+4*xfactor),
                int(20+17*v+8*xfactor),
                int(36+24*v+12*xfactor),
            )
    return im


def rr(draw,xy,fill,radius=26,outline=None,width=2):
    draw.rounded_rectangle(xy,radius=radius,fill=fill,outline=outline,width=width)


def txt(draw,pos,value,size,color=WHITE,bold=False,spacing=0):
    draw.text(pos,value,font=f(size,bold),fill=color,stroke_width=0,spacing=spacing)


def base(draw,kind):
    draw.ellipse((520,-580,1510,450),outline=(40,81,128),width=2)
    draw.ellipse((620,-490,1420,355),outline=(29,64,108),width=2)
    draw.ellipse((-460,750,500,1710),outline=(32,72,117),width=2)
    draw.line([(64,1160),(1016,1160)],fill=(57,91,128),width=2)
    rr(draw,(70,63,234,124),(232,242,255),20)
    txt(draw,(91,76),"DEBE",32,(11,28,53),True)
    txt(draw,(265,82),"AUTO INTELLIGENCE",18,(152,178,211),True)
    rr(draw,(839,70,1008,114),(24,49,79),19,outline=(64,105,150))
    txt(draw,(857,80),"PORTUGAL",17,BLUE,True)


def banner(draw,card):
    rr(draw,(69,183,575,235),(25,61,91),14,outline=(49,94,140))
    txt(draw,(89,192),card["kicker"],17,CYAN,True)
    y=275
    for idx,line in enumerate(card["headline"]):
        size=78 if len(line)>12 else 90
        txt(draw,(65,y),line,size,BLUE if idx==len(card["headline"])-1 else WHITE,True)
        y+=114
    sub_y=657
    for line in card["subtitle"]:
        txt(draw,(69,sub_y),line,30,MUTED)
        sub_y+=48


def search_art(draw):
    rr(draw,(68,794,1012,1116),(17,42,68),36,outline=(67,107,155),width=3)
    txt(draw,(104,824),"A tua pesquisa",22,CYAN,True)
    rr(draw,(104,884,706,974),(11,28,47),20,outline=(83,127,172))
    txt(draw,(129,912),"Marca  ·  Modelo  ·  Motor",23,WHITE,True)
    rr(draw,(724,884,965,974),BLUE,20)
    txt(draw,(757,912),"PESQUISAR",23,DARK,True)
    for i,label in enumerate(("Fontes","Anúncios","Comparação")):
        x=113+i*296
        rr(draw,(x,1014,x+267,1077),(26,59,90),13,outline=(51,97,137))
        txt(draw,(x+18,1030),label,21,MUTED,True)


def checklist_art(draw):
    rr(draw,(68,760,1012,1123),(18,42,68),34,outline=(71,109,153),width=3)
    items=("Histórico e VIN","Quilometragem real","Manutenção e avarias","Motorização certa","Preço face ao mercado")
    for i,label in enumerate(items):
        y=787+i*64
        rr(draw,(107,y,145,y+37),(27,95,102),11,outline=(90,190,180))
        txt(draw,(116,y+4),"✓",24,CYAN,True)
        txt(draw,(176,y),label,28,WHITE,i==0)
        if i<4:draw.line([(176,y+52),(953,y+52)],fill=(39,72,102),width=2)


def analyse_art(draw):
    rr(draw,(68,803,1012,1123),(19,42,67),34,outline=(70,105,147),width=3)
    rr(draw,(107,843,471,1080),(26,56,89),25,outline=(63,109,161))
    rr(draw,(609,843,973,1080),(26,56,89),25,outline=(63,109,161))
    txt(draw,(146,872),"01",40,CYAN,True)
    txt(draw,(146,941),"PESQUISA",29,WHITE,True)
    txt(draw,(146,991),"Vê anúncios",23,MUTED)
    txt(draw,(648,872),"02",40,CYAN,True)
    txt(draw,(648,941),"ANÁLISE",29,WHITE,True)
    txt(draw,(648,991),"Avalia o negócio",23,MUTED)
    draw.line([(498,955),(576,955)],fill=BLUE,width=9)
    draw.polygon([(577,955),(552,939),(552,971)],fill=BLUE)


def a5_art(draw):
    rr(draw,(68,802,1012,1116),(16,41,68),34,outline=(69,116,163),width=3)
    txt(draw,(103,839),"AUDI  A5  E-HYBRID",25,CYAN,True)
    rr(draw,(105,912,478,1043),(30,68,103),21,outline=(85,135,171))
    rr(draw,(600,912,973,1043),(30,68,103),21,outline=(85,135,171))
    txt(draw,(160,945),"AVANT",39,WHITE,True)
    txt(draw,(639,945),"LIMOUSINE",30,WHITE,True)
    txt(draw,(470,1090),"Filtros de motorização e carroçaria",19,MUTED)


@lru_cache(maxsize=8)
def render_png(slug):
    card=CREATIVES.get(slug)
    if not card:raise KeyError(slug)
    im=gradient()
    draw=ImageDraw.Draw(im)
    base(draw,slug)
    banner(draw,card)
    {"search":search_art,"checklist":checklist_art,"analyse":analyse_art,"a5":a5_art}[slug](draw)
    rr(draw,(70,1200,1010,1280),(149,198,255),19)
    # CTA centered if font available
    font=f(26,True)
    bbox=draw.textbbox((0,0),card["cta"],font=font)
    width=bbox[2]-bbox[0]
    draw.text(((W-width)//2,1220),card["cta"],font=font,fill=(9,25,46))
    out=BytesIO()
    im.save(out,format="PNG",optimize=True)
    return out.getvalue()
