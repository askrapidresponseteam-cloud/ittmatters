#!/usr/bin/env python3
"""
Gate for the sticky bar.

The point of this file: it does NOT ask the CSS what colour things are. It
screenshots the bar and measures the lockup's own pixels against the ground
they are actually painted on, at every scroll depth including the band edges
where a transition would have hidden a dip.

  python3 gate.py <url>
"""
import io
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
WIDTHS = [1440, 1180, 1024, 768, 390, 320]
TEXT_FLOOR = 4.5      # nav links, CTA label
GRAPHIC_FLOOR = 3.0   # the lockup, burger bars, CTA border

fails, checks = [], 0


def lum(c):
    def f(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        fails.append(label)


def lockup_legible(png, ground):
    """Share of the lockup's box whose ink clears TEXT_FLOOR against the ground
    it is actually painted on.

    Not the worst pixel: every glyph edge is an anti-aliasing gradient that runs
    all the way down to the ground, so a worst-pixel measure only ever reports
    the exclusion threshold it was given. Calibrated instead: the glyph ink
    covers ~29.5% of the box in BOTH correct states and 0.4% when the wrong
    lockup is left showing, so a 20% floor separates them with room to spare.

    The accent red is excluded. It is the same colour on both grounds by
    design, so it is not what this is testing."""
    im = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = im.size
    px = im.load()
    n = ok = 0
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if max(c) - min(c) > 40:          # accent red, skip
                continue
            n += 1
            if contrast(c, ground) >= TEXT_FLOOR:
                ok += 1
    return (ok / n if n else 0.0), n


with sync_playwright() as p:
    b = p.chromium.launch()
    for W in WIDTHS:
        pg = b.new_page(viewport={"width": W, "height": 820})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto(URL, wait_until="domcontentloaded")
        pg.wait_for_timeout(2600)
        pg.evaluate("document.documentElement.style.scrollBehavior='auto'")

        q = """() => ({
          top: Math.round(document.getElementById('why').getBoundingClientRect().top+scrollY),
          h: Math.round(document.getElementById('why').getBoundingClientRect().height),
          docH: document.documentElement.scrollHeight,
          barH: Math.round(document.getElementById('itt-bar').getBoundingClientRect().height)
        })"""
        geo = pg.evaluate(q)
        # a sticky bar is in flow: if it changes height the whole document
        # reflows under the reader. This is the regression gate for that.
        pg.evaluate("window.scrollTo(0,400)")
        pg.wait_for_timeout(500)
        stuck = pg.evaluate(q)
        pg.evaluate("window.scrollTo(0,0)")
        pg.wait_for_timeout(300)
        check(stuck["docH"] == geo["docH"],
              f"{W} document reflows when the bar sticks "
              f"({geo['docH']} -> {stuck['docH']})")
        check(stuck["top"] == geo["top"],
              f"{W} sections shift when the bar sticks "
              f"({geo['top']} -> {stuck['top']})")
        check(stuck["barH"] == geo["barH"],
              f"{W} bar changes height ({geo['barH']} -> {stuck['barH']})")

        # every 60px, plus a tight sweep across both band edges where the
        # switch happens
        stops = list(range(0, geo["docH"] - 700, 60))
        for edge in (geo["top"], geo["top"] + geo["h"]):
            stops += [edge - 120 + k * 8 for k in range(32)]
        stops = sorted({s for s in stops if 0 <= s <= geo["docH"] - 700})

        for y in stops:
            pg.evaluate(f"window.scrollTo(0,{y})")
            pg.wait_for_timeout(45)
            s = pg.evaluate(
                """() => {
              const bar = document.getElementById('itt-bar');
              if (!bar) return null;
              const r = bar.getBoundingClientRect();
              const logo = bar.querySelector('.itt-logo');
              const lr = logo.getBoundingClientRect();
              const vis = e => e && getComputedStyle(e).display !== 'none';
              const link = bar.querySelector('[data-m="navlinks"] a');
              const cta  = bar.querySelector('[data-m="navcta"]');
              const burg = bar.querySelector('[data-m="burger"]');
              const bspan= burg && burg.querySelector('span');
              const cs = getComputedStyle(bar);
              return {
                top: Math.round(r.top), h: Math.round(r.height),
                ground: bar.getAttribute('data-ground'),
                stuck: bar.getAttribute('data-stuck'),
                barBg: cs.backgroundColor,
                logo: {x:lr.x, y:lr.y, w:lr.width, h:lr.height},
                linkOn: vis(link && link.parentElement),
                linkColor: link && getComputedStyle(link).color,
                ctaOn: vis(cta), ctaColor: cta && getComputedStyle(cta).color,
                ctaBorder: cta && getComputedStyle(cta).borderTopColor,
                burgerOn: vis(burg),
                burgerBar: bspan && getComputedStyle(bspan).backgroundColor,
                sideScroll: document.documentElement.scrollWidth > window.innerWidth
              };
            }"""
            )
            check(s is not None, f"{W}@{y} bar missing")
            if not s:
                continue

            check(s["top"] == 0, f"{W}@{y} bar not pinned (top={s['top']})")
            check(not s["sideScroll"], f"{W}@{y} sideways scroll")
            check(s["stuck"] == ("1" if y > 4 else "0"), f"{W}@{y} stuck={s['stuck']}")

            def rgb(v):
                q = [float(t) for t in v.replace("rgba", "rgb").strip("rgb() ").split(",")]
                return tuple(int(round(t)) for t in q[:3])

            # the ground the bar is actually painted in
            if s["stuck"] == "1":
                ground = rgb(s["barBg"])
            else:
                ground = (11, 11, 15)   # transparent, over the hero

            # the lockup, measured off the screen
            shot = pg.screenshot(
                clip={"x": s["logo"]["x"], "y": s["logo"]["y"],
                      "width": s["logo"]["w"], "height": s["logo"]["h"]}
            )
            share, n = lockup_legible(shot, ground)
            check(n > 200, f"{W}@{y} lockup box is empty ({n}px)")
            check(share >= 0.20,
                  f"{W}@{y} LOCKUP only {share*100:.1f}% legible on {ground} "
                  f"(data-ground={s['ground']})")

            if s["linkOn"]:
                check(contrast(rgb(s["linkColor"]), ground) >= TEXT_FLOOR,
                      f"{W}@{y} nav links {contrast(rgb(s['linkColor']), ground):.2f}:1")
            if s["ctaOn"]:
                check(contrast(rgb(s["ctaColor"]), ground) >= TEXT_FLOOR,
                      f"{W}@{y} CTA label {contrast(rgb(s['ctaColor']), ground):.2f}:1")
                check(contrast(rgb(s["ctaBorder"]), ground) >= 1.9,
                      f"{W}@{y} CTA border {contrast(rgb(s['ctaBorder']), ground):.2f}:1")
            if s["burgerOn"]:
                check(contrast(rgb(s["burgerBar"]), ground) >= GRAPHIC_FLOOR,
                      f"{W}@{y} burger {contrast(rgb(s['burgerBar']), ground):.2f}:1")

            # the export's own breakpoints must still hold
            check(s["linkOn"] == (W > 960), f"{W}@{y} navlinks visible={s['linkOn']}")
            check(s["burgerOn"] == (W <= 960), f"{W}@{y} burger visible={s['burgerOn']}")
            check(s["ctaOn"] == (W > 640), f"{W}@{y} CTA visible={s['ctaOn']}")

        # the menu, opened while the bar sits on the light band
        if W <= 960:
            pg.evaluate(f"window.scrollTo(0,{geo['top'] + 200})")
            pg.wait_for_timeout(200)
            pg.click('[data-m="burger"]')
            pg.wait_for_timeout(400)
            m = pg.evaluate(
                """() => {
              const bar = document.getElementById('itt-bar');
              const mob = bar.querySelector('[data-m="mobilemenu"]');
              const a = mob.querySelector('a');
              return {open: getComputedStyle(mob).display !== 'none',
                      ground: bar.getAttribute('data-ground'),
                      bg: getComputedStyle(mob).backgroundColor,
                      link: getComputedStyle(a).color,
                      spill: document.documentElement.scrollWidth > window.innerWidth};
            }"""
            )
            check(m["open"], f"{W} menu did not open")
            check(m["ground"] == "light", f"{W} menu ground={m['ground']}")
            if m["open"]:
                bg = tuple(int(round(float(t))) for t in
                           m["bg"].replace("rgba", "rgb").strip("rgb() ").split(",")[:3])
                lk = tuple(int(round(float(t))) for t in
                           m["link"].replace("rgba", "rgb").strip("rgb() ").split(",")[:3])
                check(contrast(lk, bg) >= TEXT_FLOOR,
                      f"{W} menu links {contrast(lk, bg):.2f}:1")
                # a filled control whose fill matches its surround keeps a
                # readable label but stops looking like a button at all
                cta = pg.evaluate(
                    """() => {const a = document.querySelector(
                       '#itt-bar [data-m="mobilemenu"] a[href^="mailto:"]');
                       if (!a) return null; const c = getComputedStyle(a);
                       return {bg:c.backgroundColor, fg:c.color};}"""
                )
                if cta:
                    cbg = tuple(int(round(float(t))) for t in
                        cta["bg"].replace("rgba","rgb").strip("rgb() ").split(",")[:3])
                    cfg = tuple(int(round(float(t))) for t in
                        cta["fg"].replace("rgba","rgb").strip("rgb() ").split(",")[:3])
                    check(contrast(cbg, bg) >= 1.6,
                          f"{W} menu CTA plate {contrast(cbg, bg):.2f}:1 against the menu")
                    check(contrast(cfg, cbg) >= TEXT_FLOOR,
                          f"{W} menu CTA label {contrast(cfg, cbg):.2f}:1 on its fill")
            check(not m["spill"], f"{W} menu spills sideways")

        check(not errs, f"{W} script errors: {errs}")
        print(f"  {W}px  {len(stops)} scroll positions")
        pg.close()
    b.close()

print()
print(f"{checks - len(fails)}/{checks} checks pass")
import collections, re as _re
kinds = collections.Counter(_re.sub(r"^\d+@\d+ ", "", f).split(" only ")[0].split(" (")[0]
                            for f in fails)
for kind, n in kinds.most_common():
    print(f"  FAIL x{n}  {kind}")
    print("        e.g.", next(f for f in fails if kind in f))
sys.exit(1 if fails else 0)
