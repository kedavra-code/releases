#!/usr/bin/env node
/* Rendered-output audit for 00_Cerebrum_viewer.html — the verify.py of the pixels.
 *
 * Every viewer defect so far was caught by the owner, not by any check:
 * the radius-zero graph, the unclickable zoom, the &amp; in node labels,
 * the mid-screen scrollbar. The generator ran clean each time; the rendered
 * page was the thing that was wrong. This script is the render-and-look
 * habit made executable, so it survives the session that learned it.
 *
 * Usage:  node _scripts/viewer-check.js [path/to/00_Cerebrum_viewer.html]
 * Runs wherever node + playwright exist (librarian sessions). Exit 1 on any
 * failure. The delivery rule in 00_Cerebrum/CLAUDE.md: no viewer delivery
 * without this green — and it replaces none of the eyeballing, because it
 * checks what is listed here and nothing else.
 */
const path = require('path');
const { chromium } = require('playwright');

const FILE = path.resolve(process.argv[2] || path.join(__dirname, '..', '00_Cerebrum_viewer.html'));
let failures = 0;
const check = (ok, label, detail) => {
  console.log((ok ? 'ok      ' : 'FAIL    ') + label + (detail ? '  [' + detail + ']' : ''));
  if (!ok) failures++;
};

// The pixels of a screenshot, for what no style property can say: two lines
// drawn by different means, a pseudo-element and a shadow, compared as painted.
// Decodes what Chromium writes, an 8-bit PNG without interlacing, RGB or RGBA.
const zlib = require('zlib');
const pngPixels = buf => {
  let pos = 8, w = 0, h = 0, bpp = 4;
  const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos), type = buf.toString('ascii', pos + 4, pos + 8), body = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') { w = body.readUInt32BE(0); h = body.readUInt32BE(4); bpp = body[9] === 2 ? 3 : 4; }
    else if (type === 'IDAT') idat.push(body);
    pos += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat)), row = w * bpp, out = Buffer.alloc(row * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (row + 1)], s = y * (row + 1) + 1, o = y * row;
    for (let x = 0; x < row; x++) {
      const a = x >= bpp ? out[o + x - bpp] : 0, b = y ? out[o - row + x] : 0, c = x >= bpp && y ? out[o - row + x - bpp] : 0;
      const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
      const pred = [0, a, b, (a + b) >> 1, pa <= pb && pa <= pc ? a : pb <= pc ? b : c][f];
      out[o + x] = (raw[s + x] + pred) & 255;
    }
  }
  return (x, y) => [...out.subarray((y * w + x) * bpp, (y * w + x) * bpp + 3)];
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push(e.message));

  await page.goto('file://' + FILE);
  await page.waitForTimeout(700);

  // 1. The page boots: data present, sidebar populated, no JS errors.
  const boot = await page.evaluate(() => ({
    concepts: typeof D === 'object' ? Object.keys(D).length : 0,
    items: document.querySelectorAll('.it').length,
    setHidden: document.getElementById('setBox').hidden,
    setExpanded: document.getElementById('bSet').getAttribute('aria-expanded'),
  }));
  check(jsErrors.length === 0, 'no JS errors on load', jsErrors[0]);
  check(boot.concepts > 0, 'concept data present', boot.concepts + ' concepts');
  check(boot.items === boot.concepts, 'sidebar lists every concept',
        boot.items + ' of ' + boot.concepts);
  // Here, before anything is clicked. It sat with the other Settings checks
  // first, and passed with the panel open at load, because every click before
  // it counts as a click outside the panel and closes it.
  check(boot.setHidden && boot.setExpanded === 'false', 'Settings starts closed',
        'hidden=' + boot.setHidden + ' aria-expanded=' + boot.setExpanded);

  // 2. A concept page renders, and no HTML entity leaks into visible text.
  //    Prefer a title carrying "&": that is the regression of 10.08.2026.
  const target = await page.evaluate(() => {
    const ids = Object.keys(D);
    return ids.find(i => D[i].t.includes('&')) || ids[0];
  });
  await page.evaluate(id => show(id), target);
  await page.waitForTimeout(300);
  const rendered = await page.evaluate(() => ({
    h1: document.querySelector('#main h1').textContent,
    entity: /&(amp|lt|gt|quot|#\d+);/.test(document.getElementById('main').textContent),
  }));
  check(!rendered.entity, 'no HTML entity in rendered page text', rendered.h1);

  // 3. Search matches raw text: a title's own words must find it.
  const probe = await page.evaluate(t => {
    const q = document.getElementById('q');
    q.value = D[t].t.toLowerCase();
    q.dispatchEvent(new Event('input'));
    return document.querySelectorAll('.it').length;
  }, target);
  check(probe >= 1, 'search finds a concept by its exact title', probe + ' hits');

  // 3a-ii. The clear button. It only exists while there is something to clear,
  //        and it has to clear through the same `input` event the search runs
  //        on — setting the value alone would leave the list filtered.
  const clr = await page.evaluate(t => {
    const q = document.getElementById('q'), w = document.getElementById('qwrap');
    q.value = ''; q.dispatchEvent(new Event('input'));
    const hiddenWhenEmpty = getComputedStyle(document.getElementById('qx')).display === 'none';
    q.value = D[t].t.toLowerCase(); q.dispatchEvent(new Event('input'));
    const shownWhenTyped = getComputedStyle(document.getElementById('qx')).display !== 'none';
    const filtered = document.querySelectorAll('.it').length;
    document.getElementById('qx').click();
    return {hiddenWhenEmpty, shownWhenTyped, filtered,
            value: q.value, after: document.querySelectorAll('.it').length,
            hiddenAgain: getComputedStyle(document.getElementById('qx')).display === 'none',
            wrapClass: w.className};
  }, target);
  check(clr.hiddenWhenEmpty, 'clear button is hidden while the search box is empty');
  check(clr.shownWhenTyped, 'clear button appears once something is typed');
  check(clr.value === '', 'clicking it empties the box', JSON.stringify(clr.value));
  check(clr.after > clr.filtered, 'clicking it restores the unfiltered list',
        clr.filtered + ' filtered -> ' + clr.after + ' shown');
  check(clr.hiddenAgain && clr.wrapClass === '', 'and the button hides itself again');

  await page.evaluate(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); });

  // 3b. Group folding: headers fold their own group, the button folds all,
  //     search overrides folding, and a concept reached while its group is
  //     folded unfolds it. Added 15.08.2026 with the feature — the sidebar
  //     had grown to 223 entries in one scroll. Items stay in the DOM when
  //     folded, so check 1 above stays a true statement; visibility is what
  //     this checks.
  const fold = await page.evaluate(async () => {
    const vis = () => [...document.querySelectorAll('.it')]
      .filter(e => e.offsetParent !== null).length;
    const q = document.getElementById('q'), ball = document.getElementById('ball');
    const r = {};
    r.open = vis();

    ball.click(); r.allFolded = vis();                    // fold every group
    r.label = ball.textContent;

    q.value = D[Object.keys(D)[0]].t.toLowerCase();       // search overrides folding
    q.dispatchEvent(new Event('input'));
    r.whileSearching = vis();
    r.ballDisabled = ball.disabled;
    q.value = ''; q.dispatchEvent(new Event('input'));
    r.refolded = vis();

    show(Object.keys(D)[0]);                              // reaching a concept unfolds it
    r.afterShow = vis();
    r.selVisible = !!document.querySelector('.it.on') &&
                   document.querySelector('.it.on').offsetParent !== null;

    ball.click();                                         // back to all open
    localStorage.removeItem('okf.collapsed');
    return r;
  });
  // Only a list that was showing can prove anything by folding to zero: a
  // hidden list also counts zero visible rows.
  check(fold.open > 0 && fold.allFolded === 0, 'collapse-all folds every group',
        fold.open + ' visible before, ' + fold.allFolded + ' after');
  check(fold.label === 'Expand all', 'the button names the action it will do', fold.label);
  check(fold.whileSearching >= 1, 'search overrides folding', fold.whileSearching + ' hits shown while folded');
  check(fold.ballDisabled === true, 'collapse-all is disabled while searching', String(fold.ballDisabled));
  // While the box holds a query it wears the accent border — same grammar as
  // every other control, where accent means active.
  const qBorder = await page.evaluate(() => {
    const q = document.getElementById('q');
    q.value = 'x'; q.dispatchEvent(new Event('input'));
    const b = getComputedStyle(q).borderTopColor;
    const acc = getComputedStyle(document.documentElement).getPropertyValue('--acc').trim();
    const probe = document.createElement('i'); probe.style.color = acc; document.body.appendChild(probe);
    const accRgb = getComputedStyle(probe).color; probe.remove();
    q.value = ''; q.dispatchEvent(new Event('input'));
    return { b, accRgb };
  });
  check(qBorder.b === qBorder.accRgb, 'search box wears the accent while it holds a query',
        qBorder.b + ' vs ' + qBorder.accRgb);
  check(fold.refolded === 0, 'clearing the search restores the folded state', fold.refolded + ' visible');
  check(fold.afterShow > 0 && fold.selVisible,
        'opening a concept unfolds its group and reveals the selection',
        fold.afterShow + ' items visible, selection shown: ' + fold.selVisible);

  // 4. The graph draws ink: non-background pixels on the canvas, legend
  //    chips present. Radius zero drew nothing and stayed clickable.
  await page.click('#bGraph');
  await page.waitForTimeout(1500);
  const graph = await page.evaluate(() => {
    const cv = document.querySelector('#gc canvas') || document.querySelector('#gc');
    const c = cv.getContext('2d');
    const bg = getComputedStyle(document.body).backgroundColor.match(/\d+/g).map(Number);
    const img = c.getImageData(0, 0, cv.width, cv.height).data;
    // Chroma, not ink: the radius-zero bug of 09.08.2026 still drew hundreds
    // of grey edges, so "any pixels differ from background" passes with no
    // node on screen. Nodes are the only saturated marks; count those.
    let ink = 0, chroma = 0;
    for (let i = 0; i < img.length; i += 40) {
      const r = img[i], g = img[i + 1], b = img[i + 2];
      if (Math.abs(r - bg[0]) + Math.abs(g - bg[1]) + Math.abs(b - bg[2]) > 30) {
        ink++;
        if (Math.max(r, g, b) - Math.min(r, g, b) > 40) chroma++;
      }
    }
    // One row per block in KB_BLOCKS, each carrying the categories that
    // block's own concepts occupy. Derived, not frozen: which shelves a bundle
    // uses is its owner's business and changes when a group is added or
    // retired. What the legend must never do is disagree with the data behind
    // it, so this compares the rendered rows against cat(), the generator's
    // own classifier - the same function that drew them.
    const rows = [...document.querySelectorAll('#legend .lrow')];
    const lbl = r => r ? [...r.querySelectorAll('.chip b')].map(b => b.textContent) : [];
    // A concept at a bundle root - questions.md - has no group directory and
    // is meta by construction, which is right: rows list shelves, and the
    // root is not one.
    const want = KB_BLOCKS.map(blk => {
      const ids = Object.keys(D).filter(id => blk.kbs.includes(id.split('/')[0]));
      return [...new Set(ids.map(id => LBL[cat(id)] || cat(id)))].sort();
    });
    return { ink, chroma, chips: document.querySelectorAll('#legend .chip').length,
             rows: rows.length, blocks: KB_BLOCKS.length,
             rowCats: rows.map(r => lbl(r).slice().sort()), wantCats: want,
             tags: document.querySelectorAll('#legend .lrow i').length };
  });
  // Threshold calibrated 10.08.2026 on this corpus: a healthy 211-node graph
  // sampled 3908 chromatic pixels; the radius-zero sabotage still left 241
  // one-pixel specks under stroke caps. 1000 sits between with margin.
  check(graph.chroma > 1000, 'graph draws saturated nodes, not just grey edges',
        graph.chroma + ' chromatic of ' + graph.ink + ' inked samples');
  // Every cluster clears every other cluster's halo. A halo reaches past its
  // cluster's extent, so clearing the extents is not enough: read the halos the
  // page actually draws, which are the ones the generator lays out against.
  const corners = await page.evaluate(() => {
    const ks = Object.keys(KBC).sort(), out = [];
    for (let i = 0; i < ks.length; i++) for (let j = i + 1; j < ks.length; j++)
      out.push([ks[i].replace('_kb', ''), ks[j].replace('_kb', ''),
        Math.round(Math.hypot(KBC[ks[i]].cx - KBC[ks[j]].cx, KBC[ks[i]].cy - KBC[ks[j]].cy) - KBC[ks[i]].halo - KBC[ks[j]].halo)]);
    return out;
  });
  check(corners.every(c => c[2] >= 0), 'every knowledge base stands clear of the others\' halos',
        corners.length ? 'halo gaps: ' + corners.map(c => c[0] + '~' + c[1] + ' ' + c[2]).join(', ')
                       : 'one knowledge base, nothing to separate');
  check(graph.chips >= 1, 'legend chips present', graph.chips + ' chips');
  check(graph.rows === graph.blocks, 'the legend draws one row per block',
        graph.rows + ' rows for ' + graph.blocks + ' block(s)');
  // The literal this replaced named one vault's shelves and went red the day a
  // group was retired, which was not a rendering fault. A check a legitimate
  // reshelving breaks is a change-detector, not a guard - so compare each row
  // against its own block's data instead of against a remembered list.
  check(graph.rowCats.every((r, i) => r.join(',') === (graph.wantCats[i] || []).join(',')),
        'each legend row carries exactly its block\'s own categories',
        graph.rowCats.map((r, i) => '[' + r.join(',') + '] vs [' +
                                    (graph.wantCats[i] || []).join(',') + ']').join('  '));

  // The accent bar alone names a block: a repeated text tag misaligned the
  // chip columns, and the owner removed it on 01.09.2026. Zero tags is the
  // assertion, so the label cannot quietly return.
  check(graph.tags === 0, 'legend rows carry no text tags, only accents', graph.tags + ' tags');

  // The KB selector groups the same way the legend does: one row per block,
  // holding that block's own bundles.
  const kbRows = await page.evaluate(() => ({
    rows: [...document.querySelectorAll('#kbbar .krow')].map(r => r.querySelectorAll('button').length),
    want: KB_BLOCKS.map(b => b.kbs.length)}));
  check(kbRows.rows.join('/') === kbRows.want.join('/'),
        'the kb selector shows one row per block',
        kbRows.rows.join('/') + ' against ' + kbRows.want.join('/'));
  // The concept tree reads the selector's order flat. Both come from
  // KB_BLOCKS now; this asserts the derivation actually reaches the tree.
  const order = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('#kbbar button')]
      .map(b => b.firstChild.textContent.trim());
    const seen = [], grps = [...document.querySelectorAll('#tree .grp')];
    for (const g of grps) {
      // strip the fold caret and the trailing count before comparing
      const kb = g.textContent.replace(/[\u25b8\u25be]/g, '').trim()
                  .split(' / ')[0].replace(/\s*\d+$/, '').trim();
      if (!seen.includes(kb)) seen.push(kb);
    }
    return { btn, tree: seen };
  });
  check(order.btn.join(',') === order.tree.join(','),
        'the concept tree follows the selector order',
        'buttons [' + order.btn.join(', ') + '] tree [' + order.tree.join(', ') + ']');

  // One accent hue per ontology block: the Settings buttons wear it as their
  // fill, the legend row as its accent bar — the pairing is what says they
  // are the same thing.
  const accents = await page.evaluate(() => ({
    kb: [...document.querySelectorAll('#kbbar .krow')].map(r =>
      getComputedStyle(r.querySelector('button')).backgroundColor),
    lg: [...document.querySelectorAll('#legend .lrow')].map(r => getComputedStyle(r).borderLeftColor)
  }));
  check(accents.kb.join('|') === accents.lg.join('|'),
        'settings button fills match the legend row accents',
        accents.kb.length + ' vs ' + accents.lg.length + ' rows');
  // Every block gets its own accent, however many blocks there are. Written
  // as a literal 3 until 06.09.2026, which asserted the block count twice
  // — the row-shape check above already does that — and would have passed
  // a fourth block sharing a hue with one of the three.
  check(new Set(accents.kb).size === accents.kb.length, 'block accents are distinct',
        [...new Set(accents.kb)].join(' '));

  // 5. Theme tokens reach the paint: body background equals --bg.
  const theme = await page.evaluate(() => {
    const want = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
    const probeEl = document.createElement('div');
    probeEl.style.color = want;
    document.body.appendChild(probeEl);
    const wantRgb = getComputedStyle(probeEl).color;
    probeEl.remove();
    return { got: getComputedStyle(document.body).backgroundColor, wantRgb };
  });
  check(theme.got === theme.wantRgb, 'body background equals --bg token',
        theme.got + ' vs ' + theme.wantRgb);

  // 6. The header and the About control. Placement is the assertion, not
  // existence: "a button exists somewhere on the page" would pass with it
  // anywhere, and j4k's own About shipped in the wrong place and sat there for
  // two commits. Owner's instruction of 14.09.2026: the logo on the left, the
  // categories to its right, and the view below. Until then this checked that
  // About sat at the top of the sidebar, above the info lines and the
  // knowledge-base selectors; the sidebar now holds the list and nothing else.
  const about = await page.evaluate(() => {
    const top = document.getElementById('top'), btn = document.getElementById('aboutBtn');
    const legend = document.getElementById('legend'), stage = document.getElementById('stage');
    if (!top || !btn || !legend || !stage) return { present: !!btn };
    const r = e => e.getBoundingClientRect();
    return {
      present: true,
      first: top.firstElementChild === btn,
      inHeader: top.contains(legend),
      leftOf: r(btn).right <= r(legend).left,
      above: r(top).bottom <= r(stage).top + 0.5,
      openBefore: document.getElementById('aboutWrap').classList.contains('on'),
    };
  });
  check(about.present, 'About button present');
  check(about.first && about.inHeader && about.leftOf && about.above,
        'the logo opens the header, the categories sit to its right, and the view sits below',
        'first=' + about.first + ' categories in header=' + about.inHeader +
        ' right of the logo=' + about.leftOf + ' header above the view=' + about.above);
  // The two lines the owner removed, because About already says them, and the
  // selector that moved into Settings. Asserted as the sidebar's whole content
  // rather than as two absences, so nothing else can move in unnoticed either.
  const sideNow = await page.evaluate(() => ({
    side: [...document.getElementById('side').children].map(e => e.id).join(','),
    top: [...document.getElementById('sidetop').children].map(e => e.id).filter(i => i !== 'qwrap').join(','),
    kbInSettings: !!document.querySelector('#setBox #kbbar'),
  }));
  check(sideNow.side === 'sidetop,tree' && sideNow.top === 'ball' && sideNow.kbInSettings,
        'the sidebar holds the search, Collapse all and the list, and the kb selector is in Settings',
        'sidebar [' + sideNow.side + '] controls [' + sideNow.top + '] selector in settings=' + sideNow.kbInSettings);
  check(about.openBefore === false, 'About starts closed');

  // The mark is the vault's graph, abstracted. Owner's instruction of
  // 14.09.2026: "make it like the abstracted graph. use the halo color of the
  // kb's in the graph as colors in the graph. indicate the connections somehow".
  // Its colours are read as painted, off the header before About covers it, by
  // hue angle rather than exact value: at 69px most of a cluster is glow, the
  // hue blended into the header's ground, which keeps the angle and loses the
  // value. The three angles are the page's own block hues.
  const blockHues = await page.evaluate(() => KB_BLOCKS.map(b => b.hue));
  const angle = ([r, g, b]) => {
    const mx = Math.max(r, g, b), c = mx - Math.min(r, g, b);
    if (c < 24) return null;
    const h = 60 * (mx === r ? ((g - b) / c + 6) % 6 : mx === g ? (b - r) / c + 2 : (r - g) / c + 4);
    return h;
  };
  const hexRgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const markBox = await page.evaluate(() => { const r = document.querySelector('#aboutBtn svg').getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); });
  const markPx = pngPixels(await page.screenshot({ clip: { x: markBox[0], y: markBox[1], width: markBox[2], height: markBox[3] } }));
  const inHue = blockHues.map(() => 0);
  for (let y = 0; y < markBox[3]; y++) for (let x = 0; x < markBox[2]; x++) {
    const a = angle(markPx(x, y));
    if (a === null) continue;
    blockHues.forEach((hue, i) => { const d = Math.abs(a - angle(hexRgb(hue))); if (Math.min(d, 360 - d) <= 12) inHue[i]++; });
  }
  check(inHue.every(n => n >= 4), 'the header mark shows the three halo colours of the graph',
        blockHues.map((h, i) => h + ' ' + inHue[i] + 'px').join(', ') + ' in ' + markBox[2] + 'x' + markBox[3]);

  await page.click('#aboutBtn');
  await page.waitForTimeout(200);
  const opened = await page.evaluate(() => {
    const box = document.getElementById('aboutBox');
    const rows = [...document.querySelectorAll('#aboutFacts > div')]
      .map(d => d.querySelector('dt').textContent + '=' + d.querySelector('dd').textContent);
    return {
      visible: document.getElementById('aboutWrap').classList.contains('on'),
      wide: box.getBoundingClientRect().width > 200,
      facts: rows,
      logo: !!document.querySelector('.aboutLogo svg'),
      // every number is derived at open time; an empty or zero total means the
      // panel is reading something other than the data the page is drawn from
      concepts: (rows.find(r => r.startsWith('Concepts=')) || ''),
    };
  });
  check(opened.visible && opened.wide, 'About opens and is drawn',
        'width>' + opened.wide);
  check(opened.facts.length >= 6, 'About lists its facts', opened.facts.length + ' rows');
  check(/Concepts=\d+ in \d+ bases/.test(opened.concepts),
        'About counts concepts from the page data', opened.concepts);
  check(opened.logo, 'About draws its logo');
  // Where the mark stands each knowledge base, and what it connects, compared
  // with the data the graph is drawn from. The mark this replaced carried a
  // comment saying the generator asserted it against the layout; no such
  // assertion was ever written, so the drawing and the claim were never compared.
  const mark = await page.evaluate(() => {
    const svg = document.querySelector('.aboutLogo svg'), off = [], ratios = [], colours = [];
    for (const kb of Object.keys(KBC)) {
      const h = svg.querySelector('circle[data-kb="' + kb + '"]');
      if (!h) { off.push(kb + ' missing'); continue; }
      if (Math.abs(+h.getAttribute('cx') - KBC[kb].cx) > 1 || Math.abs(+h.getAttribute('cy') - KBC[kb].cy) > 1)
        off.push(kb + ' at ' + h.getAttribute('cx') + ',' + h.getAttribute('cy'));
      ratios.push(+h.getAttribute('r') / KBC[kb].halo);
      const gid = ((h.getAttribute('fill') || '').match(/url\(#([^)]+)\)/) || [])[1];
      const grad = gid && document.getElementById(gid), stop = grad && grad.querySelector('stop');
      // computed, not attributes: a dot takes its fill from its group, and a colour
      // set anywhere between the two is what the reader sees
      const want = 'rgb(' + [1, 3, 5].map(i => parseInt(HUE[kb].slice(i, i + 2), 16)).join(', ') + ')';
      const dots = [...svg.querySelectorAll('g[data-kb="' + kb + '"] circle')].map(c => getComputedStyle(c).fill);
      if (!(stop && getComputedStyle(stop).stopColor === want && dots.length && dots.every(f => f === want)))
        colours.push(kb);
    }
    // An empty data-ids splits to one empty string, which then fails the
    // lookup below and reads as a broken hub rather than no hub at all.
    const hub = svg.querySelector('[data-ids]'),
      hubIds = hub ? hub.getAttribute('data-ids').split(' ').filter(Boolean) : [];
    const grp = id => hubIds.includes(id) ? '_centre' : D[id].kb, live = {};
    for (const [a, c] of Object.entries(D)) for (const b of c.out)
      if (D[b] && b !== a && grp(a) !== grp(b)) { const k = [grp(a), grp(b)].sort().join(' '); live[k] = (live[k] || 0) + 1; }
    const drawn = [...svg.querySelectorAll('g[data-link]')].map(g => ({ pair: g.getAttribute('data-link'), n: +g.getAttribute('data-n'), strands: g.querySelectorAll('path').length }))
      .sort((x, y) => x.n - y.n);
    const least = drawn.length ? drawn[0].n : Infinity;
    const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
    return { off, colours, spread: ratios.length ? Math.max(...ratios) / Math.min(...ratios) : 0,
      // No CENTRE concepts, no hub: correct for a vault whose bundles share
      // no subject. Where there IS a hub, every concept in it must sit in the
      // middle, which is the property worth asserting.
      hubOk: hubIds.every(id => D[id] && Math.hypot(D[id].x, D[id].y) < 100),
      hubN: hubIds.length,
      wrongN: drawn.filter(d => d.n <= 0 || d.n !== live[d.pair]).map(d => d.pair + ' ' + d.n + '/' + live[d.pair]),
      missing: Object.keys(live).filter(k => live[k] >= least && !drawn.some(d => d.pair === k)),
      monotone: drawn.every((d, i) => !i || d.strands >= drawn[i - 1].strands),
      bundles: drawn.map(d => d.pair.replace(/_kb/g, '') + ' ' + d.n + '/' + d.strands).join(', '),
      dupIds: [...new Set(ids.filter((v, i) => ids.indexOf(v) !== i))] };
  });
  check(mark.off.length === 0 && mark.colours.length === 0 && mark.spread > 0 && mark.spread < 1.01,
        'the mark stands each knowledge base where the graph does, sized as its halo, in its halo colour',
        (mark.off.join('; ') || 'placed') + ', halo ratio spread ' + mark.spread.toFixed(3) + (mark.colours.length ? ', wrong colour: ' + mark.colours.join(' ') : ''));
  // A vault whose bundles do not cite each other has no strands to draw, and
  // no hub unless CENTRE names something. That is a property of the corpus,
  // not a rendering fault, so the assertion is on what IS drawn being right.
  check(mark.hubOk && mark.wrongN.length === 0 && mark.missing.length === 0 && mark.monotone,
        mark.bundles ? 'the mark\'s strands are the vault\'s cross-links, the strongest drawn with the most strands'
                     : 'the mark draws no strands, and the vault has no cross-bundle links to draw',
        'hub=' + mark.hubOk + '; ' + (mark.bundles || 'no bundles') + (mark.wrongN.length ? '; wrong count ' + mark.wrongN.join(' ') : '') +
        (mark.missing.length ? '; not drawn ' + mark.missing.join(' ') : '') + '; monotone=' + mark.monotone);
  check(mark.dupIds.length === 0, 'no id appears twice on the page, the mark being drawn twice', mark.dupIds.slice(0, 5).join(' '));
  // The surprise is motion, and only in About: light runs out along the strands.
  // The header stays still, and so does About for a reader who asks for less
  // motion. Sampled twice, because an animation that never advances also reads
  // as present.
  const pulse = await page.evaluate(async () => {
    const p = document.querySelector('.aboutLogo .pulse path');
    const at = () => p ? getComputedStyle(p).strokeDashoffset : '';
    const t0 = at(); await new Promise(r => setTimeout(r, 700)); const t1 = at();
    return { about: document.querySelectorAll('.aboutLogo .pulse path').length, header: document.querySelectorAll('#aboutBtn .pulse path').length, moved: !!p && t0 !== t1, t0, t1 };
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const still = await page.evaluate(() => { const g = document.querySelector('.aboutLogo .pulse'); return g ? getComputedStyle(g).display : 'absent'; });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  // Same: no strands, nothing to pulse along. The header must still be still.
  check(mark.bundles ? (pulse.about > 0 && pulse.header === 0 && pulse.moved && still === 'none')
                     : (pulse.about === 0 && pulse.header === 0),
        mark.bundles ? 'About\'s mark pulses along its strands, the header\'s does not, and a request for less motion stills it'
                     : 'no strands, so nothing pulses in either mark',
        pulse.about + ' pulse strands in About, ' + pulse.header + ' in the header, offset ' + pulse.t0 + ' -> ' + pulse.t1 + ', reduced motion: ' + still);

  // The panel caps its own height, so anything added to it can push the actions
  // row behind a scroll. That happened on 29.08.2026: moving the labels onto the
  // viewer's .78em scale grew every one of them by a quarter and took the panel
  // past its 760px cap. Nothing in the generator complains — the page is valid
  // and the dialog scrolls — so it is only visible by measuring or by looking.
  const fits = await page.evaluate(() => {
    const box = document.getElementById('aboutBox');
    const acts = document.getElementById('aboutActions').getBoundingClientRect();
    return {
      scrolls: box.scrollHeight > box.clientHeight + 1,
      need: box.scrollHeight, have: Math.round(box.getBoundingClientRect().height),
      actionsVisible: acts.bottom <= box.getBoundingClientRect().bottom + 0.5,
    };
  });
  // The dialog's buttons are the header's family: their rest colour must equal
  // the view buttons' rest colour, or the grammar has quietly forked.
  const family = await page.evaluate(() => ({
    dialog: getComputedStyle(document.querySelector('#aboutActions button')).color,
    sidebar: getComputedStyle(document.querySelector('#views button:not(.on)')).color
  }));
  check(family.dialog === family.sidebar, 'About buttons rest in the header family colour',
        family.dialog + ' vs ' + family.sidebar);
  // A selected concept is the activated fold button: accent border, no fill.
  const selStyle = await page.evaluate(() => {
    const el = document.querySelector('.it');
    el.classList.add('on');
    const s = getComputedStyle(el);
    const probe = document.createElement('i');
    probe.style.color = getComputedStyle(document.documentElement).getPropertyValue('--acc').trim();
    document.body.appendChild(probe);
    const acc = getComputedStyle(probe).color; probe.remove();
    const out = { border: s.borderTopColor, bg: s.backgroundColor, acc };
    el.classList.remove('on');
    return out;
  });
  check(selStyle.border === selStyle.acc && selStyle.bg !== selStyle.acc,
        'a selected concept wears the accent border, not an accent fill',
        'border ' + selStyle.border + ', bg ' + selStyle.bg);
  check(!fits.scrolls && fits.actionsVisible, 'About fits without scrolling',
        fits.need + ' of ' + fits.have);

  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  const closed = await page.evaluate(() =>
    document.getElementById('aboutWrap').classList.contains('on'));
  check(closed === false, 'Escape closes About');

  // 7. Two full-screen views under one header, 14.09.2026. Full screen as a
  // mode of its own, added 09.09.2026, went with it: both views take the whole
  // window, so there is nothing left to switch into, and its checks went too.
  // What they guarded carries over: the view really filling the window, the
  // canvas backing store following its size, and a focused button not ringing
  // on Escape.
  await page.click('#bGraph');
  await page.waitForTimeout(300);
  const gv = await page.evaluate(() => {
    const box = id => document.getElementById(id).getBoundingClientRect().toJSON();
    return { gc: box('gc'), top: box('askbar'), side: box('side').width, main: box('main').width,
             win: innerWidth, winH: innerHeight, on: document.getElementById('bGraph').classList.contains('on'),
             searchIn: document.getElementById('qwrap').parentNode.id };
  });
  check(gv.on && gv.side === 0 && gv.main === 0 && gv.gc.left === 0 &&
        Math.abs(gv.gc.width - gv.win) < 1 && Math.abs(gv.gc.top - gv.top.bottom) < 1 &&
        Math.abs(gv.gc.bottom - gv.winH) < 1,
        'the Graph view takes the whole window below the search bar',
        'canvas at ' + Math.round(gv.gc.left) + ',' + Math.round(gv.gc.top) + ' size ' +
        Math.round(gv.gc.width) + 'x' + Math.round(gv.gc.height) + ' in ' + gv.win + 'x' + gv.winH +
        ', header ends ' + Math.round(gv.top.bottom) + ', sidebar ' + gv.side);
  check(gv.searchIn === 'askbar', 'the search box is the bar above the graph, not inside it', 'parent=' + gv.searchIn);

  await page.click('#bList');
  await page.waitForTimeout(300);
  const cvw = await page.evaluate(() => {
    const box = id => document.getElementById(id).getBoundingClientRect().toJSON();
    return { side: box('side'), main: box('main'), top: box('askbar'), gc: box('gc'),
             win: innerWidth, winH: innerHeight, on: document.getElementById('bList').classList.contains('on'),
             searchIn: document.getElementById('qwrap').parentNode.id };
  });
  check(cvw.on && cvw.gc.width === 0 && cvw.side.left === 0 && cvw.side.width > 0 &&
        cvw.main.left >= cvw.side.right && Math.abs(cvw.main.right - cvw.win) < 1 &&
        Math.abs(cvw.side.top - cvw.top.bottom) < 1 && Math.abs(cvw.side.bottom - cvw.winH) < 1,
        'the Concept view is the list on the left and the page on the right, below the search bar',
        'list ' + Math.round(cvw.side.left) + '-' + Math.round(cvw.side.right) + ', page ' +
        Math.round(cvw.main.left) + '-' + Math.round(cvw.main.right) + ' of ' + cvw.win + ', graph width ' + cvw.gc.width);
  check(cvw.searchIn === 'askbar', 'the search box is the same bar in the Concept view, never re-parented', 'parent=' + cvw.searchIn);
  // One search bar for both views, and since 16.09.2026 it spans the window and
  // never moves: the owner asked for the full width, and Ask Claude needs the
  // room. The checks this replaced guarded a box that lived inside each pane and
  // had to match the list's width through a splitter drag and a narrow window.
  // What carries over is the reason they existed — the box has to be the same
  // box, in the same place, whichever view is showing — and it is a stronger
  // statement now, because there is one element and nothing is re-parented.
  const barSpot = () => page.evaluate(() => {
    const q = document.getElementById('q').getBoundingClientRect();
    const b = document.getElementById('askbar').getBoundingClientRect();
    return { q: [q.left, q.top, q.width, q.height], b: [b.left, b.top, b.width, b.height],
      win: document.documentElement.clientWidth,
      header: document.getElementById('top').getBoundingClientRect().bottom,
      list: document.getElementById('side').getBoundingClientRect().width };
  });
  const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 0.5);
  const at = r => r.map(v => Math.round(v * 10) / 10).join(',');
  await page.click('#bList');
  await page.waitForTimeout(300);
  const cSpot = await barSpot();
  await page.click('#bGraph');
  await page.waitForTimeout(300);
  const gSpot = await barSpot();
  check(same(gSpot.q, cSpot.q) && same(gSpot.b, cSpot.b),
        'the search bar stands in exactly the same place in both views',
        'graph ' + at(gSpot.q) + ' concept ' + at(cSpot.q));
  check(Math.abs(gSpot.b[0]) < 0.5 && Math.abs(gSpot.b[2] - gSpot.win) < 0.5 &&
        Math.abs(gSpot.b[1] - gSpot.header) < 0.5,
        'and spans the window, directly under the header',
        'bar at ' + at(gSpot.b) + ' in ' + gSpot.win + ', header ends ' + Math.round(gSpot.header));
  // The list's width is the reader's to change, and the bar must no longer care.
  await page.click('#bList');
  await page.waitForTimeout(300);
  const grip = await page.evaluate(() => { const r = document.getElementById('splitter').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 300]; });
  await page.mouse.move(grip[0], grip[1]);
  await page.mouse.down();
  await page.mouse.move(560, grip[1], { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  const cWide = await barSpot();
  check(cWide.list > cSpot.list + 50 && same(cWide.b, cSpot.b),
        'a splitter drag widens the list and leaves the bar where it was',
        'list ' + cSpot.list + ' -> ' + cWide.list + '; bar ' + at(cWide.b));
  await page.mouse.move(563, grip[1]);
  await page.mouse.down();
  await page.mouse.move(cSpot.list, grip[1], { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(150);
  // A narrow window: the bar takes the window, whatever the list does.
  await page.setViewportSize({ width: 700, height: 900 });
  await page.waitForTimeout(250);
  const cNarrow = await barSpot();
  await page.click('#bGraph');
  await page.waitForTimeout(300);
  const gNarrow = await barSpot();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(250);
  await page.click('#bList');
  await page.waitForTimeout(300);
  check(Math.abs(cNarrow.b[2] - 700) < 0.5 && same(gNarrow.b, cNarrow.b),
        'and in a 700px window it is 700px wide in both views',
        'concept ' + at(cNarrow.b) + ' graph ' + at(gNarrow.b));
  // Collapse all was the search bar's second row until 16.09.2026, when the bar
  // went full width and left the sidebar; the button now stands alone above the
  // list. Two of the four measurements went with the arrangement they described
  // — its icon under the search icon, its label on the search text's left edge —
  // because neither is above the other any more. What the owner asked for that
  // still holds is kept: an icon at the left at the search icon's size, and the
  // search bar's type rather than a concept row's. The placeholder rule is read
  // as well as the colour, because the grey the page sets is Chromium's own
  // default and the colour alone would pass with the rule gone.
  const foldRow = () => page.evaluate(() => {
    const q = document.getElementById('q'), ball = document.getElementById('ball'), qs = getComputedStyle(q);
    const sIcon = document.querySelector('#mSearch svg'), si = sIcon.getBoundingClientRect();
    const bIcon = ball.querySelector('svg'), bi = bIcon ? bIcon.getBoundingClientRect() : null;
    const walk = document.createTreeWalker(ball, NodeFilter.SHOW_TEXT);
    let t = walk.nextNode(); while (t && !t.textContent.trim()) t = walk.nextNode();
    const range = document.createRange(); if (t) range.selectNodeContents(t);
    let rule = false;
    for (const sheet of document.styleSheets) for (const r of sheet.cssRules || []) if ((r.selectorText || '').includes('#q::placeholder')) rule = true;
    return { iconLeft: bi ? Math.round(bi.left - ball.getBoundingClientRect().left) : NaN,
      iconSize: bi ? bi.width + 'x' + bi.height : 'none', searchIconSize: si.width + 'x' + si.height,
      textDx: t ? range.getBoundingClientRect().left - (q.getBoundingClientRect().left + parseFloat(qs.borderLeftWidth) + parseFloat(qs.paddingLeft)) : NaN,
      size: getComputedStyle(ball).fontSize, qSize: qs.fontSize,
      colour: getComputedStyle(ball).color, placeholder: getComputedStyle(q, '::placeholder').color,
      iconColour: bIcon ? getComputedStyle(bIcon).color : 'none',
      rule, label: ball.textContent.trim(), svg: bIcon ? bIcon.innerHTML : '' };
  });
  const row1 = await foldRow();
  await page.click('#ball');
  await page.waitForTimeout(150);
  const row2 = await foldRow();
  await page.click('#ball');
  await page.waitForTimeout(150);
  await page.evaluate(() => localStorage.removeItem('okf.collapsed'));
  check(row1.iconLeft >= 6 && row1.iconLeft <= 12 && row1.iconSize === row1.searchIconSize,
        'Collapse all carries its icon at the left, the size of the search icon',
        'icon ' + row1.iconLeft + 'px in, ' + row1.iconSize + ' vs ' + row1.searchIconSize);
  check(row1.size === row1.qSize && row1.colour === row1.placeholder && row1.rule && row1.iconColour === row1.placeholder,
        'and it wears the search bar\'s type: the same size, and the placeholder\'s grey set by the page for both label and icon',
        row1.size + ' vs ' + row1.qSize + '; label ' + row1.colour + ' vs placeholder ' + row1.placeholder +
        ', placeholder rule=' + row1.rule + '; icon ' + row1.iconColour);
  // Either label may come first: the folding checks above leave every group shut.
  check([row1.label, row2.label].sort().join(' / ') === 'Collapse all / Expand all' && !!row1.svg && !!row2.svg && row1.svg !== row2.svg,
        'its icon changes with the action the button names',
        row1.label + ' -> ' + row2.label + ', icons ' + (row1.svg && row2.svg ? (row1.svg !== row2.svg ? 'differ' : 'identical') : 'missing'));
  // The list scrolls under its controls, not with them. The search box used to
  // sit in the list's own column and had to be pinned there; since 16.09.2026 it
  // is the bar above both panes, so the statement is stronger and simpler — the
  // list cannot take it anywhere, and Collapse all, which did stay behind, still
  // has to hold its place.
  const sticky = await page.evaluate(() => {
    const tree = document.getElementById('tree');
    tree.scrollTop = tree.scrollHeight;
    const q = document.getElementById('q').getBoundingClientRect();
    const ball = document.getElementById('ball').getBoundingClientRect();
    const s = document.getElementById('side').getBoundingClientRect();
    const out = { scrolled: tree.scrollTop > 0, top: Math.round(q.top),
      above: q.bottom <= s.top + 0.5, inTree: !!document.getElementById('tree').contains(document.getElementById('q')),
      ballShown: ball.top >= s.top - 0.5 && ball.bottom <= s.bottom };
    tree.scrollTop = 0;
    return out;
  });
  // A list shorter than its pane has nothing to scroll, which is a property of
  // the corpus. What must hold either way is that the bar sits above the list
  // rather than inside it, so it cannot be scrolled away.
  check(sticky.above && !sticky.inTree && sticky.ballShown,
        sticky.scrolled ? 'the list cannot scroll the search bar away, because the bar is above it'
                        : 'the search bar sits above the list (too few concepts here to scroll)',
        'list scrolled=' + sticky.scrolled + ', bar ends above the list=' + sticky.above +
        ', Collapse all in sight=' + sticky.ballShown);

  // Opening a concept from the graph card is the move between the two views.
  // Pick the best-linked concept that is NOT already at the top of the list:
  // the first version of this test picked one whose row was in sight anyway,
  // and "scrolled into sight" passed with the scrolling removed.
  await page.click('#bGraph');
  await page.waitForTimeout(300);
  const picked = await page.evaluate(() => {
    let i = N.map((n, k) => [k, D[n.id].inb.length]).sort((a, b) => b[1] - a[1])[0][0];
    const late = N.map((n, k) => k).filter(k => k > N.length / 2);
    if (late.length) i = late.sort((a, b) => D[N[b].id].inb.length - D[N[a].id].inb.length)[0];
    select(i);
    return N[i].id;
  });
  await page.waitForTimeout(150);
  await page.click('#gcard .open');
  await page.waitForTimeout(300);
  const landed = await page.evaluate(id => {
    const row = document.querySelector('.it.on');
    const t = document.getElementById('tree').getBoundingClientRect();
    const r = row ? row.getBoundingClientRect() : null;
    return { concepts: document.body.classList.contains('vc'),
             h1: (document.querySelector('#main h1') || {}).textContent, want: D[id].t,
             side: document.getElementById('side').getBoundingClientRect().width,
             rowShown: !!r && r.top >= t.top && r.bottom <= t.bottom };
  }, picked);
  check(landed.concepts && landed.h1 === landed.want && landed.side > 0,
        'Open concept on the graph card lands in the Concept view, list and page',
        'concept view=' + landed.concepts + ' page=' + landed.h1);
  check(landed.rowShown, 'and the concept\'s row is scrolled into sight in the list');
  await page.click('#main .gbtn');
  await page.waitForTimeout(300);
  const back = await page.evaluate(id => ({ graph: document.body.classList.contains('vg'), sel: sel === idx[id],
    card: getComputedStyle(document.getElementById('gcard')).display }), picked);
  check(back.graph && back.sel && back.card !== 'none', 'Show in graph returns to the Graph view with the concept selected',
        'graph view=' + back.graph + ' selected=' + back.sel + ' card=' + back.card);

  // Fit frames the graph inside the canvas. Until 16.09.2026 this checked that
  // nothing sat under the search box, which floated over the graph's top-left
  // corner where Gamma is; the box is the bar above the canvas now and covers
  // nothing. The claim that survives is the one that mattered — a concept whose
  // centre is off the canvas is a concept the reader cannot click — and it is
  // read from node centres rather than their marks, as it was before.
  await page.evaluate(() => { clearSel(); fit(); });
  await page.waitForTimeout(200);
  const under = await page.evaluate(() => {
    const g = gc.getBoundingClientRect();
    return N.filter(n => { if (hid(n)) return false; const [x, y] = sxy(n);
      return x < 0 || y < 0 || x > g.width || y > g.height; }).length;
  });
  check(under === 0, 'Fit frames every concept inside the canvas', under + ' concepts outside it');

  // A second click on the selected concept lets it go. Owner's request of
  // 14.09.2026. Real clicks on the canvas, not select() and clearSel(): the
  // toggle lives in the mouse handler, and a check that calls the functions
  // passes with it removed. Every click's result is read, so a click that
  // missed its concept fails at the first step instead of passing as a
  // deselect. Two concepts in the open, clear of the search box, the card and
  // Fit, and far enough apart that neither click can pick the other.
  const two = await page.evaluate(() => {
    const g = gc.getBoundingClientRect(), out = [];
    for (const n of N) {
      if (hid(n)) continue;
      const [x, y] = sxy(n), px = g.left + x, py = g.top + y;
      if (x < 40 || x > gc.clientWidth - 380 || y < 90 || y > gc.clientHeight - 90) continue;
      if (document.elementFromPoint(px, py) !== gc || pick(n.x, n.y) !== n.i) continue;
      if (out.length && Math.hypot(out[0].x - px, out[0].y - py) < 120) continue;
      out.push({ i: n.i, x: px, y: py });
      if (out.length === 2) break;
    }
    return out;
  });
  if (two.length < 2) check(false, 'two concepts in the open to click in the graph', two.length + ' found');
  else {
    const [a, b] = two, seen = [];
    for (const p of [a, b, b]) {
      await page.mouse.click(p.x, p.y);
      await page.waitForTimeout(150);
      seen.push(await page.evaluate(() => ({ sel, graph: document.body.classList.contains('vg'),
        card: getComputedStyle(document.getElementById('gcard')).display })));
    }
    const say = s => 'selected ' + s.sel + ', card ' + s.card + ', graph view ' + s.graph;
    check(seen[0].sel === a.i && seen[0].card !== 'none' && seen[1].sel === b.i && seen[1].card !== 'none',
          'a click selects a concept in the graph, and a click on another moves the selection',
          'wanted ' + a.i + ' then ' + b.i + ': ' + say(seen[0]) + '; ' + say(seen[1]));
    check(seen[2].sel === -1 && seen[2].card === 'none' && seen[2].graph,
          'a second click on the selected concept lets it go', say(seen[2]));
    // A double-click is two clicks and then the open, so its second click lets
    // go of what its first selected. The concept stays selected for the way
    // back to the graph, as it did before the toggle.
    await page.mouse.dblclick(a.x, a.y);
    await page.waitForTimeout(300);
    const dbl = await page.evaluate(i => ({ concepts: document.body.classList.contains('vc'),
      h1: (document.querySelector('#main h1') || {}).textContent, want: D[N[i].id].t, sel }), a.i);
    check(dbl.concepts && dbl.h1 === dbl.want && dbl.sel === a.i,
          'a double-click opens the concept and keeps it selected in the graph',
          'concept view=' + dbl.concepts + ' page=' + dbl.h1 + ' selected ' + dbl.sel + ' of ' + a.i);
    await page.click('#bGraph');
    await page.waitForTimeout(300);
    await page.evaluate(() => { clearSel(); fit(); });
  }

  // A window resized while the Concept view shows. The canvas is hidden then
  // and measures zero, so the resize handler gives it a zero backing store;
  // only the switch back can size it again. Measured on the backing store, not
  // clientWidth, for the reason of 09.09.2026: flex sizes the element whatever
  // the script does, so clientWidth passes with the resize call removed.
  await page.click('#bList');
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.waitForTimeout(250);
  await page.click('#bGraph');
  await page.waitForTimeout(300);
  const bs = await page.evaluate(() => ({ backing: gc.width, css: gc.clientWidth, dpr: window.devicePixelRatio || 1 }));
  check(bs.css === 1200 && Math.abs(bs.backing - bs.css * bs.dpr) < 2,
        'a window resized in the Concept view leaves the graph drawn at the new width',
        'backing ' + bs.backing + ' vs ' + Math.round(bs.css * bs.dpr) + ' at css ' + bs.css);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(250);

  // 8. Escape lets go of a button it would otherwise ring. The owner reported
  // it on 09.09.2026 against the full-screen button. The Fit button is the same
  // case now: clicked, still focused, and Escape is the first keystroke after.
  // A real click, not element.click() through evaluate: only a real one moves
  // focus to the button, and without focus there is no ring to catch.
  await page.click('#gfit');
  await page.waitForTimeout(150);
  const f1 = await page.evaluate(() => document.activeElement ? document.activeElement.id : '');
  check(f1 === 'gfit', 'clicking Fit focuses it (the ring precondition)', 'activeElement=' + (f1 || 'body'));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  const f2 = await page.evaluate(() => document.activeElement ? document.activeElement.id : '');
  check(f2 !== 'gfit', 'Escape in the graph leaves no focus ring on the button', 'activeElement=' + (f2 || 'body'));
  // Read the rule, not the computed style: a programmatic .focus() does not
  // set :focus-visible in Chromium, so getComputedStyle returned the default
  // outline colour (currentColor, the button's own text) and the check failed
  // while the page was correct. The claim being made is that the rule exists
  // and paints in the page's accent, so test that.
  const ring = await page.evaluate(() => {
    let outline = null;
    for (const sheet of document.styleSheets)
      for (const r of sheet.cssRules || [])
        if (r.selectorText === 'button:focus-visible') outline = r.style.outline;
    return outline;
  });
  check(!!ring && /var\(--acc\)/.test(ring),
        'a focused button wears the page accent, not the UA blue',
        ring || 'no button:focus-visible rule');
  // `f` frames the graph, but not while typing into the box that floats on it.
  await page.evaluate(() => { sc = 3; tx = 0; ty = 0; });
  await page.click('#q');
  await page.keyboard.type('f');
  const typed = await page.evaluate(() => ({ sc, value: document.getElementById('q').value }));
  check(typed.value === 'f' && typed.sc === 3, 'typing f into the search does not refit the graph',
        'value=' + JSON.stringify(typed.value) + ' scale=' + typed.sc);
  await page.evaluate(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); q.blur(); });

  // 9. Settings, 14.09.2026: j4k's Options menu in this viewer's frame, holding
  // the knowledge-base selector that left the sidebar.
  const kbAll = await page.evaluate(() => [...new Set(Object.values(D).map(c => c.kb))]);
  await page.click('#bSet');
  await page.waitForTimeout(200);
  const s1 = await page.evaluate(() => {
    const b = document.getElementById('setBox'), r = b.getBoundingClientRect();
    const gear = document.getElementById('bSet').getBoundingClientRect(), top = document.getElementById('top').getBoundingClientRect();
    return { shown: !b.hidden && r.width > 0 && r.height > 0, below: r.top >= top.bottom,
             edge: Math.abs(r.right - gear.right) < 40 && r.right <= innerWidth,
             on: document.getElementById('bSet').classList.contains('on'),
             buttons: b.querySelectorAll('#kbbar button').length };
  });
  check(s1.shown && s1.below && s1.edge && s1.on, 'the gear opens Settings under the header, at its right edge',
        'shown=' + s1.shown + ' below header=' + s1.below + ' at the gear=' + s1.edge + ' gear active=' + s1.on);
  check(s1.buttons === kbAll.length, 'Settings offers every knowledge base', s1.buttons + ' of ' + kbAll.length);

  // The bundle to hide is the last one by name, whichever that is, so the
  // test says nothing about which knowledge bases a vault holds.
  const victim = kbAll.slice().sort()[kbAll.length - 1];
  const before = await page.evaluate(v => ({ items: document.querySelectorAll('.it').length,
    rows: document.querySelectorAll('#legend .lrow').length,
    ked: Object.values(D).filter(c => c.kb === v).length }), victim);
  await page.locator('#kbbar button', { hasText: victim.replace(/_kb$/, '') }).click();
  await page.waitForTimeout(200);
  const hid1 = await page.evaluate(v => ({
    items: document.querySelectorAll('.it').length,
    kedRows: document.querySelectorAll('.it[data-t^="' + v + '/"]').length,
    kedNodes: N.filter(n => n.kb === v && !hid(n)).length,
    rows: document.querySelectorAll('#legend .lrow').length,
    dot: (document.querySelector('#bSet .dot') || {}).textContent || '',
    open: !document.getElementById('setBox').hidden,
    stored: localStorage.getItem('okf.kbOff') }), victim);
  check(hid1.kedRows === 0 && hid1.kedNodes === 0 && hid1.items === before.items - before.ked,
        'hiding a knowledge base in Settings takes it out of the list and the graph',
        before.items + ' -> ' + hid1.items + ' rows, ' + victim + ' rows ' + hid1.kedRows +
        ', nodes drawn ' + hid1.kedNodes);
  check(hid1.rows === before.rows - 1, 'the categories count only what is showing, and an empty row leaves',
        before.rows + ' -> ' + hid1.rows + ' category rows');
  check(hid1.dot === '1', 'the gear says how many knowledge bases are hidden', 'badge=' + JSON.stringify(hid1.dot));
  check(hid1.open, 'a click inside Settings keeps it open');
  await page.reload();
  await page.waitForTimeout(900);
  const kept = await page.evaluate(v => ({ ked: document.querySelectorAll('.it[data-t^="' + v + '/"]').length,
    items: document.querySelectorAll('.it').length, dot: (document.querySelector('#bSet .dot') || {}).textContent || '' }), victim);
  check(kept.ked === 0 && kept.items === hid1.items && kept.dot === '1', 'the choice is kept for the next visit',
        'stored ' + hid1.stored + ', after reload ' + kept.items + ' rows, badge ' + JSON.stringify(kept.dot));

  // The last knowledge base showing stays on: hiding it would leave both views
  // empty, which is the dead page a stored choice must never produce. Forced,
  // because Playwright will not click an aria-disabled button and a person can.
  const survivor = kbAll.slice().sort()[0];
  await page.evaluate(([all, s]) => localStorage.setItem('okf.kbOff', JSON.stringify(all.filter(k => k !== s))), [kbAll, survivor]);
  await page.reload();
  await page.waitForTimeout(900);
  await page.click('#bSet');
  await page.waitForTimeout(150);
  await page.locator('#kbbar button', { hasText: survivor.replace(/_kb$/, '') }).click({ force: true });
  await page.waitForTimeout(200);
  const lastOne = await page.evaluate(s => ({ items: document.querySelectorAll('.it').length,
    kept: document.querySelectorAll('.it[data-t^="' + s + '/"]').length }), survivor);
  check(lastOne.items > 0 && lastOne.items === lastOne.kept, 'the last knowledge base showing cannot be hidden',
        lastOne.items + ' rows, ' + lastOne.kept + ' of them ' + survivor);
  await page.mouse.click(700, 860);
  await page.waitForTimeout(150);
  const outside = await page.evaluate(() => document.getElementById('setBox').hidden);
  check(outside, 'a click outside closes Settings');
  await page.click('#bSet');
  await page.waitForTimeout(150);
  const g1 = await page.evaluate(() => document.activeElement ? document.activeElement.id : '');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  const g2 = await page.evaluate(() => ({ hidden: document.getElementById('setBox').hidden,
    focused: document.activeElement ? document.activeElement.id : '' }));
  check(g1 === 'bSet' && g2.hidden && g2.focused !== 'bSet', 'Escape closes Settings and leaves no ring on the gear',
        'focused before=' + (g1 || 'body') + ' closed=' + g2.hidden + ' focused after=' + (g2.focused || 'body'));
  await page.evaluate(() => localStorage.removeItem('okf.kbOff'));
  await page.reload();
  await page.waitForTimeout(900);

  // 10. The header sits over both views, so what it filters, it filters in
  // both. Until 14.09.2026 the categories filtered only the graph, which was
  // right while they sat inside it.
  await page.click('#bList');
  await page.waitForTimeout(200);
  const catF = await page.evaluate(() => {
    const chipFor = name => [...document.querySelectorAll('#legend .chip')].find(c => c.querySelector('b').textContent === name);
    const rows = () => [...document.querySelectorAll('.it')];
    const r = { before: rows().length, people: rows().filter(e => cat(e.dataset.t) === 'people').length };
    chipFor('people').click();
    r.after = rows().length;
    r.peopleAfter = rows().filter(e => cat(e.dataset.t) === 'people').length;
    r.drawn = N.filter(n => cat(n.id) === 'people' && !hid(n)).length;
    chipFor('people').click();
    r.restored = rows().length;
    return r;
  });
  check(catF.people > 0 && catF.peopleAfter === 0 && catF.after === catF.before - catF.people &&
        catF.drawn === 0 && catF.restored === catF.before,
        'a category switched off in the header leaves the list as well as the graph',
        catF.before + ' rows, ' + catF.people + ' people -> ' + catF.after + ', drawn ' + catF.drawn + ', back to ' + catF.restored);

  // 11. A stored state must not reopen as a dead page. Caught by the owner on
  // 14.09.2026: the viewer "is not working under chrome" while Safari showed it
  // The search bar, the two modes and the reports window. Added 16.09.2026,
  // when the bar went full width and gained Ask Claude. The page is one file
  // opened from disk and the helper that answers a question is started by
  // hand, so the state these checks care about most is the helper being OFF:
  // that is how the page is opened nearly always, and the bar has to be the
  // search box it has always been, with the two new buttons saying plainly
  // that they cannot work rather than failing when pressed.
  const bar = await page.evaluate(() => {
    const b = document.getElementById('askbar');
    const r = b && b.getBoundingClientRect();
    return {
      w: r ? Math.round(r.width) : 0,
      page: Math.round(document.documentElement.clientWidth),
      left: r ? Math.round(r.left) : -1,
      search: !!document.getElementById('mSearch'),
      ask: !!document.getElementById('mAsk'),
      reports: !!document.getElementById('bRep'),
      searchOn: document.getElementById('mSearch').classList.contains('on'),
      askOn: document.getElementById('mAsk').classList.contains('on')
    };
  });
  check(bar.w === bar.page && bar.left === 0, 'the search bar spans the window',
        bar.w + ' of ' + bar.page + ', left ' + bar.left);
  check(bar.search && bar.ask && bar.reports && bar.searchOn && !bar.askOn,
        'the bar carries both modes, and opens in search',
        'search=' + bar.search + ' ask=' + bar.ask + ' reports=' + bar.reports +
        ' searchOn=' + bar.searchOn);

  // The progress bar fills the search box. It was a 2px line under the bar
  // until 16.09.2026, and the owner read that as a hairline rather than a bar;
  // it now sits in the input's own grid cell, behind the placeholder that says
  // what the librarian is doing. Both halves of that are measured, because both
  // can regress silently: a CSS change that takes the fill out of the cell
  // leaves it somewhere plausible-looking, and one that restores a fixed height
  // leaves it a line again. It is driven directly rather than by asking a
  // question — a real run costs money and minutes, and the geometry is the same.
  const qbarBox = () => page.evaluate(() => {
    const el = document.getElementById('qbar'),
      r = el.getBoundingClientRect(), f = el.firstElementChild.getBoundingClientRect(),
      i = document.getElementById('q').getBoundingClientRect();
    return { bar: [r.left, r.top, r.right, r.bottom, r.height],
             q: [i.left, i.top, i.right, i.bottom, i.height], fill: f.width };
  });
  await page.evaluate(() => bar(true));
  await page.waitForTimeout(600);          // the fill eases over .45s
  const qbZero = await qbarBox();
  await page.evaluate(() => { bar(); bar(); });
  await page.waitForTimeout(600);
  const qbTwo = await qbarBox();
  await page.evaluate(() => { const el = document.getElementById('qbar');
    el.hidden = true; el.classList.remove('done');
    el.firstElementChild.style.width = '0%'; });
  const prog = { zero: qbZero, two: qbTwo };
  const z = prog.zero;
  const inside = z.bar[0] >= z.q[0] - 0.5 && z.bar[1] >= z.q[1] - 0.5 &&
                 z.bar[2] <= z.q[2] + 0.5 && z.bar[3] <= z.q[3] + 0.5;
  check(inside, 'the progress bar sits inside the search box',
        'bar ' + z.bar.slice(0, 4).map(Math.round).join(',') +
        ' in box ' + z.q.slice(0, 4).map(Math.round).join(','));
  check(z.bar[4] >= 12 && z.bar[4] >= z.q[4] * 0.6,
        'and is a bar rather than a line: it takes the box\'s height',
        Math.round(z.bar[4]) + 'px of the box\'s ' + Math.round(z.q[4]) + 'px');
  check(z.fill < 1 && prog.two.fill > z.fill + 10 &&
        prog.two.fill <= prog.two.bar[2] - prog.two.bar[0] + 0.5,
        'and the fill grows with each milestone, never past the box',
        Math.round(z.fill) + 'px -> ' + Math.round(prog.two.fill) + 'px of ' +
        Math.round(prog.two.bar[2] - prog.two.bar[0]) + 'px');

  // Is the helper there? Everything after this branches on the answer, because
  // a check that needs a server started by hand is a check that fails for the
  // wrong reason on every other machine.
  const helper = await page.evaluate(async () => {
    try { const r = await fetch('http://127.0.0.1:8760/health', {cache: 'no-store'});
          return r.ok ? await r.json() : null; } catch (e) { return null; }
  });

  if (!helper) {
    const off = await page.evaluate(() => ({
      ask: document.getElementById('mAsk').disabled,
      rep: document.getElementById('bRep').disabled,
      title: document.getElementById('mAsk').title
    }));
    check(off.ask && off.rep && /Open 00_Cerebrum\.command/.test(off.title),
          'with no helper running, Ask and Reports are off and name the launcher',
          'ask=' + off.ask + ' reports=' + off.rep + ' title="' + off.title + '"');
    await page.click('#mAsk', {force: true});
    await page.waitForTimeout(250);
    const stayed = await page.evaluate(() =>
      document.getElementById('mSearch').classList.contains('on')
      && !document.getElementById('askbar').classList.contains('ask'));
    check(stayed, 'and pressing Ask leaves the bar in search mode');
  } else {
    await page.click('#mAsk');
    await page.waitForTimeout(250);
    const on = await page.evaluate(() => ({
      askOn: document.getElementById('mAsk').classList.contains('on'),
      barAsk: document.getElementById('askbar').classList.contains('ask'),
      ph: document.getElementById('q').placeholder
    }));
    check(on.askOn && on.barAsk && /Ask Claude/.test(on.ph),
          'the helper is running, so Ask mode switches the bar',
          'askOn=' + on.askOn + ' placeholder="' + on.ph + '"');
    await page.click('#bRep');
    await page.waitForTimeout(700);
    const rep = await page.evaluate(() => ({
      open: document.getElementById('repWrap').classList.contains('on'),
      rows: document.querySelectorAll('#repList .rr').length,
      groups: document.querySelectorAll('#repList .rgrp').length,
      first: (document.querySelector('#repList .rr') || {}).dataset ?
        document.querySelector('#repList .rr').dataset.p : null
    }));
    // Only the question reports: the audits are in Outputs/HealthChecks/ and
    // are not listed, on the owner's instruction of 16.09.2026.
    const want = await page.evaluate(async () =>
      ((await (await fetch('http://127.0.0.1:8760/reports', {cache: 'no-store'})).json()).reports || [])
        .filter(r => !r.audit).length);
    check(rep.open && rep.rows === want && want < helper.reports,
          'the reports window lists the question reports and not the health checks',
          rep.rows + ' row(s) against ' + want + ' question report(s), ' + helper.reports + ' in the register');
    check(!!rep.first && /\.md$/.test(rep.first),
          'and a row carries the report it opens', String(rep.first));
    // The date and the knowledge base share the first line, and the question
    // is under them. Owner's instruction of 16.09.2026: they were a line each,
    // which spent a line per row on two short strings. Measured rather than
    // read off the stylesheet, because a wrapping rule or a display change
    // puts them back on two lines without touching the rule that says so.
    const shape = await page.evaluate(() => {
      const rr = document.querySelector('#repList .rr');
      if (!rr) return null;
      const g = c => { const e = rr.querySelector('.' + c);
        return e ? e.getBoundingClientRect() : null; };
      const d = g('rd'), sc = g('rs'), q = g('rq'), row = rr.getBoundingClientRect();
      return d && sc && q ? { dTop: d.top, sTop: sc.top, qTop: q.top,
        dBottom: d.bottom, height: row.height } : null;
    });
    check(!!shape && Math.abs(shape.dTop - shape.sTop) < 2 &&
          shape.qTop >= shape.dBottom - 2,
          'a row puts the knowledge base beside the date, with the question under both',
          shape ? 'date top ' + Math.round(shape.dTop) + ', scope top ' +
            Math.round(shape.sTop) + ', question top ' + Math.round(shape.qTop) +
            ', row ' + Math.round(shape.height) + 'px' : 'no row');
    await page.keyboard.press('Escape');
    await page.click('#mSearch');
    await page.waitForTimeout(200);

    // Settings › Brain. Added 16.09.2026 on the owner's instruction, shaped
    // after the Brain tab of his own GLaDOS: the model first, then what it
    // costs to run, then one line saying what leaves this Mac. Every check
    // below reads the rendered control rather than the stylesheet, because
    // each of these can regress while the rule that sets it still reads right.
    await page.click('#bSet');
    await page.waitForTimeout(900);
    const brain = await page.evaluate(() => {
      const g = id => document.getElementById(id);
      const opts = [...g('bModel').options];
      return {
        models: opts.length,
        locals: opts.filter(o => o.value.startsWith('local:')).length,
        picked: g('bModel').value,
        efforts: [...g('bEffort').options].map(o => o.value).join(','),
        effortDisabled: g('bEffort').disabled,
        where: g('brainWhere').textContent.trim(),
        badge: g('brainN').textContent.trim(),
        rows: document.querySelectorAll('#bWeights .wr').length
      };
    });
    check(brain.models >= 5 && brain.locals === 3 &&
          brain.efforts === 'low,medium,high,xhigh,max' &&
          brain.picked.startsWith('claude-') && !brain.effortDisabled,
          'Settings carries a Brain with every model and every effort level',
          brain.models + ' model(s), ' + brain.locals + ' local; efforts ' +
          brain.efforts + '; picked ' + brain.picked);
    check(brain.rows === 3 && !!brain.badge && /Anthropic/.test(brain.where),
          'and a weights row per local model, with the badge and the where-line',
          brain.rows + ' row(s), badge "' + brain.badge + '", "' +
          brain.where.slice(0, 60) + '…"');

    // **Proving this one by removing the confirmation deletes the model.** Done
    // on 16.09.2026 and it cost seventeen gigabytes of Qwen weights and the
    // download again: with the `arm` branch switched off, the first press is
    // the real delete. The check below is safe — it presses once and expects
    // nothing to happen — but a defect proof against it must use a throwaway
    // model folder, never an installed one. The same argument is why the
    // confirmation exists.
    //
    // Delete asks before it acts, and the question names what saying yes costs.
    // GLaDOS puts the way out before the action rather than during it, because
    // the delete takes an instant and the undo is the whole download. Measured
    // as two presses: the first must not delete, and must say the price.
    const del = await page.evaluate(async () => {
      const b = document.querySelector('#bWeights .wr .del');
      if (!b) return {skip: 'no installed local model on this Mac'};
      const r = b.closest('.wr');
      const before = r.querySelector('.ws').textContent;
      b.click();
      await new Promise(x => setTimeout(x, 300));
      return {armed: r.classList.contains('arm'),
              label: b.textContent.trim(),
              said: r.querySelector('.ws').textContent.trim(),
              before: before.trim()};
    });
    if (del.skip) {
      check(true, 'the Delete confirmation is not checked here', del.skip);
    } else {
      check(del.armed && /really/i.test(del.label) &&
            /Frees .*GB/.test(del.said) && /Getting it back/.test(del.said) &&
            del.said !== del.before,
            'Delete asks first, and the question names what saying yes costs',
            'button "' + del.label + '", row says "' + del.said + '"');
    }
    await page.evaluate(() => loadBrain());
    await page.waitForTimeout(700);

    // The disk figure must be the one Finder shows, not `statvfs`. On this Mac
    // they differ by more than a hundred gigabytes, because APFS counts local
    // Time Machine snapshots as purgeable and deletes them when a write needs
    // the room. The owner caught the wrong one on 16.09.2026: the window said
    // 26 GB free and refused a download his Mac had 158 GB for. Checked against
    // `statvfs` read in the browser's own process, so a regression to the small
    // number fails here rather than being reported as a shortage.
    const disk = await page.evaluate(async () => {
      const d = await (await fetch('http://127.0.0.1:8760/models',
                                   {cache: 'no-store'})).json();
      return {free: d.free,
              // The hint moved out of #bWeights into #brainDisk when the rows
              // were rebuilt on 16.09.2026, and this selector went on pointing
              // at the old place: the check crashed on null, and a grep on
              // "viewer-check:" hid the crash line, which reads "crashed" with
              // no colon. Read the tail unfiltered, always.
              hint: document.getElementById('brainDisk').textContent};
    });
    // Written once as `free >= statvfs`, which passed the very regression it
    // was for, because the wrong number equals statvfs exactly. It now asks
    // the question that separates them: when the volume is holding purgeable
    // snapshots, the reported figure must be larger than statvfs. On a Mac
    // with no snapshots the two agree honestly, so that case only requires
    // they match.
    //
    // The margin was `statvfs * 1.5` until 20.09.2026, and that failed on a
    // correct viewer. The factor was fitted to the day it was written, when
    // 24 snapshots put 158 GB against 26.7. With 21 smaller snapshots the
    // honest figures were 127 GB against 97, a ratio of 1.3, and the check
    // called a right answer wrong. How much purgeable data a volume happens
    // to hold is not something the viewer controls, so it cannot be the
    // threshold. Strictly greater is the whole question: the regression this
    // guards against reports statvfs exactly.
    const sh = require('child_process');
    const statvfs = sh.execSync("df -k '" + process.cwd() +
      "' | tail -1 | awk '{print $4}'").toString().trim() * 1024;
    let snaps = 0;
    try { snaps = sh.execSync('tmutil listlocalsnapshots / 2>/dev/null | grep -c com.apple || true')
      .toString().trim() * 1; } catch (e) { snaps = 0; }
    const bigger = snaps > 0 ? disk.free > statvfs : disk.free >= statvfs * 0.95;
    check(bigger && /free on disk/.test(disk.hint) &&
          /only one is in memory/.test(disk.hint),
          'the weights hint reports the space macOS would actually give, and says it is disk',
          Math.round(disk.free / 1e9) + ' GB reported against df\'s ' +
          Math.round(statvfs / 1e9) + ' GB, with ' + snaps + ' purgeable ' +
          'snapshot(s); hint "' + disk.hint.slice(0, 60) + '…"');

    // Haiku takes no effort level at all — the API rejects the flag — so the
    // row greys rather than staying live and sending something that fails.
    const haiku = await page.evaluate(async () => {
      const m = document.getElementById('bModel');
      m.value = 'claude-haiku-4-5';
      m.dispatchEvent(new Event('change'));
      await new Promise(r => setTimeout(r, 700));
      return {disabled: document.getElementById('bEffort').disabled,
              title: document.getElementById('bEffort').title};
    });
    check(haiku.disabled && /no effort/i.test(haiku.title),
          'picking Haiku greys the effort level, which it does not take',
          'disabled=' + haiku.disabled + ' title="' + haiku.title + '"');

    // The one thing this window must say out loud: a local model is a
    // completion and Ask Claude is an agent. Picking one here means the Ask
    // button will refuse rather than run and produce nothing.
    const localPick = await page.evaluate(async () => {
      const m = document.getElementById('bModel');
      const opt = [...m.options].find(o => o.value.startsWith('local:'));
      opt.disabled = false;                  // installed or not, the line is the same
      m.value = opt.value;
      m.dispatchEvent(new Event('change'));
      await new Promise(r => setTimeout(r, 700));
      return {where: document.getElementById('brainWhere').textContent.trim(),
              sent: JSON.stringify(brainBody())};
    });
    // The wording was shortened on the owner's instruction on 16.09.2026 and
    // the first cut dropped the Ask clause entirely; this check caught it. The
    // two facts the line must state are what is matched, not the old phrasing.
    check(/Nothing leaves/i.test(localPick.where) &&
          /Ask needs/i.test(localPick.where) &&
          localPick.sent.includes('local:'),
          'a local model says nothing leaves the Mac, and that Ask needs another',
          '"' + localPick.where.slice(0, 90) + '…"; request body ' + localPick.sent);

    // The choice has to survive a reload, or it is a control the reader sets
    // once per visit. Back to the default afterwards, so no later check runs
    // against a brain this one happened to leave selected.
    await page.evaluate(() => {
      const m = document.getElementById('bModel');
      m.value = 'claude-sonnet-5'; m.dispatchEvent(new Event('change'));
    });
    await page.waitForTimeout(400);
    await page.reload();
    await page.waitForTimeout(3000);
    const kept = await page.evaluate(() => ({
      stored: localStorage.getItem('okf.model'),
      sent: JSON.stringify(brainBody())
    }));
    check(kept.stored === 'claude-sonnet-5' && kept.sent.includes('claude-sonnet-5'),
          'and the chosen brain survives a reload and rides on the next question',
          'stored ' + kept.stored + ', body ' + kept.sent);
    await page.evaluate(() => { localStorage.removeItem('okf.model');
      localStorage.removeItem('okf.effort'); });

    // A report that carries figures shows them. `inline()` escapes every line
    // it renders, which is right for prose and turned three hand-authored SVGs
    // into a wall of markup — reported by the owner on 16.09.2026, who could
    // see them in Obsidian and not in the viewer. Measured as drawn boxes, not
    // as tags present: an <svg> with no viewBox honoured lays out at zero and
    // an escaped one is not an element at all.
    const FIGREP = '2026-09-02_two-loops-of-self-learning.md';
    const fig = await page.evaluate(async (rel) => {
      const r = await fetch('http://127.0.0.1:8760/report/' + rel,
                            {cache: 'no-store'});
      if (!r.ok) return {status: r.status};
      const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:-9999px;top:0;width:900px';
      host.innerHTML = doc.body.innerHTML;
      document.body.appendChild(host);
      const svgs = [...host.querySelectorAll('figure.fig svg')]
        .map(e => Math.round(e.getBoundingClientRect().width) + 'x' +
                  Math.round(e.getBoundingClientRect().height));
      const out = {status: 200, svgs,
        escaped: /&lt;svg|＜svg/.test(host.innerHTML) ||
                 host.textContent.includes('<svg'),
        scripts: host.querySelectorAll('figure.fig script').length};
      host.remove();
      return out;
    }, FIGREP);
    check(fig.status === 200 && fig.svgs && fig.svgs.length === 3 &&
          fig.svgs.every(d => { const [w, h] = d.split('x').map(Number);
            return w > 200 && h > 100; }) && !fig.escaped && !fig.scripts,
          'a report\'s inline figures are drawn, not escaped into markup',
          fig.status !== 200 ? 'the helper answered ' + fig.status
            : (fig.svgs || []).join(', ') + '; escaped=' + fig.escaped +
              ' scripts=' + fig.scripts);
  }

  // Whatever the helper was doing, the box must still be the search box.
  // The term comes from the data, not from a remembered corpus: the first
  // version typed one vault's product name and went red on every other vault.
  const term = await page.evaluate(() => {
    // From a concept's own filename, which every vault has and which the
    // search matches through the title. Longest wins, so it is the least
    // likely to appear in every other concept too.
    const w = Object.keys(D).map(id => id.split('/').pop().replace(/\.md$/, ''))
      .flatMap(s => s.split('-')).filter(s => s.length > 4)
      .sort((a, b) => b.length - a.length);
    return (w[0] || 'the').toLowerCase();
  });
  await page.fill('#q', term);
  await page.waitForTimeout(350);
  const hits = await page.evaluate(() => document.querySelectorAll('#tree .it').length);
  await page.fill('#q', '');
  await page.waitForTimeout(350);
  const restored = await page.evaluate(() => document.querySelectorAll('#tree .it').length);
  const total = await page.evaluate(() => Object.keys(D).length);
  // hits < restored only where the term does not match every concept, which a
  // two-concept demo cannot promise. What must hold is that it filters to
  // something and that clearing it restores everything.
  check(hits > 0 && hits <= restored && restored === total,
        'the bar still searches, and clearing it brings the list back (\'' + term + '\')',
        hits + ' hit(s), ' + restored + ' rows after clearing');

  // fine. Chrome keeps one localStorage for every file:// page, so full screen
  // left on in an earlier viewer came back on the next load and opened the page
  // with its only exit hidden. Every check above starts from an empty store, so
  // none of them could see that. The page has one stored setting now, which
  // knowledge bases show, and the old flag may still sit in the store. Load the
  // page over the worst of each and require a working page.
  for (const [label, value] of [
    ['a store hiding every knowledge base, and one that no longer exists', JSON.stringify(kbAll.concat(['Gone_kb']))],
    ['a store holding something that is not JSON', '{not json'],
  ]) {
    await page.evaluate(v => { localStorage.setItem('okf.fs', '1'); localStorage.setItem('okf.kbOff', v); }, value);
    await page.reload();
    await page.waitForTimeout(900);
    const st = await page.evaluate(() => {
      const seen = id => { const r = document.getElementById(id).getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      return { header: seen('top'), gear: seen('bSet'), views: seen('bGraph') && seen('bList'), graph: seen('gc'),
               rows: document.querySelectorAll('.it').length, all: Object.keys(D).length,
               fs: localStorage.getItem('okf.fs') };
    });
    check(jsErrors.length === 0 && st.header && st.gear && st.views && st.graph && st.rows === st.all,
          'reopens as a working page over ' + label,
          'errors=' + jsErrors.length + ' header=' + st.header + ' gear=' + st.gear + ' graph=' + st.graph +
          ' rows ' + st.rows + ' of ' + st.all);
    check(st.fs === null, 'and the retired full-screen flag is cleared from the store', 'okf.fs=' + st.fs);
  }
  await page.evaluate(() => localStorage.removeItem('okf.kbOff'));

  await browser.close();
  console.log(failures ? 'viewer-check: ' + failures + ' FAILURE(S)' : 'viewer-check: green');
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error('viewer-check crashed: ' + e.message); process.exit(1); });
