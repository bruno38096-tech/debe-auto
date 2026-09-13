"""Small copy patch used by the public DEBE beta."""

def patch_live_copy(path='index.html'):
    try:
        txt=open(path,encoding='utf-8').read()
        replacements={
            'O teu copiloto na ':'O seu copiloto na ',
            'Cola aqui o link do anúncio':'Cole aqui o link do anúncio',
            'Confirma apenas se necessário.':'Confirme apenas se necessário.',
            'Confirma os dados':'Confirme os dados',
            'Antes de comprar, confirma isto':'Antes de comprar, confirme estes pontos',
            'O DEBE ajuda-te a encontrar':'O DEBE ajuda a encontrar',
        }
        for old,new in replacements.items():
            txt=txt.replace(old,new)
        open(path,'w',encoding='utf-8').write(txt)
        print('DEBE runtime: public beta copy applied',flush=True)
    except Exception as e:
        print('DEBE public beta copy patch failed:',e,flush=True)
