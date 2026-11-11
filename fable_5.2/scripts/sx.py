# minimal s-expression parser / writer for KiCad files
import re
class Sym(str): pass
def parse(text):
    tok=re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')
    pos=0; stack=[[]]; n=len(text)
    while pos<n:
        m=tok.match(text,pos)
        if not m: break
        pos=m.end()
        if m.group(1): stack.append([])
        elif m.group(2):
            l=stack.pop(); stack[-1].append(l)
        elif m.group(3) is not None:
            stack[-1].append(re.sub(r'\\(.)', lambda k: {'n': '\n'}.get(k.group(1), k.group(1)), m.group(3)))
        else: stack[-1].append(Sym(m.group(4)))
    return stack[0][0]
def q(s): return '"'+s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
def dump(x,ind=0):
    if isinstance(x,list):
        simple=all(not isinstance(i,list) for i in x)
        if simple: return '('+' '.join(dump(i) for i in x)+')'
        out='('+dump(x[0])
        for i in x[1:]:
            if isinstance(i,list): out+='\n'+'\t'*(ind+1)+dump(i,ind+1)
            else: out+=' '+dump(i)
        return out+'\n'+'\t'*ind+')'
    if isinstance(x,Sym): return str(x)
    if isinstance(x,str): return q(x)
    if isinstance(x,float): return ('%.4f'%x).rstrip('0').rstrip('.')
    return str(x)
def find(l,name): return [i for i in l if isinstance(i,list) and i and i[0]==name]
def first(l,name):
    r=find(l,name); return r[0] if r else None
