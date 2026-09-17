import sys,pymupdf
pdf,tag,pages=sys.argv[1],sys.argv[2],[int(x) for x in sys.argv[3].split(',')]
d=pymupdf.open(pdf)
for p in pages:
    pix=d[p-1].get_pixmap(dpi=110); pix.save(f'{tag}_P{p}.png')
print('pages',len(d))
