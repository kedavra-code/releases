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

const FILE = path.resolve(process.argv.slice(2).find(a => !a.startsWith('--')) || path.join(__dirname, '..', '00_Cerebrum_viewer.html'));
// `--only=6,9b` runs those numbered sections alone, with the boot before them and
// the last checks after, so a proof aimed at one check takes seconds, not the two
// minutes of a whole run (owner, 24.10.2026: "do 1", making proofs cheap rather
// than fewer). A section names in NEEDS the sections it cannot run without. A
// section's top-level names are `var`, so a skipped section leaves them empty
// rather than undeclared; a whole run, with no `--only`, is unchanged.
const NEEDS = { 3: ['2'], '3b': ['3'], '8b': ['8'], 11: ['9'] };
const ONLY = ((process.argv.find(a => a.startsWith('--only=')) || '').slice(7)).split(',').filter(Boolean);
for (let k = 0; k < ONLY.length; k++) for (const m of NEEDS[ONLY[k]] || []) if (!ONLY.includes(m)) ONLY.push(m);
const part = n => !ONLY.length || ONLY.includes(n);
let failures = 0;
const check = (ok, label, detail) => {
  console.log((ok ? 'ok      ' : 'FAIL    ') + label + (detail ? '  [' + detail + ']' : ''));
  if (!ok) failures++;
};

// The newest full Chromium in Playwright's own cache, whatever build it is.
function cachedChromium() {
  const fs = require('fs'), os = require('os');
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH,
    path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright'),
    path.join(os.homedir(), '.cache', 'ms-playwright')].filter(Boolean);
  const inside = ['chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
    'chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
    'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium',
    'chrome-mac/Chromium.app/Contents/MacOS/Chromium',
    'chrome-linux64/chrome', 'chrome-linux/chrome'];
  for (const root of roots) {
    let builds = [];
    try { builds = fs.readdirSync(root).filter(d => /^chromium-\d+$/.test(d)); } catch (e) { continue; }
    builds.sort((x, y) => Number(y.split('-')[1]) - Number(x.split('-')[1]));
    for (const build of builds)
      for (const rel of inside) {
        const exe = path.join(root, build, rel);
        if (fs.existsSync(exe)) return { build, exe };
      }
  }
  return null;
}

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
  // The full Chromium, headless, and not Playwright's default headless shell: the
  // shell draws WebGL in software (SwiftShader), the full browser on the graphics
  // chip, as the owner's Chrome does. Measured 27.09.2026 on the 3D view: 11 frames
  // a second in the shell, 60 in the full browser, and the check that the 3D view
  // "keeps drawing it" — more than 10 frames in 0.6 s — failed on the shell alone,
  // on the viewer before and after that day's change alike. A check of the page
  // must not be a check of the test's renderer. Where the full browser is not
  // installed, the shell is used and says so.
  //
  // Playwright looks for the one build its own version names. Where the cache
  // holds another build of the full browser, that one is used and named: on the
  // owner's Mac the vault's playwright asked for 1234 and the cache held 1243,
  // so the check ran only through a wrapper script kept in a temporary folder,
  // and on 05.10.2026 a change to the helper went in with the check not run.
  // CEREBRUM_CHROMIUM names a browser outright.
  const browser = await chromium.launch(
    process.env.CEREBRUM_CHROMIUM ? { executablePath: process.env.CEREBRUM_CHROMIUM } : { channel: 'chromium' }
  ).catch(e => {
    const other = cachedChromium();
    if (other) {
      console.log('note    the full Chromium of another build is used: ' + other.build);
      return chromium.launch({ executablePath: other.exe });
    }
    console.log('note    the full Chromium is not installed; the headless shell draws WebGL in software  [' + e.message.split('\n')[0] + ']');
    return chromium.launch();
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push(e.message));
  // No step of this check deletes or downloads a model's weights. On 24.10.2026
  // the local model, 17.2 GB, was gone after that day's proofs, run four at a
  // time on broken copies of the page, and the helper's own window is the only
  // record of which run asked. So a request to delete or fetch weights is
  // answered here, refused, and never reaches the helper, and the last check
  // says whether any was made.
  const weightAsks = [];
  await page.route(/127\.0\.0\.1:8760\/models\/(delete|pull)/, r => {
    weightAsks.push(r.request().method() + ' ' + r.request().url().replace(/.*8760/, '') + ' ' + (r.request().postData() || ''));
    r.fulfill({ status: 403, headers: { 'Access-Control-Allow-Origin': 'null', 'Access-Control-Allow-Headers': 'content-type', 'content-type': 'application/json' },
      body: JSON.stringify({ error: 'a check never deletes or fetches a model' }) }); });

  await page.goto('file://' + FILE);
  await page.waitForTimeout(700);

  if (part('1')) {
    // 1. The page boots: data present, no JS errors. That the sidebar lists
    // every concept is asked where the page is reopened, at the end: the same
    // count on the same boot. It was asked here as well until 04.10.2026.
    var boot = await page.evaluate(() => ({
      concepts: typeof D === 'object' ? Object.keys(D).length : 0,
      setHidden: !document.getElementById('setWrap').classList.contains('on'),
      setExpanded: document.getElementById('bSet').getAttribute('aria-expanded'),
    }));
    check(jsErrors.length === 0, 'no JS errors on load', jsErrors[0]);
    check(boot.concepts > 0, 'concept data present', boot.concepts + ' concepts');
    // Here, before anything is clicked. It sat with the other Settings checks
    // first, and passed with the panel open at load, because every click before
    // it counts as a click outside the panel and closes it.
    check(boot.setHidden && boot.setExpanded === 'false', 'Settings starts closed',
          'hidden=' + boot.setHidden + ' aria-expanded=' + boot.setExpanded);
    // The gear is j4k's, Lucide's Settings icon (owner, 24.10.2026: "please use
    // the settings icon from j4k as well").
    var gearD = await page.evaluate(() => { const g = document.querySelector('#bSet svg path'); return g ? g.getAttribute('d') : ''; });
    check(gearD.startsWith('M12.22 2h-.44a2 2 0 0 0-2 2v.18'), 'the gear is j4k\'s settings icon', gearD.slice(0, 32) || 'no path');

    // The build code says `uncommitted` exactly when a file the page is built
    // from differs from the commit, and never for a file it does not read. It
    // said so after every commit until 27.09.2026, because verify.py rewrites
    // its own state file in the pre-commit hook. Asked of the repository the
    // page sits in, with the inputs `visualize.py` itself declares.
    {
      const cp = require('child_process'), fs = require('fs');
      const src = fs.readFileSync(path.join(__dirname, 'visualize.py'), 'utf8');
      const inputs = [...(src.match(/^PAGE_INPUTS = \[(.*)\]$/m) || ['', ''])[1].matchAll(/'([^']+)'/g)].map(m => m[1]);
      const dir = path.dirname(FILE);
    // A template fresh from its archive is not a git checkout yet, and the
    // page then says so rather than naming a commit.
    let dirty = null;
    try {
      dirty = inputs.length ? cp.execFileSync('git', ['--no-optional-locks', '-C', dir, 'status', '--porcelain', '--', ...inputs],
                                              { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() : '?';
    } catch (e) { dirty = null; }
      const stamp = await page.evaluate(() => GIT);
    if (dirty === null)
      check(inputs.length > 0 && /^not a git checkout/.test(stamp) && !/uncommitted/.test(stamp),
            'outside a git checkout the build code says so', 'stamp "' + stamp + '"');
    else
      check(inputs.length > 0 && /uncommitted/.test(stamp) === (dirty !== ''),
            'the build code says uncommitted exactly when a file the page reads is changed',
            'stamp "' + stamp + '"; changed inputs: ' + (dirty ? dirty.split('\n').length + ', first ' + dirty.split('\n')[0].trim() : 'none'));
    }
  }

  if (part('2')) {
    // 2. A concept page renders, and no HTML entity leaks into visible text.
    //    Prefer a title carrying "&": that is the regression of 10.08.2026.
    var target = await page.evaluate(() => {
      const ids = Object.keys(D);
      return ids.find(i => D[i].t.includes('&')) || ids[0];
    });
    await page.evaluate(id => show(id), target);
    await page.waitForTimeout(300);
    var rendered = await page.evaluate(() => ({
      h1: document.querySelector('#main h1').textContent,
      entity: /&(amp|lt|gt|quot|#\d+);/.test(document.getElementById('main').textContent),
    }));
    check(!rendered.entity, 'no HTML entity in rendered page text', rendered.h1);
  }

  if (part('3')) {
    // 3. Search matches raw text: a title's own words must find it.
    var probe = await page.evaluate(t => {
      const q = document.getElementById('q');
      q.value = D[t].t.toLowerCase();
      q.dispatchEvent(new Event('input'));
      return document.querySelectorAll('.it').length;
    }, target);
    check(probe >= 1, 'search finds a concept by its exact title', probe + ' hits');

    // 3a-ii. The clear button. It only exists while there is something to clear,
    //        and it has to clear through the same `input` event the search runs
    //        on — setting the value alone would leave the list filtered.
    var clr = await page.evaluate(t => {
      const q = document.getElementById('q'), w = document.getElementById('qwrap');
      q.value = D[t].t.toLowerCase(); q.dispatchEvent(new Event('input'));
      const shownWhenTyped = getComputedStyle(document.getElementById('qx')).display !== 'none';
      const filtered = document.querySelectorAll('.it').length;
      document.getElementById('qx').click();
      return {shownWhenTyped, filtered,
              value: q.value, after: document.querySelectorAll('.it').length,
              hiddenAgain: getComputedStyle(document.getElementById('qx')).display === 'none',
              wrapClass: w.className};
    }, target);
    check(clr.shownWhenTyped, 'clear button appears once something is typed');
    check(clr.value === '', 'clicking it empties the box', JSON.stringify(clr.value));
    check(clr.after > clr.filtered, 'clicking it restores the unfiltered list',
          clr.filtered + ' filtered -> ' + clr.after + ' shown');
    check(clr.hiddenAgain && clr.wrapClass === '', 'and the button hides itself again');

    await page.evaluate(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); });
  }

  if (part('3b')) {
    // 3b. Group folding: headers fold their own group, the button folds all,
    //     search overrides folding, and a concept reached while its group is
    //     folded unfolds it. Added 15.08.2026 with the feature — the sidebar
    //     had grown to 223 entries in one scroll. Items stay in the DOM when
    //     folded, so the count of rows against concepts, taken where the page is
    //     reopened at the end, stays a true statement; visibility is what
    //     this checks.
    var fold = await page.evaluate(async () => {
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
      localStorage.removeItem('okf.foldKb');
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
    var qBorder = await page.evaluate(() => {
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
  }

  if (part('3c')) {
    // 3c. Two levels, owner's instruction of 27.09.2026: a header per knowledge
    //     base, in the button Settings gives that base (filled with its hue,
    //     the count after the name), and under it the category groups that
    //     were the list's only level before. A first version replaced the
    //     categories instead of adding the level above them; the second check
    //     is there so that cannot happen again.
    var kbTree = await page.evaluate(() => {
      const want = {}, cats = new Set();
      Object.keys(D).forEach(id => { const k = id.split('/')[0];
        if (offKB.has(k)) return; want[k] = (want[k] || 0) + 1;
        const p = id.split('/'); if (p.slice(2, -1).length) cats.add(group(id)); });
      const probe = document.createElement('i'); document.body.appendChild(probe);
      const rgb = h => { probe.style.color = h; return getComputedStyle(probe).color; };
      const rows = [...document.querySelectorAll('#tree .kbh')].map(g => ({ kb: g.dataset.kb,
        n: +g.querySelector('small').textContent, bg: getComputedStyle(g).backgroundColor,
        hue: HUE[g.dataset.kb] ? rgb(HUE[g.dataset.kb]) : null,
        grps: g.nextElementSibling ? g.nextElementSibling.querySelectorAll('.grp').length : 0 }));
      const setBtn = [...document.querySelectorAll('#kbbar button')][0];
      const out = { rows, want, cats: cats.size, grps: document.querySelectorAll('#tree .kbbody .grp').length,
        radius: [getComputedStyle(document.querySelector('#tree .kbh')).borderRadius, setBtn ? getComputedStyle(setBtn).borderRadius : null] };
      probe.remove(); return out;
    });
    var kbKeys = Object.keys(kbTree.want);
    check(kbTree.rows.length === kbKeys.length && kbTree.rows.every(r => kbTree.want[r.kb] === r.n),
          'the concept list has one header per knowledge base, counting its concepts',
          kbTree.rows.map(r => r.kb + ' ' + r.n).join(', ') + ' against ' + kbKeys.map(k => k + ' ' + kbTree.want[k]).join(', '));
  check(kbTree.grps === kbTree.cats && kbTree.rows.every(r => r.grps > 0 || r.n < 2),
          'and the category groups stand under their base, every one of them',
          kbTree.grps + ' category headers for ' + kbTree.cats + ' categories');
    check(kbTree.rows.length > 0 && kbTree.rows.every(r => r.hue && r.bg === r.hue) && kbTree.radius[0] === kbTree.radius[1],
          'each base header is the Settings button: filled with its hue, same corners',
          kbTree.rows.map(r => r.kb + ' ' + r.bg).join(', ') + '; corners ' + kbTree.radius.join(' vs '));
  }

  if (part('3d')) {
    // 3d. The vault's figures, one line at the top left of each graph in the
    //     hints' own style, owner's instruction of 27.09.2026. They stood under
    //     the logo until then. Same font, colour and opacity as the hints, the
    //     same distance from the left edge, and as far from the top as the hints
    //     are from the bottom. The logo carries none any more.
    var stat = id => page.evaluate(([s, h]) => {
      const e = document.getElementById(s), g = document.getElementById(h);
      const P = e.parentElement.getBoundingClientRect(), r = e.getBoundingClientRect(), q = g.getBoundingClientRect();
      const c = getComputedStyle(e), d = getComputedStyle(g);
      const cs = Object.values(D), sw = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "'");
      const inb = cs.reduce((a, x) => a + x.inb.length, 0), out = cs.reduce((a, x) => a + x.out.length, 0);
      return { shown: r.width > 0, text: e.textContent, oneLine: r.height < 20,
        want: new Set(cs.map(x => x.kb)).size + ' bases · ' + sw(cs.length) + ' concepts · ' + sw(inb) + ' links · ' +
          sw(cs.reduce((a, x) => a + (x.ns || 0), 0)) + ' citations', both: inb === out,
        left: Math.round(r.left - P.left), hintLeft: Math.round(q.left - P.left),
        top: Math.round(r.top - P.top), hintBottom: Math.round(P.bottom - q.bottom),
        style: ['fontSize', 'fontFamily', 'color', 'opacity', 'letterSpacing'].every(k => c[k] === d[k]),
        logo: !!document.querySelector('#aboutBtn .st, #brandStats') };
    }, id);
    await page.click('#bGraph');
    await page.waitForTimeout(300);
    var st2 = await stat(['g2stat', 'g2hint']);
    await page.click('#b3d');
    await page.waitForTimeout(700);
    var st3 = await stat(['g3stat', 'g3hint']);
    // A fresh page again: the 3D checks below expect the view's first opening.
    await page.reload();
    await page.waitForTimeout(900);
    for (const [v, x] of [['2D', st2], ['3D', st3]]) {
      check(x.shown && x.text === x.want && x.both && x.oneLine && !x.logo,
            'the ' + v + ' graph carries the vault\'s figures in one line, and one links figure is both totals',
            JSON.stringify(x.text) + (x.both ? '' : ' — outbound and inbound totals differ') + (x.logo ? '; the logo still carries figures' : ''));
      check(x.style && x.left === x.hintLeft && Math.abs(x.top - x.hintBottom) <= 1,
            'and in the ' + v + ' hints\' style, top left as the hints are bottom left',
            'style ' + x.style + ', left ' + x.left + ' vs ' + x.hintLeft + ', ' + x.top + 'px from the top vs ' + x.hintBottom + 'px from the bottom');
    }
  }

  if (part('4')) {
    // 4. The graph draws ink: non-background pixels on the canvas, legend
    //    chips present. Radius zero drew nothing and stayed clickable.
    await page.click('#bGraph');
    await page.waitForTimeout(1500);
    var graph = await page.evaluate(() => {
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
      return { ink, chroma,
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
    // No knowledge base is drawn as a speck: at 19 concepts one base sat in a
    // radius of 139 under a name wider than the cluster. visualize.py gives
    // every base a radius of at least 330, and a halo reaches past the radius;
    // 330 is what the halo must at least reach.
    var small = await page.evaluate(() => Object.keys(KBC).filter(k => HUE[k] && !offKB.has(k))
      .map(k => [k, Math.round(KBC[k].halo)]));
    check(small.length > 0 && small.every(([, h]) => h >= 330), 'no knowledge base is drawn smaller than the floor',
          small.map(([k, h]) => k.replace('_kb', '') + ' ' + h).join(', '));
    // Every knowledge base is drawn round, not as a line. Owner's instruction of
    // 29.09.2026: one base, whose shelves link to one another in a chain, came out
    // 3.3 times as long as it was wide. visualize.py raises a group's gravity
    // until its layout is round; this measures the positions actually drawn, as
    // the ratio of the long axis of each base's spread to its short axis.
    var roundness = await page.evaluate(() => KB_ALL.map(kb => { const ns = N.filter(n => n.kb === kb);
      const mx = ns.reduce((a, n) => a + n.x, 0) / ns.length, my = ns.reduce((a, n) => a + n.y, 0) / ns.length;
      let sxx = 0, syy = 0, sxy = 0;
      ns.forEach(n => { sxx += (n.x - mx) ** 2; syy += (n.y - my) ** 2; sxy += (n.x - mx) * (n.y - my); });
      const tr = (sxx + syy) / ns.length, det = (sxx * syy - sxy * sxy) / ns.length ** 2, q = Math.sqrt(Math.max(tr * tr / 4 - det, 0));
      return [kb, Math.sqrt((tr / 2 + q) / Math.max(tr / 2 - q, 1e-9)), ns.length]; }));
    // A base of fewer than twelve concepts is named and not judged: a handful of
    // points has no shape to measure, and the made-up base of seven that the
    // template is tried on came out at 1.96.
    var roundBig = roundness.filter(([, , n]) => n >= 12);
    check(roundness.length > 0 && roundBig.every(([, r]) => r <= 1.5),
          'every knowledge base is drawn round, not as a line' + (roundBig.length ? '' : ' (none has twelve concepts to measure yet)'),
          roundness.map(([k, r, n]) => k.replace('_kb', '') + ' ' + r.toFixed(2) + (n < 12 ? ' of ' + n + ' concepts, not judged' : '')).join(', '));
    var corners = await page.evaluate(() => {
      const ks = Object.keys(KBC).sort(), out = [];
      for (let i = 0; i < ks.length; i++) for (let j = i + 1; j < ks.length; j++)
        out.push([ks[i].replace('_kb', ''), ks[j].replace('_kb', ''),
          Math.round(Math.hypot(KBC[ks[i]].cx - KBC[ks[j]].cx, KBC[ks[i]].cy - KBC[ks[j]].cy) - KBC[ks[i]].halo - KBC[ks[j]].halo)]);
      return out;
    });
    // By the 40 units the layout keeps, not merely clear: a check at zero let
    // one halo stand 129 units into another's while every pair still passed.
    check(corners.every(c => c[2] >= 39), 'no two knowledge bases\' halos come closer than the 40-unit gap',
          corners.length ? 'halo gaps: ' + corners.map(c => c[0] + '~' + c[1] + ' ' + c[2]).join(', ')
                         : 'one knowledge base, nothing to separate');
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

    // The KB selector is rows of three at one width. Read off the rendered
    // buttons, so a layout that wraps differently fails: every row full but the
    // last, and every button the same width.
    var kbRows = await page.evaluate(() => {
      document.getElementById('setWrap').classList.add('on');
      const b = [...document.querySelectorAll('#kbbar button')].map(e => e.getBoundingClientRect());
      document.getElementById('setWrap').classList.remove('on');
      const tops = [...new Set(b.map(r => Math.round(r.top)))];
      return { rows: tops.map(t => b.filter(r => Math.round(r.top) === t).length),
               widths: [...new Set(b.map(r => Math.round(r.width)))] };
    });
    check(kbRows.rows.length > 0 && kbRows.rows.slice(0, -1).every(n => n === 3) && kbRows.rows[kbRows.rows.length - 1] <= 3
          && kbRows.widths.length === 1, 'kb selector shows rows of three, every button one width',
          kbRows.rows.join('/') + ', widths ' + kbRows.widths.join(', '));
    // The concept tree reads the selector's order flat. Both come from
    // KB_BLOCKS now; this asserts the derivation actually reaches the tree.
    var order = await page.evaluate(() => {
      const btn = [...document.querySelectorAll('#kbbar button')]
        .map(b => b.firstChild.textContent.trim());
      // The base headers carry the name alone in .gn since 27.09.2026.
      const seen = [...document.querySelectorAll('#tree .kbh .gn')].map(g => g.textContent.trim());
      return { btn, tree: seen };
    });
    check(order.btn.join(',') === order.tree.join(','),
          'the concept tree follows the selector order',
          'buttons [' + order.btn.join(', ') + '] tree [' + order.tree.join(', ') + ']');

    // One accent hue per ontology block: the Settings buttons wear it as their
    // fill, the legend row as its accent bar — the pairing is what says they
    // are the same thing.
    var accents = await page.evaluate(() => ({
      kb: [...new Set([...document.querySelectorAll('#kbbar button')].map(b => b.dataset.block))].map(bi =>
        getComputedStyle(document.querySelector('#kbbar button[data-block="' + bi + '"]')).backgroundColor),
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
  }

  if (part('5')) {
    // 5. Theme tokens reach the paint: body background equals --bg.
    var theme = await page.evaluate(() => {
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
  }

  if (part('6')) {
    // 6. The header and the About control. Placement is the assertion, not
    // existence: "a button exists somewhere on the page" would pass with it
    // anywhere, and j4k's own About shipped in the wrong place and sat there for
    // two commits. Owner's instruction of 14.09.2026: the logo on the left, the
    // categories to its right, and the view below. Until then this checked that
    // About sat at the top of the sidebar, above the info lines and the
    // knowledge-base selectors; the sidebar now holds the list and nothing else.
    var about = await page.evaluate(() => {
      const top = document.getElementById('top'), btn = document.getElementById('aboutBtn');
      const legend = document.getElementById('legend'), stage = document.getElementById('stage');
      if (!top || !btn || !legend || !stage) return {};
      const r = e => e.getBoundingClientRect();
      return {
        first: top.firstElementChild === btn,
        inHeader: top.contains(legend),
        leftOf: r(btn).right <= r(legend).left,
        above: r(top).bottom <= r(stage).top + 0.5,
        openBefore: document.getElementById('setWrap').classList.contains('on'),
      };
    });
    check(about.first && about.inHeader && about.leftOf && about.above,
          'the logo opens the header, the categories sit to its right, and the view sits below',
          'first=' + about.first + ' categories in header=' + about.inHeader +
          ' right of the logo=' + about.leftOf + ' header above the view=' + about.above);
    // The two lines the owner removed, because About already says them, and the
    // selector that moved into Settings. Asserted as the sidebar's whole content
    // rather than as two absences, so nothing else can move in unnoticed either.
    var sideNow = await page.evaluate(() => ({
      side: [...document.getElementById('side').children].map(e => e.id).join(','),
      top: [...document.getElementById('sidetop').children].map(e => e.id).filter(i => i !== 'qwrap').join(','),
      kbInSettings: !!document.querySelector('#setWin #paneKb #kbbar'),
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
    var blockHues = await page.evaluate(() => KB_BLOCKS.map(b => b.hue));
    var angle = ([r, g, b]) => {
      const mx = Math.max(r, g, b), c = mx - Math.min(r, g, b);
      if (c < 24) return null;
      const h = 60 * (mx === r ? ((g - b) / c + 6) % 6 : mx === g ? (b - r) / c + 2 : (r - g) / c + 4);
      return h;
    };
    var hexRgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    var markBox = await page.evaluate(() => { const r = document.querySelector('#aboutBtn svg').getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); });
    var markPx = pngPixels(await page.screenshot({ clip: { x: markBox[0], y: markBox[1], width: markBox[2], height: markBox[3] } }));
    var inHue = blockHues.map(() => 0);
    for (let y = 0; y < markBox[3]; y++) for (let x = 0; x < markBox[2]; x++) {
      const a = angle(markPx(x, y));
      if (a === null) continue;
      blockHues.forEach((hue, i) => { const d = Math.abs(a - angle(hexRgb(hue))); if (Math.min(d, 360 - d) <= 12) inHue[i]++; });
    }
    check(inHue.every(n => n >= 4), 'the header mark shows the three halo colours of the graph',
          blockHues.map((h, i) => h + ' ' + inHue[i] + 'px').join(', ') + ' in ' + markBox[2] + 'x' + markBox[3]);

    // About is the first part of Settings since 24.10.2026, as About j4k is in
    // j4k's Settings window, and the mark in the header opens Settings on it.
    await page.click('#aboutBtn');
    await page.waitForTimeout(200);
    var opened = await page.evaluate(() => {
      const win = document.getElementById('setWin');
      const rows = [...document.querySelectorAll('#partAbout .stat')]
        .map(d => d.querySelector('.sn').textContent + '=' + d.querySelector('b').textContent);
      const docs = document.getElementById('setDocs');
      return {
        visible: document.getElementById('setWrap').classList.contains('on'),
        shown: [...document.querySelectorAll('.setPart')].filter(p => !p.hasAttribute('inert')).map(p => p.id).join(','),
        title: document.getElementById('setTitle').textContent,
        wide: win.getBoundingClientRect().width > 200,
        facts: rows,
        logo: !!document.querySelector('#partAbout .aboutLogo svg'),
        // every number is derived at open time; one that differs from the data the
        // page is drawn from means the part is reading something else
        concepts: (rows.find(r => r.startsWith('Concepts=')) || ''), want: 'Concepts=' + sw(Object.keys(D).length),
        docs: docs.href, docsNew: docs.target === '_blank', docsHidden: docs.closest('.setRow').hidden,
      };
    });
    check(opened.visible && opened.wide && opened.shown === 'partAbout' && opened.title === 'About 00_Cerebrum',
          'the mark in the header opens Settings on About 00_Cerebrum', 'open=' + opened.visible + ' showing ' + opened.shown + ' titled "' + opened.title + '"');
    check(opened.facts.length >= 8, 'About lists its facts', opened.facts.length + ' figures');
    check(opened.concepts === opened.want, 'About counts concepts from the page data', opened.concepts + ' against ' + opened.want);
    check(opened.logo, 'About draws its logo');
    // Docs opens the manual named in FIELD_MANUAL in a new tab, and is hidden
    // where none is named, as in the template.
    check(opened.docsHidden || (/^https?:\/\//.test(opened.docs) && opened.docsNew),
          'About\'s Docs opens your manual in a new tab, or is hidden without one',
          opened.docsHidden ? 'hidden: no FIELD_MANUAL set' : opened.docs + ' new tab=' + opened.docsNew);
    // What's new, owner's request of 24.10.2026: "why does cerebrum not have a
    // whats new. please build"; then, the same day, in folia's window: "make in
    // settings whats new look like the one from folia", "use the style of folia
    // as well". The list is written by hand for the reader, a title and a line a
    // change; two of the changes are made unread here.
    // The template ships _scripts/whats-new.json empty, so a vault with no
    // changes listed gets sixty made-up ones here, three a day, newest first,
    // for the window to be measured with. A vault's own list is used as it is.
    await page.evaluate(() => { if (NEWS.length) return;
      for (let i = 0; i < 60; i++) { const d = new Date(Date.UTC(2026, 2, 1) - Math.floor(i / 3) * 864e5).toISOString().slice(0, 10);
        NEWS.push({ k: d + ' change ' + i, d, t: 'A made-up change ' + (60 - i), x: 'It stands here so the window has something to show.' }); } });
    { const nw = await page.evaluate(() => { localStorage.setItem('okf.newsSeen', NEWS[2] ? NEWS[2].k : ''); paintNews();
        const t = document.getElementById('newsTab'), p = document.getElementById('newsPill');
        return { tab: t.hidden ? '' : t.textContent, pill: p.hidden ? '' : p.textContent, n: NEWS.length }; });
      // About's name stays on one line with the count beside it (owner,
      // 24.10.2026: "fix the about line too"); it broke in two in a 224px side.
      const tabLine = await page.evaluate(() => { const t = document.querySelector('.setTab[data-part="partAbout"]'), s = t.querySelector('span'), k = document.getElementById('newsTab'),
          o = document.querySelector('.setTab[data-part="paneKb"] span'), r = e => e.getBoundingClientRect();
        return { h: r(s).height, one: r(o).height, gap: r(k).left - r(s).right, inTab: r(k).right <= r(t).right - 4, count: k.hidden ? '' : k.textContent }; });
      check(tabLine.count === '2' && Math.abs(tabLine.h - tabLine.one) < 1 && tabLine.gap >= 4 && tabLine.inTab,
            'About 00_Cerebrum stands on one line in the side list, with its count of unread changes beside it',
            'name ' + Math.round(tabLine.h) + 'px high against ' + Math.round(tabLine.one) + 'px for one line, ' + Math.round(tabLine.gap) + 'px to the count ' +
            JSON.stringify(tabLine.count) + ', count inside the tab=' + tabLine.inTab);
      await page.click('#setNews');
      await page.waitForTimeout(200);
      const list = await page.evaluate(() => {
        const days = [...document.querySelectorAll('#newsList .nwDay h4')].map(h => h.textContent),
          when = days.map(d => Date.parse(d)), rows = [...document.querySelectorAll('#newsList .nwRow')],
          win = document.getElementById('newsWin'), r = win.getBoundingClientRect(), cs = e => getComputedStyle(e),
          title = rows[0] && rows[0].querySelector('.nwTitle'), line = rows[0] && rows[0].querySelector('.nwDetail'), h4 = document.querySelector('#newsList .nwDay h4');
        return { open: document.getElementById('newsWrap').classList.contains('on'), set: document.getElementById('setWrap').classList.contains('on'),
          rows: rows.length, said: rows.filter(w => { const t = w.querySelector('.nwTitle'), x = w.querySelector('.nwDetail');
            return t && x && t.textContent.trim() && !/\.$/.test(t.textContent) && /\.$/.test(x.textContent); }).length,
          days: days.length, named: days.every(d => /^[A-Z][a-z]{2} \d{1,2}, \d{4}$/.test(d)), sorted: when.every((t, i) => !isNaN(t) && (!i || t < when[i - 1])),
          count: document.getElementById('newsCount').textContent, tab: document.getElementById('newsTab').hidden,
          mark: localStorage.getItem('okf.newsSeen') === (NEWS[0] || {}).k,
          w: r.width, h: r.height, W: innerWidth, H: innerHeight,
          look: [cs(win).backgroundColor, cs(win).borderRadius, title && cs(title).fontSize, title && cs(title).fontWeight, line && cs(line).fontSize, line && cs(line).color,
            h4 && cs(h4).fontSize, h4 && cs(h4).textTransform, cs(document.getElementById('newsDone')).backgroundColor].join(' | ') }; });
      check(nw.n > 50 && list.open && list.rows === nw.n && list.said === nw.n && list.named && list.sorted && list.count === nw.n + ' changes listed.',
            'What\'s new lists every change with its title and a line on what it does, newest first, a day a card under its date',
            list.said + ' of ' + list.rows + ' rows titled and said, ' + nw.n + ' changes in ' + list.days + ' days, dates as folia writes them=' + list.named +
            ', newest first=' + list.sorted + ', foot "' + list.count + '"');
      check(!list.set && Math.abs(list.w - Math.min(520, list.W - 48)) <= 1 && list.h <= list.H * .86 + 1 && list.h >= list.H * .86 - 2,
            'What\'s new takes Settings\' place in folia\'s size: 520 px wide, and no more than 86% of the page high',
            'Settings open=' + list.set + ', ' + Math.round(list.w) + 'x' + Math.round(list.h) + ' in ' + list.W + 'x' + list.H + ' (' + Math.round(list.h / list.H * 100) + '% high)');
      check(list.look === 'rgb(30, 30, 30) | 14px | 13.5px | 650 | 12.5px | rgb(165, 161, 152) | 11.5px | uppercase | rgb(217, 155, 38)',
            'What\'s new is set in folia\'s style: its window colour, corners, type and Done', list.look);
      check(nw.tab === '2' && nw.pill === '2 new' && list.tab && list.mark,
            'the changes not read yet are counted on About and its row, and opening What\'s new reads them',
            'About ' + JSON.stringify(nw.tab) + ', row ' + JSON.stringify(nw.pill) + ', counts cleared=' + list.tab + ', read up to the newest=' + list.mark);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(150);
      // About opens by its button's own click: a Settings window left open by a
      // fault would cover the header and stop the run, not fail the check.
      const about = ms => page.evaluate(() => document.getElementById('aboutBtn').click()).then(() => page.waitForTimeout(ms));
      const shut = () => page.evaluate(() => [document.getElementById('newsWrap'), document.getElementById('setWrap')].map(w => w.classList.contains('on')).join(','));
      const esc = await shut();
      await about(150); await page.click('#setNews'); await page.waitForTimeout(150);
      await page.click('#newsDone'); await page.waitForTimeout(150);
      const done = await shut();
      await about(150); await page.click('#setNews'); await page.waitForTimeout(150);
      await page.mouse.click(8, 8); await page.waitForTimeout(150);
      const out = await shut();
      check(esc === 'false,false' && done === 'false,false' && out === 'false,false',
            'Escape, Done or a click beside it closes What\'s new, and Settings with it, as in folia',
            'open (What\'s new, Settings) after Escape ' + esc + ', after Done ' + done + ', after a click beside ' + out);
      await about(200); }
    // The two link figures carry a visible note saying what they count, owner's
    // instruction of 27.09.2026: the meaning had lived in a tooltip, and the
    // owner asked three times what the figures meant. The note stands on the
    // value's line, because the panel has to fit without scrolling.
    var notes = await page.evaluate(() => [...document.querySelectorAll('#partAbout .stat')]
      .filter(d => /^(Links|Unlinked)$/.test(d.querySelector('.sn').textContent))
      .map(d => { const n = d.querySelector('.sd'); return n && n.offsetHeight > 0 ? n.textContent : ''; }));
    check(notes.length === 2 && notes.every(t => /concepts/.test(t)),
          'About says in words what both link figures count', notes.map(t => t.slice(0, 40)).join(' | '));
    // Where the mark stands each knowledge base, and what it connects, compared
    // with the data the graph is drawn from. The mark this replaced carried a
    // comment saying the generator asserted it against the layout; no such
    // assertion was ever written, so the drawing and the claim were never compared.
    var mark = await page.evaluate(() => {
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
    var pulse = await page.evaluate(async () => {
      const p = document.querySelector('.aboutLogo .pulse path');
      const at = () => p ? getComputedStyle(p).strokeDashoffset : '';
      const t0 = at(); await new Promise(r => setTimeout(r, 700)); const t1 = at();
      return { about: document.querySelectorAll('.aboutLogo .pulse path').length, header: document.querySelectorAll('#aboutBtn .pulse path').length, moved: !!p && t0 !== t1, t0, t1 };
    });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    var still = await page.evaluate(() => { const g = document.querySelector('.aboutLogo .pulse'); return g ? getComputedStyle(g).display : 'absent'; });
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
    // About has no scrollbar on a screen of this size: j4k's rule (23.10.2026), and the old
    // About box's, whose cap once pushed its last row behind a scroll (29.08.2026).
    // The buttons of the old About box went with it.
    // About itself is measured: the scheduled tasks are read live from the
    // helper, and a long list may make their part, and so the window, scroll.
    var fits = await page.evaluate(() => {
      const body = document.querySelector('#setWin .winBody'), win = document.getElementById('setWin').getBoundingClientRect();
      const done = document.getElementById('setDone').getBoundingClientRect(), pad = parseFloat(getComputedStyle(body).paddingTop) + parseFloat(getComputedStyle(body).paddingBottom);
      const need = Math.ceil(document.getElementById('partAbout').getBoundingClientRect().height + pad);
      return { scrolls: need > body.clientHeight + 1, need, have: body.clientHeight,
        doneVisible: done.height > 0 && done.bottom <= win.bottom + 0.5 && win.bottom <= innerHeight };
    });
    // A selected concept is the activated fold button: accent border, no fill.
    var selStyle = await page.evaluate(() => {
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
    check(!fits.scrolls && fits.doneVisible, 'Settings fits without scrolling, About included, and its Done shows',
          fits.need + ' of ' + fits.have + ', Done shown=' + fits.doneVisible);

    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    var closed = await page.evaluate(() =>
      document.getElementById('setWrap').classList.contains('on'));
    check(closed === false, 'Escape closes Settings opened on About');
  }

  if (part('7')) {
    // 7. Two full-screen views under one header, 14.09.2026. Full screen as a
    // mode of its own, added 09.09.2026, went with it: both views take the whole
    // window, so there is nothing left to switch into, and its checks went too.
    // What they guarded carries over: the view really filling the window, the
    // canvas backing store following its size, and a focused button not ringing
    // on Escape.
    await page.click('#bGraph');
    await page.waitForTimeout(300);
    var gv = await page.evaluate(() => {
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
    // The Concept view asked the same of the same element until 04.10.2026, as
    // "never re-parented". Nothing in the page moves the box, so one reading
    // holds for both views.
    check(gv.searchIn === 'askbar', 'the search box is the bar above the graph, not inside it', 'parent=' + gv.searchIn);
    // Each graph says how to drive it, bottom left, in one style: owner's
    // request of 23.09.2026, for the 2D graph after the 3D view had one.
    var hints = await page.evaluate(() => {
      const one = id => { const e = document.getElementById(id), r = e.getBoundingClientRect(), c = getComputedStyle(e);
        return { shown: r.width > 0, left: r.left, bottom: innerHeight - r.bottom, font: c.fontSize, color: c.color, text: e.textContent }; };
      return { g2: one('g2hint'), g3: one('g3hint'), hasFit: !!document.getElementById('gfit'), gesture: 'ongesturestart' in window };
    });
    check(hints.g2.shown && !hints.g3.shown && /Drag.*move.*Scroll.*zoom.*Click.*select.*Double-click.*open.*Double-click empty space.*fit/.test(hints.g2.text) &&
          /Double-click empty space.*fit/.test(hints.g3.text) && !hints.hasFit &&
          hints.g2.left === 16 && hints.g2.font === hints.g3.font && hints.g2.color === hints.g3.color,
          'the Graph view says how to move, zoom, select, open and fit, in the 3D view\'s style, and there is no Fit button',
          JSON.stringify(hints.g2.text) + ' at left ' + hints.g2.left + ', ' + hints.g2.font);
    // And how to turn, since 08.10.2026: the Option key with a two-finger swipe
    // in every browser, and the two-finger turn itself only where the browser
    // gives that gesture to the page, which Chromium does not.
    check(/Scroll.*zoom.*(Option|Alt)-scroll.*to turn.*Click/.test(hints.g2.text) && /Scroll.*zoom.*(Option|Alt)-scroll.*to roll.*Click/.test(hints.g3.text) &&
          /Two fingers turning/.test(hints.g2.text) === hints.gesture && /Two fingers turning/.test(hints.g3.text) === hints.gesture,
          'each graph\'s line says how to turn it, and names the two-finger turn only where the browser gives that gesture to the page',
          JSON.stringify(hints.g2.text.split(' · ')[2]) + ' and ' + JSON.stringify(hints.g3.text.split(' · ')[3]) + '; this browser gives the gesture: ' + hints.gesture);

    await page.click('#bList');
    await page.waitForTimeout(300);
    var cvw = await page.evaluate(() => {
      const box = id => document.getElementById(id).getBoundingClientRect().toJSON();
      return { side: box('side'), main: box('main'), top: box('askbar'), gc: box('gc'),
               win: innerWidth, winH: innerHeight, on: document.getElementById('bList').classList.contains('on') };
    });
    check(cvw.on && cvw.gc.width === 0 && cvw.side.left === 0 && cvw.side.width > 0 &&
          cvw.main.left >= cvw.side.right && Math.abs(cvw.main.right - cvw.win) < 1 &&
          Math.abs(cvw.side.top - cvw.top.bottom) < 1 && Math.abs(cvw.side.bottom - cvw.winH) < 1,
          'the Concept view is the list on the left and the page on the right, below the search bar',
          'list ' + Math.round(cvw.side.left) + '-' + Math.round(cvw.side.right) + ', page ' +
          Math.round(cvw.main.left) + '-' + Math.round(cvw.main.right) + ' of ' + cvw.win + ', graph width ' + cvw.gc.width);
    // One search bar for both views, and since 16.09.2026 it spans the window and
    // never moves: the owner asked for the full width, and Ask Claude needs the
    // room. The checks this replaced guarded a box that lived inside each pane and
    // had to match the list's width through a splitter drag and a narrow window.
    // What carries over is the reason they existed — the box has to be the same
    // box, in the same place, whichever view is showing — and it is a stronger
    // statement now, because there is one element and nothing is re-parented.
    var barSpot = () => page.evaluate(() => {
      const q = document.getElementById('q').getBoundingClientRect();
      const b = document.getElementById('askbar').getBoundingClientRect();
      return { q: [q.left, q.top, q.width, q.height], b: [b.left, b.top, b.width, b.height],
        win: document.documentElement.clientWidth,
        header: document.getElementById('top').getBoundingClientRect().bottom,
        list: document.getElementById('side').getBoundingClientRect().width };
    });
    var same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 0.5);
    var at = r => r.map(v => Math.round(v * 10) / 10).join(',');
    await page.click('#bList');
    await page.waitForTimeout(300);
    var cSpot = await barSpot();
    await page.click('#bGraph');
    await page.waitForTimeout(300);
    var gSpot = await barSpot();
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
    var grip = await page.evaluate(() => { const r = document.getElementById('splitter').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 300]; });
    await page.mouse.move(grip[0], grip[1]);
    await page.mouse.down();
    await page.mouse.move(560, grip[1], { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(150);
    var cWide = await barSpot();
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
    var cNarrow = await barSpot();
    await page.click('#bGraph');
    await page.waitForTimeout(300);
    var gNarrow = await barSpot();
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
    var foldRow = () => page.evaluate(() => {
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
    var row1 = await foldRow();
    await page.click('#ball');
    await page.waitForTimeout(150);
    var row2 = await foldRow();
    await page.click('#ball');
    await page.waitForTimeout(150);
    await page.evaluate(() => localStorage.removeItem('okf.foldKb'));
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
    // Only a list long enough to scroll can prove this. Since 27.09.2026 the
    // groups are the six bases, and folded they no longer fill the column, so
    // the list is unfolded for the measurement and folded back after it.
    var sticky = await page.evaluate(() => {
      const tree = document.getElementById('tree'), ball0 = document.getElementById('ball');
      const wasShut = ball0.textContent.includes('Expand'); if (wasShut) ball0.click();
      tree.scrollTop = tree.scrollHeight;
      const q = document.getElementById('q').getBoundingClientRect();
      const ball = document.getElementById('ball').getBoundingClientRect();
      const s = document.getElementById('side').getBoundingClientRect();
      const out = { scrolled: tree.scrollTop > 0, top: Math.round(q.top),
        above: q.bottom <= s.top + 0.5, inTree: !!document.getElementById('tree').contains(document.getElementById('q')),
        ballShown: ball.top >= s.top - 0.5 && ball.bottom <= s.bottom };
      tree.scrollTop = 0; if (wasShut) ball0.click();
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
    var picked = await page.evaluate(() => {
      let i = N.map((n, k) => [k, D[n.id].inb.length]).sort((a, b) => b[1] - a[1])[0][0];
      const late = N.map((n, k) => k).filter(k => k > N.length / 2);
      if (late.length) i = late.sort((a, b) => D[N[b].id].inb.length - D[N[a].id].inb.length)[0];
      select(i);
      return N[i].id;
    });
    await page.waitForTimeout(150);
    // The card is a segment of the page, docked in the search bar's grammar,
    // not a floating window: owner's instruction of 23.09.2026. It runs from the
    // search bar to the bottom at the right edge, on the bar's ground, with the
    // bar's divider on its open side. Its open action
    // is the Concept view icon.
    var dock = await page.evaluate(() => {
      const cs = e => getComputedStyle(e), c = document.getElementById('gcard'), bar = document.getElementById('askbar');
      const r = c.getBoundingClientRect(), o = c.querySelector('.open');
      return { top: r.top, barBottom: bar.getBoundingClientRect().bottom, right: r.right, bottom: r.bottom, win: innerWidth, winH: innerHeight,
               radius: cs(c).borderTopLeftRadius, shadow: cs(c).boxShadow, bg: cs(c).backgroundColor, barBg: cs(bar).backgroundColor,
               line: cs(c).borderLeftColor, barLine: cs(bar).borderBottomColor, lineW: cs(c).borderLeftWidth,
               openIcon: !!(o && o.querySelector('svg')), openText: o ? o.textContent.trim() : null };
    });
    check(Math.abs(dock.top - dock.barBottom) < 1 && Math.abs(dock.right - dock.win) < 1 && Math.abs(dock.bottom - dock.winH) < 1 &&
          dock.radius === '0px' && dock.shadow === 'none' && dock.bg === dock.barBg && dock.line === dock.barLine && dock.lineW === '1px',
          'the concept card is docked right, full height, in the search bar\'s ground and divider',
          'top ' + Math.round(dock.top) + ' vs bar ' + Math.round(dock.barBottom) + ', right ' + Math.round(dock.right) + ', bottom ' +
          Math.round(dock.bottom) + ', radius ' + dock.radius + ', shadow ' + dock.shadow + ', ground ' + dock.bg + ' vs ' + dock.barBg +
          ', line ' + dock.lineW + ' ' + dock.line + ' vs ' + dock.barLine);
    check(dock.openIcon && dock.openText === '', 'the card opens its concept with the Concept view icon, not a text button',
          'icon=' + dock.openIcon + ' text=' + JSON.stringify(dock.openText));
    await page.click('#gcard .open');
    await page.waitForTimeout(300);
    var landed = await page.evaluate(id => {
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
    // Since 23.09.2026 the concept page carries the header's two graph icons in
    // place of "Show in graph", one for each graph.
    await page.click('#main .g2');
    await page.waitForTimeout(300);
    var back = await page.evaluate(id => ({ graph: document.body.classList.contains('vg'), sel: sel === idx[id],
      card: getComputedStyle(document.getElementById('gcard')).display }), picked);
    check(back.graph && back.sel && back.card !== 'none', 'the Graph icon on a concept page returns to the Graph view with the concept selected',
          'graph view=' + back.graph + ' selected=' + back.sel + ' card=' + back.card);
    await page.evaluate(id => show(id), picked);
    await page.waitForTimeout(300);
    var icons = await page.evaluate(() => [...document.querySelectorAll('#main .gbtns button')].map(b =>
      b.className + ':' + (b.querySelector('svg') ? 'svg' : 'none')));
    check(icons.join() === 'ib g2:svg,ib g3:svg', 'a concept page shows the Graph and 3D icons, and nothing else there',
          icons.join(' ') || 'none');
    await page.click('#main .g3');
    await page.waitForTimeout(900);
    var back3 = await page.evaluate(id => { const g = document.getElementById('g3'), p = G3.project(idx[id]);
      return { v3: document.body.classList.contains('v3'), sel: sel === idx[id],
               card: getComputedStyle(document.getElementById('gcard')).display,
               off: p ? Math.hypot(p[0] - g.clientWidth / 2, p[1] - g.clientHeight / 2) : 1e9 }; }, picked);
    check(back3.v3 && back3.sel && back3.card !== 'none' && back3.off < 5,
          'the 3D icon on a concept page opens the 3D view with the concept selected and centred',
          '3D view=' + back3.v3 + ' selected=' + back3.sel + ' card=' + back3.card + ', ' + Math.round(back3.off) + 'px from centre');
    await page.click('#bGraph');
    await page.waitForTimeout(300);

    // Fit frames the graph inside the canvas. Until 16.09.2026 this checked that
    // nothing sat under the search box, which floated over the graph's top-left
    // corner where Gamma is; the box is the bar above the canvas now and covers
    // nothing. The claim that survives is the one that mattered — a concept whose
    // centre is off the canvas is a concept the reader cannot click — and it is
    // read from node centres rather than their marks, as it was before.
    await page.evaluate(() => { clearSel(); fit(); });
    await page.waitForTimeout(200);
    var under = await page.evaluate(() => {
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
    // A vault of a few concepts has most of them on the frame's edge after Fit,
    // outside the band this search allows, so the view steps out around its
    // middle until two are in the open. A large vault finds them at once.
    var two = await page.evaluate(() => {
      const g = gc.getBoundingClientRect();
      const find = () => { const out = [];
        for (const n of N) {
          if (hid(n)) continue;
          const [x, y] = sxy(n), px = g.left + x, py = g.top + y;
          if (x < 40 || x > gc.clientWidth - 380 || y < 90 || y > gc.clientHeight - 90) continue;
          if (document.elementFromPoint(px, py) !== gc || pick(n.x, n.y) !== n.i) continue;
          if (out.length && Math.hypot(out[0].x - px, out[0].y - py) < 120) continue;
          out.push({ i: n.i, x: px, y: py });
          if (out.length === 2) break;
        }
        return out; };
      let out = find();
      for (let k = 0; out.length < 2 && k < 4; k++) {
        sc *= 0.7; dirty = true; draw();
        out = find();
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
    var bs = await page.evaluate(() => ({ backing: gc.width, css: gc.clientWidth, dpr: window.devicePixelRatio || 1 }));
    check(bs.css === 1200 && Math.abs(bs.backing - bs.css * bs.dpr) < 2,
          'a window resized in the Concept view leaves the graph drawn at the new width',
          'backing ' + bs.backing + ' vs ' + Math.round(bs.css * bs.dpr) + ' at css ' + bs.css);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(250);
  }

  if (part('8')) {
    // 8. Escape lets go of a button it would otherwise ring. The owner reported
    // it on 09.09.2026 against the full-screen button. The Graph view button is
    // the same case: clicked, still focused, and Escape is the first keystroke
    // after. It was the Fit button until Fit went, 23.09.2026.
    // A real click, not element.click() through evaluate: only a real one moves
    // focus to the button, and without focus there is no ring to catch.
    await page.click('#bGraph');
    await page.waitForTimeout(150);
    var f1 = await page.evaluate(() => document.activeElement ? document.activeElement.id : '');
    check(f1 === 'bGraph', 'clicking a view button focuses it (the ring precondition)', 'activeElement=' + (f1 || 'body'));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    var f2 = await page.evaluate(() => document.activeElement ? document.activeElement.id : '');
    check(f2 !== 'bGraph', 'Escape in the graph leaves no focus ring on the button', 'activeElement=' + (f2 || 'body'));
    // Read the rule, not the computed style: a programmatic .focus() does not
    // set :focus-visible in Chromium, so getComputedStyle returned the default
    // outline colour (currentColor, the button's own text) and the check failed
    // while the page was correct. The claim being made is that the rule exists
    // and paints in the page's accent, so test that.
    var ring = await page.evaluate(() => {
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
    var typed = await page.evaluate(() => ({ sc, value: document.getElementById('q').value }));
    check(typed.value === 'f' && typed.sc === 3, 'typing f into the search does not refit the graph',
          'value=' + JSON.stringify(typed.value) + ' scale=' + typed.sc);
    await page.evaluate(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); q.blur(); });
    // The map can be turned. Owner's request of 08.10.2026: "i want to rotate on
    // the mac with the usual two-finger rotation gesture on the trackpad. if this
    // doesnt work, please come up with an idea". Chrome keeps that gesture from
    // the page, so the idea is the Option key with a two-finger swipe, which is a
    // wheel event with altKey. Safari gives the gesture itself, as gesture
    // events, and those are made by hand here. All of it is read from where the
    // page puts four concepts on the screen.
    var turn2d = 0;
    {
      await page.evaluate(() => { clearSel(); rot = 0; fit(); });
      const gb = await page.evaluate(() => { const b = gc.getBoundingClientRect(); return { l: b.left, t: b.top }; });
      const at = { x: gb.l + 500, y: gb.t + 400 };
      const where = () => page.evaluate(() => ({ rot, sc, pts: [0, .25, .5, .75].map(f => sxy(N[Math.floor(f * N.length)])) }));
      const before = await where();
      await page.mouse.move(at.x, at.y);
      await page.keyboard.down('Alt'); await page.mouse.wheel(0, -200); await page.keyboard.up('Alt');
      await page.waitForTimeout(200);
      const after = await where(), by = after.rot - before.rot;
      turn2d = by;
      const off = before.pts.map((q, i) => { const dx = q[0] - 500, dy = q[1] - 400;
        return Math.hypot(500 + dx * Math.cos(by) - dy * Math.sin(by) - after.pts[i][0], 400 + dx * Math.sin(by) + dy * Math.cos(by) - after.pts[i][1]); });
      check(by > .1 && after.sc === before.sc && Math.max(...off) < .5,
            'Option with a two-finger swipe turns the 2D map about the pointer, and does not zoom it',
            'turned ' + (by * 180 / Math.PI).toFixed(1) + ' degrees; four concepts stand where a turn about the pointer puts them, off by ' + Math.max(...off).toFixed(2) + 'px at most; scale ' + before.sc.toFixed(3) + ' before, ' + after.sc.toFixed(3) + ' after');
      // every name and every mark is drawn upright in the turned map: read from the
      // canvas's own transform at the moment a text or a mark is drawn
      const upright = await page.evaluate(() => new Promise(done => { const P = CanvasRenderingContext2D.prototype, f = P.fillText, sh = shp;
        let names = 0, slant = 0, marks = 0, tilted = 0; const bent = c => { const m = c.getTransform(); return Math.abs(m.b) > 1e-6 || Math.abs(m.c) > 1e-6; };
        P.fillText = function (...a) { if (this.canvas === gc) { names++; if (bent(this)) slant++; } return f.apply(this, a); };
        shp = function (c, ...a) { if (c.canvas === gc) { marks++; if (bent(c)) tilted++; } return sh(c, ...a); };
        dirty = true; requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => { P.fillText = f; shp = sh; done({ names, slant, marks, tilted, rot }); }))); }));
      check(upright.rot === after.rot && upright.names > 3 && upright.slant === 0 && upright.marks > 3 && upright.tilted === 0,
            'in a turned 2D map every name and every mark is drawn upright',
            upright.names + ' names drawn, ' + upright.slant + ' at a slant; ' + upright.marks + ' marks drawn, ' + upright.tilted + ' tilted');
      // a fit keeps the turn and frames the turned map, and a click still finds what is under the pointer
      const hit = await page.evaluate(() => { fit(); const all = N.filter(n => !hid(n)).map(n => ({ i: n.i, s: sxy(n), r: rEff(n) * sc }));
        const o = all.find(o => o.s[0] > 60 && o.s[0] < gc.clientWidth - 420 && o.s[1] > 90 && o.s[1] < gc.clientHeight - 60 &&
          all.every(q => q.i === o.i || Math.hypot(q.s[0] - o.s[0], q.s[1] - o.s[1]) > q.r + 12));
        const v = all.map(q => q.s), x0 = Math.min(...v.map(q => q[0])), y0 = Math.min(...v.map(q => q[1])), x1 = Math.max(...v.map(q => q[0])), y1 = Math.max(...v.map(q => q[1]));
        return { o, rot, left: x0 - 28, right: gc.clientWidth - 28 - x1, top: y0 - 76, bottom: gc.clientHeight - 28 - y1 }; });
      if (hit.o) { await page.mouse.click(gb.l + hit.o.s[0], gb.t + hit.o.s[1]); await page.waitForTimeout(200); }
      const picked = await page.evaluate(() => sel);
      check(hit.rot === after.rot && !!hit.o && picked === hit.o.i && Math.abs(hit.left - hit.right) < 1 && Math.abs(hit.top - hit.bottom) < 1 &&
            Math.min(hit.left, hit.top) > -1 && Math.min(hit.left, hit.top) < 1.5,
            'in a turned 2D map a fit keeps the turn and frames the whole map, and a click selects the concept under the pointer',
            'room left ' + hit.left.toFixed(1) + ', right ' + hit.right.toFixed(1) + ', top ' + hit.top.toFixed(1) + ', bottom ' + hit.bottom.toFixed(1) + '; clicked concept ' + (hit.o ? hit.o.i : 'none found') + ', selected ' + picked);
      await page.evaluate(() => clearSel());
      const ges = await page.evaluate(([x, y]) => { const ev = (t, r, z) => { const e = new Event(t, { bubbles: true, cancelable: true }); e.clientX = x; e.clientY = y; e.rotation = r; e.scale = z; gc.dispatchEvent(e); return e.defaultPrevented; };
        const r0 = rot, s0 = sc, w0 = world({ clientX: x, clientY: y }), kept = [ev('gesturestart', 0, 1), ev('gesturechange', 30, 1.5)];
        const mid = { dr: (rot - r0) * 180 / Math.PI, ds: sc / s0 }; kept.push(ev('gesturechange', -45, .5), ev('gestureend', -45, .5));
        const w1 = world({ clientX: x, clientY: y }); return { mid, dr: (rot - r0) * 180 / Math.PI, ds: sc / s0, moved: Math.hypot(w1[0] - w0[0], w1[1] - w0[1]), kept: kept.every(Boolean) }; }, [at.x, at.y]);
      check(Math.abs(ges.mid.dr - 30) < 1e-6 && Math.abs(ges.mid.ds - 1.5) < 1e-6 && Math.abs(ges.dr + 45) < 1e-6 && Math.abs(ges.ds - .5) < 1e-6 && ges.moved < 1e-6 && ges.kept,
            'the two-finger turn that Safari gives the page turns the 2D map by the gesture\'s angle and zooms it by the pinch, about the pointer',
            'at 30 degrees and a pinch of 1.5: ' + ges.mid.dr.toFixed(2) + ' degrees, ' + ges.mid.ds.toFixed(2) + ' times; on to -45 and 0.5: ' + ges.dr.toFixed(2) + ' degrees, ' + ges.ds.toFixed(2) + ' times; the place under the pointer moved ' + ges.moved.toFixed(4) + '; the page kept the gesture from the browser: ' + ges.kept);
      await page.evaluate(() => { rot = 0; fit(); });
    }
    // The 2D zoom goes far past its old limits of 0.08 and 14, owner's request
    // of 23.09.2026, and a double-click on empty space fits, as the help line
    // says now that the Fit button is gone.
    await page.evaluate(() => { fit(); });
    var gmid = await page.evaluate(() => { const b = gc.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; });
    await page.mouse.move(gmid.x, gmid.y);
    for (let k = 0; k < 40; k++) await page.mouse.wheel(0, -400);
    await page.waitForTimeout(200);
    var zin = await page.evaluate(() => sc);
    for (let k = 0; k < 80; k++) await page.mouse.wheel(0, 400);
    await page.waitForTimeout(200);
    var zout = await page.evaluate(() => sc);
    check(zin > 14 && zout < .08, 'the 2D graph zooms far past its old limits both ways',
          'in to ' + zin.toFixed(1) + 'x, out to ' + zout.toFixed(4) + 'x');
    var empty2 = await page.evaluate(() => { const b = gc.getBoundingClientRect();
      for (let y = 80; y < gc.clientHeight - 60; y += 37) for (let x = 60; x < gc.clientWidth - 400; x += 41) {
        const wx = (x - gc.clientWidth / 2) / sc - tx, wy = (y - gc.clientHeight / 2) / sc - ty;
        if (pick(wx, wy) < 0 && document.elementFromPoint(b.left + x, b.top + y) === gc) return { x: b.left + x, y: b.top + y };
      }
      return null; });
    await page.mouse.dblclick(empty2.x, empty2.y);
    await page.waitForTimeout(200);
    var sc2 = await page.evaluate(() => { const s0 = sc; fit(); return { dbl: s0, fit: sc }; });
    check(Math.abs(sc2.dbl - sc2.fit) < 1e-9, 'a double-click on empty space in the graph fits it',
          'scale ' + zout.toFixed(4) + ' to ' + sc2.dbl.toFixed(4) + ', Fit gives ' + sc2.fit.toFixed(4));

    // A selected concept's links wear their direction, owner's request of
    // 23.09.2026: blue arriving, orange leaving, a gradient for a pair linked
    // both ways. Read from the strokes the 2D graph actually makes, and the card
    // carries the legend. The concept with the most kinds of link, and each
    // check asks only for the kinds it has: a small vault may lack one.
    var dirNode = await page.evaluate(() => { let best = -1, bk = 0;
      N.forEach(n => { const d = D[n.id], k = [d.out.some(o => !D[o].out.includes(n.id)), d.inb.some(x => !d.out.includes(x)),
        d.out.some(o => D[o].out.includes(n.id))].filter(Boolean).length; if (k > bk) { bk = k; best = n.i; } });
      return best; });
    var kinds = await page.evaluate(i => { if (i < 0) return {}; const n = N[i], d = D[n.id];
      return { out: d.out.some(o => !D[o].out.includes(n.id)), inn: d.inb.some(x => !d.out.includes(x)), both: d.out.some(o => D[o].out.includes(n.id)) }; }, dirNode);
    var strokes = await page.evaluate(i => {
      const P = CanvasRenderingContext2D.prototype, orig = P.stroke, st = new Set();
      P.stroke = function () { if (this.globalAlpha === .85) st.add(typeof this.strokeStyle === 'string' ? this.strokeStyle : 'gradient'); return orig.apply(this, arguments); };
      select(i); draw(); P.stroke = orig;
      const lk = c => { const e = document.querySelector('#gcard .lk.' + c); return e ? getComputedStyle(e).backgroundColor : null; };
      const hex = v => { const [r, g, b] = v.match(/\d+/g).map(Number); return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join(''); };
      return { st: [...st], lin: css('--lin'), lout: css('--lout'), legIn: lk('in') && hex(lk('in')), legOut: lk('out') && hex(lk('out')) };
    }, dirNode);
  var wantS = [kinds.inn && strokes.lin, kinds.out && strokes.lout, kinds.both && 'gradient'].filter(Boolean);
  check(dirNode >= 0 && wantS.length > 0 && wantS.every(w => strokes.st.includes(w)) &&
          !strokes.st.some(x => x !== strokes.lin && x !== strokes.lout && x !== 'gradient'),
          'the 2D graph draws a selection\'s links blue in, orange out, and a gradient both ways',
          'strokes ' + strokes.st.join(' '));
  check((strokes.legIn || strokes.legOut) && (!strokes.legIn || strokes.legIn === strokes.lin) && (!strokes.legOut || strokes.legOut === strokes.lout),
        'the card\'s list headings carry the link colours as a legend',
          'in ' + strokes.legIn + ', out ' + strokes.legOut);
    await page.evaluate(() => clearSel());
    // Hovering a concept lights its links the same way, without dimming the
    // rest, as in the 3D view: owner's request of 23.09.2026.
    var hov2 = await page.evaluate(i => {
      const P = CanvasRenderingContext2D.prototype, orig = P.stroke, st = new Map();
      P.stroke = function () { const k = this.globalAlpha + ' ' + (typeof this.strokeStyle === 'string' ? this.strokeStyle : 'gradient'); st.set(k, (st.get(k) || 0) + 1); return orig.apply(this, arguments); };
      hov = i; draw(); P.stroke = orig; hov = -1;
      return { st: [...st.keys()], lin: css('--lin'), lout: css('--lout'), mut: css('--mut'),
               others: L.some(([a, b]) => a !== i && b !== i && !hid(N[a]) && !hid(N[b])) };
    }, dirNode);
    var wantH = [kinds.inn && '0.7 ' + hov2.lin, kinds.out && '0.7 ' + hov2.lout, kinds.both && '0.7 gradient',
                   hov2.others && '0.28 ' + hov2.mut].filter(Boolean);
    check(wantH.length > 0 && wantH.every(w => hov2.st.includes(w)),
          'hovering a concept in the graph lights its links in their colours, and dims nothing',
          hov2.st.join(', '));
    // The moving light, as in the logo: a faint bead on links everywhere, a
    // bright one in the link's colour on the focus's links. Owner's requests of
    // 23.09.2026. Counted over sixty frames at fixed times, not one live frame:
    // on a small vault a single frame may by chance show no faint bead at all.
    var beads2 = await page.evaluate(i => {
      const P = CanvasRenderingContext2D.prototype, orig = P.fill, seen = {};
      P.fill = function () { if (this.__arc) { const k = typeof this.fillStyle === 'string' ? this.fillStyle : 'x'; seen[k] = (seen[k] || 0) + 1; } return orig.apply(this, arguments); };
      const oa = P.arc; P.arc = function () { this.__arc = true; return oa.apply(this, arguments); };
      const ob = P.beginPath; P.beginPath = function () { this.__arc = false; return ob.apply(this, arguments); };
      const pn = performance.now; let T = 0; performance.now = () => T;
      const frames = () => { for (let k = 0; k < 60; k++) { T = k * 333; draw(); } };
      frames(); const none = { ...seen };
      for (const k in seen) delete seen[k];
      select(i); frames(); const focus = { ...seen };
      performance.now = pn; P.fill = orig; P.arc = oa; P.beginPath = ob; clearSel();
      return { none, focus, fg: css('--fg'), lin: css('--lin'), lout: css('--lout') };
    }, dirNode);
    check((beads2.none[beads2.fg] || 0) > 0 && (!(kinds.inn || kinds.both) || (beads2.focus[beads2.lin] || 0) > 0) &&
          (!(kinds.out || kinds.both) || (beads2.focus[beads2.lout] || 0) > 0),
          'the graph carries moving light on its links, and brighter beads in the link colours on a selection\'s',
          (beads2.none[beads2.fg] || 0) + ' faint beads with nothing selected; with a selection ' + (beads2.focus[beads2.lin] || 0) +
          ' blue and ' + (beads2.focus[beads2.lout] || 0) + ' orange');
    // and it keeps moving: the graph redraws on its own, but never for a
    // reader who has asked for less motion
    var loop2 = async () => page.evaluate(() => new Promise(r => { const o = draw; let n = 0;
      draw = function () { n++; return o.apply(this, arguments); }; setTimeout(() => { draw = o; r(n); }, 800); }));
    var moving2 = await loop2();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.waitForTimeout(200);
    var still2 = await loop2();
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    check(moving2 > 10 && still2 === 0, 'the graph\'s light moves on its own, and stands still for reduced motion',
          moving2 + ' frames in 0.8s, ' + still2 + ' with reduced motion');
  }

  if (part('8b')) {
    // 8b. The 3D view, 23.09.2026: the same map with depth, in WebGL2 on its own
    // canvas. Everything here goes through the page as a reader would reach it —
    // the button, real clicks, real keys — and reads back through G3, the view's
    // test handle, because a WebGL canvas cannot be read with getImageData.
    // The header first: the third view button cost 42px, and at 1440px that
    // wrapped the employer row of categories onto a second line, which no check
    // saw. The row is one line of 24px chips.
    var hdr = await page.evaluate(() => Math.round(document.querySelector('#legend .lrow').getBoundingClientRect().height));
    check(hdr <= 30, 'the employer categories stay on one line at 1440px', 'row height ' + hdr + 'px');
    await page.click('#b3d');
    await page.waitForTimeout(2200);
    // Framed first: the concept page's 3D icon earlier left the camera close to
    // one concept, and since the bases became spheres, 23.09.2026, a close camera
    // sits inside the map with a few concepts behind it, rightly not drawn.
    await page.evaluate(() => G3.fit());
    await page.waitForTimeout(700);
    var v3 = await page.evaluate(() => {
      const box = id => document.getElementById(id).getBoundingClientRect().toJSON();
      const g = document.getElementById('g3');
      return { ok: G3.ok, opaque: G3.opaque, v3: document.body.classList.contains('v3'), on: document.getElementById('b3d').classList.contains('on'),
               pressed: document.getElementById('b3d').getAttribute('aria-pressed'), g3: box('g3'), gc: box('gc'), main: box('main'),
               top: box('askbar'), win: innerWidth, winH: innerHeight, backing: g.width, css: g.clientWidth,
               dpr: Math.min(window.devicePixelRatio || 1, 2), drawn: G3.drawn,
               showing: N.filter(n => !hid(n)).length, zs: G3.cam.zs,
               zspread: (() => { const z = N.map(n => D[n.id].z); const m = z.reduce((a, b) => a + b, 0) / z.length;
                 return Math.sqrt(z.reduce((a, b) => a + (b - m) ** 2, 0) / z.length); })() };
    });
    check(v3.ok && v3.v3 && v3.on && v3.pressed === 'true', 'the 3D button opens the 3D view, on WebGL2',
          'webgl2=' + v3.ok + ' body.v3=' + v3.v3 + ' pressed=' + v3.pressed);
    check(v3.g3.left === 0 && Math.abs(v3.g3.width - v3.win) < 1 && Math.abs(v3.g3.top - v3.top.bottom) < 1 &&
          Math.abs(v3.g3.bottom - v3.winH) < 1 && v3.gc.width === 0 && v3.main.width === 0,
          'the 3D view takes the whole window below the search bar, and nothing else shows',
          'canvas ' + Math.round(v3.g3.width) + 'x' + Math.round(v3.g3.height) + ' at top ' + Math.round(v3.g3.top) +
          ', 2D ' + v3.gc.width + ', page ' + v3.main.width);
    // The owner saw the links vanish and a coloured square round every mark on
    // screen, while this check's headless browser drew both correctly. The glow
    // and the links are colour with no alpha, which a see-through canvas cannot
    // hold. The canvas must be opaque; what it looks like here proves nothing.
    check(v3.opaque, 'the 3D canvas is opaque, so its glow and links cannot vanish or box on screen',
          'alpha=' + !v3.opaque);
    // A faint square round every mark on the owner's GPU, invisible here: the
    // shader sampled its shape sheet inside an if, where a GPU may choose any
    // blur level. No pixel this browser draws can show it, so the source is read.
    var branchy = await page.evaluate(() => [...document.scripts].map(s => s.textContent).join('')
      .match(/\bif\s*\([^;{}]*\)\s*[\w.]+\s*=\s*texture\s*\(/g) || []);
    check(branchy.length === 0, 'no 3D shader samples a texture inside an if', branchy[0]);
    // The shape sheet grew from four rows to five on 27.09.2026, when a
    // seventeenth category arrived. The sheet's rows, the shader's divisor and
    // the number of shapes have to agree, or every mark below the first row
    // reads another shape's cell; no drawn pixel here says which shape is right.
    var sheet = await page.evaluate(() => { const src = [...document.scripts].map(s => s.textContent).join('');
      const rows = (src.match(/a\.height=CELL\*(\d+)/) || [])[1], div = (src.match(/\/vec2\(4\.,(\d+)\.\)/) || [])[1];
      return { rows: +rows, div: +div, shapes: SHAPES.length, cats: CATS.length }; });
  check(sheet.rows === sheet.div && sheet.shapes <= 4 * sheet.rows && sheet.shapes >= sheet.cats,
          'the 3D shape sheet, its shader and the categories agree',
          sheet.rows + ' rows, shader divides by ' + sheet.div + ', ' + sheet.shapes + ' shapes for ' + sheet.cats + ' categories');
    check(Math.abs(v3.backing - v3.css * v3.dpr) < 2, 'the 3D canvas is drawn at its size times the pixel ratio',
          'backing ' + v3.backing + ' vs ' + Math.round(v3.css * v3.dpr));
  check(v3.drawn === v3.showing && v3.zs === 1 && v3.zspread > 0,
          'the 3D view draws every showing concept, lifted to full depth',
          v3.drawn + ' drawn of ' + v3.showing + ', depth scale ' + v3.zs + ', depth spread ' + Math.round(v3.zspread));
    // Each large knowledge base is a ball, not a disc: owner's request of
    // 23.09.2026. Its spread in depth matches its spread across, within a margin.
    var balls = await page.evaluate(() => { const out = [];
      for (const kb of KB_ALL) { const ns = N.filter(n => n.kb === kb); if (ns.length < 100) continue;
        const sd = f => { const v = ns.map(f), m = v.reduce((a, b) => a + b, 0) / v.length; return Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length); };
        out.push([kb, sd(n => D[n.id].z) / ((sd(n => n.x) + sd(n => n.y)) / 2)]); }
      return out; });
  check(balls.every(([, r]) => r > .75 && r < 1.3),
        'each large knowledge base is a sphere in 3D, as deep as it is wide' + (balls.length ? '' : ' (none has 100 concepts to measure yet)'),
          balls.map(([k, r]) => k.replace('_kb', '') + ' ' + r.toFixed(2)).join(', '));
    // Chroma, for the reason the 2D check gives: links alone are colour too, so
    // the bar is set on strongly saturated pixels, which only the concepts and
    // their glow make. Read from a screenshot, the only way to see WebGL output.
  // Read where the concepts are, not counted over the whole canvas: with a
  // handful of concepts the links and glow alone came within a few samples of
  // the count with the concepts drawn, so no fixed bar could tell the two
  // apart. Most showing concepts must carry bright colour at their centre.
  // Calibrated on two bases of four: drawn, every concept read 158 or more
  // at its brightest; with the concepts left out, one of eight did, where a
  // base's name lay over it.
    {
    const pts = await page.evaluate(() => N.filter(n => !hid(n)).map(n => G3.project(n.i)).filter(Boolean));
      const png = await page.screenshot({ clip: { x: v3.g3.left, y: v3.g3.top, width: v3.g3.width, height: v3.g3.height } });
      const px = pngPixels(png);
    let lit = 0;
    for (const [cx, cy] of pts) {
      let hit = false;
      for (let dy = -2; dy <= 2 && !hit; dy++)
        for (let dx = -2; dx <= 2 && !hit; dx++) {
          const x = Math.round(cx) + dx, y = Math.round(cy) + dy;
          if (x < 0 || y < 0 || x >= Math.floor(v3.g3.width) || y >= Math.floor(v3.g3.height)) continue;
          const [r, g, b] = px(x, y);
          if (Math.max(r, g, b) > 150 && Math.max(r, g, b) - Math.min(r, g, b) > 40) hit = true;
        }
      if (hit) lit++;
    }
    check(pts.length > 0 && lit >= pts.length / 2, '3D view paints saturated concepts, not just links and glow',
          lit + ' of ' + pts.length + ' concepts carry bright colour at their centre');
    }
    // Fit frames every showing concept inside the canvas, from any direction.
    await page.evaluate(() => { G3.orient(1.1, .6); G3.cam.d *= 3; G3.fit(); });
    await page.waitForTimeout(800);
    var out3 = await page.evaluate(() => {
      const g = document.getElementById('g3');
      return N.filter(n => { if (hid(n)) return false; const p = G3.project(n.i);
        return !p || p[0] < 0 || p[1] < 0 || p[0] > g.clientWidth || p[1] > g.clientHeight; }).length;
    });
    check(out3 === 0, 'Fit in 3D frames every concept inside the canvas, turned and tilted', out3 + ' concepts outside it');
    // Real clicks, as in the 2D graph: select, move the selection, let go.
    var two3 = await page.evaluate(() => {
      const g = document.getElementById('g3'), b = g.getBoundingClientRect(), out = [];
      for (const n of N) {
        if (hid(n)) continue;
        const p = G3.project(n.i); if (!p) continue;
        const [x, y] = p;
        if (x < 40 || x > g.clientWidth - 380 || y < 40 || y > g.clientHeight - 90) continue;
        if (document.elementFromPoint(b.left + x, b.top + y) !== g || G3.pick(x, y) !== n.i) continue;
        if (out.length && Math.hypot(out[0].x - b.left - x, out[0].y - b.top - y) < 120) continue;
        out.push({ i: n.i, x: b.left + x, y: b.top + y });
        if (out.length === 2) break;
      }
      return out;
    });
    if (two3.length < 2) check(false, 'two concepts in the open to click in 3D', two3.length + ' found');
    else {
      const [a, b] = two3, seen = [];
      for (const p of [a, b, b]) {
        await page.mouse.click(p.x, p.y);
        await page.waitForTimeout(150);
        seen.push(await page.evaluate(() => ({ sel, v3: document.body.classList.contains('v3'),
          card: getComputedStyle(document.getElementById('gcard')).display })));
      }
      const say = s => 'selected ' + s.sel + ', card ' + s.card + ', 3D ' + s.v3;
      check(seen[0].sel === a.i && seen[0].card !== 'none' && seen[1].sel === b.i && seen[1].card !== 'none',
            'a click selects a concept in 3D, and a click on another moves the selection',
            'wanted ' + a.i + ' then ' + b.i + ': ' + say(seen[0]) + '; ' + say(seen[1]));
      check(seen[2].sel === -1 && seen[2].card === 'none' && seen[2].v3,
            'a second click on the selected concept in 3D lets it go', say(seen[2]));
      // A drag turns the map and selects nothing.
      const q0 = await page.evaluate(() => G3.q());
      await page.mouse.move(a.x, a.y);
      await page.mouse.down();
      for (let k = 1; k <= 10; k++) await page.mouse.move(a.x + k * 20, a.y + k * 4);
      await page.mouse.up();
      await page.waitForTimeout(150);
      const turned = await page.evaluate(q => ({ dy: G3.angle(q), sel }), q0);
      check(turned.dy > .3 && turned.sel === -1, 'a drag in 3D turns the map and selects nothing',
            'turned ' + turned.dy.toFixed(2) + ' rad, selected ' + turned.sel);
      await page.evaluate(() => { G3.orient(.34, -.46); G3.fit(); });
      await page.waitForTimeout(800);
      // Turned and refitted, the first concept can sit behind another at its own
      // point: the week's links of 27.09.2026 put ID CxS in front of it. So the
      // double-click goes to a concept that is on top where it is drawn, the
      // first one clicked if it still is.
      const pa = await page.evaluate(i => { const g = document.getElementById('g3'), b = g.getBoundingClientRect();
        for (const j of [i, ...N.map(n => n.i)]) { if (hid(N[j])) continue; const p = G3.project(j); if (!p) continue;
          if (p[0] < 40 || p[0] > g.clientWidth - 380 || p[1] < 40 || p[1] > g.clientHeight - 90) continue;
          if (G3.pick(p[0], p[1]) === j && document.elementFromPoint(b.left + p[0], b.top + p[1]) === g) return { x: b.left + p[0], y: b.top + p[1], i: j }; }
        return null; }, a.i);
      await page.mouse.dblclick(pa.x, pa.y);
      await page.waitForTimeout(300);
      const dbl3 = await page.evaluate(i => ({ concepts: document.body.classList.contains('vc'),
        h1: (document.querySelector('#main h1') || {}).textContent, want: D[N[i].id].t, sel }), pa.i);
      check(dbl3.concepts && dbl3.h1 === dbl3.want && dbl3.sel === pa.i,
            'a double-click in 3D opens the concept and keeps it selected',
            'concept view=' + dbl3.concepts + ' page=' + dbl3.h1 + ' selected ' + dbl3.sel + ' of ' + pa.i);
      // A window resized while the Concept view shows, then back to 3D.
      await page.setViewportSize({ width: 1200, height: 800 });
      await page.waitForTimeout(250);
      await page.click('#b3d');
      await page.waitForTimeout(400);
      const bs3 = await page.evaluate(() => { const g = document.getElementById('g3');
        return { backing: g.width, css: g.clientWidth, dpr: Math.min(window.devicePixelRatio || 1, 2), sel,
                 card: getComputedStyle(document.getElementById('gcard')).display }; });
      check(bs3.css === 1200 && Math.abs(bs3.backing - bs3.css * bs3.dpr) < 2,
            'a window resized in the Concept view leaves the 3D view drawn at the new width',
            'backing ' + bs3.backing + ' vs ' + Math.round(bs3.css * bs3.dpr) + ' at css ' + bs3.css);
      check(bs3.sel === pa.i && bs3.card !== 'none', 'back in 3D the concept is still selected, with its card',
            'selected ' + bs3.sel + ', card ' + bs3.card);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(250);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(150);
      const esc3 = await page.evaluate(() => ({ sel, card: getComputedStyle(document.getElementById('gcard')).display }));
      check(esc3.sel === -1 && esc3.card === 'none', 'Escape in 3D lets go of the selection', 'selected ' + esc3.sel + ', card ' + esc3.card);
    }
    // The 3D view rolls: the picture turned in its own plane, by the same two
    // ways as the 2D map and the same way round. Owner's request of 08.10.2026.
    {
      await page.evaluate(() => { clearSel(); G3.orient(.34, -.46); G3.fit(); });
      await page.waitForTimeout(700);
      const pts3 = () => page.evaluate(() => { const g = document.getElementById('g3');
        return { c: [g.clientWidth / 2, g.clientHeight / 2], d: G3.cam.d, t: G3.cam.t.slice(),
          p: [0, .25, .5, .75].map(f => { const n = N[Math.floor(f * N.length)]; return G3.at([n.x, -n.y, D[n.id].z || 0], true); }) }; });
      const m3 = await page.evaluate(() => { const b = document.getElementById('g3').getBoundingClientRect(); return { x: b.left + b.width / 2 + 130, y: b.top + b.height / 2 + 70 }; });
      const a3 = await pts3();
      await page.mouse.move(m3.x, m3.y);
      await page.keyboard.down('Alt'); await page.mouse.wheel(0, -200); await page.keyboard.up('Alt');
      await page.waitForTimeout(300);
      const b3 = await pts3();
      const turns = a3.p.map((q, i) => { let a = Math.atan2(b3.p[i][1] - a3.c[1], b3.p[i][0] - a3.c[0]) - Math.atan2(q[1] - a3.c[1], q[0] - a3.c[0]);
        if (a > Math.PI) a -= 2 * Math.PI; if (a < -Math.PI) a += 2 * Math.PI;
        return { a, dr: Math.abs(Math.hypot(b3.p[i][0] - a3.c[0], b3.p[i][1] - a3.c[1]) - Math.hypot(q[0] - a3.c[0], q[1] - a3.c[1])) }; });
      check(turns.every(t => Math.abs(t.a - turn2d) < 1e-3 && t.dr < .5) && turn2d > .1 && b3.d === a3.d && b3.t.every((v, k) => v === a3.t[k]),
            'Option with a two-finger swipe rolls the 3D view about the middle of the picture, the same way round as the 2D map, and neither zooms nor moves it',
            'four concepts turned ' + turns.map(t => (t.a * 180 / Math.PI).toFixed(1)).join(', ') + ' degrees about the middle, the 2D map ' + (turn2d * 180 / Math.PI).toFixed(1) + '; their distance from the middle changed by ' + Math.max(...turns.map(t => t.dr)).toFixed(2) + 'px at most; the eye\'s distance ' + Math.round(a3.d) + ' before, ' + Math.round(b3.d) + ' after');
      const g3ges = await page.evaluate(() => { const g = document.getElementById('g3'), ev = (t, r, z) => { const e = new Event(t, { bubbles: true, cancelable: true }); e.rotation = r; e.scale = z; g.dispatchEvent(e); return e.defaultPrevented; };
        const dir = () => { const e = G3.eye(); return [0, 1, 2].map(k => (e[k] - G3.cam.t[k]) / G3.cam.d); };
        const q0 = G3.q(), d0 = G3.cam.d, s0 = dir(), kept = [ev('gesturestart', 0, 1), ev('gesturechange', 90, 2), ev('gestureend', 90, 2)], s1 = dir();
        return { angle: G3.angle(q0) * 180 / Math.PI, d: G3.cam.d / d0, sight: Math.hypot(s1[0] - s0[0], s1[1] - s0[1], s1[2] - s0[2]), kept: kept.every(Boolean) }; });
      check(Math.abs(g3ges.angle - 90) < 1e-3 && Math.abs(g3ges.d - .5) < 1e-6 && g3ges.sight < 1e-6 && g3ges.kept,
            'the two-finger turn that Safari gives the page rolls the 3D view by the gesture\'s angle about the line of sight, and its pinch zooms',
            'at 90 degrees and a pinch of 2: the view turned ' + g3ges.angle.toFixed(2) + ' degrees, the eye stands at ' + g3ges.d.toFixed(2) + ' of its distance, the line of sight moved ' + g3ges.sight.toExponential(1) + '; the page kept the gesture from the browser: ' + g3ges.kept);
    }
    // Endless in every direction, owner's requests of 23.09.2026. A vertical
    // drag carries the view over the top until the camera is upside down, which
    // a yaw and pitch camera cannot reach; the wheel flies on through the map
    // past where the orbit point was; and zooming out does not stop at a few
    // map widths.
    await page.evaluate(() => { clearSel(); G3.orient(0, 0); G3.fit(); });
    await page.waitForTimeout(700);
    var c3 = await page.evaluate(() => { const b = document.getElementById('g3').getBoundingClientRect();
      return { x: b.left + b.width * .3, y: b.top + 60, h: b.height }; });
    await page.mouse.move(c3.x, c3.y);
    await page.mouse.down();
    for (let k = 1; k <= 20; k++) await page.mouse.move(c3.x, c3.y + k * 30);
    // read before letting go: the turn's momentum carries on after release
    var over = await page.evaluate(() => G3.up()[1]);
    await page.mouse.up();
    await page.mouse.move(5, 5);
    await page.waitForTimeout(600);
    check(over < 0, 'a drag in 3D turns the map over the top, endlessly', 'camera up y=' + over.toFixed(2) + ' after a 600px drag');
    await page.evaluate(() => { G3.orient(.34, -.46); G3.fit(); });
    await page.waitForTimeout(700);
    var fly = await page.evaluate(() => ({ eye: G3.eye(), d: G3.cam.d }));
    var mid = await page.evaluate(() => { const b = document.getElementById('g3').getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; });
    await page.mouse.move(mid.x, mid.y);
    for (let k = 0; k < 60; k++) await page.mouse.wheel(0, -400);
    await page.waitForTimeout(300);
    var flown = await page.evaluate(e0 => { const e = G3.eye(); return Math.hypot(e[0] - e0[0], e[1] - e0[1], e[2] - e0[2]); }, fly.eye);
    check(flown > fly.d * 1.2, 'scrolling in 3D flies on through the map instead of stopping',
          'the eye travelled ' + Math.round(flown) + ', the map was ' + Math.round(fly.d) + ' away');
    for (let k = 0; k < 60; k++) await page.mouse.wheel(0, 400);
    await page.waitForTimeout(300);
    var outD = await page.evaluate(() => ({ d: G3.cam.d, r: (() => { let r = 0; for (const n of N) r = Math.max(r, Math.abs(n.x), Math.abs(n.y)); return r; })() }));
    check(outD.d > outD.r * 20, 'scrolling out in 3D goes far past the old limit',
          'distance ' + Math.round(outD.d) + ' against a map radius of about ' + Math.round(outD.r));
    // A double-click on empty space fits, as the help line says, in 3D.
    var empty3 = await page.evaluate(() => { const g = document.getElementById('g3'), b = g.getBoundingClientRect();
      for (let y = 80; y < g.clientHeight - 60; y += 37) for (let x = 60; x < g.clientWidth - 400; x += 41)
        if (G3.pick(x, y) < 0 && document.elementFromPoint(b.left + x, b.top + y) === g) return { x: b.left + x, y: b.top + y };
      return null; });
    var dFar = await page.evaluate(() => G3.cam.d);
    await page.mouse.dblclick(empty3.x, empty3.y);
    await page.waitForTimeout(700);
    var dFit = await page.evaluate(() => ({ d: G3.cam.d, v3: document.body.classList.contains('v3') }));
    check(dFit.v3 && dFit.d < dFar * .5, 'a double-click on empty space in 3D fits the view',
          'distance ' + Math.round(dFar) + ' to ' + Math.round(dFit.d));
    // `f` frames the 3D view, and never while typing.
    await page.evaluate(() => { G3.cam.d *= 4; document.activeElement && document.activeElement.blur(); });
    var far3 = await page.evaluate(() => G3.cam.d);
    await page.keyboard.press('f');
    await page.waitForTimeout(700);
    var fit3 = await page.evaluate(() => G3.cam.d);
    check(fit3 < far3 * .6, 'f frames the 3D view', 'distance ' + Math.round(far3) + ' to ' + Math.round(fit3));
    await page.evaluate(() => { G3.cam.d = 99999; });
    await page.click('#q');
    await page.keyboard.type('f');
    await page.waitForTimeout(600);
    var typed3 = await page.evaluate(() => ({ d: G3.cam.d, value: document.getElementById('q').value }));
    check(typed3.value === 'f' && typed3.d === 99999, 'typing f into the search does not refit the 3D view',
          'value=' + JSON.stringify(typed3.value) + ' distance=' + typed3.d);
    await page.evaluate(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); q.blur(); G3.fit(); });
    await page.waitForTimeout(700);
    // A hidden knowledge base leaves the 3D view as it leaves the 2D one.
    // The last knowledge base is hidden; with only one there is nothing to hide,
    // since the last one showing always stays on.
    var kbOff3 = await page.evaluate(async () => {
      const kb = KB_ALL.length > 1 ? KB_ALL[KB_ALL.length - 1] : null;
      if (kb) offKB.add(kb); dirty = true;
      await new Promise(r => setTimeout(r, 200));
      const r = { kb, drawn: G3.drawn, showing: N.filter(n => !hid(n)).length, inKb: kb ? N.filter(n => n.kb === kb).length : 0 };
      if (kb) offKB.delete(kb); dirty = true;
      await new Promise(r => setTimeout(r, 200));
      r.back = G3.drawn; r.all = N.filter(n => !hid(n)).length;
      return r;
    });
    check(kbOff3.drawn === kbOff3.showing && kbOff3.drawn === kbOff3.all - kbOff3.inKb && kbOff3.back === kbOff3.all,
          'a hidden knowledge base leaves the 3D view, and comes back' + (kbOff3.kb ? '' : ' (one knowledge base: nothing to hide)'),
          kbOff3.drawn + ' drawn with ' + (kbOff3.kb || 'none') + ' hidden, ' + kbOff3.back + ' after, of ' + kbOff3.all);
    // The same colours in 3D, read from the link colours the view uploads.
    var cols3 = await page.evaluate(i => {
      if (i < 0) return {};
      select(i); dirty = true;
      return new Promise(r => setTimeout(() => {
        const d = D[N[i].id], id = N[i].id;
        const h = x => { x = x.replace('#', ''); return [0, 2, 4].map(k => parseInt(x.substr(k, 2), 16)); };
        const outOnly = d.out.find(o => !D[o].out.includes(id)), inOnly = d.inb.find(x => !d.out.includes(x)),
              both = d.out.find(o => D[o].out.includes(id));
        r({ out: G3.linkCols(idx[outOnly]), inn: G3.linkCols(idx[inOnly]), both: G3.linkCols(idx[both]),
            lin: h(css('--lin')), lout: h(css('--lout')) });
      }, 200));
    }, dirNode);
    var rgbIs = (a, b) => !!a && a.every((v, k) => Math.abs(v - b[k]) <= 2);
  check((!kinds.out || (rgbIs(cols3.out.focus, cols3.lout) && rgbIs(cols3.out.other, cols3.lout))) &&
        (!kinds.inn || (rgbIs(cols3.inn.focus, cols3.lin) && rgbIs(cols3.inn.other, cols3.lin))) &&
        (!kinds.both || (rgbIs(cols3.both.focus, cols3.lout) && rgbIs(cols3.both.other, cols3.lin))) && dirNode >= 0,
          'the 3D view colours a selection\'s links blue in, orange out, orange to blue both ways',
          JSON.stringify({ out: cols3.out, inn: cols3.inn, both: cols3.both }));
    // The moving light in 3D: the focus's links flow the way they point, and
    // every other link carries its own faint flow, all read from what the view
    // uploads. Reduced motion stops all of it.
    // a wheel tick first, so the idle drift cannot be what keeps it drawing
    { const b = await page.evaluate(() => { const r = document.getElementById('g3').getBoundingClientRect(); return { x: r.left + 200, y: r.top + 200 }; });
      await page.mouse.move(b.x, b.y); await page.mouse.wheel(0, 1); await page.mouse.move(5, 5); await page.waitForTimeout(100); }
    var flow3 = await page.evaluate(i => i < 0 ? {} : new Promise(r => { select(i); dirty = true; setTimeout(() => {
        const d = D[N[i].id], id = N[i].id;
        const res = { out: G3.flow(idx[d.out.find(o => !D[o].out.includes(id))]), inn: G3.flow(idx[d.inb.find(x => !d.out.includes(x))]),
                      both: G3.flow(idx[d.out.find(o => D[o].out.includes(id))]) };
        clearSel(); dirty = true;
        res.pairs = new Set(L.filter(([a, b]) => !hid(N[a]) && !hid(N[b])).map(([a, b]) => Math.min(a, b) + '-' + Math.max(a, b))).size;
        setTimeout(() => { res.ambient = G3.flowing(); res.f0 = G3.frames;
          setTimeout(() => { res.f1 = G3.frames; r(res); }, 600); }, 150);
      }, 200); }), dirNode);
    check((!kinds.out || flow3.out === 'out') && (!kinds.inn || flow3.inn === 'in') && (!kinds.both || flow3.both === 'both'),
          'the 3D view\'s light runs out along outbound links, in along inbound, both ways on a pair',
          'outbound ' + flow3.out + ', inbound ' + flow3.inn + ', both ' + flow3.both);
    check(flow3.ambient > 0 && flow3.ambient === flow3.pairs && flow3.f1 - flow3.f0 > 10, 'the 3D view carries moving light on all its links, and keeps drawing it',
          flow3.ambient + ' of ' + flow3.pairs + ' links flowing, ' + (flow3.f1 - flow3.f0) + ' frames in 0.6s');
    // A bead is a round dot, the same on screen in 3D as in 2D: owner's choice
    // of 23.09.2026, after the 3D beads came out as streaks as long as a share of
    // their link. With the clock stopped, each white bead core in a screenshot is
    // measured for how stretched it is — about 1 for a dot, 3 or more for a streak.
    var shape = await page.evaluate(() => { const i = N.reduce((b, n) => D[n.id].inb.length > D[N[b].id].inb.length ? n.i : b, 0);
      // brought close first, as the card's links do: on a small vault fitted
      // whole, a concept's links are a few pixels long and hide their beads
      // and alone: the fog is measured from the middle of what shows, which with
      // several bases is empty space between them, and would grey the bead cores
      window.__hidOthers = KB_ALL.filter(k => k !== N[i].kb && !offKB.has(k)); window.__hidOthers.forEach(k => offKB.add(k));
      G3.freeze(12.3); select(i); G3.focus(i); dirty = true;
      return new Promise(r => setTimeout(() => { const g = document.getElementById('g3').getBoundingClientRect(), p = G3.project(i);
        r({ x: g.left, y: g.top, w: g.width, h: g.height, hx: p ? p[0] : -1e4, hy: p ? p[1] : -1e4 }); }, 1000)); });
    {
      // nine stopped moments along the beads' path: on a small vault any one
      // moment may put every bead under a mark; and only cores of five pixels or
      // more are measured, since a core half under a mark looks stretched
      const el = [];
      for (let k = 0; k < 9; k++) { const t = 12.3 + k * .45;
      await page.evaluate(t => G3.freeze(t), t);
      await page.waitForTimeout(150);
      const png = await page.screenshot({ clip: { x: shape.x, y: shape.y, width: shape.w, height: shape.h } });
      const px = pngPixels(png), W = Math.floor(shape.w), H = Math.floor(shape.h), seen = new Uint8Array(W * H);
      const white = (x, y) => { const [r, g, b] = px(x, y); return r > 240 && g > 240 && b > 240; };
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
        if (seen[y * W + x] || !white(x, y) || Math.hypot(x - shape.hx, y - shape.hy) < 25) continue;   // the hub's own mark; 90 in the source vault, where hundreds of links pile to white round it
        const st = [[x, y]], pts = []; seen[y * W + x] = 1;
        while (st.length) { const [cx, cy] = st.pop(); pts.push([cx, cy]);
          for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const nx = cx + dx, ny = cy + dy;
            if (nx >= 0 && ny >= 0 && nx < W && ny < H && !seen[ny * W + nx] && white(nx, ny)) { seen[ny * W + nx] = 1; st.push([nx, ny]); } } }
        if (pts.length < 5 || pts.length > 60) continue;
        const mx = pts.reduce((a, p) => a + p[0], 0) / pts.length, my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
        let sxx = .25, syy = .25, sxy = 0; for (const [a, b] of pts) { sxx += (a - mx) ** 2 / pts.length; syy += (b - my) ** 2 / pts.length; sxy += (a - mx) * (b - my) / pts.length; }
        const t2 = (sxx + syy) / 2, d = Math.sqrt(((sxx - syy) / 2) ** 2 + sxy * sxy);
        el.push(Math.sqrt((t2 + d) / (t2 - d)));
      }
      }
      el.sort((a, b) => a - b);
      const med = el.length ? el[el.length >> 1] : 99;
      check(el.length >= 1 && med < 1.8, '3D beads are round dots, not streaks', el.length + ' bead cores, median stretch ' + med.toFixed(2));
      await page.evaluate(() => { (window.__hidOthers || []).forEach(k => offKB.delete(k)); dirty = true; });
    }
    await page.evaluate(() => { G3.freeze(null); clearSel(); G3.fit(); });
    await page.waitForTimeout(500);
    // The drift runs with a concept selected too: owner's request of 23.09.2026.
    await page.evaluate(() => { select(N.findIndex(n => !hid(n))); });
    await page.mouse.move(5, 5);
    var qSel0 = await page.evaluate(() => G3.q());
    await page.waitForTimeout(7500);
    var drift = await page.evaluate(q => ({ dy: G3.angle(q), sel }), qSel0);
    check(drift.dy > .01 && drift.sel >= 0, 'the 3D view drifts after six idle seconds, with a concept selected',
          'turned ' + drift.dy.toFixed(3) + ' rad, selected ' + drift.sel);
    // and it does not stop after a while: owner's request of 23.09.2026, when it
    // had stopped after two minutes left alone
    var qLong = await page.evaluate(() => { G3.age(180000); return G3.q(); });
    await page.waitForTimeout(1000);
    var long = await page.evaluate(q => G3.angle(q), qLong);
    check(long > .02, 'the drift goes on after minutes left alone', 'turned ' + long.toFixed(3) + ' rad in 1s, three minutes idle');
    await page.evaluate(() => clearSel());
    // Nothing is drawn while nothing changes, for a reader who has asked for
    // less motion: no drift, no loop burning frames on a still picture.
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.waitForTimeout(400);
    var fr0 = await page.evaluate(() => G3.frames);
    await page.waitForTimeout(1200);
    var fr1 = await page.evaluate(() => G3.frames);
    var flowRM = await page.evaluate(() => G3.flowing());
    check(fr1 === fr0 && flowRM === 0, 'with reduced motion the 3D view draws nothing while nothing changes, and no light moves',
          (fr1 - fr0) + ' frames in 1.2s idle, ' + flowRM + ' links flowing');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.click('#bGraph');
    await page.waitForTimeout(300);
    check(jsErrors.length === 0, 'no JS errors in the 3D view', jsErrors[0]);
  }

  if (part('8c')) {
    // 8c. The Timelapse, 24.10.2026: the 3D view with a director. It was the
    // Film of 07.10.2026, one of two cinema modes on the owner's "i want more
    // cinema, more spectacle"; the other, Flight, is gone. His words of
    // 24.10.2026: "get rid of the flight", "name the film timelapse", "make the
    // timelaps more cinematic. and also faster". Entered by its button and
    // driven by real clicks and keys; read back through G3.cine, and through
    // G3.link and G3.mark, which give a link and a mark as the last frame
    // uploaded them. What it must show at a time is worked out here, from the
    // dates in the page's data and this check's own statement of the rule, so a
    // film that follows another rule fails.
    // The section stands in a block of its own, because this file is one function
    // and the section's names are many.
    {
      await page.click('#b3d');
      await page.waitForTimeout(500);
      await page.evaluate(() => G3.fit());
      await page.waitForTimeout(600);
      // The rule: a concept's month is that of its oldest dated source; the film
      // begins at the first month that has another within a year after it.
      const film = await page.evaluate(() => {
        const ms = [...new Set(N.map(n => D[n.id].b).filter(b => b != null).map(b => Math.floor(b / 31)))].sort((a, b) => a - b);
        let k = 0; while (k < ms.length - 1 && ms[k + 1] - ms[k] > 12) k++;
        return { t0: ms[k], tot: ms[ms.length - 1] - ms[k] + 1, showing: N.filter(n => !hid(n)).length,
                 links: new Set(L.map(([a, b]) => a < b ? a + ',' + b : b + ',' + a)).size, bases: new Set(N.filter(n => !hid(n)).map(n => n.kb)).size };
      });
      const yearOf = m => String(Math.floor(m / 12)), thou = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "'");
      const cineSay = () => page.evaluate(() => ({ ...G3.cine.state(), big: document.getElementById('cineBig').textContent,
        sub: document.getElementById('cineSub').textContent, name: document.getElementById('cineName').textContent,
        years: document.getElementById('cineYears').textContent, title: document.getElementById('cineTitle').style.opacity,
        cap: document.getElementById('cineCap').style.opacity, drawn: G3.drawn, flowing: G3.flowing(), sel }));
      // How the cinema's words are set, and how the page sets the same kinds of
      // words itself: a title, the small grey label, and text. Owner's
      // instruction of 07.10.2026, "please use the same font and font color":
      // the first cut set the film's date thin, off-white and 78px high.
      const typeOf = () => page.evaluate(() => {
        const st = e => { const c = getComputedStyle(e); return [c.fontFamily, c.fontSize, c.fontWeight, c.color].join(', '); };
        const made = (tag, cls) => { const e = document.createElement(tag); e.className = cls; e.textContent = 'x'; document.body.appendChild(e);
          const v = st(e); e.remove(); return v; };
        const two = e => { const c = getComputedStyle(e); return [c.fontFamily, c.color].join(', '); };
        return { big: st(document.getElementById('cineBig')), name: st(document.getElementById('cineName')), years: st(document.getElementById('cineYears')),
                 sub: two(document.getElementById('cineSub')), h1: made('h1', ''), label: made('div', 'grp'), text: two(document.body) }; });
      // One cinema button, the Timelapse, and no Flight.
      const go = await page.evaluate(() => [...document.querySelectorAll('#cineGo button')].map(b => b.textContent));
      check(go.join(' ') === 'Timelapse' && !(await page.$('#bFly')), 'the 3D view has one cinema button, Timelapse, and no Flight', go.join(', '));
      await page.click('#bFilm');
      const fIn = await page.evaluate(() => { const g = document.getElementById('g3').getBoundingClientRect();
        return { kind: G3.cine.state().kind, cine: document.body.classList.contains('cine'),
                 top: getComputedStyle(document.getElementById('top')).display, ask: getComputedStyle(document.getElementById('askbar')).display,
                 y: g.top, h: g.height, win: innerHeight, wide: innerWidth, bars: [...document.querySelectorAll('#cine .bar')].map(b => Math.round(b.getBoundingClientRect().height)) }; });
      check(fIn.kind === 'film' && fIn.cine && fIn.top === 'none' && fIn.ask === 'none' && fIn.y === 0 && Math.abs(fIn.h - fIn.win) < 1 &&
            fIn.bars.length === 2 && fIn.bars.every(h => h >= 50),
            'the Timelapse button makes the 3D view a cinema: the picture fills the window, between two black bars',
            'kind=' + fIn.kind + ' header ' + fIn.top + ', search bar ' + fIn.ask + ', canvas ' + Math.round(fIn.h) + ' of ' + fIn.win + 'px, bars ' + fIn.bars.join('+'));
      // It opens on its title: the vault's name and its years, over an empty sky,
      // with the caption below not yet there.
      const tIn = await cineSay();
      check(tIn.playing && tIn.intro > 0 && tIn.fp === 0 && tIn.drawn === 0 && tIn.title === '1' && tIn.cap === '0' &&
            tIn.name === '00_Cerebrum' && tIn.years === yearOf(film.t0) + '–' + yearOf(film.t0 + film.tot - 1),
            'the Timelapse opens on its title, the vault\'s name and its years, over an empty sky',
            JSON.stringify(tIn.name) + ' ' + JSON.stringify(tIn.years) + ' at opacity ' + tIn.title + ', caption ' + tIn.cap + '; ' + tIn.drawn + ' concepts drawn, month ' + tIn.fp + ', title time left ' + Math.round(tIn.intro) + 'ms');
      const typeFilm = await typeOf();
      // It runs by itself from the press of the button: nothing here starts it.
      await page.waitForTimeout(2800);
      const fRun = await cineSay();
      check(fRun.playing && fRun.fp > 3 && fRun.fp < 8 && fRun.drawn > 0 && /^\d{4}$/.test(fRun.big) && / concepts?$/.test(fRun.sub),
            'the Timelapse runs by itself after its title, about five and a half months a second, and counts its year and its concepts',
            fRun.fp.toFixed(2) + ' months 2.8s after the press, ' + fRun.drawn + ' drawn, ' + JSON.stringify(fRun.big) + ', ' + JSON.stringify(fRun.sub));
      // The title gives way as the first cluster comes: when the first concept is
      // there the title still shows, fainter, and it is gone some months on. In
      // the director's own steps, from the start. No frame is drawn inside one
      // evaluate, so the concepts there are read from the caption's count.
      const intro = await page.evaluate(() => { G3.cine.start('film'); G3.cine.play(true); const A = () => +document.getElementById('cineTitle').style.opacity;
        const there = () => parseInt(document.getElementById('cineSub').textContent.replace(/'/g, ''), 10) || 0;
        let n = 0; while (there() === 0 && n++ < 400) G3.cine.advance(50);
        const at = { a: A(), fp: G3.cine.state().fp, drawn: there() }; while (A() > 0 && n++ < 800) G3.cine.advance(50);
        const gone = G3.cine.state().fp; G3.cine.play(false); return { ...at, gone }; });
      check(intro.drawn > 0 && intro.a > 0 && intro.a < 1 && intro.gone > intro.fp && intro.gone < 10,
            'the title fades as the first cluster comes',
            'at the first concepts there (' + intro.drawn + ', month ' + intro.fp.toFixed(2) + ') the title at ' + intro.a.toFixed(2) + '; gone at month ' + intro.gone.toFixed(2));
      // About thirty seconds, title and all: the Film lasted 68.
      const span = await page.evaluate(() => { G3.cine.start('film'); G3.cine.play(true); let ms = 0;
        while (G3.cine.state().playing && ms < 120000) { G3.cine.advance(50); ms += 50; } return ms; });
      // A month takes 180 ms, so a vault of thirteen years plays in about thirty
      // seconds and a younger one in less: the made-up base of fourteen months
      // that the template is tried on plays in four and a half.
      const spanWant = 1800 + film.tot * 180;
      check(spanWant >= 24000 ? span >= 24000 && span <= 36000 : Math.abs(span - spanWant) <= spanWant * .15,
            'the Timelapse lasts about thirty seconds, its title included' + (spanWant >= 24000 ? '' : ' (a younger vault: 180 ms a month)'),
            (span / 1000).toFixed(1) + ' s of the director\'s clock' + (spanWant >= 24000 ? '' : ', ' + (spanWant / 1000).toFixed(1) + ' s expected for ' + film.tot + ' months'));
      // Taken back to its start, the sky is empty, the title is gone, and the
      // caption names the first year.
      await page.evaluate(() => { G3.cine.play(false); G3.cine.seek(0); });
      await page.waitForTimeout(500);
      const f0 = await cineSay();
      check(f0.fp === 0 && f0.drawn === 0 && f0.flowing === 0 && f0.t0 === film.t0 && f0.total === film.tot && f0.big === yearOf(film.t0) && f0.title === '0',
            'taken back to its start, the Timelapse shows an empty sky, in the year of the first month whose dates follow one another, and no title',
            f0.drawn + ' concepts and ' + f0.flowing + ' links drawn, ' + JSON.stringify(f0.big) + ', title at ' + f0.title + ', ' + f0.total + ' months from ' + f0.t0 + ', expected ' + film.tot + ' from ' + film.t0);
      // And dark: no halo of a knowledge base either. A halo is the one thing the
      // two counts above do not see, so the picture is read, between the bars and
      // above the caption. The ground, the dust and the date are grey.
      {
        const top = fIn.bars[0], png = await page.screenshot({ clip: { x: 0, y: top, width: fIn.wide, height: fIn.win - 2 * top - 240 } });
        const px = pngPixels(png);
        let hue = 0;
        for (let y = 0; y < fIn.win - 2 * top - 240; y += 3)
          for (let x = 0; x < fIn.wide; x += 3) { const [r, g, b] = px(x, y); if (Math.max(r, g, b) - Math.min(r, g, b) > 25) hue++; }
        check(hue <= 2, 'the Timelapse\'s first frame is dark: no concept, no link, and no halo of a knowledge base', hue + ' coloured samples');
      }
      // At any time: exactly the concepts whose oldest source is older, and
      // exactly the links whose two ends are both there.
      const at = [];
      for (const k of [Math.round(film.tot * .25), Math.round(film.tot * .5), Math.round(film.tot * .75), film.tot]) {
        await page.evaluate(k => G3.cine.seek(k), k);
        await page.waitForTimeout(800);
        await page.evaluate(() => G3.fit());
        await page.waitForTimeout(600);
        at.push(await page.evaluate(({ k, t0, tot }) => {
          const here = n => !hid(n) && (k >= tot || (D[n.id].b != null && D[n.id].b / 31 < t0 + k));
          const pairs = new Set(L.filter(([a, b]) => here(N[a]) && here(N[b])).map(([a, b]) => a < b ? a + ',' + b : b + ',' + a));
          return { k, drawn: G3.drawn, want: N.filter(here).length, flowing: G3.flowing(), links: pairs.size, big: document.getElementById('cineBig').textContent };
        }, { k, t0: film.t0, tot: film.tot }));
      }
      check(at.every(a => a.drawn === a.want) && at[0].want > 0 && at[0].want < at[1].want && at[1].want < at[2].want && at[3].want === film.showing,
            'the Timelapse shows exactly the concepts whose oldest source is older than its date',
            at.map(a => a.k + ': ' + a.drawn + ' of ' + a.want).join(', '));
      check(at.every(a => a.flowing === a.links) && at[0].links > 0 && at[3].links === film.links,
            'a link shows in the Timelapse only when both its concepts are there',
            at.map(a => a.k + ': ' + a.flowing + ' of ' + a.links).join(', '));
      check(at.slice(0, 3).every(a => a.big === yearOf(film.t0 + a.k)), 'the Timelapse\'s date is the year its playhead stands in',
            at.slice(0, 3).map(a => a.k + ' → ' + a.big).join(', '));
      // The year changes behind a fade: the caption dims, the next year comes
      // while it is dim, and it lights again. Stepped in the director's clock
      // across the end of a year.
      const turn = await page.evaluate(({ t0 }) => { let k = 1; while ((t0 + k) % 12 !== 11) k++;
        G3.cine.seek(k + .5); G3.cine.advance(600); G3.cine.play(true); const cap = document.getElementById('cineCap'), big = document.getElementById('cineBig'), seen = [];
        for (let n = 0; n < 40; n++) { G3.cine.advance(20); seen.push([big.textContent, +cap.style.opacity]); }
        G3.cine.play(false); return { k, seen }; }, film);
      {
        // Up to the end's caption, which a short film reaches inside these samples.
        const end = turn.seen.findIndex(v => !/^\d{4}$/.test(v[0])), s = end < 0 ? turn.seen : turn.seen.slice(0, end);
        const ch = s.findIndex((v, i) => i && v[0] !== s[i - 1][0]), years = [...new Set(s.map(v => v[0]))];
        const part = v => v[1] > 0 && v[1] < 1, dims = s.slice(0, ch).filter(part).length, lights = s.slice(ch + 1).filter(part).length;
        check(years.length === 2 && +years[1] === +years[0] + 1 && ch > 0 && s[ch][1] < .15 && s[0][1] === 1 && s.slice(ch).some(v => v[1] === 1) && dims >= 3 && lights >= 3,
              'the year changes behind a fade: the caption dims, the next year comes, it lights again',
              'dimming in ' + dims + ' steps, lighting in ' + lights + '; from month ' + (turn.k + .5) + ': ' + s.filter((v, i) => i % 4 === 0 || i === ch).map(v => v[0] + '@' + v[1].toFixed(2)).join(' '));
      }
      // A link draws itself: half of it stands at half its time, from the younger
      // concept toward the older, and all of it afterwards.
      const pair = await page.evaluate(({ t0, tot }) => {
        const r = i => D[N[i].id].b == null ? null : Math.max(0, D[N[i].id].b / 31 - t0), inb = n => D[n.id].inb.length;
        const hub = N.reduce((m, n) => inb(n) > inb(m) ? n : m, N[0]).i;   // the film shows that one from its start, not from its date
        for (const [a, b] of L) { const ra = r(a), rb = r(b);
          if (a === hub || b === hub || ra == null || rb == null || hid(N[a]) || hid(N[b]) || Math.abs(ra - rb) < 3) continue;
          const lb = Math.max(ra, rb); if (lb < 2 || lb > tot - 4) continue;
          return { a, b, lb, young: ra > rb ? a : b, old: ra > rb ? b : a }; }
        return null; }, film);
      if (!pair) check(false, 'a link between two concepts of different dates, to watch it draw itself', 'none found');
      else {
        const reach = async p => { await page.evaluate(p => G3.cine.seek(p), p); await page.waitForTimeout(300);
          return page.evaluate(({ a, b, young, old }) => { const l = G3.link(a, b), pos = i => [N[i].x, -N[i].y, D[N[i].id].z || 0];
            const dist = (u, v) => Math.hypot(u[0] - v[0], u[1] - v[1], u[2] - v[2]);
            const ye = young < old ? l.lo : l.hi, oe = young < old ? l.hi : l.lo;
            return { from: dist(ye, pos(young)), part: dist(oe, pos(young)) / dist(pos(old), pos(young)), alpha: l.alpha }; }, pair); };
        const half = await reach(pair.lb + .6), whole = await reach(pair.lb + 3), none = await reach(pair.lb - .5);
        check(half.from < .5 && Math.abs(half.part - .5) < .06 && Math.abs(whole.part - 1) < .001 && whole.alpha > 0 && none.alpha === 0,
              'a link draws itself in the Timelapse, from its younger concept to its older one',
              'before its date alpha ' + none.alpha + '; at half its time ' + (half.part * 100).toFixed(0) + '% of its length, ' + half.from.toFixed(1) + ' from the younger end; then ' + (whole.part * 100).toFixed(0) + '%');
      }
      // A concept arrives larger and brighter than it stays.
      const flash = await page.evaluate(async ({ t0, tot }) => {
        const n = N.find(n => !hid(n) && D[n.id].b != null && D[n.id].b / 31 - t0 > 5 && D[n.id].b / 31 - t0 < tot - 6);
        const r = D[n.id].b / 31 - t0, wait = ms => new Promise(f => setTimeout(f, ms)), out = { r0: n.r };
        for (const [key, p] of [['new', r + .2], ['old', r + 4]]) { G3.cine.seek(p); await wait(800); G3.fit(); await wait(600);
          const m = G3.mark(n.i); out[key] = m ? m.r : -1; out[key + 'Rgb'] = m ? Math.max(...m.rgb) : -1; }
        return out; }, film);
      check(flash.new > flash.r0 * 1.5 && Math.abs(flash.old - flash.r0) < 1e-3 && flash.newRgb > flash.oldRgb * 1.5,
            'a concept arrives in the Timelapse larger and brighter than it stays',
            'radius ' + flash.new.toFixed(1) + ' on arrival, ' + flash.old.toFixed(1) + ' four months on, of ' + flash.r0 + '; brightest channel ' + flash.newRgb.toFixed(2) + ' then ' + flash.oldRgb.toFixed(2));
      // The camera. Owner's words of 08.10.2026 on the Film's first camera, which
      // followed the newest concepts in and out: "dont zoom in and out so much.
      // this looks hectic and you loose sight", "start small inside the first
      // cluster, then zoom out over time"; and on the second: "keep the camera
      // always slightly in motion. especially at the beginning it was to static
      // and towards the end". The Timelapse's turns round the vault instead of
      // swaying. Played from its title to its end in the frame loop's own steps,
      // a month a step: the camera never comes nearer and starts at less than
      // half its last distance; its view turns in every step, the title's
      // included; it comes nearer to the end's direction in every step, so it
      // never turns back; the picture's upright stays where it is, so the turn
      // is round the vault and does not tip; and the whole turn is a real one.
      const drawBack = await page.evaluate(MSM => { G3.cine.start('film'); G3.cine.play(true);
        const d = [G3.cam.d], qs = [G3.q()], ups = [G3.up()];
        while (G3.cine.state().playing) { G3.cine.advance(MSM); d.push(G3.cam.d); qs.push(G3.q()); ups.push(G3.up()); }
        const qa = (a, b) => 2 * Math.acos(Math.min(1, Math.abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3])));
        const end = qs[qs.length - 1], toEnd = qs.map(q => qa(q, end)), u0 = ups[0];
        const steps = qs.length - 1, upMoved = Math.max(...ups.map(u => Math.acos(Math.min(1, u[0] * u0[0] + u[1] * u0[1] + u[2] * u0[2]))));
        let rests = 0, back = 0; for (let i = 1; i < steps; i++) { if (qa(qs[i], qs[i - 1]) < 1e-5) rests++; if (toEnd[i] >= toEnd[i - 1]) back++; }
        const last = d[d.length - 2];   // before the end, which frames the whole vault
        // the month each base begins, a tenth of its concepts there: the camera can
        // only start close in the first where the bases do not all begin at once
        const ms = {}; N.forEach(n => { if (hid(n) || D[n.id].b == null) return; (ms[n.kb] = ms[n.kb] || []).push(D[n.id].b); });
        const begins = new Set(Object.values(ms).map(b => b.sort((x, y) => x - y)[Math.floor(b.length * .1)] / 31 | 0));
        return { first: d[0], last, nearer: d.slice(0, -1).filter((v, i) => i && v < d[i - 1] - 1e-9).length, steps, rests, back, whole: toEnd[0], upMoved, apart: begins.size > 1 }; }, 180);
      check(drawBack.steps > 5 && drawBack.nearer === 0 && (!drawBack.apart || drawBack.first < drawBack.last * .5) && drawBack.rests === 0 && drawBack.back === 0 &&
            drawBack.whole > .5 && drawBack.whole < 1.6 && drawBack.upMoved < 1e-4,
            'the Timelapse\'s camera starts close, only draws back, and turns round the vault in every step, one way only, without tipping',
            'distance ' + Math.round(drawBack.first) + ' at the start, ' + Math.round(drawBack.last) + ' at the last month; nearer in ' + drawBack.nearer + ' of ' + drawBack.steps + ' steps; the view at rest in ' + drawBack.rests +
            ', turned back in ' + drawBack.back + '; the whole turn ' + drawBack.whole.toFixed(2) + ' rad; the upright moved ' + drawBack.upMoved.toExponential(1) + ' rad');
      // And nothing that matters is outside the picture: every knowledge base that
      // has begun, a tenth of its concepts being there, has all of those in it.
      const inView = [];
      for (const k of [Math.round(film.tot * .3), Math.round(film.tot * .55), Math.round(film.tot * .8)]) {
        await page.evaluate(k => G3.cine.seek(k), k);
        await page.waitForTimeout(1000);
        inView.push(await page.evaluate(({ k, t0 }) => { const g = document.getElementById('g3'), bar = document.querySelector('#cine .bar').getBoundingClientRect().height;
          const here = n => !hid(n) && D[n.id].b != null && D[n.id].b / 31 < t0 + k, all = {}, born = {};
          N.forEach(n => { if (hid(n)) return; all[n.kb] = (all[n.kb] || 0) + 1; if (here(n)) born[n.kb] = (born[n.kb] || 0) + 1; });
          const begun = Object.keys(born).filter(kb => born[kb] >= all[kb] * .1);
          const out = N.filter(n => { if (!here(n) || !begun.includes(n.kb)) return false; const p = G3.project(n.i);
            return !p || p[0] < 0 || p[0] > g.clientWidth || p[1] < bar || p[1] > g.clientHeight - bar; }).length;
          return { k, begun: begun.length, out, bases: Object.keys(all).length }; }, { k, t0: film.t0 }));
      }
      check(inView.every(v => v.begun > 0 && v.out === 0) && (inView[0].begun === inView[0].bases || inView[2].begun > inView[0].begun), 'every knowledge base that has begun is in the Timelapse\'s picture',
            inView.map(v => 'month ' + v.k + ': ' + v.begun + ' bases, ' + v.out + ' concepts outside').join('; '));
      // And the most-linked concept of the vault, whatever its base and whatever
      // its date: it is there in the film's first month. Owner's words of
      // 08.10.2026, whose own concept that is: "make it such that you are showing
      // me from the beginning on. i am out of sight until about concept 80". Its
      // oldest source is a year younger than the film's first month, and it
      // stands between the bases, so the frame of the first base alone left it out
      // in a window of his shape, five wide to four high; in this check's wider
      // window that frame happened to hold it. So the window is made his for this.
      await page.setViewportSize({ width: 1000, height: 830 });
      await page.waitForTimeout(400);
      const hubIn = await page.evaluate(async t0 => { const inb = n => D[n.id].inb.length, hub = N.filter(n => !hid(n)).reduce((m, n) => !m || inb(n) > inb(m) ? n : m, null);
        const g = document.getElementById('g3'), bar = document.querySelector('#cine .bar').getBoundingClientRect().height;
        G3.cine.seek(1); await new Promise(f => setTimeout(f, 1000)); const p = G3.project(hub.i);
        // in the picture is clear of the edges and of the caption: on 08.10.2026 it passed as "in" at the lower edge, half behind the bar
        return { t: D[hub.id].t, big: document.getElementById('cineBig').textContent, drawn: G3.drawn, at: p && p.map(Math.round),
                 inside: !!p && p[0] > 30 && p[0] < g.clientWidth - 30 && p[1] > bar + 30 && p[1] < g.clientHeight - bar - 120 }; }, film.t0);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(400);
      check(hubIn.inside, 'the most-linked concept is in the Timelapse\'s picture from its first month', JSON.stringify(hubIn.t) + ' in ' + hubIn.big + ', with ' + hubIn.drawn + ' concepts drawn, in a window of 1000 by 830: at ' + hubIn.at + ', in the picture ' + hubIn.inside);
      // The time bar shows where the film is, and a press on it moves the film.
      const barBox = await page.evaluate(() => { const b = document.getElementById('cineTime').getBoundingClientRect();
        return { x: b.left, y: b.top + b.height / 2, w: b.width, v: +document.getElementById('cineTime').value, fp: G3.cine.state().fp }; });
      await page.mouse.click(barBox.x + barBox.w * .25, barBox.y);
      await page.waitForTimeout(200);
      const barred = await cineSay();
      check(Math.abs(barBox.v / 1000 * film.tot - barBox.fp) < .2 && Math.abs(barred.fp - film.tot * .25) < film.tot * .03,
            'the time bar shows where the Timelapse is, and a press on it moves it there',
            'bar at ' + barBox.v + ' of 1000 for month ' + barBox.fp + '; pressed at a quarter, the film stands at ' + barred.fp.toFixed(1) + ' of ' + film.tot);
      // Space plays and pauses, as in any player.
      await page.keyboard.press(' ');
      await page.waitForTimeout(600);
      const sp1 = await cineSay();
      await page.keyboard.press(' ');
      const sp2 = await cineSay();
      await page.waitForTimeout(500);
      const sp3 = await cineSay();
      check(sp1.playing && sp1.fp > barred.fp + .5 && !sp2.playing && sp3.fp === sp2.fp, 'Space plays the Timelapse and pauses it',
            'playing ' + sp1.playing + ', ' + (sp1.fp - barred.fp).toFixed(2) + ' months in 0.6s; then playing ' + sp2.playing + ', ' + (sp3.fp - sp2.fp) + ' months in 0.5s');
      // The speed button: twice the pace, then four times, then back; each a
      // stated 0.9 seconds of the frame loop, compared with the first.
      await page.click('#cineSpeed');
      await page.click('#cineSpeed');
      await page.click('#cineSpeed');
      // 0.9 s a step, or 0.15 s where the film is under five years, so the four
      // steps, 8.3 months at 180 ms a month and four times the pace, stay inside it.
      const pace = await page.evaluate(tot => { const b = document.getElementById('cineSpeed'), fp = () => G3.cine.state().fp, out = [], ms = tot >= 60 ? 900 : 150;
        G3.cine.seek(Math.min(10, tot * .05)); G3.cine.play(true);
        for (let k = 0; k < 4; k++) { const a = fp(); G3.cine.advance(ms); out.push({ lab: b.textContent, d: fp() - a }); if (k < 3) b.click(); }
        G3.cine.play(false); return { labs: out.map(o => o.lab).join(' '), r: out.map(o => o.d / out[0].d), d0: out[0].d }; }, film.tot);
      check(pace.labs === '1× 2× 4× 1×' && Math.abs(pace.r[1] - 2) < .05 && Math.abs(pace.r[2] - 4) < .1 && Math.abs(pace.r[3] - 1) < .05,
            'the speed button doubles the Timelapse\'s pace, then doubles it again, then returns',
            'the button read ' + pace.labs + '; 0.9s ran ' + pace.d0.toFixed(2) + ' months at first, then ' + pace.r.slice(1).map(r => r.toFixed(2) + ' times that').join(', '));
      // The end: the film stops by itself, on the whole vault, and the caption
      // names the vault and its totals. It is played from a month of the last
      // year, with the caption settled on that year, so only the end can change it.
      await page.evaluate(({ t0, tot }) => G3.cine.seek(tot - 1 - Math.min(2, (t0 + tot - 1) % 12)), film);
      await page.waitForTimeout(500);
      await page.evaluate(() => G3.cine.play(true));
      await page.waitForTimeout(3600);
      const fEnd = await cineSay();
      const outEnd = await page.evaluate(() => { const g = document.getElementById('g3'), bar = document.querySelector('#cine .bar').getBoundingClientRect().height;
        return N.filter(n => { if (hid(n)) return false; const p = G3.project(n.i);
          return !p || p[0] < 0 || p[0] > g.clientWidth || p[1] < bar || p[1] > g.clientHeight - bar - 120; }).length; });
      const totals = thou(film.showing) + ' concepts · ' + thou(film.links) + ' links · ' + film.bases + (film.bases === 1 ? ' knowledge base' : ' knowledge bases');
      check(!fEnd.playing && fEnd.fp === film.tot && fEnd.drawn === film.showing && fEnd.flowing === film.links && outEnd === 0,
            'the Timelapse ends by itself on the whole vault, framed between the bars and above its caption',
            'playing ' + fEnd.playing + ', ' + fEnd.drawn + ' of ' + film.showing + ' concepts, ' + outEnd + ' outside the frame');
      check(fEnd.big === '00_Cerebrum' && fEnd.sub === totals && fEnd.cap === '1' && fEnd.title === '0',
            'at its end the Timelapse\'s caption names the vault and its totals',
            JSON.stringify(fEnd.big) + ' ' + JSON.stringify(fEnd.sub) + ' at opacity ' + fEnd.cap + ', expected ' + JSON.stringify(totals));
      // The time bar is at its end too: its knob stands at the end of the bar, with
      // nothing of the bar left beyond it. The owner saw a film that "does not go to
      // the end", 07.10.2026: the page's padding for inputs kept the knob ten pixels
      // short, on a film that had ended. Read from the picture, as a reader sees it:
      // the last lit pixel of the bar's middle line belongs to the knob, which is in
      // the accent colour, and not to the grey of the bar.
      {
        const b = await page.evaluate(() => document.getElementById('cineTime').getBoundingClientRect().toJSON());
        const png = await page.screenshot({ clip: { x: b.left - 4, y: b.top - 4, width: b.width + 8, height: b.height + 8 } });
        const px = pngPixels(png), row = Math.round(b.height / 2) + 4, lit = x => Math.max(...px(x, row).slice(0, 3)) > 40;   // the grey of the bar is about 59, the black behind it 0
        let x = Math.floor(b.width) + 7; while (x > 3 && !lit(x)) x--;
        const [r, g, bl] = px(x - 3, row);
        check(x > 3 && Math.max(r, g, bl) - Math.min(r, g, bl) > 60, 'at the Timelapse\'s end the time bar\'s knob stands at the end of the bar',
              'the bar ends in rgb(' + [r, g, bl].join(', ') + '), ' + (Math.floor(b.width) + 4 - x) + 'px before the end of its box');
      }
      // A click in the cinema turns the picture and selects nothing.
      const inFilm = await page.evaluate(() => { const g = document.getElementById('g3'), b = g.getBoundingClientRect();
        for (const n of N) { if (hid(n)) continue; const p = G3.project(n.i); if (!p) continue;
          if (p[0] < 60 || p[0] > g.clientWidth - 60 || p[1] < 120 || p[1] > g.clientHeight - 300) continue;
          if (document.elementFromPoint(b.left + p[0], b.top + p[1]) === g && G3.pick(p[0], p[1]) === n.i) return { x: b.left + p[0], y: b.top + p[1] }; }
        return null; });
      if (!inFilm) check(false, 'a concept in the open to click in the Timelapse', 'none found');
      else { await page.mouse.click(inFilm.x, inFilm.y); await page.waitForTimeout(200);
        const s = await page.evaluate(() => ({ sel, on: G3.cine.on() }));
        check(s.sel === -1 && s.on, 'a click on a concept in the Timelapse selects nothing', 'selected ' + s.sel); }
      // Play at the end starts the film again, from its title.
      await page.mouse.move(700, 500);
      await page.click('#cinePlay');
      await page.waitForTimeout(450);
      const again = await cineSay();
      await page.evaluate(() => G3.cine.play(false));
      check(again.playing && again.fp === 0 && again.intro > 0 && again.title === '1' && again.name === '00_Cerebrum',
            'Play at the end of the Timelapse starts it again, from its title',
            'playing ' + again.playing + ', at month ' + again.fp + ', title time left ' + Math.round(again.intro) + 'ms, title at ' + again.title);
      // The words as the page sets its own: the year and the vault's name as a
      // title, the count as text, the years under the title as the small label.
      check(typeFilm.big === typeFilm.h1 && typeFilm.name === typeFilm.h1 && typeFilm.sub === typeFilm.text && typeFilm.years === typeFilm.label,
            'the cinema sets its words as the page sets its own: a title, text, a small label',
            'year ' + typeFilm.big + '; name ' + typeFilm.name + '; a title of the page ' + typeFilm.h1 + '; years ' + typeFilm.years + '; a label ' + typeFilm.label + '; count ' + typeFilm.sub + '; text ' + typeFilm.text);
      // What the bar holds, named, so a control that comes back, or goes, is seen.
      const bar8c = await page.evaluate(() => [...document.querySelectorAll('#cineCtl > *')].filter(e => getComputedStyle(e).display !== 'none').map(e => e.id));
      check(bar8c.join(' ') === 'cinePlay cineTime cineSpeed cineFull cineX', 'the Timelapse\'s bar holds Play, the time bar, the speed, full screen and Leave', bar8c.join(' '));
      // Escape leaves, and the whole vault is back, with every link whole: left
      // from the middle of the film, while the watched link is half drawn.
      await page.evaluate(p => G3.cine.seek(p), pair ? pair.lb + .6 : film.tot * .5);
      await page.waitForTimeout(300);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(900);
      const fOut = await page.evaluate(p => { const pos = i => [N[i].x, -N[i].y, D[N[i].id].z || 0], l = p ? G3.link(p.a, p.b) : null;
        const d = (u, v) => Math.hypot(u[0] - v[0], u[1] - v[1], u[2] - v[2]);
        return { on: G3.cine.on(), cine: document.body.classList.contains('cine'), top: getComputedStyle(document.getElementById('top')).display,
                 box: document.getElementById('cine').hidden, v3: document.body.classList.contains('v3'), drawn: G3.drawn, flowing: G3.flowing(),
                 ends: l ? d(l.lo, pos(Math.min(p.a, p.b))) + d(l.hi, pos(Math.max(p.a, p.b))) : 0 }; }, pair);
      check(!fOut.on && !fOut.cine && fOut.box && fOut.top !== 'none' && fOut.v3 && fOut.drawn === film.showing && fOut.flowing === film.links && fOut.ends < .01,
            'Escape leaves the Timelapse for the 3D view, and the whole vault is back',
            'cinema ' + fOut.on + ', header ' + fOut.top + ', ' + fOut.drawn + ' of ' + film.showing + ' concepts, ' + fOut.flowing + ' of ' + film.links + ' links');
      // A reader who asked for less motion gets the film, and it waits for Play.
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.click('#bFilm');
      await page.waitForTimeout(700);
      const fRM = await cineSay();
      await page.keyboard.press('Escape');
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      await page.waitForTimeout(300);
      check(fRM.kind === 'film' && !fRM.playing && fRM.fp === 0, 'with reduced motion the Timelapse waits for Play', 'playing ' + fRM.playing + ', at month ' + fRM.fp);
      // The Timelapse is the 3D view's: another view ends it. By the address, as
      // the owner's voice assistant switches views.
      await page.evaluate(() => G3.cine.start('film'));
      await page.evaluate(() => { location.hash = '#view=graph&n=cine'; });
      await page.waitForTimeout(400);
      const gone8c = await page.evaluate(() => ({ on: G3.cine.on(), cine: document.body.classList.contains('cine'), vg: document.body.classList.contains('vg'),
        top: getComputedStyle(document.getElementById('top')).display }));
      check(!gone8c.on && !gone8c.cine && gone8c.vg && gone8c.top !== 'none', 'another view ends the cinema, and the header is back',
            'cinema ' + gone8c.on + ', body.cine ' + gone8c.cine + ', header ' + gone8c.top);
      await page.evaluate(() => clearSel());
      check(jsErrors.length === 0, 'no JS errors in the Timelapse', jsErrors[0]);
    }
  }

  if (part('9')) {
    // 9. Settings, 14.09.2026: j4k's Options menu in this viewer's frame, holding
    // the knowledge-base selector that left the sidebar. Since 24.10.2026 j4k's
    // Settings window: a window in the middle of the page, its parts down the left.
    //
    // The helper is kept out of this section, and the page reloaded without it.
    // Opening Settings asks the helper for the scheduled tasks, and a running
    // helper's answer can land between two of the geometry measurements below:
    // on 28.09.2026 it made Settings 157px taller while a knowledge base was
    // hidden, and "hiding moves nothing" failed for a reason that was not the
    // page. 9b feeds Settings a fixed helper answer; this section needs none.
    var noHelper = r => r.abort();
    await page.route('http://127.0.0.1:8760/**', noHelper);
    await page.reload();
    await page.waitForTimeout(900);
    var kbAll = await page.evaluate(() => [...new Set(Object.values(D).map(c => c.kb))]);
    await page.click('#bSet');
    await page.waitForTimeout(200);
    var s1 = await page.evaluate(() => {
      const r = document.getElementById('setWin').getBoundingClientRect();
      return { shown: document.getElementById('setWrap').classList.contains('on') && r.width > 0 && r.height > 0,
               centred: Math.abs(r.left + r.width / 2 - innerWidth / 2) < 2 && Math.abs(r.top + r.height / 2 - innerHeight / 2) < 2,
               part: [...document.querySelectorAll('.setPart')].filter(p => !p.hasAttribute('inert')).map(p => p.id).join(','),
               on: document.getElementById('bSet').classList.contains('on') };
    });
    check(s1.shown && s1.centred && s1.part === 'paneKb' && s1.on, 'the gear opens Settings as a window in the middle of the page, on Knowledge bases',
          'shown=' + s1.shown + ' centred=' + s1.centred + ' showing ' + s1.part + ' gear active=' + s1.on);

    // The geometry stays fixed when a knowledge base is hidden, owner's
    // instruction of 27.09.2026: the header, the search bar, the views, the gear,
    // Settings itself and every category chip keep their place and size. An
    // emptied row or chip goes blank rather than away.
    // A vault of one knowledge base has nothing to hide: the last one showing
    // always stays on. Otherwise the base that sorts last is hidden, so the
    // test says nothing about which bases a vault holds.
    if (kbAll.length < 2) check(true, 'hiding a knowledge base in Settings (one knowledge base: nothing to hide)');
    else {
    var victim = kbAll.slice().sort()[kbAll.length - 1];
    var geo = () => page.evaluate(() => {
      const r = e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height].map(v => Math.round(v * 2) / 2).join(','); };
      const out = {};
      ['top', 'askbar', 'stage', 'bSet', 'setWin', 'gc'].forEach(id => out['#' + id] = r(document.getElementById(id)));
      document.querySelectorAll('#legend .chip').forEach((c, i) => out['chip ' + i + ' ' + c.querySelector('b').textContent] = r(c));
      return out;
    });
    var moved = (a, b) => Object.keys(a).filter(k => a[k] !== b[k]).map(k => k + ' ' + a[k] + ' -> ' + (b[k] || 'gone'));
    var geo0 = await geo();
    var before = await page.evaluate(v => ({ items: document.querySelectorAll('.it').length,
      rows: document.querySelectorAll('#legend .lrow:not(.void)').length,
      ked: Object.values(D).filter(c => c.kb === v).length }), victim);
    await page.locator('#kbbar button', { hasText: victim.replace(/_kb$/, '') }).click();
    await page.waitForTimeout(200);
    var hid1 = await page.evaluate(v => ({
      items: document.querySelectorAll('.it').length,
      kedRows: document.querySelectorAll('.it[data-t^="' + v + '/"]').length,
      kedNodes: N.filter(n => n.kb === v && !hid(n)).length,
      rows: document.querySelectorAll('#legend .lrow:not(.void)').length,
      dot: (document.querySelector('#bSet .dot') || {}).textContent || '',
      stored: localStorage.getItem('okf.kbOff') }), victim);
    check(hid1.kedRows === 0 && hid1.kedNodes === 0 && hid1.items === before.items - before.ked,
          'hiding a knowledge base in Settings takes it out of the list and the graph',
          before.items + ' -> ' + hid1.items + ' rows, ' + victim + ' rows ' + hid1.kedRows + ', nodes drawn ' + hid1.kedNodes);
    check(hid1.rows === before.rows - 1, 'the categories count only what is showing, and an empty row goes blank',
          before.rows + ' -> ' + hid1.rows + ' category rows showing');
    var geo1 = await geo(), mv1 = moved(geo0, geo1);
    check(mv1.length === 0, 'hiding a knowledge base moves nothing on the screen', mv1.slice(0, 4).join('; ') || Object.keys(geo0).length + ' boxes in place');
    check(hid1.dot === '1', 'the gear says how many knowledge bases are hidden', 'badge=' + JSON.stringify(hid1.dot));
    await page.reload();
    await page.waitForTimeout(900);
    var kept = await page.evaluate(v => ({ ked: document.querySelectorAll('.it[data-t^="' + v + '/"]').length,
      items: document.querySelectorAll('.it').length, dot: (document.querySelector('#bSet .dot') || {}).textContent || '' }), victim);
    check(kept.ked === 0 && kept.items === hid1.items && kept.dot === '1', 'the choice is kept for the next visit',
          'stored ' + hid1.stored + ', after reload ' + kept.items + ' rows, badge ' + JSON.stringify(kept.dot));
    }

    // The last knowledge base showing stays on: hiding it would leave both views
    // empty, which is the dead page a stored choice must never produce. Forced,
    // because Playwright will not click an aria-disabled button and a person can.
    var survivor = kbAll.slice().sort()[0];
    await page.evaluate(([all, s]) => localStorage.setItem('okf.kbOff', JSON.stringify(all.filter(k => k !== s))), [kbAll, survivor]);
    await page.reload();
    await page.waitForTimeout(900);
    await page.click('#bSet');
    await page.waitForTimeout(150);
    await page.locator('#kbbar button', { hasText: survivor.replace(/_kb$/, '') }).click({ force: true });
    await page.waitForTimeout(200);
    var lastOne = await page.evaluate(s => ({ items: document.querySelectorAll('.it').length,
      kept: document.querySelectorAll('.it[data-t^="' + s + '/"]').length }), survivor);
    check(lastOne.items > 0 && lastOne.items === lastOne.kept, 'the last knowledge base showing cannot be hidden',
          lastOne.items + ' rows, ' + lastOne.kept + ' of them ' + survivor);
    // On the dimmed page left of the window, which starts at x=250 on this screen.
    await page.mouse.click(60, 450);
    await page.waitForTimeout(150);
    var outside = await page.evaluate(() => !document.getElementById('setWrap').classList.contains('on'));
    check(outside, 'a click outside closes Settings');
    await page.click('#bSet');
    await page.waitForTimeout(150);
    var g1 = await page.evaluate(() => document.activeElement ? document.activeElement.id : '');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    var g2 = await page.evaluate(() => ({ hidden: !document.getElementById('setWrap').classList.contains('on'),
      focused: document.activeElement ? document.activeElement.id : '' }));
    check(g1 === 'bSet' && g2.hidden && g2.focused !== 'bSet', 'Escape closes Settings and leaves no ring on the gear',
          'focused before=' + (g1 || 'body') + ' closed=' + g2.hidden + ' focused after=' + (g2.focused || 'body'));
    await page.evaluate(() => localStorage.removeItem('okf.kbOff'));
    await page.unroute('http://127.0.0.1:8760/**', noHelper);
    await page.reload();
    await page.waitForTimeout(900);
  }

  if (part('9b')) {
    // 9b. Settings in j4k's shape, owner's instruction of 27.09.2026, read off
    // the rendered window. The scheduled tasks stood in it from 27.09.2026 until
    // the owner had them taken out on 24.10.2026 ("please get rid of the
    // scheduled tasks in settings"), with their checks.
    var os = require('os'), fs = require('fs'), cp = require('child_process');
    var cors = { 'Access-Control-Allow-Origin': 'null', 'content-type': 'application/json' };
    var login = { state: 'ok' };
    await page.route('http://127.0.0.1:8760/health', r => r.fulfill({ status: 200, headers: cors,
      body: JSON.stringify({ ok: true, busy: false, model: 'claude-opus-5-5', effort: 'high', login, reports: 0 }) }));
    await page.route('http://127.0.0.1:8760/models', r => r.fulfill({ status: 200, headers: cors, body: JSON.stringify({
      models: [{ id: 'claude-opus-5-5', label: 'Opus 5.5', provider: 'anthropic', effort: true, agentic: true, installed: true, note: '' },
               { id: 'local:q', label: 'Qwen3 30B (local)', provider: 'local', effort: false, installed: true, onDisk: 17e9, bytes: 17e9, fits: true },
               { id: 'local:g', label: 'Gemma 3 27B (local)', provider: 'local', effort: false, installed: false, bytes: 15e9, fits: true }],
      efforts: ['low', 'medium', 'high', 'xhigh', 'max'], default: 'claude-opus-5-5', defaultEffort: 'high', free: 9e10, mlx: true }) }));
    await page.click('#bSet');
    await page.waitForTimeout(700);
    // Settings in three parts down the left of its window since 24.10.2026, About
    // 00_Cerebrum first, as in j4k's Settings window, then two of the three tabs
    // of 08.10.2026. Every part is rendered and only the shown one is visible, so
    // each is measured shown.
    var setOpens = await page.evaluate(() => ({
      on: [...document.querySelectorAll('.setTab')].filter(t => t.getAttribute('aria-current') === 'page').map(t => t.dataset.part).join(','),
      shown: [...document.querySelectorAll('.setPart')].filter(p => !p.hasAttribute('inert')).map(p => p.id).join(',') }));
    var setShape = () => page.evaluate(() => {
      const win = document.getElementById('setWin'), wr = win.getBoundingClientRect();
      const part = [...document.querySelectorAll('.setPart')].find(p => !p.hasAttribute('inert')), pr = part.getBoundingClientRect();
      const ctl = [...part.querySelectorAll('button,select')].filter(e => e.getBoundingClientRect().height > 0);
      const tabs = [...document.querySelectorAll('.setTab')].map(t => ({ id: t.dataset.part, name: t.querySelector('span').textContent, on: t.getAttribute('aria-current') === 'page',
        bg: getComputedStyle(t).backgroundColor }));
      const x = document.getElementById('setX').getBoundingClientRect(), head = document.querySelector('#setWin .winHead').getBoundingClientRect();
      // One width: every block of the shown part runs from its left edge to its
      // right. One surface: every control and card in it wears one background,
      // the knowledge bases' own buttons apart.
      // The model and effort selectors stand on the right of their rows, as in j4k's Assistant.
      const rows = [...part.querySelectorAll(':scope > *, .setCard, .stats, #bWeights .wr')]
        .filter(e => e.getBoundingClientRect().height > 0);
      const off = rows.filter(e => { const r = e.getBoundingClientRect(); return Math.abs(r.left - pr.left) > 1 || Math.abs(r.right - pr.right) > 1; })
        .map(e => (e.id || e.className) + ' ' + Math.round(e.getBoundingClientRect().left - pr.left) + '/' + Math.round(pr.right - e.getBoundingClientRect().right));
      const bgs = [...part.querySelectorAll('button, select, a.btn, .setCard, .stat, #bWeights .wr')].filter(e => !e.closest('#kbbar'))
        .map(e => getComputedStyle(e).backgroundColor);
      return { heights: [...new Set(ctl.map(e => Math.round(e.getBoundingClientRect().height)))], n: ctl.length, tabs,
        shown: part.id, size: [wr.width, wr.height].map(Math.round).join('x'),
        home: !!win.querySelector('#paneKb #kbbar') && !!win.querySelector('#paneBrain #bModel') && !!win.querySelector('#paneBrain #bWeights') &&
              !!win.querySelector('#partAbout #setVersion') && !win.querySelector('#tasks, #asked, [data-part="paneTasks"]'),
        rowsN: rows.length, off, bgs: [...new Set(bgs)], bgN: bgs.length,
        xEnd: x.right <= head.right && head.right - x.right < 24 && x.top >= head.top && x.bottom <= head.bottom,
        build: document.getElementById('setBuild').textContent };
    });
    var setPart = {}, setFour = ['partAbout', 'paneKb', 'paneBrain'];
    for (const t of ['paneBrain', 'partAbout', 'paneKb']) { await page.click('.setTab[data-part="' + t + '"]'); await page.waitForTimeout(150); setPart[t] = await setShape(); }
    var j4k = { n: setFour.reduce((v, t) => v + setPart[t].n, 0), heights: [...new Set(setFour.flatMap(t => setPart[t].heights))],
      rowsN: setFour.reduce((v, t) => v + setPart[t].rowsN, 0), off: setFour.flatMap(t => setPart[t].off.map(o => t + ': ' + o)),
      bgs: [...new Set(setFour.flatMap(t => setPart[t].bgs))], bgN: setFour.reduce((v, t) => v + setPart[t].bgN, 0),
      sizes: [...new Set(setFour.map(t => setPart[t].size))], xEnd: setFour.every(t => setPart[t].xEnd),
      build: setPart.paneBrain.build };
  check(j4k.n > 4 && j4k.heights.length === 1 && j4k.heights[0] === 32,
          'every control in Settings is 32px high, as in j4k', j4k.n + ' controls over the three parts, heights ' + j4k.heights.join(', '));
    var setPartsOk = setFour.every(t => { const q = setPart[t];
      return q.tabs.map(x => x.name).join('|') === 'About 00_Cerebrum|Knowledge bases|Brain' && q.tabs.filter(x => x.on).map(x => x.id).join(',') === t &&
        q.shown === t && q.home && q.tabs.filter(x => !x.on).every(x => x.bg !== q.tabs.find(y => y.on).bg); });
    check(setOpens.on === 'paneKb' && setOpens.shown === 'paneKb' && setPartsOk,
          'Settings lists three parts down the left, About 00_Cerebrum first, and no scheduled tasks: the gear opens on Knowledge bases, each shows its own part alone, and the shown one is marked',
          'opens on ' + setOpens.on + ' with ' + setOpens.shown + '; ' + setFour.map(t => t + ' shows ' + (setPart[t].shown || 'nothing') + ', marked ' +
            (setPart[t].tabs.filter(x => x.on).map(x => x.name).join(',') || 'none')).join('; ') + '; each part in its place: ' + setPart.paneKb.home);
    check(j4k.sizes.length === 1, 'Settings keeps its size from part to part', j4k.sizes.join(' | '));
    check(j4k.rowsN > 12 && j4k.off.length === 0, 'every row in Settings runs from the same left edge to the same right edge',
          j4k.rowsN + ' rows over the three parts; off the edges: ' + (j4k.off.join(', ') || 'none'));
    check(j4k.bgN > 8 && j4k.bgs.length === 1, 'every control and card in Settings wears one background',
          j4k.bgN + ' elements, backgrounds ' + j4k.bgs.join(' | '));
    check(j4k.xEnd && /^Build \d+ · /.test(j4k.build),
          'the × ends the head of every part, and the foot says the build',
          '× at the end=' + j4k.xEnd + ' "' + j4k.build + '"');
    // The launcher stops a helper that began before its script last changed, and
    // starts the new one. A helper reads its code and its model list one time;
    // until 08.10.2026 the launcher left any helper that answered, and the owner
    // started the viewer again after two models had left the list and saw them
    // still. The test is the helper's own, `--stale`, asked here of a process
    // made for it, against a file dated an hour before and an hour after.
    {
      const vs = path.join(__dirname, 'viewer-server.py'), tf = path.join(os.tmpdir(), 'cerebrum-stale-' + process.pid);
      const kid = cp.spawn('sleep', ['60']), ask = (pid, f) => cp.spawnSync('python3', [vs, '--stale', String(pid), f]).status;
      fs.writeFileSync(tf, 'x');
      const hour = h => { const t = new Date(Date.now() + h * 3600e3); fs.utimesSync(tf, t, t); };
      hour(-1); const fileOlder = ask(kid.pid, tf);
      hour(1); const fileNewer = ask(kid.pid, tf);
      kid.kill(); await new Promise(r => kid.on('exit', r));
      const gone = ask(kid.pid, tf);
      fs.rmSync(tf, { force: true });
      const launcher = fs.readFileSync(path.join(__dirname, '..', 'Open 00_Cerebrum.command'), 'utf8');
      const asks = /viewer-server\.py --stale "\$OLD"; then[\s\S]*?"busy": true[\s\S]*?kill "\$OLD"[\s\S]*?starting the helper/.test(launcher);
      check(fileOlder === 1 && fileNewer === 0 && gone === 2 && asks,
            'the launcher can tell a helper that began before its script last changed, and stops it so that the new one starts, unless it is answering',
            'a process against a file an hour older: exit ' + fileOlder + ' (1 is "not older"); against one an hour newer: exit ' + fileNewer + ' (0 is "older"); a process that is gone: exit ' + gone + ' (2 is "cannot tell"); the launcher asks, spares a busy helper, stops and starts: ' + asks);
    }
    // The command-line login lasts 28 days. A week before its end the Ask button
    // says so, and it has to say where the way out is: until 05.10.2026 it named
    // the day and nothing else, and the owner asked for it to be fixed. The
    // launcher asks to sign in again from that day on.
    var askSays = async state => { login = state; return page.evaluate(async () => { await pingHelper();
      const b = document.getElementById('mAsk'); return { title: b.title, warn: b.classList.contains('warn') }; }); };
    var soon = await askSays({ state: 'soon', days: 7, when: '13.10.2026' });
    var dead = await askSays({ state: 'expired', days: -1, when: '13.10.2026' });
    var fine = await askSays({ state: 'ok', days: 20, when: '02.11.2026' });
    check(soon.warn && /expires in 7 day\(s\), on 13\.10\.2026\. Double-click "Open 00_Cerebrum\.command" to sign in again/.test(soon.title) &&
          dead.warn && /expired on 13\.10\.2026\. Double-click "Open 00_Cerebrum\.command" to sign in again/.test(dead.title) &&
          !fine.warn && !/login/.test(fine.title),
          'a login near its end or past it is marked on the Ask button with where to sign in again, and a sound one is not',
          '"' + soon.title.split(' — ')[1] + '" | "' + dead.title.split(' — ')[1] + '" | fine: warn=' + fine.warn);
    await page.click('.setTab[data-part="paneKb"]');
    await page.click('.setTab[data-part="partAbout"]');
    await page.waitForTimeout(200);
    var ab = await page.evaluate(() => ({ open: document.getElementById('setWrap').classList.contains('on'),
      shown: [...document.querySelectorAll('.setPart')].filter(p => !p.hasAttribute('inert')).map(p => p.id).join(','),
      title: document.getElementById('setTitle').textContent }));
    check(ab.open && ab.shown === 'partAbout' && ab.title === 'About 00_Cerebrum', 'About 00_Cerebrum in the list shows About in the same window',
          'open=' + ab.open + ' showing ' + ab.shown + ' titled "' + ab.title + '"');
    // The window moves by its head, as j4k's does (the owner on j4k, 23.10.2026:
    // "cant move the settings window ... stuck in space"), stays 8px inside the
    // page however far it is pulled, and opens in the middle again.
    { const winAt = () => page.evaluate(() => { const r = document.getElementById('setWin').getBoundingClientRect();
      return { l: Math.round(r.left), t: Math.round(r.top), w: r.width, h: r.height, cx: Math.abs(r.left + r.width / 2 - innerWidth / 2) < 2 }; });
    var grip = await page.evaluate(() => { const r = document.querySelector('#setWin .winHead h2').getBoundingClientRect(); return [r.left + 20, r.top + r.height / 2]; });
    var wA = await winAt();
    await page.mouse.move(grip[0], grip[1]); await page.mouse.down(); await page.mouse.move(grip[0] - 120, grip[1], { steps: 6 }); await page.mouse.up();
    var wB = await winAt();
    var grip2 = await page.evaluate(() => { const r = document.querySelector('#setWin .winHead h2').getBoundingClientRect(); return [r.left + 20, r.top + r.height / 2]; });
    await page.mouse.move(grip2[0], grip2[1]); await page.mouse.down(); await page.mouse.move(grip2[0] - 3000, grip2[1], { steps: 6 }); await page.mouse.up();
    var wC = await winAt();
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    await page.click('#bSet');
    await page.waitForTimeout(300);
    var wD = await winAt();
    check(wB.l === wA.l - 120 && wB.t === wA.t && wC.l === 8 && wD.cx,
          'the head moves Settings, it stays 8px inside the page, and it opens in the middle again',
          'left ' + wA.l + ' -> ' + wB.l + ' after 120px, ' + wC.l + ' after 3000px; reopened centred=' + wD.cx); }
    await page.keyboard.press('Escape');
    await page.unroute('http://127.0.0.1:8760/health');
    await page.unroute('http://127.0.0.1:8760/models');
    await page.reload();
    await page.waitForTimeout(900);
  }

  if (part('10')) {
    // 10. The header sits over both views, so what it filters, it filters in
    // both. Until 14.09.2026 the categories filtered only the graph, which was
    // right while they sat inside it.
    await page.click('#bList');
    await page.waitForTimeout(200);
    var catF = await page.evaluate(() => {
      const chipFor = name => [...document.querySelectorAll('#legend .chip')].find(c => c.querySelector('b').textContent === name);
      const rows = () => [...document.querySelectorAll('.it')];
    // the category with the most concepts, whichever a vault has, rather than
    // one this checker's source vault happens to use
    const cnt = {}; N.forEach(n => { const c = cat(n.id); cnt[c] = (cnt[c] || 0) + 1; });
    const cc = Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a])[0], lab = LBL[cc] || cc;
    const r = { cat: cc, before: rows().length, people: rows().filter(e => cat(e.dataset.t) === cc).length };
    chipFor(lab).click();
      r.after = rows().length;
    r.peopleAfter = rows().filter(e => cat(e.dataset.t) === cc).length;
    r.drawn = N.filter(n => cat(n.id) === cc && !hid(n)).length;
    chipFor(lab).click();
      r.restored = rows().length;
      return r;
    });
    check(catF.people > 0 && catF.peopleAfter === 0 && catF.after === catF.before - catF.people &&
          catF.drawn === 0 && catF.restored === catF.before,
          'a category switched off in the header leaves the list as well as the graph',
        catF.before + ' rows, ' + catF.people + ' ' + catF.cat + ' -> ' + catF.after + ', drawn ' + catF.drawn + ', back to ' + catF.restored);
  }

  if (part('11')) {
    // 11. A stored state must not reopen as a dead page. Caught by the owner on
    // 14.09.2026: the viewer "is not working under chrome" while Safari showed it
    // The search bar, the two modes and the reports window. Added 16.09.2026,
    // when the bar went full width and gained Ask Claude. The page is one file
    // opened from disk and the helper that answers a question is started by
    // hand, so the state these checks care about most is the helper being OFF:
    // that is how the page is opened nearly always, and the bar has to be the
    // search box it has always been, with the two new buttons saying plainly
    // that they cannot work rather than failing when pressed.
    var bar = await page.evaluate(() => {
      return {
        search: !!document.getElementById('mSearch'),
        ask: !!document.getElementById('mAsk'),
        reports: !!document.getElementById('bRep'),
        searchOn: document.getElementById('mSearch').classList.contains('on'),
        askOn: document.getElementById('mAsk').classList.contains('on')
      };
    });
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
    var qbarBox = () => page.evaluate(() => {
      const el = document.getElementById('qbar'),
        r = el.getBoundingClientRect(), f = el.firstElementChild.getBoundingClientRect(),
        i = document.getElementById('q').getBoundingClientRect();
      return { bar: [r.left, r.top, r.right, r.bottom, r.height],
               q: [i.left, i.top, i.right, i.bottom, i.height], fill: f.width };
    });
    await page.evaluate(() => bar(true));
    await page.waitForTimeout(600);          // the fill eases over .45s
    var qbZero = await qbarBox();
    await page.evaluate(() => { bar(); bar(); });
    await page.waitForTimeout(600);
    var qbTwo = await qbarBox();
    await page.evaluate(() => { const el = document.getElementById('qbar');
      el.hidden = true; el.classList.remove('done');
      el.firstElementChild.style.width = '0%'; });
    var prog = { zero: qbZero, two: qbTwo };
    var z = prog.zero;
    var inside = z.bar[0] >= z.q[0] - 0.5 && z.bar[1] >= z.q[1] - 0.5 &&
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
    var helper = await page.evaluate(async () => {
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
      const brain = await page.evaluate(async () => {
        const g = id => document.getElementById(id);
        const opts = [...g('bModel').options];
        const served = (await (await fetch('http://127.0.0.1:8760/models', { cache: 'no-store' })).json()).models;
        return {
          models: opts.length,
          locals: opts.filter(o => o.value.startsWith('local:')).length,
          served: served.length, servedLocal: served.filter(m => m.provider === 'local').length,
          missing: served.filter(m => !opts.some(o => o.value === m.id)).map(m => m.label),
          picked: g('bModel').value,
          effortControl: !!g('bEffort'), efforts: [...(g('bEffort') || { options: [] }).options].map(o => o.textContent).join('|'),
          where: g('brainWhere').textContent.trim(),
          rows: document.querySelectorAll('#bWeights .wr').length
        };
      });
      // The effort selector left on 27.09.2026, on the owner's instruction, and
      // came back on 24.10.2026 with j4k's Assistant as the shape: "look at the
      // assistant section of j4k. model and effort selector".
      // The counts are the helper's own, asked of it here. Until 08.10.2026 the
      // check asked for three local models by number. Two left the helper's list
      // that day, and the check stayed green for hours, because the helper that
      // answered had started before they left; it turned red the moment the
      // owner started a new one.
      check(brain.models === brain.served && brain.missing.length === 0 && brain.locals === brain.servedLocal &&
            brain.locals >= 1 && brain.models > brain.locals &&
            brain.picked.startsWith('claude-') && brain.effortControl && brain.efforts === 'Low|Medium|High|Extra high|Max',
            'Settings carries a Brain with every model, and an effort selector, as j4k\'s Assistant',
            brain.models + ' model(s) of the ' + brain.served + ' the helper serves, ' + brain.locals + ' local of its ' + brain.servedLocal +
            (brain.missing.length ? '; not in the list: ' + brain.missing.join(', ') : '') + '; picked ' +
            brain.picked + '; effort ' + (brain.efforts || 'none'));
      // The badge naming the model beside the Brain title left on 27.09.2026
      // with j4k's shape: the select already names it, and j4k removed its own
      // twin of that for the same reason — two controls reporting one fact.
      check(brain.rows === brain.servedLocal && brain.rows >= 1 && /Anthropic/.test(brain.where),
            'and a weights row per local model, and the where-line',
            brain.rows + ' row(s) for ' + brain.servedLocal + ' local model(s), "' + brain.where.slice(0, 60) + '…"');
      // One width for the Brain's controls, owner's request of 24.10.2026: "please
      // make the buttons in settings brain equal width". Open, Model, Effort and
      // each local model's button, measured as drawn, ending on one line.
      const cols = await page.evaluate(() => [document.getElementById('brainAsk'), document.getElementById('bModel'), document.getElementById('bEffort'),
        ...document.querySelectorAll('#bWeights .wr button')].map(e => { const r = e.getBoundingClientRect(); return [r.width, r.right]; }));
      check(cols.length >= 4 && cols.every(c => c[0] > 100 && Math.abs(c[0] - cols[0][0]) < 0.5 && Math.abs(c[1] - cols[0][1]) < 0.5),
            'the Brain\'s controls are one width and end on one line: Open, Model, Effort and each local model\'s button',
            cols.map(c => Math.round(c[0]) + '@' + Math.round(c[1])).join(', '));
      // Their words stand in the middle, a menu's as a button's (owner, 24.10.2026:
      // "make the text in the buttons in brain consistent, all centered"). Read
      // from the painted controls: where the ink of the words lies, a menu's arrow
      // left out. Brain is shown for the pictures, and Knowledge bases again after.
      await page.click('.setTab[data-part="paneBrain"]');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(200);
      const mid = [];
      for (const sel of ['#brainAsk', '#bModel', '#bEffort', '#bWeights .wr button']) {
        const el = page.locator(sel).first(), bx = await el.boundingBox(), px = pngPixels(await el.screenshot()),
          W = Math.floor(bx.width), H = Math.floor(bx.height), bg = px(4, H >> 1), ink = [];
        for (let x = 4; x < W - 4; x++) for (let y = H >> 2; y < H * 3 / 4; y++) {
          const c = px(x, y); if (Math.abs(c[0] - bg[0]) + Math.abs(c[1] - bg[1]) + Math.abs(c[2] - bg[2]) > 120) { ink.push(x); break; } }
        const runs = []; for (const x of ink) { if (runs.length && x - runs[runs.length - 1][1] <= 6) runs[runs.length - 1][1] = x; else runs.push([x, x]); }
        if ((sel === '#bModel' || sel === '#bEffort') && runs.length > 1 && runs[runs.length - 1][0] > W - 24) runs.pop();
        mid.push(runs.length ? (runs[0][0] + runs[runs.length - 1][1]) / 2 - W / 2 : NaN);
      }
      await page.click('.setTab[data-part="paneKb"]');
      await page.waitForTimeout(150);
      check(mid.every(d => Math.abs(d) <= 1.5), 'the words in the Brain\'s controls stand in their middle, a menu\'s as a button\'s',
            'off the middle by ' + mid.map(d => d.toFixed(1)).join(', ') + ' px: Open, Model, Effort, the local model\'s button');

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

      // The effort chosen rides on the question, and the selector shows it.
      const eff = await page.evaluate(async () => {
        localStorage.setItem('okf.effort', 'max');
        localStorage.setItem('okf.model', 'claude-opus-5-5');
        loadPick(); await loadBrain();
        return {sent: JSON.stringify(brainBody()), shown: document.getElementById('bEffort').value,
                off: document.getElementById('bEffort').disabled, ask: document.getElementById('mAsk').title};
      });
      check(/"model":"claude-opus-5-5"/.test(eff.sent) && /"effort":"max"/.test(eff.sent) && eff.shown === 'max' && !eff.off,
            'a question carries the effort chosen, and the selector shows it',
            'body ' + eff.sent + ', selector ' + eff.shown + (eff.off ? ' (disabled)' : ''));

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
                sent: JSON.stringify(brainBody()), effortOff: document.getElementById('bEffort').disabled};
      });
      // The wording was shortened on the owner's instruction on 16.09.2026 and
      // the first cut dropped the Ask clause entirely; this check caught it. The
      // two facts the line must state are what is matched, not the old phrasing.
      check(/Nothing leaves/i.test(localPick.where) &&
            /Ask needs/i.test(localPick.where) &&
            localPick.sent.includes('local:') && !/effort/.test(localPick.sent) && localPick.effortOff,
            'a local model says nothing leaves the Mac, and that Ask needs another, and takes no effort level',
            '"' + localPick.where.slice(0, 90) + '…"; request body ' + localPick.sent);

      // The choice has to survive a reload, or it is a control the reader sets
      // once per visit. Back to the default afterwards, so no later check runs
      // against a brain this one happened to leave selected.
      // The model is taken from the list the helper serves, not named here. The
      // check named Sonnet 5 until 04.10.2026, when that model left the list;
      // naming its successor failed at once, because a helper that is still
      // running serves the list it started with. What is tested is that a choice
      // survives, whichever model it is.
      const chosen = await page.evaluate(() => {
        const m = document.getElementById('bModel');
        const ids = MODELS.filter(x => x.provider !== 'local').map(x => x.id);
        const id = ids.find(i => i.includes('sonnet')) || ids[ids.length - 1];
        m.value = id; m.dispatchEvent(new Event('change'));
        const e = document.getElementById('bEffort'); e.value = 'low'; e.dispatchEvent(new Event('change'));
        return id;
      });
      await page.waitForTimeout(400);
      await page.reload();
      await page.waitForTimeout(3000);
      const kept = await page.evaluate(() => ({
        stored: localStorage.getItem('okf.model'), effort: localStorage.getItem('okf.effort'),
        sent: JSON.stringify(brainBody())
      }));
      check(!!chosen && kept.stored === chosen && kept.sent.includes(chosen) && kept.effort === 'low',
            'and the chosen brain and effort survive a reload, and the brain rides on the next question',
            'stored ' + kept.stored + ' at ' + kept.effort + ', body ' + kept.sent);
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
    var hits = await page.evaluate(() => document.querySelectorAll('#tree .it').length);
    await page.fill('#q', '');
    await page.waitForTimeout(350);
    var restored = await page.evaluate(() => document.querySelectorAll('#tree .it').length);
    var total = await page.evaluate(() => Object.keys(D).length);
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

    // The address names a view and a search, 27.09.2026, for GLaDOS, the owner's
    // voice assistant: "switch to concepts, 2D view and 3D view", "search for
    // something using the search bar (not ask for Claude)", "this should work in all
    // views". `#view=…&q=…` applies on load and on every change of the fragment, which
    // is how she steers the viewer's tab without reloading it; a part the fragment
    // does not name is left as it is, an empty q clears the search, and the search is
    // always Search, never Ask. She looks for the meta tag before telling anyone the
    // page followed her.
    // A word from a title that some concept does not carry, so the search it
    // makes narrows the list rather than leaving it whole.
    var word = await page.evaluate(() => {
      const hay = Object.keys(D).map(id => (D[id].t + ' ' + D[id].d + ' ' + D[id].tags.join(' ') + ' ' + id).toLowerCase());
      return Object.values(D).flatMap(c => c.t.split(/\s+/)).filter(w => /^[A-Za-z]{3,}$/.test(w))
        .find(w => hay.some(h => !h.includes(w.toLowerCase())));
    });
    var addr = async hash => {
      await page.evaluate(h => { location.hash = h; }, hash);
      await page.waitForTimeout(400);
      return page.evaluate(() => ({
        view: ['vg', 'vc', 'v3'].filter(c => document.body.classList.contains(c)).join(','),
        q: document.getElementById('q').value,
        search: document.getElementById('mSearch').getAttribute('aria-pressed'),
        rows: document.querySelectorAll('#tree .it').length, total: Object.keys(D).length,
      }));
    };
    await page.goto('about:blank');
    await page.goto('file://' + FILE + '#view=3d&q=' + encodeURIComponent(word) + '&n=1');
    await page.waitForTimeout(900);
    var onLoad = await page.evaluate(() => ({
      view: ['vg', 'vc', 'v3'].filter(c => document.body.classList.contains(c)).join(','),
      q: document.getElementById('q').value, search: document.getElementById('mSearch').getAttribute('aria-pressed'),
      rows: document.querySelectorAll('#tree .it').length, total: Object.keys(D).length,
      meta: document.querySelector('meta[name="cerebrum-address"]')?.content ?? null,
    }));
    check(onLoad.meta === 'view q cine', 'the page says it reads its address, and which parts of it', String(onLoad.meta));
    check(onLoad.view === 'v3' && onLoad.q === word && onLoad.search === 'true' && onLoad.rows > 0 && onLoad.rows < onLoad.total,
          'an address opens the page on its view, searching for its q',
          'view=' + onLoad.view + ' q=' + JSON.stringify(onLoad.q) + ' search=' + onLoad.search + ' ' + onLoad.rows + ' of ' + onLoad.total);
    var toConcepts = await addr('view=concepts&n=2');
    check(toConcepts.view === 'vc' && toConcepts.q === word && toConcepts.rows === onLoad.rows,
          'a changed address switches the view and leaves the search it does not name',
          'view=' + toConcepts.view + ' q=' + JSON.stringify(toConcepts.q) + ' ' + toConcepts.rows + ' rows');
    var toGraph = await addr('view=2d&q=&n=3');
    check(toGraph.view === 'vg' && toGraph.q === '' && toGraph.rows === toGraph.total,
          '2d is the Graph view, and an empty q clears the search',
          'view=' + toGraph.view + ' q=' + JSON.stringify(toGraph.q) + ' ' + toGraph.rows + ' of ' + toGraph.total);
    // The address can start the Film, 08.10.2026, for the same assistant. The
    // owner's words, passed on by her session: "in Cerebrum, in 3D view, can you
    // teach glados to start the film?". `cine=film` does what the Film button
    // did, and the Timelapse button does since 24.10.2026, on a changed address
    // and on load. An address without `cine` leaves
    // what plays; the same address again, made new by `n`, starts the film from
    // its beginning, as a second press of the button does; with Reduce Motion
    // the film opens and waits for Play, as it does from the button. She sends
    // `cine` only when the tag above names it.
    {
    var film = () => page.evaluate(() => { const s = G3.cine.state();
      return { kind: s.kind, playing: s.playing, fp: s.fp, intro: s.intro, cine: document.body.classList.contains('cine'), v3: document.body.classList.contains('v3'), drawn: G3.drawn }; });
    await addr('view=3d&cine=film&n=4');
    var started = await film();
    check(started.kind === 'film' && started.playing && started.cine && started.v3 && started.fp === 0 && started.intro > 0,
          'a changed address with cine=film starts the Timelapse at its title, as its button does',
          'cinema ' + started.kind + ', playing ' + started.playing + ', month ' + (started.fp ?? 0).toFixed(1) + ', title time left ' + Math.round(started.intro ?? 0) + 'ms, view ' + (started.v3 ? '3d' : 'another'));
    // A third of the film, not a month of one vault's years.
    var third = await page.evaluate(() => { const m = G3.cine.state().total / 3; G3.cine.seek(m); return m; });
    await addr('view=3d&q=&n=5');
    var kept = await film();
    check(kept.kind === 'film' && kept.playing && kept.fp > third,
          'an address without cine leaves the Timelapse that plays',
          'cinema ' + kept.kind + ', playing ' + kept.playing + ', month ' + (kept.fp ?? 0).toFixed(1) + ' after month ' + third.toFixed(1));
    await addr('view=3d&cine=film&n=6');
    var again = await film();
    check(again.kind === 'film' && again.playing && again.fp === 0 && again.intro > 0,
          'the same address again, made new, starts the Timelapse from its title',
          'cinema ' + again.kind + ', playing ' + again.playing + ', month ' + (again.fp ?? 0).toFixed(1) + ', title time left ' + Math.round(again.intro ?? 0) + 'ms');
    await page.evaluate(() => G3.cine.stop());
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await addr('view=3d&cine=film&n=7');
    var calm = await film();
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    check(calm.kind === 'film' && !calm.playing && calm.fp === 0 && calm.cine,
          'with reduced motion an address opens the Timelapse and it waits for Play',
          'cinema ' + calm.kind + ', playing ' + calm.playing + ', month ' + calm.fp);
    // On load: a new tab opened with the address, before the 3D view has drawn a frame.
    await page.goto('about:blank');
    await page.goto('file://' + FILE + '#view=3d&cine=film&n=8');
    await page.waitForTimeout(3300);   // past the title's 1.8 seconds
    var born = await film();
    check(born.kind === 'film' && born.playing && born.cine && born.v3 && born.fp > 1 && born.drawn > 0,
          'an address with cine=film opens the page in the Timelapse, and it plays',
          'cinema ' + born.kind + ', playing ' + born.playing + ', month ' + (born.fp ?? 0).toFixed(1) + ', ' + born.drawn + ' concepts in the picture, view ' + (born.v3 ? '3d' : 'another'));
    }
  }
  check(jsErrors.length === 0, 'and no JS error on the way', jsErrors[0]);
  check(weightAsks.length === 0, 'no step of this check asked the helper to delete or fetch a model', weightAsks.slice(0, 3).join('; ') || 'none asked');

  await browser.close();
  console.log((failures ? 'viewer-check: ' + failures + ' FAILURE(S)' : 'viewer-check: green') + (ONLY.length ? '  [sections ' + ONLY.join(', ') + ' only]' : ''));
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error('viewer-check crashed: ' + e.message); process.exit(1); });
