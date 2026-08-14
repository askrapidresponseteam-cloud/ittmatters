"""Edge cases for the logo-home behaviour that the main gate does not cover:
the no-script fallback, modified clicks, and reduced motion."""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
fails, n = [], 0
def check(ok, label):
    global n
    n += 1
    if not ok: fails.append(label)

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. the href alone, with the enhancement removed
    pg = b.new_page(viewport={"width": 1440, "height": 820})
    pg.goto(URL, wait_until="domcontentloaded"); pg.wait_for_timeout(2600)
    pg.evaluate("()=>{const a=document.querySelector('.itt-logo');"
                "const c=a.cloneNode(true);a.replaceWith(c);}")   # drop nothing:
    pg.evaluate("window.scrollTo(0,2200)"); pg.wait_for_timeout(300)
    # suppress the delegated handler so only the native href acts
    pg.evaluate("()=>{document.addEventListener('click',e=>e.stopPropagation(),true);}")
    pg.click(".itt-logo"); pg.wait_for_timeout(600)
    y = pg.evaluate("()=>Math.round(window.scrollY)")
    check(y == 0, f"native href fallback landed at {y}, not the top")
    check(pg.evaluate("()=>location.hash") == "#top",
          "native fallback did not set the hash (so it did not navigate)")

    # 2. a modified click must be left alone, so open-in-new-tab still works
    pg2 = b.new_page(viewport={"width": 1440, "height": 820})
    pg2.goto(URL, wait_until="domcontentloaded"); pg2.wait_for_timeout(2600)
    pg2.evaluate("window.scrollTo(0,2200)"); pg2.wait_for_timeout(300)
    res = pg2.evaluate(
        """()=>{const a=document.querySelector('.itt-logo');
           const ev=new MouseEvent('click',{bubbles:true,cancelable:true,metaKey:true});
           const img=a.querySelector('img'); img.dispatchEvent(ev);
           return {prevented: ev.defaultPrevented, y: Math.round(window.scrollY)};}"""
    )
    check(not res["prevented"], "meta-click was swallowed, breaking open-in-new-tab")

    # 3. reduced motion must land instantly rather than animating
    pg3 = b.new_page(viewport={"width": 1440, "height": 820}, reduced_motion="reduce")
    pg3.goto(URL, wait_until="domcontentloaded"); pg3.wait_for_timeout(2600)
    pg3.evaluate("window.scrollTo(0,2200)"); pg3.wait_for_timeout(300)
    pg3.click(".itt-logo"); pg3.wait_for_timeout(120)
    y3 = pg3.evaluate("()=>Math.round(window.scrollY)")
    check(y3 == 0, f"under reduced motion the return was still animating ({y3})")

    # 4. and without it, the return really is animated rather than a jump
    pg4 = b.new_page(viewport={"width": 1440, "height": 820})
    pg4.goto(URL, wait_until="domcontentloaded"); pg4.wait_for_timeout(2600)
    pg4.evaluate("window.scrollTo(0,2600)"); pg4.wait_for_timeout(300)
    pg4.click(".itt-logo"); pg4.wait_for_timeout(90)
    mid = pg4.evaluate("()=>Math.round(window.scrollY)")
    pg4.wait_for_timeout(1500)
    end = pg4.evaluate("()=>Math.round(window.scrollY)")
    check(0 < mid < 2600, f"the return was a jump, not a scroll (mid={mid})")
    check(end == 0, f"the animated return did not finish at the top ({end})")
    print(f"  mid-flight at {mid}px, settled at {end}px")
    b.close()

print(f"{n-len(fails)}/{n} edge checks pass")
for f in fails: print("  FAIL", f)
sys.exit(1 if fails else 0)
