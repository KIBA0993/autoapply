/* autoapply — browser field inventory + four-layer fill verification.
 *
 * WHY: a full-tree read_page is up to ~12.5k tokens and several per form dwarf every
 * profile file combined. This library does the two expensive browser reads — enumerate
 * the fields, and verify a fill — in one small javascript_tool call each (~300 tokens),
 * and verifies four ways so the "form submits blank / silent no-op" failure class is
 * caught before hand-off.
 *
 * HOW: inject this whole file ONCE per tab via javascript_tool (it defines window.aa and
 * returns a readiness line). Then every later call is tiny:
 *     JSON.stringify(aa.inventory())     // #2 — enumerate fillable fields (replaces read_page)
 *     JSON.stringify(aa.verify())        // #1 — four-layer post-fill check; returns PROBLEMS only
 *     aa.fill('aa3', 'value')            // native-setter fill for plain fields (see caveat)
 * window.aa persists on the page until navigation/reload — and our rule is never to
 * navigate a filled tab — so one injection covers the whole fill. Re-inject only after a
 * wizard step rebuilds the DOM (Workday) or in a fresh tab.
 *
 * Fields are stamped with data-aa-ref so inventory -> fill -> verify share one ref space.
 * Traverses shadow DOM + same-origin iframes; skips hidden/disabled/submit controls.
 *
 * CAVEAT: aa.fill() handles text/textarea/select/checkbox/radio via the native setter +
 * input/change dispatch. It deliberately REFUSES comboboxes (react-select), file inputs,
 * and rich-text — those need the documented per-ATS method (react-select: focus -> real
 * `type` -> Enter, one per call; file upload: the user). inventory() flags them by type so
 * you know which path to take. Never rely on fill() for a combobox.
 */
(function () {
  const FILLABLE = 'input, textarea, select, [role=combobox], [contenteditable=true]';
  const SKIP_TYPES = new Set(['hidden', 'submit', 'button', 'reset', 'image']);

  // Yield document, every shadow root, and every same-origin iframe document.
  function* roots(root) {
    yield root;
    for (const el of root.querySelectorAll('*')) {
      if (el.shadowRoot) yield* roots(el.shadowRoot);
    }
    for (const f of root.querySelectorAll('iframe')) {
      let doc = null;
      try { doc = f.contentDocument; } catch (e) { doc = null; } // cross-origin -> skip
      if (doc) yield* roots(doc);
    }
  }

  function visible(el) {
    if (el.disabled) return false;
    if (el.type && SKIP_TYPES.has(el.type)) return false;
    const win = el.ownerDocument.defaultView || window;
    const s = win.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    if (el.offsetParent === null && s.position !== 'fixed') return false;
    return true;
  }

  // CSS.escape is present in every modern browser, but fall back defensively so a stray
  // embedded/older context can't throw mid-inventory.
  function cssEscape(s) {
    if (typeof CSS !== 'undefined' && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, function (c) { return '\\' + c; });
  }

  // Resolve an id within the element's own root (document OR its shadow root) — a shadow
  // field's <label for>/aria targets live in the shadow root, not el.ownerDocument.
  function byId(root, id) { return root.querySelector('#' + cssEscape(id)); }

  function labelFor(el) {
    const root = el.getRootNode();
    if (el.id) {
      const l = root.querySelector('label[for="' + cssEscape(el.id) + '"]');
      if (l && l.textContent.trim()) return l.textContent.trim().slice(0, 120);
    }
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const t = lb.split(/\s+/)
        .map(function (id) { const n = byId(root, id); return n && n.textContent.trim(); })
        .filter(Boolean).join(' ');
      if (t) return t.slice(0, 120);
    }
    const al = el.getAttribute('aria-label');
    if (al && al.trim()) return al.trim().slice(0, 120);
    const wl = el.closest('label');
    if (wl && wl.textContent.trim()) return wl.textContent.trim().slice(0, 120);
    const grp = el.closest('[class*=field], [class*=form-group], [class*=question], fieldset');
    if (grp) {
      const lbl = grp.querySelector('label, legend, [class*=label]');
      if (lbl && lbl.textContent.trim()) return lbl.textContent.trim().slice(0, 120);
    }
    if (el.placeholder && el.placeholder.trim()) return el.placeholder.trim().slice(0, 120);
    return el.name || '(unlabeled)';
  }

  function fieldType(el) {
    if (el.getAttribute('role') === 'combobox' || el.closest('[class*=select__control]')) return 'combobox';
    const tag = el.tagName.toLowerCase();
    if (tag === 'textarea') return 'textarea';
    if (tag === 'select') return 'select';
    if (el.isContentEditable) return 'richtext';
    return (el.type || 'text').toLowerCase();
  }

  function allFields() {
    const out = [];
    const seen = new Set();
    for (const root of roots(document)) {
      for (const el of root.querySelectorAll(FILLABLE)) {
        if (seen.has(el) || !visible(el)) continue;
        seen.add(el);
        out.push(el);
      }
    }
    return out;
  }

  function isChecky(type) { return type === 'checkbox' || type === 'radio'; }

  // react-select and similar keep the chosen value in a display span, not the input's
  // .value — read that so verify doesn't false-flag a filled dropdown as empty.
  function fieldValue(el, type) {
    if (isChecky(type)) return !!el.checked;
    if (type === 'combobox') {
      const ctrl = el.closest('[class*=select__control], [class*=select__container]') || el.parentElement;
      const sv = ctrl && ctrl.querySelector('[class*=single-value], [class*=multi-value__label]');
      if (sv && sv.textContent.trim()) return sv.textContent.trim();
    }
    return el.value || '';
  }

  function inventory() {
    let n = 0;
    const rows = [];
    for (const el of allFields()) {
      const ref = 'aa' + (++n);
      el.setAttribute('data-aa-ref', ref);
      const type = fieldType(el);
      const rec = {
        ref: ref,
        label: labelFor(el),
        type: type,
        required: !!(el.required || el.getAttribute('aria-required') === 'true'),
        value: fieldValue(el, type),
      };
      if (type === 'select') rec.options = [].map.call(el.options, function (o) { return o.text.trim(); }).slice(0, 40);
      rows.push(rec);
    }
    return rows;
  }

  function byRef(ref) {
    for (const root of roots(document)) {
      const el = root.querySelector('[data-aa-ref="' + ref + '"]');
      if (el) return el;
    }
    return null;
  }

  function setNative(el, value) {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
      : el.tagName === 'SELECT' ? HTMLSelectElement.prototype
      : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    // Capture the pre-fill value BEFORE we overwrite it — React's diff needs the old value.
    const lastValue = el.value;
    if (desc && desc.set) desc.set.call(el, value); else el.value = value;
    // React 16+ hangs a hidden `_valueTracker` on the element holding its last-known value.
    // Setting `.value` (even via the native setter) does NOT update that tracker, so when the
    // `input` event fires React compares the event against the stale tracker, decides "nothing
    // changed", ignores our value, and reverts it on the next re-render — the field then shows
    // empty/invalid and submit refuses. Priming the tracker with the OLD value makes React see
    // a real diff and accept the fill on the first pass. (No-op on non-React pages.)
    if (el._valueTracker) el._valueTracker.setValue(lastValue);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    // onBlur-mode validators (Formik, react-hook-form) only clear a required-error and mark the
    // field valid on blur. Without a blur the value is in the DOM but the field stays flagged
    // invalid — which is what forced the costly manual-retype fallback loop. Fire blur/focusout
    // so validation runs now. (Safe here: fill() refuses comboboxes, whose menus close on blur.)
    el.dispatchEvent(new FocusEvent('blur', { bubbles: false }));
    el.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
  }

  function fill(ref, value) {
    const el = byRef(ref);
    if (!el) return { ref: ref, ok: false, err: 'not found' };
    const type = fieldType(el);
    if (type === 'combobox' || type === 'file' || type === 'richtext')
      return { ref: ref, ok: false, err: 'use the documented method for type=' + type };
    if (isChecky(type)) {
      if (!!el.checked !== !!value) el.click();
    } else if (type === 'select') {
      const opt = [].find.call(el.options, function (o) { return o.text.trim() === value || o.value === value; });
      if (!opt) return { ref: ref, ok: false, err: 'no option matches: ' + value };
      el.value = opt.value;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      el.focus();
      setNative(el, value);
    }
    return { ref: ref, ok: true, value: isChecky(type) ? el.checked : el.value };
  }

  // Layer 4: an error message adjacent to (or referenced by) the field.
  function nearbyError(el) {
    const root = el.getRootNode();
    for (const attr of ['aria-errormessage', 'aria-describedby']) {
      const v = el.getAttribute(attr);
      if (!v) continue;
      for (const id of v.split(/\s+/)) {
        const n = byId(root, id);
        if (n && n.textContent.trim() &&
            (n.getAttribute('role') === 'alert' || /error|invalid|required/i.test(n.className + ' ' + n.textContent)))
          return n.textContent.trim().slice(0, 120);
      }
    }
    const grp = el.closest('[class*=field], [class*=form-group], [class*=question], fieldset');
    if (grp) {
      const e = grp.querySelector('[role=alert], [aria-invalid="true"], [class*=error]:not(input):not(select):not(textarea)');
      if (e && e.textContent.trim() && e !== el) return e.textContent.trim().slice(0, 120);
    }
    return null;
  }

  // #1 — four-layer verify. Returns PROBLEMS only + a pass count, plus form-level signal.
  function verify(refs) {
    const els = refs
      ? refs.map(byRef).filter(Boolean)
      : allFields().filter(function (e) { return e.hasAttribute('data-aa-ref'); });
    const problems = [];
    let ok = 0;
    for (const el of els) {
      const type = fieldType(el);
      const value = fieldValue(el, type);
      const required = !!(el.required || el.getAttribute('aria-required') === 'true');
      const issues = [];
      if (required && (value === '' || value === false)) issues.push('required-empty');          // layer 1: readback
      if (typeof el.checkValidity === 'function' && !el.checkValidity())
        issues.push('invalid:' + (el.validationMessage || '').slice(0, 60));                       // layer 2: HTML5 validity
      if (el.getAttribute('aria-invalid') === 'true') issues.push('aria-invalid');                 // layer 3: ARIA
      const err = nearbyError(el);
      if (err) issues.push('error:' + err);                                                        // layer 4: error banner
      if (issues.length) problems.push({ ref: el.getAttribute('data-aa-ref'), label: labelFor(el), type: type, value: value, issues: issues });
      else ok++;
    }
    const forms = [].slice.call(document.querySelectorAll('form'));
    const formValid = forms.length ? forms.every(function (f) { return f.checkValidity(); }) : null;
    const banners = [].map.call(document.querySelectorAll('[role=alert]'), function (b) { return b.textContent.trim(); })
      .filter(Boolean).slice(0, 5);
    return { ok: ok, problems: problems, formValid: formValid, banners: banners };
  }

  // Pre-submit identity gate: what job is THIS live page, right now? Read immediately before
  // the irreversible click and compare host + ATS job-id against the dispatched url — catches a
  // post-fill redirect, an expired-session bounce, or the wrong tab being fronted after the
  // embedded-ATS new-tab hop, none of which aa.verify() (a field-level check) can see. host and
  // jobId are the hard gate (exact); header is advisory only (fuzzy title, may be generic on SPAs).
  function identity() {
    var path = location.pathname;
    var jobId = null, m;
    if ((m = path.match(/\/jobs\/(\d+)/))) jobId = m[1];                 // greenhouse / generic /jobs/{n}
    else if ((m = path.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i))) jobId = m[1].toLowerCase(); // lever / ashby uuid
    else if ((m = path.match(/\/j\/([A-Za-z0-9]{6,})/))) jobId = m[1];   // workable shortcode /j/XXXX
    else if ((m = path.match(/\/(\d+)\/?$/))) jobId = m[1];              // trailing numeric segment (bamboohr /careers/21)
    else if ((m = path.match(/(\d{4,})/))) jobId = m[1];                 // any 4+ digit id elsewhere in path
    var h = document.querySelector('h1, [class*=posting-headline], [class*=job-title], [class*=jobTitle], [data-testid*=title]');
    var header = ((h && h.textContent) || document.title || '').trim().slice(0, 200);
    return { host: location.host, path: path, jobId: jobId, header: header };
  }

  // ---- combobox / choice helpers — DOM reads that replace the screenshot→coordinate-click
  // loop that dominated cost. react-select is fought entirely through the DOM here: no picture,
  // no pixel math. inventory() flags type=combobox; use these instead of fill() for those. ----

  function comboControl(el) {
    return el.closest('[class*=select__control], [class*=select__container], [class*=-container], [role=combobox]')
      || el.parentElement || el;
  }

  // react-select portals its open menu to <body>, so scan every root — not the control subtree.
  function optionNodes() {
    const out = [], seen = new Set();
    for (const root of roots(document)) {
      for (const o of root.querySelectorAll('[role=option], [class*=select__option], [class*=-option]')) {
        if (seen.has(o)) continue;
        seen.add(o);
        if (o.offsetParent !== null || (o.getClientRects && o.getClientRects().length)) out.push(o);
      }
    }
    return out;
  }

  function optionList() {
    return optionNodes()
      .map(function (o, i) { return { i: i, text: (o.textContent || '').trim().slice(0, 80) }; })
      .filter(function (r) { return r.text; });
  }

  // Open a custom dropdown. react-select opens on the control's mousedown; native <select>
  // needs nothing. Returns options already rendered (some versions paint synchronously); if the
  // list comes back empty, call aa.options(ref) again next turn once React has painted the menu.
  function openMenu(ref) {
    const el = byRef(ref);
    if (!el) return { ref: ref, ok: false, err: 'not found' };
    if (fieldType(el) === 'select')
      return { ref: ref, ok: true, native: true,
               options: [].map.call(el.options, function (o) { return o.text.trim(); }).slice(0, 60) };
    const ctrl = comboControl(el);
    try { el.focus(); } catch (e) {}
    for (const ev of ['pointerdown', 'mousedown', 'mouseup'])
      ctrl.dispatchEvent(new MouseEvent(ev, { bubbles: true, cancelable: true, view: window }));
    // ArrowDown nudges react-select to open + highlight the first option if mousedown alone didn't.
    (el.tagName === 'INPUT' ? el : ctrl).dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, bubbles: true }));
    return { ref: ref, ok: true, native: false, options: optionList() };
  }

  // The rendered choice list for an already-open (or native) dropdown — no screenshot needed.
  function options(ref) {
    const el = byRef(ref);
    if (el && fieldType(el) === 'select')
      return { ref: ref, native: true,
               options: [].map.call(el.options, function (o) { return o.text.trim(); }).slice(0, 60) };
    return { ref: ref, native: false, options: optionList() };
  }

  // Choose a rendered option by case-insensitive exact-then-contains text — react-select commits
  // on the option's mousedown. Verifies and returns the committed value.
  function pick(ref, text) {
    const el = byRef(ref);
    if (!el) return { ref: ref, ok: false, err: 'not found' };
    const type = fieldType(el);
    if (type === 'select') return fill(ref, text);
    const want = String(text).trim().toLowerCase();
    const nodes = optionNodes();
    const target = nodes.find(function (o) { return (o.textContent || '').trim().toLowerCase() === want; })
      || nodes.find(function (o) { return (o.textContent || '').trim().toLowerCase().indexOf(want) !== -1; });
    if (!target) return { ref: ref, ok: false, err: 'no rendered option matches: ' + text, options: optionList() };
    const chosen = (target.textContent || '').trim();
    for (const ev of ['pointerdown', 'mousedown', 'mouseup', 'click'])
      target.dispatchEvent(new MouseEvent(ev, { bubbles: true, cancelable: true, view: window }));
    return { ref: ref, ok: true, chosen: chosen, value: fieldValue(el, type) };
  }

  // One-shot select. Native <select> completes synchronously. A custom combobox needs the
  // open→read→pick sequence (the menu paints async), so if the option isn't rendered yet this
  // returns the options + the exact next call rather than racing a picture. Never a screenshot.
  function select(ref, text) {
    const el = byRef(ref);
    if (!el) return { ref: ref, ok: false, err: 'not found' };
    if (fieldType(el) === 'select') return fill(ref, text);
    const opened = openMenu(ref);
    const got = pick(ref, text);
    if (got.ok) return got;
    return { ref: ref, ok: false, combobox: true,
             err: 'menu opened; option not rendered yet or no text match',
             options: (opened.options && opened.options.length) ? opened.options : optionList(),
             next: "call aa.options('" + ref + "') to read the list, then aa.pick('" + ref + "','<exact option text>')" };
  }

  // What is this control? For image/radio groups and unlabeled widgets the model would otherwise
  // screenshot — return the text/alt/title/options as ~200 tokens instead of an image.
  function describe(ref) {
    const el = byRef(ref);
    if (!el) return { ref: ref, err: 'not found' };
    const type = fieldType(el);
    const grp = el.closest('[role=radiogroup], fieldset, [class*=field], [class*=question], [class*=form-group]')
      || el.parentElement;
    const opts = grp ? [].map.call(
      grp.querySelectorAll('[role=radio], [role=option], input[type=radio], button, [class*=option]'),
      function (o) {
        // a bare radio/checkbox input has no text of its own — its label is on a wrapping/sibling
        // <label>, so fall back to labelFor() (same resolver inventory uses) before giving up.
        const t = (o.getAttribute('aria-label') || o.getAttribute('title') || o.getAttribute('alt')
                   || (o.textContent || '').trim() || labelFor(o) || '').trim();
        return { text: t.slice(0, 60),
                 checked: o.getAttribute('aria-checked') === 'true' || !!o.checked };
      }).filter(function (o) { return o.text && o.text !== '(unlabeled)'; }).slice(0, 20) : [];
    return {
      ref: ref, tag: el.tagName.toLowerCase(), type: type,
      role: el.getAttribute('role') || null, name: el.name || null,
      label: labelFor(el), value: fieldValue(el, type),
      alt: el.getAttribute('alt') || null, title: el.getAttribute('title') || null,
      nearbyText: grp ? (grp.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 200) : null,
      options: opts,
    };
  }

  // Interstitials the model would otherwise screenshot to confirm: captcha, login/SSO wall, and
  // third-party autofill extensions (Simplify) whose autofill RACES our fills and silently
  // reverts them. Detect fast so the worker parks with a clear reason instead of retrying 200x.
  function blockers() {
    const q = function (sel) { for (const r of roots(document)) { if (r.querySelector(sel)) return true; } return false; };
    const captcha = q('iframe[src*=recaptcha], iframe[src*=hcaptcha], iframe[src*=turnstile], '
      + '[class*=cf-challenge], [id*=cf-challenge], [class*=captcha], [data-sitekey]');
    const login = q('input[type=password]') && q('[name*=pass], [id*=pass], [autocomplete=current-password]');
    const autofill = q('[class*=simplify], [id*=simplify], simplify-autofill, [data-simplify], [class*=autofill-ext]');
    const banners = [].map.call(document.querySelectorAll('[role=alert]'), function (b) { return (b.textContent || '').trim(); })
      .filter(Boolean).slice(0, 5);
    return { captcha: captcha, login: !!login, autofillExtension: autofill, banners: banners };
  }

  window.aa = {
    inventory: inventory, verify: verify, fill: fill, identity: identity, byRef: byRef,
    openMenu: openMenu, options: options, pick: pick, select: select,
    describe: describe, blockers: blockers, version: 3,
  };
  return 'aa v3 ready: ' + allFields().length + ' fillable fields'
    + ' — fill()/select()/pick()/options()/describe()/verify()/blockers()/identity()';
})();
