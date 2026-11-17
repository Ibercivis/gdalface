/* Lost at Night — staff review of georeferencing attempts.
   Layout and map layers copied from the work area (gettask): a full-height Leaflet map with the same layers
   (OSM / Satellite / VIIRS / SDGSAT EU-UK) and an always-open "Map adjustments" panel, plus a right-hand rail.
   Every attempt is an outline (its warped photo). Flow:
     idle   → click a point on the map: the rail lists image → attempts covering it; the other outlines turn grey.
     list   → click an attempt: it expands in place (details, OK / Not OK) and only its outline + photo stay on the map.
              Click it again (or Esc) to collapse; a click elsewhere on the map starts over. */
(function () {
    'use strict';
    var R = window.REVIEW, T = R.t;
    var C_BASE = '#5f6fff', C_SEL = '#ff6a3d', C_OFF = '#8a8a99';   // attempt, selected, not at this point

    function cookie(name) {
        var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }
    // Tiny DOM helper: el('div', {class: 'x', onclick: fn}, 'text' | node | [children])
    function el(tag, attrs, kids) {
        var n = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (k) {
            if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), attrs[k]);
            else if (k === 'class') n.className = attrs[k];
            else n.setAttribute(k, attrs[k]);
        });
        [].concat(kids == null ? [] : kids).forEach(function (c) {
            n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
        });
        return n;
    }

    // ── Map: same layers and options as the work area (frontend/static/js/main.js) ──
    var osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap contributors', className: 'osm-tiles' });
    var googleSat = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', { maxZoom: 18, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'], transparent: true });
    var viirs = L.tileLayer('https://lostatnight.org/viirs_tiles/{z}/{x}/{y}.png', {
        maxZoom: 18, maxNativeZoom: 12, transparent: true, tms: 1, attribution: 'The Earth Observation Group (EOG)', opacity: 0.8, className: 'viirs-tiles' });
    var sdgsat = L.tileLayer('https://lostatnight.org/tileset/SDGSAT_EU_UK/{z}/{x}/{y}.png', {
        maxZoom: 18, maxNativeZoom: 13, transparent: true, tms: 1, attribution: 'SDGSAT @ LostAtNight.org', opacity: 0.8, className: 'sdgsat-tiles' });

    var esri = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/';
    var dark = L.tileLayer(esri + 'World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 18, maxNativeZoom: 16, attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors' });
    var darkRoads = L.tileLayer(esri + 'World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, maxNativeZoom: 16, pane: 'rvLabels' });

    var map = L.map('rvMap', { preferCanvas: true, worldCopyJump: true, zoomSnap: 0.5, maxZoom: 18 }).setView([40, -2], 5);
    map.createPane('rvPhoto').style.zIndex = 395;          // photo under the outlines (overlay pane is 400)
    map.createPane('rvLabels').style.zIndex = 396;         // roads and labels over the photo, under the outlines
    window.rvMap = map;                                    // handle for debugging / automated checks
    var activeBase = [dark, darkRoads];
    dark.addTo(map); darkRoads.addTo(map); viirs.addTo(map); sdgsat.addTo(map);
    map.getContainer().classList.add('rv-dark');          // dark base: VIIRS / SDGSAT only add their lights
    var outlines = L.layerGroup().addTo(map);

    var feats = [];          // {p: properties, ring: [[lat, lon], ...], poly: L.Polygon}
    var hits = [];           // attempts under the last click
    var current = null;      // selected attempt
    var photo = null;        // L.ImageOverlay of the selected attempt
    var mode = 'idle';       // 'idle' | 'list' | 'detail'
    var photoOpacity = 0.75, lightsOnly = false;
    var photoRow = null;

    // "Map adjustments": base layer buttons + one opacity row per layer. Always open, like in the work area.
    function sliderRow(label, initial, onInput) {
        var val = el('span', { class: 'mono val' }, initial.toFixed(2));
        var slider = el('input', { type: 'range', min: 0, max: 1, step: 0.05, value: initial });
        slider.addEventListener('input', function () { var v = parseFloat(this.value); val.textContent = v.toFixed(2); onInput(v); });
        ['mousedown', 'mouseup', 'dblclick'].forEach(function (ev) { slider.addEventListener(ev, function (e) { e.stopPropagation(); }); });
        return { row: el('div', { class: 'rv-row' }, [el('span', { class: 'rv-lbl' }, label), slider, val]), slider: slider, val: val };
    }
    function checkRow(label, checked, onChange) {
        var box = el('input', { type: 'checkbox' }); box.checked = checked;
        box.addEventListener('change', function () { onChange(this.checked); });
        return el('div', { class: 'rv-row' }, [el('label', {}, [box, ' ' + label])]);
    }
    L.Control.Adjust = L.Control.extend({
        onAdd: function () {
            var outer = L.DomUtil.create('div', 'leaflet-control-layers leaflet-control-layers-expanded ds-map-adjust');
            outer.style.fontSize = '12px';
            L.DomEvent.disableClickPropagation(outer); L.DomEvent.disableScrollPropagation(outer);
            outer.appendChild(el('div', { class: 'ds-map-adjust__head' }, el('span', {}, [el('i', { class: 'fa-solid fa-layer-group' }), ' ' + T.mapAdjust])));
            var body = el('div', { class: 'ds-map-adjust__body' });
            var bases = [[T.dark, [dark, darkRoads]], ['OSM', [osm]], [T.satellite, [googleSat]]];
            var btns = bases.map(function (b, i) {
                var btn = el('button', { type: 'button', class: 'ds-baselayer-btn' + (i === 0 ? ' is-active' : '') }, b[0]);
                btn.addEventListener('click', function () {
                    activeBase.forEach(function (l) { map.removeLayer(l); });
                    activeBase = b[1];
                    activeBase.forEach(function (l) { l.addTo(map); if (l.options.pane !== 'rvLabels') l.bringToBack(); });
                    map.getContainer().classList.toggle('rv-dark', b[1][0] === dark);
                    btns.forEach(function (x) { x.classList.toggle('is-active', x === btn); });
                });
                return btn;
            });
            body.appendChild(el('div', { class: 'ds-baselayer-row' }, btns));
            body.appendChild(sliderRow('VIIRS', 0.8, function (v) { viirs.setOpacity(v); }).row);
            body.appendChild(sliderRow('SDGSAT EU/UK', 0.8, function (v) { sdgsat.setOpacity(v); }).row);
            photoRow = sliderRow(T.photo, photoOpacity, function (v) { photoOpacity = v; if (photo) photo.setOpacity(v); });
            body.appendChild(photoRow.row);
            body.appendChild(checkRow(T.lightsOnly, false, function (on) { lightsOnly = on; applyBlend(); }));
            body.appendChild(checkRow(T.outlines, true, function (on) { if (on) map.addLayer(outlines); else map.removeLayer(outlines); }));
            outer.appendChild(body);
            return outer;
        }
    });
    new L.Control.Adjust({ position: 'bottomleft' }).addTo(map);

    var elCount = document.getElementById('rvCount'), elHint = document.getElementById('rvHint'), body = document.getElementById('rvBody');
    var statusText = T.loading;

    // ── Outline styles: one colour for attempts, one for the selection, grey for the rest ──
    function style(f) {
        var mine = !!f.p.mine, dash = mine ? '5 4' : null;
        if (mode === 'detail') {
            return f === current
                ? { color: C_SEL, weight: 3, opacity: 1, fillColor: C_SEL, fillOpacity: 0.06, dashArray: null, interactive: false }
                : { weight: 0, opacity: 0, fillOpacity: 0, interactive: false };
        }
        if (mode === 'list') {
            return hits.indexOf(f) >= 0
                ? { color: C_BASE, weight: 2, opacity: 1, fillColor: C_BASE, fillOpacity: 0.05, dashArray: dash, interactive: false }
                : { color: C_OFF, weight: 1, opacity: 0.22, fillColor: C_OFF, fillOpacity: 0, dashArray: null, interactive: false };
        }
        return { color: C_BASE, weight: 1, opacity: 0.5, fillColor: C_BASE, fillOpacity: 0, dashArray: dash, interactive: false };   // no fill: thousands of them would hide the map
    }
    function restyle() { feats.forEach(function (f) { f.poly.setStyle(style(f)); }); }
    function inside(lat, lon, ring) {            // ray casting; ring is [[lat, lon], ...]
        var c = false;
        for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            var yi = ring[i][0], xi = ring[i][1], yj = ring[j][0], xj = ring[j][1];
            if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) c = !c;
        }
        return c;
    }

    function applyBlend() {
        var n = photo && photo.getElement && photo.getElement();
        if (n) n.style.mixBlendMode = lightsOnly ? 'screen' : '';
    }
    function removePhoto() { if (photo) { map.removeLayer(photo); photo = null; } photoRow.row.classList.add('is-off'); }

    // ── Rail ──
    function voteLabel(v) { return v === 'ok' ? '✓ ' + T.ok : v === 'not_ok' ? '✗ ' + T.notOk : '—'; }
    function votesSummary(p) { return p.ok + ' ✓ · ' + p.not_ok + ' ✗'; }

    var expanded = {};       // image_id → true while that image is open

    function groups() {
        var by = {}, order = [];
        hits.forEach(function (f) {
            var id = f.p.image_id;
            if (!by[id]) { by[id] = { id: id, name: f.p.name, taken: f.p.taken, items: [] }; order.push(by[id]); }
            by[id].items.push(f);
        });
        order.forEach(function (g) { g.items.sort(function (a, b) { return a.p.id - b.p.id; }); });
        order.sort(function (a, b) {                                 // by date, then name
            return String(a.taken || '').localeCompare(String(b.taken || '')) || a.name.localeCompare(b.name);
        });
        return order;
    }

    function hover(node, items) {                    // highlight on the map while the pointer is over a rail row
        node.addEventListener('mouseenter', function () {
            if (mode === 'detail') return;
            items.forEach(function (f) { f.poly.bringToFront(); f.poly.setStyle({ color: C_SEL, weight: 3, opacity: 1 }); });
        });
        node.addEventListener('mouseleave', function () { items.forEach(function (f) { f.poly.setStyle(style(f)); }); });
    }

    function header() {
        elHint.innerHTML = '';
        if (mode === 'idle') {
            elCount.textContent = statusText;
            elHint.textContent = feats.length ? T.hint : '';
        } else {
            var imgs = {}; hits.forEach(function (f) { imgs[f.p.image_id] = true; });
            elCount.textContent = hits.length + ' ' + T.here + ' · ' + Object.keys(imgs).length + ' ' + T.images;
            elHint.appendChild(el('button', { type: 'button', class: 'rv-link', onclick: goIdle }, T.clear));
            elHint.appendChild(document.createTextNode('  ·  ' + T.keys));
        }
    }

    function render() {
        var top = body.scrollTop;
        header();
        body.innerHTML = '';
        if (mode === 'idle') {
            if (!feats.length && statusText === T.none) body.appendChild(el('div', { class: 'rv-empty' }, T.none));
        } else {
            body.appendChild(treeView());
        }
        body.scrollTop = top;
    }

    function treeView() {
        var tree = el('div', {});
        groups().forEach(function (g) {
            var open = !!expanded[g.id];
            var head = el('button', { type: 'button', class: 'rv-img', onclick: function () { expanded[g.id] = !expanded[g.id]; render(); } }, [
                el('span', { class: 'rv-caret' }, open ? '▾' : '▸'),
                el('span', { class: 'rv-name' }, g.name),
                el('span', { class: 'rv-meta' }, (g.taken || T.unknown) + ' · ' + g.items.length)
            ]);
            hover(head, g.items);
            tree.appendChild(head);
            if (!open) return;
            var kids = el('div', { class: 'rv-kids' });
            g.items.forEach(function (f) {
                var sel = f === current;
                var badge = el('span', { class: 'rv-vb' + (f.p.mine ? ' is-voted' : ''), title: T.yourVote + ': ' + (f.p.mine ? voteLabel(f.p.mine) : T.notVoted) },
                    f.p.mine === 'ok' ? '✓' : f.p.mine === 'not_ok' ? '✗' : '–');
                var row = el('button', { type: 'button', class: 'rv-att' + (sel ? ' is-sel' : ''), onclick: function () { if (sel) goList(); else select(f); } }, [
                    el('span', { class: 'rv-id' }, '#' + f.p.id + (f.p.own ? ' · ' + T.own : '')),
                    el('span', { class: 'rv-sub' }, f.p.points + ' ' + T.points + ' · ' + Math.round(f.p.area_km2).toLocaleString() + ' km²'),
                    badge
                ]);
                hover(row, [f]);
                kids.appendChild(row);
                if (sel) kids.appendChild(detailBlock(f));
            });
            tree.appendChild(kids);
        });
        return tree;
    }

    function detailBlock(f) {
        var p = f.p, msg = el('div', { class: 'rv-msg' });
        function btn(verdict, label) {
            var b = el('button', { type: 'button', class: 'ds-btn ds-btn--md ' + (p.mine === verdict ? 'ds-btn--primary' : 'ds-btn--secondary'),
                onclick: function () { vote(f, verdict, msg); } }, label);
            if (p.own) b.disabled = true;
            return b;
        }
        return el('div', { class: 'rv-open' }, [
            el('dl', { class: 'rv-info' }, [
                el('dt', {}, T.taken), el('dd', {}, p.taken || T.unknown),
                el('dt', {}, T.by), el('dd', {}, p.user_id == null ? '—' : String(p.user_id)),
                el('dt', {}, T.votes), el('dd', {}, votesSummary(p))
            ]),
            p.own ? el('div', { class: 'rv-note' }, T.own_note) : el('div', { class: 'rv-yours' }, [T.yourVote + ': ', el('b', {}, p.mine ? voteLabel(p.mine) : T.notVoted)]),
            el('div', { class: 'rv-vote' }, [btn('ok', '✓ ' + T.ok), btn('not_ok', '✗ ' + T.notOk)]),
            msg
        ]);
    }

    function goIdle() { mode = 'idle'; hits = []; current = null; removePhoto(); restyle(); render(); }
    function goList() { mode = 'list'; current = null; removePhoto(); restyle(); render(); }
    function select(f) {
        mode = 'detail'; current = f;
        expanded[f.p.image_id] = true;
        removePhoto();
        photo = L.imageOverlay(f.p.overlay, f.p.bounds, { opacity: photoOpacity, interactive: false, pane: 'rvPhoto' });
        photo.on('load', applyBlend);
        photo.on('error', function () { var m = body.querySelector('.rv-msg'); if (m) m.textContent = T.imgError; });
        photo.addTo(map);
        photoRow.row.classList.remove('is-off');
        restyle();
        f.poly.bringToFront();                      // the chosen outline goes on top
        var lb = L.latLngBounds(f.p.bounds);          // frame the photo if it is off-screen or tiny at the current zoom
        if (!map.getBounds().intersects(lb) || map.getBoundsZoom(lb) - map.getZoom() >= 2) map.fitBounds(lb, { padding: [40, 40], maxZoom: 12 });
        render();
        var sel = body.querySelector('.rv-att.is-sel');
        if (sel && sel.scrollIntoView) sel.scrollIntoView({ block: 'nearest' });
    }

    function vote(f, verdict, msg) {
        msg.textContent = '…';
        fetch(R.voteUrl, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
            body: JSON.stringify({ geoattempt: f.p.id, verdict: verdict })
        }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (res) {
              if (!res.ok) { msg.textContent = (res.d && res.d.error) || T.error; return; }
              f.p.ok = res.d.ok; f.p.not_ok = res.d.not_ok; f.p.mine = res.d.mine;
              restyle(); f.poly.bringToFront();
              render();
              var m = body.querySelector('.rv-msg'); if (m) m.textContent = T.saved;
          }).catch(function () { msg.textContent = T.error; });
    }

    map.on('click', function (e) {
        hits = feats.filter(function (f) { return inside(e.latlng.lat, e.latlng.lng, f.ring); });
        if (!hits.length) { goIdle(); elHint.textContent = T.nothingHere; return; }
        expanded = {};
        var imgs = {}; hits.forEach(function (f) { imgs[f.p.image_id] = true; });
        if (Object.keys(imgs).length === 1) expanded[hits[0].p.image_id] = true;   // single image: show its attempts
        if (hits.length === 1) { select(hits[0]); } else { goList(); }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        if (mode === 'detail') goList(); else goIdle();
    });

    removePhoto();
    render();
    fetch(R.footprintsUrl, { credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (gj) {
            gj.features.forEach(function (feature) {
                var ring = feature.geometry.coordinates[0].map(function (c) { return [c[1], c[0]]; });
                var f = { p: feature.properties, ring: ring };
                f.poly = L.polygon(ring, style(f)).addTo(outlines);
                feats.push(f);
            });
            statusText = feats.length ? feats.length + ' ' + T.total : T.none;
            if (mode === 'idle') render();
            if (feats.length) {
                var b = L.latLngBounds(feats.reduce(function (acc, f) { return acc.concat(f.ring); }, []));
                map.fitBounds(b, { padding: [30, 30], maxZoom: 7 });
            }
        })
        .catch(function () { statusText = T.loadError; if (mode === 'idle') render(); });
})();
