/* Execute the actual package assets with DOM/HTTP protocol doubles.
 * No browser, package rendering, real server persistence or grade claim.
 * MEREKA_SCORM_CLIENT can select an unmodified upstream client asset.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.join(__dirname, '../openedxscorm/static/js/src');
function target() {
    const handlers = new Map();
    return {handlers, addEventListener(k, f) {const list = handlers.get(k) || []; list.push(f); handlers.set(k, list);},
        removeEventListener(k, f) {handlers.set(k, (handlers.get(k) || []).filter(x => x !== f));},
        emit(k) {(handlers.get(k) || []).forEach(f => f());}};
}
function scorm(staff = false) {
    const window = Object.assign(target(), {location: {href: 'https://preview.test/course'}});
    const document = Object.assign(target(), {cookie: 'csrftoken=scorm-token', visibilityState: 'visible'});
    const requests = [], ajax = [], nodes = [];
    let setValue, selectedReport, reportResponse, ready;
    function node(tag, props = {}) {
        const n = {tag, props, children: [], length: tag === '.scorm-reports .report' ? Number(staff) : 1,
            find(selector) {return node(selector);}, get() {return {addEventListener() {}};},
            on() {return n;}, html(value) {n.htmlValue = value; return n;},
            empty() {n.children = []; return n;}, append(value) {n.children.push(value); return n;},
            removeClass() {return n;}, addClass() {return n;}};
        nodes.push(n); return n;
    }
    function $(arg, props) {if (typeof arg === 'function') {ready = arg; return;} return node(arg, props);}
    $.each = (values, f) => values.forEach((v, i) => f(i, v));
    $.extend = (...args) => Object.assign(...args);
    $.ui = {autocomplete(options) {selectedReport = options.select;}};
    $.ajax = options => {
        ajax.push(options);
        const chain = {success(f) {reportResponse = f; return chain;}, fail() {return chain;}, complete() {return chain;}};
        return chain;
    };
    const context = vm.createContext({window, document, $, console,
        initScorm(version, get, set) {setValue = set;},
        renderjson: {set_show_to_level() {return raw => ({raw});}},
        fetch(url, options) {requests.push({url, options}); return Promise.resolve({ok: true});}});
    const source = process.env.MEREKA_SCORM_CLIENT || path.join(assets, 'scormxblock.js');
    vm.runInContext(fs.readFileSync(source, 'utf8'), context);
    context.ScormXBlock({handlerUrl: (el, handler) => '/native/' + handler}, {},
        {scorm_data: {}, scorm_version: '1.2', popup_on_launch: false});
    ready($);
    return {window, document, requests, ajax, nodes, set: (...args) => setValue(...args),
        report(data) {selectedReport({}, {item: {data: {student_id: 1}}}); reportResponse(data);}};
}
test('SCORM pending resume survives pagehide with correct native endpoint and CSRF', () => {
    const s = scorm(); assert.equal(s.set('cmi.suspend_data', 'owned-answer'), 'true');
    s.window.emit('pagehide'); s.document.visibilityState = 'hidden'; s.document.emit('visibilitychange');
    assert.equal(s.requests.length, 1);
    const {url, options} = s.requests[0];
    assert.equal(url, '/native/scorm_set_values'); assert.equal(options.keepalive, true);
    assert.equal(options.headers['X-CSRFToken'], 'scorm-token');
    assert.deepEqual(JSON.parse(options.body), [{name: 'cmi.suspend_data', value: 'owned-answer'}]);
});
test('SCORM acknowledged state is not retransmitted; late writes survive an older acknowledgment', () => {
    const s = scorm(); s.set('cmi.suspend_data', 'old'); s.set('cmi.suspend_data', 'new');
    s.ajax[0].success([]); s.ajax[0].complete(); s.window.emit('pagehide');
    assert.equal(s.requests.length, 1);
    assert.deepEqual(JSON.parse(s.requests[0].options.body), [{name: 'cmi.suspend_data', value: 'new'}]);
    const a = scorm(); a.set('cmi.location', 'saved'); a.ajax[0].success([]); a.ajax[0].complete();
    a.window.emit('pagehide'); assert.equal(a.requests.length, 0);
});
test('SCORM unload fallback never sends grades, status, completion, session time or exit', () => {
    const s = scorm();
    for (const key of ['cmi.core.lesson_status', 'cmi.completion_status', 'cmi.success_status',
        'cmi.core.score.raw', 'cmi.score.raw', 'cmi.score.scaled', 'cmi.mode',
        'cmi.progress_measure', 'cmi.session_time', 'cmi.core.session_time', 'cmi.exit', 'cmi.core.exit']) s.set(key, '1');
    s.window.emit('pagehide'); assert.equal(s.requests.length, 0);
});
test('SCORM report keeps learner content as text and elides long resume state', () => {
    const s = scorm(true), attack = '<img src=x onerror=alert(1)>';
    s.report({'cmi.core.student_name': attack, 'cmi.core.lesson_status': 'completed', 'cmi.suspend_data': 'x'.repeat(500)});
    assert(s.nodes.some(n => n.tag === '<td>' && n.props.text === attack));
    assert(!s.nodes.some(n => n.htmlValue === attack));
    const rendered = s.nodes.flatMap(n => n.children).find(n => n?.raw);
    assert.equal(rendered.raw['cmi.suspend_data'], '[resume state omitted: 500 chars]');
});
