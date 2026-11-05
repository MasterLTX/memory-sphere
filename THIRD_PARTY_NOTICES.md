# Third-party notices

Fetched at build time into `vendor/` (never committed):

| component | version | license | url |
|---|---|---|---|
| three.js | r160 (three.min.js) | MIT | https://github.com/mrdoob/three.js |
| KaTeX | 0.16.9 (js + css) | MIT | https://github.com/KaTeX/KaTeX |

Both are inlined into the generated single-file HTML so the output stays offline-capable.
KaTeX web fonts are referenced from jsDelivr and degrade gracefully to system serif fonts
when offline.
