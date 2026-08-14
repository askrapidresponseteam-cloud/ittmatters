from PIL import Image

SRC   = 'assets/f7ab245c-4972-4a93-8e2d-ac5d184aeb0a.png'
OUT   = 'logo-dark.png'
DARK_GROUND  = 11.0    # #0b0b0f, the ground the original was drawn for
LIGHT_GROUND = 242.0   # #f2f2f4, the light band
INK          = 11.0    # target for what is currently pure white

im = Image.open(SRC).convert('RGBA')
w, h = im.size
src = im.load()
out = Image.new('RGBA', (w, h))
dst = out.load()

for y in range(h):
    for x in range(w):
        r, g, b, a = src[x, y]
        if a == 0:
            dst[x, y] = (0, 0, 0, 0)
            continue
        mx, mn = max(r, g, b), min(r, g, b)
        sat = (mx - mn) / 255.0          # 0 for neutral, high for the accent red

        # neutral tone, expressed as "how far above the dark ground it sits"
        v = (r + g + b) / 3.0
        c = (v - DARK_GROUND) / (255.0 - DARK_GROUND)
        c = 0.0 if c < 0 else (1.0 if c > 1 else c)
        # same amount of contrast, measured downward from the light ground
        nv = LIGHT_GROUND - c * (LIGHT_GROUND - INK)
        nr = ng = nb = nv

        if sat > 0.02:                   # blend cleanly through the red's soft edges
            k = min(1.0, sat / 0.35)
            nr = nr * (1 - k) + r * k
            ng = ng * (1 - k) + g * k
            nb = nb * (1 - k) + b * k

        dst[x, y] = (int(round(nr)), int(round(ng)), int(round(nb)), a)

out.save(OUT, optimize=True)
print('wrote', OUT, out.size)

for name, ground in [('dark-onlight', (242, 242, 244, 255)), ('dark-onwhite', (255, 255, 255, 255))]:
    bg = Image.new('RGBA', out.size, ground)
    bg.alpha_composite(out)
    bg.convert('RGB').resize((w // 2, h // 2)).save(f'logo-{name}.png')
print('previews written')
