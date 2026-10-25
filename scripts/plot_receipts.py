"""Plot only measured receipt deltas from the published scenario artifact."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
r = json.loads((root / 'evidence/demo/report.json').read_text())
rows = [s for s in r['scenarios'] if len(s['observations']) == 2]
labels = [s['id'].replace('_', ' ') for s in rows]
fig, ax = plt.subplots(figsize=(14, 9), facecolor='#f5f0e5')
ax.set_facecolor('#f5f0e5')
y = list(range(len(rows)))
for j,(mode,color) in enumerate([('baseline','#172b46'),('guarded','#078b7d')]):
 vals = [next(o['receipt_delta'] for o in s['observations'] if o['mode']==mode) for s in rows]
 pos = [v + (j-.5)*.32 for v in y]
 ax.barh(pos, vals, height=.29, color=color, label=f'{mode.capitalize()} bridge')
 for yy,v in zip(pos,vals): ax.text(v+.025,yy,str(v),va='center',fontsize=12,color=color)
ax.set_yticks(y, labels, fontsize=12)
ax.invert_yaxis();ax.set_xlim(0,1.25);ax.set_xticks([0,1]);ax.set_xlabel('Calls received by controlled server (per scenario)',fontsize=13)
ax.spines[['top','right','left']].set_visible(False)
ax.legend(loc='lower right',frameon=False,fontsize=12)
fig.suptitle('CallStencil | Did the call reach the server?',fontsize=24,fontweight='bold',x=.06,ha='left',color='#172b46')
fig.text(.06,.91,'Same 10 calls through real Streamable HTTP → stdio; one receipt means one received call.',fontsize=13,color='#172b46')
fig.text(.06,.05,'Controlled offline fixture, no GitHub mutations. Malformed baseline calls arrive then fail schema validation.\nAllowed upstream error still arrives. Invalid-policy startup is separate. No production-security or speed claim.',fontsize=11,color='#172b46')
fig.subplots_adjust(left=.23,right=.94,top=.86,bottom=.15)
fig.savefig(root/'campaign/assets/receipts-comparison.png',dpi=140)
