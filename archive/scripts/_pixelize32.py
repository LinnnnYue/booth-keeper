from PIL import Image, ImageFilter

SRC = 'D:/Lin_Agent/WB-WorkSpace/BoothKeeper/assets/art/scene-reimu-egg-icon_src720.png'
OUT_SVG = 'D:/Lin_Agent/WB-WorkSpace/booth-vault-toolhub/assets/logo/bv5-mark-line-32.svg'
OUT_PREVIEW = 'D:/Lin_Agent/WB-WorkSpace/booth-vault-toolhub/assets/logo/bv5-mark-line-32_preview.png'

im = Image.open(SRC).convert('RGB')
im32 = im.resize((32, 32), Image.LANCZOS)
q = im32.quantize(colors=8, method=Image.MEDIANCUT, dither=Image.NONE).convert('RGB')
q = q.filter(ImageFilter.ModeFilter(3))

pixels = list(q.getdata())
W = H = 32
rects = []
for y in range(H):
    x = 0
    while x < W:
        c = pixels[y * W + x]
        x2 = x
        while x2 + 1 < W and pixels[y * W + x2 + 1] == c:
            x2 += 1
        run = x2 - x + 1
        hexc = '#{:02X}{:02X}{:02X}'.format(*c)
        rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{hexc}"/>')
        x = x2 + 1

svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" shape-rendering="crispEdges">\n' + '\n'.join(rects) + '\n</svg>'
with open(OUT_SVG, 'w', encoding='utf-8') as f:
    f.write(svg)

preview = q.resize((256, 256), Image.NEAREST)
preview.save(OUT_PREVIEW)
print('svg rects:', len(rects))
print('svg bytes:', len(svg))
print('preview:', OUT_PREVIEW)
