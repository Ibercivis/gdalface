/* Lost at Night — reusable map of located photos.
   Usage: LAN.locatedMap('#el', { url: '/map/data.geojson', fit: true, bbox: [[s,w],[n,e]],
                                   interactive: true, cluster: true, i18n: {...} })
   Requires Leaflet 1.9 and (optionally) Leaflet.markercluster loaded first. */
(function () {
    'use strict';
    window.LAN = window.LAN || {};

    var DEFAULT_T = {
        contributions: 'contributions', contribution: 'contribution', points: 'control points',
        taken: 'Taken', nasa: 'Original at NASA', pending: 'Still needs more eyes', mine: 'You located this one',
        lights: 'Night lights (VIIRS)', black_marble: 'NASA Black Marble', photos: 'Located photos', mine_photos: 'My photos',
        empty: 'Nothing located here yet.'
    };

    function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

    function icon(mine, n) {
        var size = n >= 4 ? 14 : n >= 2 ? 12 : 10;
        var color = mine ? '#ffffff' : '#e9f990';
        return L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
            html: '<div style="width:' + size + 'px;height:' + size + 'px;border-radius:50%;background:' + color +
                  ';border:2px solid ' + (mine ? '#e9f990' : 'rgba(10,6,18,.9)') + ';box-shadow:0 0 6px ' + color + '"></div>' });
    }

    function popup(p, T) {
        var n = p.contributions;
        return '<div class="lan-map-pop">'
            + (p.thumb ? '<a href="' + esc(p.nasa || p.thumb) + '" target="_blank" rel="noopener"><img src="' + esc(p.thumb) + '" alt="" loading="lazy"></a>' : '')
            + '<div class="lan-map-pop__name">' + esc(p.name) + (p.mine ? ' <span class="lan-map-pop__mine">★ ' + T.mine + '</span>' : '') + '</div>'
            + '<div class="lan-map-pop__meta">'
            +   (p.taken ? T.taken + ' ' + esc(p.taken) + ' · ' : '')
            +   n + ' ' + (n === 1 ? T.contribution : T.contributions) + ' · ' + p.points + ' ' + T.points
            + '</div>'
            + (p.pending ? '<div class="lan-map-pop__pending">' + T.pending + '</div>' : '')
            + (p.nasa ? '<a class="lan-map-pop__link" href="' + esc(p.nasa) + '" target="_blank" rel="noopener">' + T.nasa + ' ↗</a>' : '')
            + '</div>';
    }

    LAN.locatedMap = function (selector, opts) {
        opts = opts || {};
        var T = Object.assign({}, DEFAULT_T, opts.i18n || {});
        var el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el || typeof L === 'undefined') return null;
        var interactive = opts.interactive !== false;
        var map = L.map(el, {
            zoomControl: interactive, scrollWheelZoom: interactive, dragging: interactive, touchZoom: interactive,
            doubleClickZoom: interactive, boxZoom: interactive, keyboard: interactive, attributionControl: true,
            worldCopyJump: true,
        }).setView(opts.center || [25, 10], opts.zoom || 2);
        // Basemap: Esri World Dark Gray (no API key, attribution required). CARTO's
        // free tiles answer "API key required" to browsers from unregistered domains.
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors', maxZoom: 16 }).addTo(map);
        var labels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 16, pane: 'shadowPane' });
        // Night-light tiles are opaque black where there is no light; blended with
        // "screen" the black disappears and only the lights are added on top.
        var lights = L.tileLayer('https://lostatnight.org/viirs_tiles/{z}/{x}/{y}.png', {
            maxZoom: 8, maxNativeZoom: 8, attribution: 'VIIRS', className: 'lan-lights' });
        var blackMarble = L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png', {
            maxZoom: 8, maxNativeZoom: 8, attribution: 'NASA GIBS Black Marble', className: 'lan-lights' });
        if (opts.lights !== false) lights.addTo(map);
        labels.addTo(map);

        function makeGroup() {
            return (opts.cluster !== false && L.markerClusterGroup)
                ? L.markerClusterGroup({ maxClusterRadius: 40, disableClusteringAtZoom: 7, showCoverageOnHover: false, spiderfyOnMaxZoom: true,
                    iconCreateFunction: function (c) { var n = c.getChildCount();
                        return L.divIcon({ className: '', iconSize: [34, 34], html: '<div class="lan-map-cluster">' + n + '</div>' }); } })
                : L.layerGroup();
        }
        // onlyMine: show just the viewer's photos (the public map has everyone's).
        var group = makeGroup(); group.addTo(map);
        if (interactive) L.control.layers(null, (function () {
            var o = {}; o[T.lights] = lights; o[T.black_marble] = blackMarble;
            o[opts.onlyMine ? T.mine_photos : T.photos] = group;
            return o; })(), { collapsed: true }).addTo(map);

        if (opts.bbox) {
            L.rectangle(opts.bbox, { color: '#e9f990', weight: 1.5, dashArray: '6 4', fill: true, fillOpacity: 0.04 }).addTo(map);
            map.fitBounds(opts.bbox, { padding: [20, 20] });
        }

        var api = { map: map, group: group, features: [] };
        fetch(opts.url || '/map/data.geojson', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (gj) {
                api.features = gj.features || [];
                var bounds = [];
                api.features.forEach(function (f) {
                    var c = f.geometry.coordinates, p = f.properties;
                    var m = L.marker([c[1], c[0]], { icon: icon(p.mine, p.contributions), title: p.name });
                    if (interactive) m.bindPopup(popup(p, T), { maxWidth: 260, className: 'lan-map-popup' });
                    if (opts.onlyMine && !p.mine) return;
                    group.addLayer(m);
                    if (!opts.bbox) bounds.push([c[1], c[0]]);
                });
                if (opts.fit && bounds.length && !opts.bbox) map.fitBounds(bounds, { padding: [30, 30], maxZoom: opts.maxZoom || 6 });
                if (!api.features.length) {
                    var note = L.control({ position: 'topright' });
                    note.onAdd = function () { var d = L.DomUtil.create('div', 'lan-map-empty'); d.textContent = T.empty; return d; };
                    note.addTo(map);
                }
                if (typeof opts.onLoad === 'function') opts.onLoad(gj, api);
            })
            .catch(function (e) { console.error('located map', e); });
        return api;
    };
})();
