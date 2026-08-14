#!/usr/bin/env python3
"""
Adds a sticky, ground-aware top bar to the ittmatters bundle.

Re-runnable against a fresh export from the design tool. Refuses to run
twice on the same file.

  python3 patch2.py <in.html> <out.html> <logo-dark.png>

Two things this file exists to remember:

  * The export styles the bar inline and drives its breakpoints with
    [data-m="..."] selectors that sit in the helmet, ABOVE the markup. So a
    naive replace of data-m="navlinks" rewrites the CSS SELECTOR, not the
    element, and silently kills the responsive rule. Nothing is hooked by
    editing those elements here; the stylesheet below matches them where
    they already are.

  * The component runtime re-renders the bar from its own template, so any
    node captured at startup goes stale and any attribute set on it lands on
    an orphan. The script below looks the bar up fresh every time and
    re-applies after a re-render.
"""
import base64
import json
import re
import sys

MARK = "itt-stickybar"
LIGHT_UUID = "f7ab245c-4972-4a93-8e2d-ac5d184aeb0a"   # the cream lockup, already shipped
DARK_UUID = "9c1f4b70-3a2e-4d15-8f6b-2ea70d4c19b3"    # the ink lockup this adds

IN, OUT, DARK_LOGO = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(IN, encoding="utf-8").read()
if MARK in src:
    sys.exit("already patched: " + IN)


def block(kind):
    m = re.search(
        r'(<script[^>]*type="__bundler/%s"[^>]*>)(.*?)(</script>)' % kind, src, re.S
    )
    if not m:
        sys.exit("no __bundler/%s block found" % kind)
    return m


tpl_m = block("template")
manifest = json.loads(block("manifest").group(2))
tpl = json.loads(tpl_m.group(2))

# ── 1. the ink lockup joins the manifest under its own uuid ───────────────
if DARK_UUID in manifest:
    sys.exit("uuid collision")
manifest[DARK_UUID] = {
    "mime": "image/png",
    "compressed": False,
    "data": base64.b64encode(open(DARK_LOGO, "rb").read()).decode("ascii"),
}

# ── 2. the two lockups stack, so the swap shifts no layout ────────────────
old_logo = (
    '<img src="%s" alt="ittmatters" style="height:34px;width:auto;display:block;">'
    % LIGHT_UUID
)
if tpl.count(old_logo) != 1:
    sys.exit("logo markup not found exactly once; the export has changed shape")
tpl = tpl.replace(
    old_logo,
    '<span class="itt-logo">'
    '<img class="itt-logo-cream" src="%s" alt="ittmatters">'
    '<img class="itt-logo-ink" src="%s" alt="" aria-hidden="true">'
    "</span>" % (LIGHT_UUID, DARK_UUID),
    1,
)

# ── 3. the nav and the mobile menu travel together in one sticky wrapper ──
nav_open = '<nav data-m="nav"'
menu_end = '</div>\n\n<header data-m="hero"'
for probe in (nav_open, menu_end):
    if tpl.count(probe) != 1:
        sys.exit("anchor not found exactly once: " + probe[:40])
tpl = tpl.replace(
    nav_open, '<div id="itt-bar" data-ground="dark" data-stuck="0">' + nav_open, 1
)
tpl = tpl.replace(menu_end, '</div></div>\n\n<header data-m="hero"', 1)

# ── 4. the stylesheet ─────────────────────────────────────────────────────
# Every control on the bar carries an inline style and inline beats a rule,
# so these declarations are !important on purpose. Elements are matched on
# the data-m attributes they already have; none of them is edited.
CSS = """
/* ---- sticky, ground-aware top bar ---------------------------------- */
/* overflow-x:hidden makes body a scroll container, and position:sticky is
   dead inside one. clip does the same job without that side effect. */
html,body{overflow-x:clip!important}

/* NO transition on the ground or on the lockup, and this is deliberate.
   Crossfading a cream lockup into an ink one over a fading ground passes
   through a state where both sit at mid-grey: it measures 1.19:1 at the
   quarter point, which is worse than the problem this whole thing exists to
   fix. The band edge is a hard line, so the bar meets it with a hard switch. */
#itt-bar{position:sticky!important;top:0!important;z-index:60!important;
  background:transparent}

/* The bar keeps ONE height at every scroll depth. A condensing bar was the
   first version and it had to go: position:sticky stays in normal flow, so
   trimming its padding shrank the document 22px and pulled every section up
   under the reader mid-scroll. Nothing here changes layout; only the fill
   and the hairline come and go. */
#itt-bar[data-stuck="1"][data-ground="dark"]{background:#0b0b0f!important;
  box-shadow:0 1px 0 rgba(244,242,236,.12)!important}
#itt-bar[data-stuck="1"][data-ground="light"]{background:#f2f2f4!important;
  box-shadow:0 1px 0 rgba(11,11,15,.14)!important}

/* Set for the one frame the ground changes on. Hovers stay smooth; the
   switch itself never animates, so it cannot pass through the mid-grey
   state that measures 1.19:1. */
/* the attribute is doubled on purpose: #itt-bar[data-switching] * scores
   (1,1,0) and loses to the hover rule below at (1,1,1), so the suppression
   never reached the links. Doubling takes it to (1,2,0). */
#itt-bar[data-switching="1"][data-switching="1"],
#itt-bar[data-switching="1"][data-switching="1"] *{transition:none!important}

/* the mark: both files stacked, one fading into the other */
.itt-logo{position:relative!important;display:block!important;height:34px!important}
.itt-logo img{height:100%!important;width:auto!important;display:block!important}
.itt-logo .itt-logo-ink{position:absolute!important;left:0!important;top:0!important;opacity:0!important}
#itt-bar[data-ground="light"] .itt-logo .itt-logo-cream{opacity:0!important}
#itt-bar[data-ground="light"] .itt-logo .itt-logo-ink{opacity:1!important}

/* everything else on the bar turns with it */
#itt-bar[data-ground="light"] [data-m="navlinks"] a{color:#565963!important}
#itt-bar[data-ground="light"] [data-m="navcta"]{border-color:rgba(11,11,15,.4)!important;color:#0b0b0f!important}
#itt-bar[data-ground="light"] [data-m="burger"]{border-color:rgba(11,11,15,.4)!important}
#itt-bar[data-ground="light"] [data-m="burger"] span{background:#0b0b0f!important}
#itt-bar[data-ground="light"] [data-m="mobilemenu"]{background:#f2f2f4!important;
  border-bottom-color:rgba(11,11,15,.14)!important}
#itt-bar[data-ground="light"] [data-m="mobilemenu"] a{color:#0b0b0f!important;
  border-top-color:rgba(11,11,15,.14)!important}
/* the menu's solid CTA is a cream plate. On the light ground its fill and the
   ground behind it are the same value, so the label stayed readable while the
   button itself vanished. It inverts with everything else. */
#itt-bar[data-ground="light"] [data-m="mobilemenu"] a[href^="mailto:"]{
  background:#0b0b0f!important;color:#f4f2ec!important}

/* the export ships hovers in a style-hover attribute no browser reads, so
   the bar's own hovers are written out here as real rules */
#itt-bar [data-m="navlinks"] a{transition:color .2s ease!important}
#itt-bar [data-m="navlinks"] a:hover{color:#f4f2ec!important}
#itt-bar[data-ground="light"] [data-m="navlinks"] a:hover{color:#0b0b0f!important}
#itt-bar [data-m="navcta"]:hover{background:#f4f2ec!important;color:#0b0b0f!important}
#itt-bar[data-ground="light"] [data-m="navcta"]:hover{background:#0b0b0f!important;color:#f4f2ec!important}

@media (max-width:960px){.itt-logo{height:30px!important}}
"""

JS = """
/* Keeps the bar readable over whatever it is sitting on. The ground is read
   off the page itself rather than a hard-coded list of sections, so a light
   band added later needs no change here.

   The bar is looked up fresh on every pass: the component runtime rebuilds
   it from its own template, and a node captured once goes stale, taking
   every attribute set on it out of the document with it. */
(function(){
  function lum(p){
    function f(v){ v = v/255; return v <= 0.03928 ? v/12.92
                   : Math.pow((v+0.055)/1.055, 2.4); }
    return 0.2126*f(+p[0]) + 0.7152*f(+p[1]) + 0.0722*f(+p[2]);
  }

  function isLightAt(bar, x, y){
    var stack = document.elementsFromPoint(x, y), i, el, bg, p, a;
    for (i = 0; i < stack.length; i++){
      el = stack[i];
      if (bar === el || bar.contains(el)) continue;
      bg = getComputedStyle(el).backgroundColor;
      p = bg ? bg.match(/[\\d.]+/g) : null;
      if (!p || p.length < 3) continue;
      a = p.length > 3 ? parseFloat(p[3]) : 1;
      if (a < 0.5) continue;                       /* see straight through it */
      return lum(p) > 0.4;
    }
    return false;
  }

  var queued = false;
  function apply(){
    queued = false;
    var bar = document.getElementById('itt-bar');
    if (!bar) return;
    bar.setAttribute('data-stuck', window.scrollY > 4 ? '1' : '0');
    var y = Math.max(1, Math.round(bar.getBoundingClientRect().bottom) - 2);
    var w = window.innerWidth;
    /* two samples, and light wins: a cream mark lost on a pale ground is the
       failure worth avoiding */
    var want = (isLightAt(bar, Math.min(40, w/2), y)
             || isLightAt(bar, Math.round(w/2), y)) ? 'light' : 'dark';

    /* Compared against the attribute rather than a remembered value, so a
       re-render that resets it is corrected the same way. */
    if (bar.getAttribute('data-ground') !== want){
      bar.setAttribute('data-switching', '1');
      bar.setAttribute('data-ground', want);
      void bar.offsetWidth;              /* commit the new colours unanimated */
      requestAnimationFrame(function(){
        var b = document.getElementById('itt-bar');
        if (b) b.removeAttribute('data-switching');
      });
    }
  }
  function tick(){ if (!queued){ queued = true; requestAnimationFrame(apply); } }

  function start(){
    window.addEventListener('scroll', tick, {passive:true});
    window.addEventListener('resize', tick);
    /* a re-render drops the attributes back to the template defaults; watching
       for nodes coming and going puts them back. childList only, so writing
       the attributes cannot retrigger this. */
    if (window.MutationObserver){
      new MutationObserver(tick).observe(document.documentElement,
        {childList:true, subtree:true});
    }
    tick();
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', start);
  else start();
})();
"""

anchor = "</style></helmet>"
if anchor not in tpl:
    sys.exit("end of the helmet not found")
tpl = tpl.replace(anchor, '</style><style id="%s">%s</style></helmet>' % (MARK, CSS), 1)

if "</body></html>" not in tpl:
    sys.exit("end of body not found")
tpl = tpl.replace(
    "</body></html>", '<script id="%s-js">%s</script></body></html>' % (MARK, JS), 1
)


# ── 5. write the bundle back ──────────────────────────────────────────────
def embed(obj):
    """JSON for a <script> body. A literal </ closes the tag early and
    truncates the bundle, which is why the exporter escapes it this way."""
    return json.dumps(obj).replace("</", "<\\u002F")


out = src[: tpl_m.start(2)] + "\n" + embed(tpl) + "\n  " + src[tpl_m.end(2) :]
man2 = re.search(
    r'(<script[^>]*type="__bundler/manifest"[^>]*>)(.*?)(</script>)', out, re.S
)
out = out[: man2.start(2)] + "\n" + embed(manifest) + "\n  " + out[man2.end(2) :]

open(OUT, "w", encoding="utf-8").write(out)
print("wrote %s (%d bytes, %d assets)" % (OUT, len(out), len(manifest)))
