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
test('page hide never starts a parallel resume write while the native queue is in flight', () => {
    const s = scorm(); s.set('cmi.suspend_data', 'old'); s.set('cmi.suspend_data', 'new');
    assert.equal(s.ajax.length, 1);
    s.window.emit('pagehide'); s.document.visibilityState = 'hidden'; s.document.emit('visibilitychange');
    assert.equal(s.requests.length, 0);
    assert.equal(s.ajax.filter(r => r.url === '/native/scorm_set_values').length, 1);
    assert.deepEqual(JSON.parse(s.ajax[0].data), [{name: 'cmi.suspend_data', value: 'old'}]);
    // Destroyed-page delivery is deliberately unclaimed. With a live page,
    // acknowledgement serializes the next request after the first completes.
    s.ajax[0].success([]); s.ajax[0].complete();
    const saves = s.ajax.filter(r => r.url === '/native/scorm_set_values');
    assert.equal(saves.length, 2);
    assert.deepEqual(JSON.parse(saves[1].data), [{name: 'cmi.suspend_data', value: 'new'}]);
});
test('normal queue preserves score, completion and session values in their original order', () => {
    const s = scorm();
    const pairs = [['cmi.core.score.raw', '0'], ['cmi.completion_status', 'completed'],
        ['cmi.session_time', 'PT1M'], ['cmi.exit', 'suspend']];
    pairs.forEach(pair => s.set(...pair));
    assert.equal(s.ajax.length, 1);
    s.ajax[0].success([{grade: 0}]); s.ajax[0].complete();
    assert.deepEqual(JSON.parse(s.ajax[0].data), [{name: pairs[0][0], value: pairs[0][1]}]);
    assert.deepEqual(JSON.parse(s.ajax[1].data), pairs.slice(1).map(([name, value]) => ({name, value})));
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
