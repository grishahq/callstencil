"""Render the canonical campaign into a local review gallery (no publishing)."""
import html
import json
from pathlib import Path

here = Path(__file__).resolve().parent
data = json.loads((here / 'campaign.json').read_text())
e = html.escape
cards = []
for b in data['beats']:
    threads = ''.join(f'<li><pre>{e(t)}</pre></li>' for t in b['x_thread'])
    states=[]
    for platform,item in b['platform_items'].items():
        state='published' if item['published'] else 'scheduled' if item['scheduled'] else 'prepared'
        when=item.get('schedule',{}).get('scheduled_for','')
        states.append(f'{platform}: {state} {when}')
    cards.append(f'''<article><p class="eyebrow">{e(b['id'])}</p><h2>{e(b['name'])}</h2>
<img src="{e(b['image'])}" alt="{e(b['alt_text'])}">
<p class="caption">{e(b['image_kind'])} · {e(b['alt_text'])}</p>
<p><strong>Audience:</strong> {e(b['audience'])}</p><p><strong>Evidence:</strong> {e(', '.join(b['evidence_references']))}</p>
<p><strong>State:</strong> {e(' | '.join(states))}</p>
<div class="copy"><section><h3>LinkedIn</h3><pre>{e(b['linkedin'])}</pre></section>
<section><h3>X thread</h3><ol>{threads}</ol></section></div></article>''')
(here / 'REVIEW.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CallStencil launch review</title>
<style>body{max-width:1200px;margin:auto;background:#f5f0e5;color:#172b46;padding:40px;font:17px/1.6 system-ui}h1{font-size:56px;line-height:1.1}h2{font-size:32px}article{padding:36px;margin:36px 0;background:#fffaf0;border:1px solid #d7d2c7;border-radius:20px}img{display:block;max-width:100%;max-height:720px;margin:25px auto;object-fit:contain}.eyebrow{color:#078b7d;letter-spacing:.1em;text-transform:uppercase}.caption{font-size:13px}.copy{display:grid;grid-template-columns:1fr 1fr;gap:35px}pre{white-space:pre-wrap;font:15px/1.7 system-ui}li{padding-bottom:12px}a{color:#087d73}@media(max-width:800px){.copy{display:block}body{padding:18px}article{padding:20px}}</style>
<header><p class="eyebrow">English engineering campaign · review copy</p><h1>CallStencil launch kit</h1><p>Five story beats, adapted for LinkedIn and X. Concept art is labeled separately from actual software evidence.</p>
<p><a href="https://github.com/grishahq/callstencil/releases/tag/v0.1.0">Verified immutable public alpha release</a> · <a href="campaign.json">Canonical copy and states</a> · <a href="provenance.json">Visual provenance</a></p></header>'''+''.join(cards)+f'<footer>{e(data["attribution"])}</footer></html>', encoding='utf-8')
print('Rendered campaign/REVIEW.html from canonical campaign.json')
