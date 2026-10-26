#!/usr/bin/env python3
"""作品ごとのページ（w/<id>/index.html）と、SNS で共有したときの画像（images/ogp/）を作ります。

サイトは index.html 1枚で作品を切り替えていますが、SNS は # から後ろを読まないため、
#w-<id> のままでは作品ごとの題名・説明・画像を出せません。そこで index.html を元に、
作品ごとに OGP の部分だけを差し替えたページを w/<id>/ に書き出します（中身は index.html と同じ）。

使い方:
  python3 tools/make_pages.py          作品ごとのページを書き出し、まだない共有画像を作る
  python3 tools/make_pages.py --all    共有画像もすべて作り直す
  python3 tools/make_pages.py her      ページを書き出し、her の共有画像だけ作り直す（題名を変えたときなど）

index.html か works.js を書き換えたら、毎回このスクリプトを実行します。
必要なもの: Node.js（npm）と Python の playwright（Chromium）。
書体（Shippori Mincho）は初回に tools/.cache/ へ自動で入れます。
"""
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / 'tools' / '.cache'
FONTS = CACHE / 'fonts' / 'node_modules' / '@fontsource'
SITE_URL = 'https://writingbook1210.github.io/'
AUTHOR = '及川 渉'
SITE_NAME = AUTHOR
OGP_START = '<!-- OGP（SNS などで共有したときに出る題名・説明・画像）ここから。'
OGP_END = '<!-- OGP ここまで -->'


def load_works():
    js = ("const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);"
          "vm.runInContext(fs.readFileSync('works.js','utf8')+';this.__W=W',c);"
          "process.stdout.write(JSON.stringify(c.__W))")
    out = subprocess.run(['node', '-e', js], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def ogp_block(title, desc, url, image, kind):
    a = lambda s: html.escape(s, quote=True)
    return '\n'.join([
        f'<link rel="canonical" href="{a(url)}">',
        f'<meta property="og:site_name" content="{a(SITE_NAME)}">',
        f'<meta property="og:type" content="{kind}">',
        f'<meta property="og:title" content="{a(title)}">',
        f'<meta property="og:description" content="{a(desc)}">',
        f'<meta property="og:url" content="{a(url)}">',
        f'<meta property="og:image" content="{a(image)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="ja_JP">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def work_page(template, w):
    a = lambda s: html.escape(s, quote=True)
    title = f"{w['t']}｜{AUTHOR}"
    desc = w.get('syn') or w.get('sub') or w['type']
    url = f"{SITE_URL}w/{w['id']}/"
    s = template
    s = s.replace('<meta charset="UTF-8">',
                  '<meta charset="UTF-8">\n<!-- このページは tools/make_pages.py が index.html から作ります。直接書き換えないでください -->\n'
                  '<base href="../../">', 1)
    s = re.sub(r'<title>.*?</title>', lambda m: f'<title>{a(title)}</title>', s, count=1)
    s = re.sub(r'<meta name="description" content="[^"]*">',
               lambda m: f'<meta name="description" content="{a(desc)}">', s, count=1)
    i, j = s.index(OGP_START), s.index(OGP_END) + len(OGP_END)
    s = s[:i] + ogp_block(title, desc, url, f"{SITE_URL}images/ogp/{w['id']}.png", 'article') + s[j:]
    s = s.replace('<script src="works.js', f"<script>var START='{w['id']}';</script>\n<script src=\"works.js", 1)
    return s


def write_pages(works):
    template = (ROOT / 'index.html').read_text(encoding='utf-8')
    assert OGP_START in template and OGP_END in template, 'index.html の OGP の印が見つかりません'
    out = ROOT / 'w'
    keep = set()
    for w in works:
        assert re.fullmatch(r'[A-Za-z0-9_-]+', w['id']), w['id']
        d = out / w['id']
        d.mkdir(parents=True, exist_ok=True)
        (d / 'index.html').write_text(work_page(template, w), encoding='utf-8')
        keep.add(w['id'])
        print('書き出しました:', (d / 'index.html').relative_to(ROOT))
    for d in out.iterdir():                      # なくなった作品のページは消す
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d)
            print('消しました:', d.relative_to(ROOT))


# ---------- 共有画像（1200×630） ----------
def ensure_fonts():
    if (FONTS / 'shippori-mincho').exists():
        return
    d = CACHE / 'fonts'
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(['npm', 'init', '-y'], cwd=d, check=True, capture_output=True)
    subprocess.run(['npm', 'install', '--silent', '@fontsource/shippori-mincho@5'], cwd=d, check=True)


def font_links():
    files = ['shippori-mincho/400.css', 'shippori-mincho/500.css']
    return ''.join(f'<link rel="stylesheet" href="{(FONTS / f).as_uri()}">' for f in files)


BASE_CSS = """
*{box-sizing:border-box}
html,body{margin:0;background:#fff;color:#111}
body{width:1200px;height:630px;position:relative;overflow:hidden;
  font-family:'Shippori Mincho','Noto Serif CJK JP',serif}
.frame{position:absolute;inset:56px 72px;border-top:1.5px solid #111;border-bottom:1px solid rgba(0,0,0,.35)}
"""


def page(inner, css=''):
    return (f'<!doctype html><html lang="ja"><head><meta charset="utf-8">{font_links()}'
            f'<style>{BASE_CSS}{css}</style></head><body>{inner}</body></html>')


def site_html():
    css = """
.frame{display:flex;align-items:center;justify-content:center}
.nm{font-size:104px;font-weight:500;letter-spacing:.3em;padding-left:.3em;line-height:1}
"""
    return page(f'<div class="frame"><span class="nm">{html.escape(AUTHOR)}</span></div>', css)


def work_html(w):
    e = html.escape
    meta = '　／　'.join(x for x in [w.get('type'), w.get('st')] if x)
    if w.get('type') == '小説':                 # 小説は題名を縦に組む
        css = """
.top{position:absolute;left:0;top:30px;display:flex;flex-direction:column;gap:14px}
.meta{font-size:17px;letter-spacing:.18em;color:#555}
.date{position:absolute;left:0;bottom:30px;font-size:17px;letter-spacing:.14em;color:#555}
.vw{position:absolute;right:120px;top:40px;bottom:40px;writing-mode:vertical-rl;
  display:flex;flex-direction:column;gap:44px}
.vt{margin:0;font-size:92px;font-weight:500;letter-spacing:.32em;line-height:1.2}
.va{margin:0;align-self:flex-end;font-size:24px;letter-spacing:.3em}
"""
        inner = (f'<div class="frame"><div class="top"><span class="meta">{e(meta)}</span></div>'
                 f'<div class="vw"><h1 class="vt">{e(w["t"])}</h1><p class="va">{e(AUTHOR)}</p></div>'
                 f'<span class="date">{e(w.get("date", ""))}</span></div>')
        return page(inner, css)
    n = len(w['t'])
    size = 64 if n <= 14 else 54 if n <= 22 else 48
    css = f"""
.frame{{display:flex;flex-direction:column;justify-content:space-between;padding:30px 0 26px}}
.top{{display:flex;justify-content:space-between;align-items:baseline}}
.meta{{font-size:17px;letter-spacing:.18em;color:#555}}
.mid{{display:flex;flex-direction:column;gap:18px;max-width:980px}}
h1{{margin:0;font-size:{size}px;font-weight:500;line-height:1.45;letter-spacing:.05em;word-break:auto-phrase;text-wrap:balance}}
.sub{{margin:0;font-size:24px;line-height:1.7;letter-spacing:.06em;color:#555;word-break:auto-phrase;text-wrap:balance}}
.bot{{display:flex;justify-content:space-between;align-items:baseline;font-size:22px;letter-spacing:.2em}}
.bot .date{{font-size:17px;letter-spacing:.14em;color:#555}}
"""
    inner = (f'<div class="frame"><div class="top"><span class="meta">{e(meta)}</span></div>'
             f'<div class="mid"><h1>{e(w["t"])}</h1>'
             + (f'<p class="sub">{e(w["sub"])}</p>' if w.get('sub') else '') +
             f'</div><div class="bot"><span>{e(AUTHOR)}</span><span class="date">{e(w.get("date", ""))}</span></div></div>')
    return page(inner, css)


def render(pw_page, markup, out):
    tmp = CACHE / 'render.html'
    tmp.write_text(markup, encoding='utf-8')
    pw_page.goto(tmp.as_uri())
    pw_page.evaluate('document.fonts.ready')
    pw_page.wait_for_timeout(300)
    out.parent.mkdir(parents=True, exist_ok=True)
    pw_page.screenshot(path=str(out), clip={'x': 0, 'y': 0, 'width': 1200, 'height': 630})
    print('作りました:', out.relative_to(ROOT))


def make_images(works, redo_all, only):
    from playwright.sync_api import sync_playwright
    ensure_fonts()
    CACHE.mkdir(parents=True, exist_ok=True)
    ogp = ROOT / 'images' / 'ogp'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={'width': 1200, 'height': 630})
        if redo_all or not (ogp / 'site.png').exists():
            render(pg, site_html(), ogp / 'site.png')
        for w in works:
            target = ogp / f"{w['id']}.png"
            if redo_all or w['id'] in only or not target.exists():
                render(pg, work_html(w), target)
        browser.close()


def main():
    args = sys.argv[1:]
    works = load_works()
    write_pages(works)
    make_images(works, '--all' in args, [a for a in args if not a.startswith('--')])


if __name__ == '__main__':
    main()
