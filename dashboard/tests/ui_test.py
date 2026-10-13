"""Optional browser test (needs: pip install playwright && playwright install chromium). Run: python dashboard/tests/ui_test.py"""
import sys
from playwright.sync_api import sync_playwright
import os, tempfile
OUT=tempfile.mkdtemp()+'/'
url='file://'+os.path.abspath(os.path.join(os.path.dirname(__file__),'..','index.html'))
res=[]
def ok(name,cond): res.append((name,bool(cond)))
with sync_playwright() as p:
    b=p.chromium.launch()
    for name,vp,touch in [('desktop',{'width':1280,'height':900},False),('mobile',{'width':390,'height':844},True)]:
        ctx=b.new_context(viewport=vp,has_touch=touch,is_mobile=touch,device_scale_factor=1)
        pg=ctx.new_page(); errs=[]
        pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None); pg.on('pageerror',lambda e: errs.append(str(e)))
        pg.goto(url); pg.wait_for_timeout(400)
        ok(f"{name}: no JS errors", not errs)
        ok(f'{name}: no horizontal page scroll', pg.evaluate('document.documentElement.scrollWidth')<=vp['width'])
        ok(f'{name}: heat hist 20 rows', pg.locator('#heat-hist-tbl tbody tr').count()==21)
        ok(f'{name}: heat new 4 rows', pg.locator('#heat-new-tbl tbody tr').count()==5)
        ok(f'{name}: Oct 2026 in progress', pg.locator('#heat-new-tbl td.partial').count()==1)
        ok(f'{name}: Nov/Dec 2026 future', pg.locator('#heat-new-tbl td.future').count()==2)
        ok(f'{name}: 132 rules', '132 of 132' in pg.locator('#rule-count').inner_text())
        ok(f'{name}: glossary entries', pg.locator('#glossary .gl').count()>=40)
        # tooltip
        btn=pg.locator('#summary button.info').first
        if touch: btn.tap()
        else: btn.click()
        pg.wait_for_timeout(150)
        ok(f'{name}: tooltip opens', pg.locator('.pop').count()==1)
        pg.keyboard.press('Escape'); ok(f'{name}: Esc closes tooltip', pg.locator('.pop').count()==0)
        if not touch:
            pg.locator('#tbl-months thead button.info').first.hover(); pg.wait_for_timeout(150)
            ok('desktop: hover tooltip', pg.locator('.pop').count()==1)
            pg.mouse.move(5,5); pg.wait_for_timeout(100)
        # toggle
        pg.locator('.seg[data-chart="months"] button[data-v="both"]').click(); pg.wait_for_timeout(100)
        ok(f'{name}: months toggle both -> 24 bars', pg.locator('#ch-months rect[data-t]').count()==24)
        pg.locator('.seg[data-chart="path"] button[data-v="recent"]').click()
        ok(f'{name}: path toggle', '2023' in pg.locator('#lg-path').inner_text())
        # sort
        pg.locator('#tbl-months th[data-k="avg"]').click()
        first=pg.locator('#tbl-months tbody tr td').first.inner_text()
        ok(f'{name}: sort by avg desc -> Apr first', first.strip()=='Apr')
        # expand primary row
        pg.locator('#tbl-primaries tr.expandable').first.click()
        ok(f'{name}: expand primary', pg.locator('#tbl-primaries tr.detail:not([hidden])').count()==1)
        # search
        pg.fill('#rule-search','Nov16'); ok(f'{name}: rule search', '5 of 132' in pg.locator('#rule-count').inner_text())
        pg.fill('#gl-search','drawdown'); ok(f'{name}: glossary search', pg.locator('#glossary .gl:not([hidden])').count()>=1)
        pg.fill('#rule-search',''); pg.fill('#gl-search','')
        # keyboard focus on info buttons
        ok(f'{name}: info buttons focusable', pg.evaluate("document.querySelectorAll('button.info').length")>50)
        pg.reload(); pg.wait_for_timeout(300)
        pg.screenshot(path=OUT+f'{name}_full.png',full_page=True)
        ctx.close()
    b.close()
for n,c in res: print('PASS' if c else 'FAIL',n)
print(sum(c for _,c in res),'/',len(res))
