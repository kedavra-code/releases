#!/usr/bin/env node
/* Rendered-output audit for okf-viewer.html — the verify.py of the pixels.
 *
 * Every viewer defect so far was caught by the owner, not by any check:
 * the radius-zero graph, the unclickable zoom, the &amp; in node labels,
 * the mid-screen scrollbar. The generator ran clean each time; the rendered
 * page was the thing that was wrong. This script is the render-and-look
 * habit made executable, so it survives the session that learned it.
 *
 * Usage:  node _scripts/viewer-check.js [path/to/okf-viewer.html]
 * Runs wherever node + playwright exist (librarian sessions). Exit 1 on any
 * failure. The delivery rule in 00_Cerebrum/CLAUDE.md: no viewer delivery
 * without this green — and it replaces none of the eyeballing, because it
 * checks what is listed here and nothing else.
 */
const path = require('path');
const { chromium } = require('playwright');

const FILE = path.resolve(process.argv[2] || path.join(__dirname, '..', 'okf-viewer.html'));
let failures = 0;
const check = (ok, label, detail) => {
  console.log((ok ? 'ok      ' : 'FAIL    ') + label + (detail ? '  [' + detail + ']' : ''));
  if (!ok) failures++;
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
  }));
  check(jsErrors.length === 0, 'no JS errors on load', jsErrors[0]);
  check(boot.concepts > 0, 'concept data present', boot.concepts + ' concepts');
  check(boot.items === boot.concepts, 'sidebar lists every concept',
        boot.items + ' of ' + boot.concepts);

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
  check(fold.allFolded === 0, 'collapse-all folds every group', fold.allFolded + ' items still visible');
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
  await page.evaluate(() => document.querySelectorAll('#views button')[1].click());
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
    // The legend draws one row per KB_BLOCKS entry. What is checked here is
    // structural — that rows and chips exist at all, and that the chips carry
    // real category labels — because the block arrangement is the vault's own
    // to choose. Assert your own row shape here once you have one.
    const rows = [...document.querySelectorAll('#legend .lrow')];
    const lbl = r => r ? [...r.querySelectorAll('.chip b')].map(b => b.textContent) : [];
    return { ink, chroma, chips: document.querySelectorAll('#legend .chip').length,
             rows: rows.length, firstRow: lbl(rows[0]),
             tags: document.querySelectorAll('#legend .lrow i').length };
  });
  // Threshold calibrated 10.08.2026 on this corpus: a healthy 211-node graph
  // sampled 3908 chromatic pixels; the radius-zero sabotage still left 241
  // one-pixel specks under stroke caps. 1000 sits between with margin.
  check(graph.chroma > 1000, 'graph draws saturated nodes, not just grey edges',
        graph.chroma + ' chromatic of ' + graph.ink + ' inked samples');
  // One chip per category actually present. A bundle small enough to use
  // only two groups still gets two; raise this once your corpus has a
  // category count worth asserting.
  check(graph.chips >= 1, 'legend chips present', graph.chips + ' chips');
  check(graph.rows >= 1, 'legend draws at least one category row', graph.rows + ' rows');
  check(graph.firstRow.length > 0, 'legend row carries labelled category chips',
        graph.firstRow.join(',') || 'none');
  // The accent bar alone names a block: a repeated text tag misaligned the
  // chip columns, and the owner removed it on 01.09.2026. Zero tags is the
  // assertion, so the label cannot quietly return.
  check(graph.tags === 0, 'legend rows carry no text tags, only accents', graph.tags + ' tags');

  // The KB selector draws one row per block. Structural check only: every
  // knowledge base with concepts must get a button somewhere in the bar.
  const kbRows = await page.evaluate(() =>
    [...document.querySelectorAll('#kbbar .krow')].map(r => r.querySelectorAll('button').length));
  check(kbRows.reduce((a, b) => a + b, 0) >= 1, 'kb selector shows a button per knowledge base',
        kbRows.join('/') || 'none');
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

  // One accent hue per ontology block: the sidebar buttons wear it as their
  // fill, the legend row as its accent bar — the pairing is what says they
  // are the same thing.
  const accents = await page.evaluate(() => ({
    kb: [...document.querySelectorAll('#kbbar .krow')].map(r =>
      getComputedStyle(r.querySelector('button')).backgroundColor),
    lg: [...document.querySelectorAll('#legend .lrow')].map(r => getComputedStyle(r).borderLeftColor)
  }));
  check(accents.kb.join('|') === accents.lg.join('|'),
        'sidebar button fills match the legend row accents',
        accents.kb.length + ' vs ' + accents.lg.length + ' rows');
  // Every block gets its own accent, however many blocks there are — the
  // check is that no two share one, not that there are three.
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

  // 6. The About panel. Placement is the assertion, not existence: the owner
  // asked for it above the knowledge-base selectors and above the info lines,
  // and "a button exists somewhere on the page" would pass with it anywhere.
  // j4k's own About shipped in the wrong place and sat there for two commits.
  const about = await page.evaluate(() => {
    const side = document.getElementById('side');
    const btn = document.getElementById('aboutBtn');
    if (!side || !btn) return { present: false };
    const kids = [...side.children];
    return {
      present: true,
      first: kids.indexOf(btn) === 0,
      beforeStat: kids.indexOf(btn) < kids.findIndex(e => e.classList.contains('stat')),
      beforeKbbar: kids.indexOf(btn) < kids.findIndex(e => e.id === 'kbbar'),
      openBefore: document.getElementById('aboutWrap').classList.contains('on'),
    };
  });
  check(about.present, 'About button present');
  check(about.first && about.beforeStat && about.beforeKbbar,
        'About sits at the top of the sidebar, above the info lines and the kb selectors',
        'first=' + about.first + ' beforeStat=' + about.beforeStat + ' beforeKbbar=' + about.beforeKbbar);
  check(about.openBefore === false, 'About starts closed');

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
  // The dialog's buttons are the sidebar family: their rest colour must equal
  // the view toggles' rest colour, or the grammar has quietly forked.
  const family = await page.evaluate(() => ({
    dialog: getComputedStyle(document.querySelector('#aboutActions button')).color,
    sidebar: getComputedStyle(document.querySelector('#views button:not(.on)')).color
  }));
  check(family.dialog === family.sidebar, 'About buttons rest in the sidebar family colour',
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

  await browser.close();
  console.log(failures ? 'viewer-check: ' + failures + ' FAILURE(S)' : 'viewer-check: green');
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error('viewer-check crashed: ' + e.message); process.exit(1); });
