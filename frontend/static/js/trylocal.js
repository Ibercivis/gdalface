(function () {
    'use strict';

    var tryLocalLayer = null;

    // ═══════════════════════════════════════════════════════════════════════
    // TPS — Thin Plate Spline
    // Kernel: U(r²) = r² · ln(r²),  U(0) = 0
    // System: [K P; Pᵀ 0] · [w; a] = [v; 0]   (size n+3 × n+3)
    // ═══════════════════════════════════════════════════════════════════════

    function tpsKernel(r2) {
        return r2 < 1e-20 ? 0 : r2 * Math.log(r2);
    }

    function distSq(ax, ay, bx, by) {
        var dx = ax - bx, dy = ay - by;
        return dx * dx + dy * dy;
    }

    // Gaussian elimination with partial pivoting.
    // Solves A·x = b (A is modified in place). Returns solution vector x.
    function gaussSolve(A, b) {
        var n = A.length;
        // Build augmented matrix
        var M = A.map(function (row, i) { return row.slice().concat(b[i]); });

        for (var col = 0; col < n; col++) {
            // Partial pivot
            var best = col;
            for (var row = col + 1; row < n; row++) {
                if (Math.abs(M[row][col]) > Math.abs(M[best][col])) best = row;
            }
            var tmp = M[col]; M[col] = M[best]; M[best] = tmp;

            var pivot = M[col][col];
            if (Math.abs(pivot) < 1e-12) continue;

            for (var row = col + 1; row < n; row++) {
                var f = M[row][col] / pivot;
                for (var k = col; k <= n; k++) M[row][k] -= f * M[col][k];
            }
        }

        // Back-substitution
        var x = new Array(n).fill(0);
        for (var i = n - 1; i >= 0; i--) {
            x[i] = M[i][n];
            for (var j = i + 1; j < n; j++) x[i] -= M[i][j] * x[j];
            x[i] /= M[i][i];
        }
        return x;
    }

    function buildMatrix(gcps, lambda) {
        var n = gcps.length;
        var N = n + 3;
        var A = [];
        for (var i = 0; i < N; i++) A.push(new Array(N).fill(0));

        // K block (n×n) with Tikhonov regularisation λ on diagonal
        for (var i = 0; i < n; i++) {
            for (var j = 0; j < n; j++) {
                var r2 = distSq(gcps[i].actualPx, gcps[i].actualPy,
                                gcps[j].actualPx, gcps[j].actualPy);
                A[i][j] = tpsKernel(r2) + (i === j ? lambda : 0);
            }
        }
        // P block (n×3) and Pᵀ (3×n)
        for (var i = 0; i < n; i++) {
            A[i][n] = 1;  A[i][n+1] = gcps[i].actualPx;  A[i][n+2] = gcps[i].actualPy;
            A[n][i] = 1;  A[n+1][i] = gcps[i].actualPx;  A[n+2][i] = gcps[i].actualPy;
        }
        // Bottom-right 3×3 stays 0
        return A;
    }

    // Solve TPS for all GCPs → returns object with weights for lat and lon
    function solveTPS(gcps) {
        var n = gcps.length;
        var N = n + 3;
        var LAMBDA = 1e-6;  // regularisation

        var bLat = new Array(N).fill(0);
        var bLon = new Array(N).fill(0);
        for (var i = 0; i < n; i++) { bLat[i] = gcps[i].lat; bLon[i] = gcps[i].lon; }

        var wLat = gaussSolve(buildMatrix(gcps, LAMBDA), bLat);
        var wLon = gaussSolve(buildMatrix(gcps, LAMBDA), bLon);

        return { gcps: gcps, wLat: wLat, wLon: wLon };
    }

    // Evaluate TPS: pixel (px, py) → [lat, lon]
    function tpsEval(tps, px, py) {
        var gcps = tps.gcps, n = gcps.length;
        // Affine part stored at indices n, n+1, n+2
        var lat = tps.wLat[n] + tps.wLat[n+1]*px + tps.wLat[n+2]*py;
        var lon = tps.wLon[n] + tps.wLon[n+1]*px + tps.wLon[n+2]*py;
        for (var i = 0; i < n; i++) {
            var u = tpsKernel(distSq(px, py, gcps[i].actualPx, gcps[i].actualPy));
            lat += tps.wLat[i] * u;
            lon += tps.wLon[i] * u;
        }
        return [lat, lon];
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Canvas triangle texture mapping
    // Maps source triangle (sx0,sy0)-(sx1,sy1)-(sx2,sy2) from img
    // onto destination triangle (dx0,dy0)-(dx1,dy1)-(dx2,dy2) in ctx.
    // Uses affine transform per triangle (exact for small cells).
    // ═══════════════════════════════════════════════════════════════════════

    function drawTriangle(ctx, img,
        sx0, sy0, sx1, sy1, sx2, sy2,
        dx0, dy0, dx1, dy1, dx2, dy2) {

        // Compute T = D · S⁻¹  (maps image coords → canvas coords)
        // S = [[sx0,sx1,sx2],[sy0,sy1,sy2],[1,1,1]]
        var det = sx0*(sy1 - sy2) + sx1*(sy2 - sy0) + sx2*(sy0 - sy1);
        if (Math.abs(det) < 0.5) return;
        var id = 1 / det;

        // S⁻¹ rows:
        var i00 = (sy1-sy2)*id,  i01 = (sy2-sy0)*id,  i02 = (sy0-sy1)*id;
        var i10 = (sx2-sx1)*id,  i11 = (sx0-sx2)*id,  i12 = (sx1-sx0)*id;
        var i20 = (sx1*sy2-sx2*sy1)*id, i21 = (sx2*sy0-sx0*sy2)*id, i22 = (sx0*sy1-sx1*sy0)*id;

        // T = D(2×3) · S⁻¹(3×3)   →   2×3 result
        var a = dx0*i00 + dx1*i01 + dx2*i02;   // T[0][0]
        var c = dx0*i10 + dx1*i11 + dx2*i12;   // T[0][1]
        var e = dx0*i20 + dx1*i21 + dx2*i22;   // T[0][2]
        var b = dy0*i00 + dy1*i01 + dy2*i02;   // T[1][0]
        var d = dy0*i10 + dy1*i11 + dy2*i12;   // T[1][1]
        var f = dy0*i20 + dy1*i21 + dy2*i22;   // T[1][2]

        // ctx.transform convention: [a c e; b d f; 0 0 1]
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(dx0, dy0); ctx.lineTo(dx1, dy1); ctx.lineTo(dx2, dy2);
        ctx.closePath();
        ctx.clip();
        ctx.setTransform(a, b, c, d, e, f);
        ctx.drawImage(img, 0, 0);
        ctx.restore();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Modal helpers
    // ═══════════════════════════════════════════════════════════════════════

    function getGeoModal() {
        return bootstrap.Modal.getOrCreateInstance(document.getElementById('georeferencingModal'));
    }

    function showLoading() {
        document.querySelector('#georeferencingModal .modal-title').textContent = 'Local georeferencing…';
        document.querySelector('#georeferencingModal .modal-body').innerHTML =
            'Computing TPS warp in browser. Please wait.<br><br>' +
            '<div class="d-flex justify-content-center">' +
            '<img width="40px" src="/static/img/doing.gif"/></div>';
        getGeoModal().show();
    }

    function hideLoading() {
        try { getGeoModal().hide(); } catch (e) {}
        // Force-close via DOM in case Bootstrap ignores the hide() call
        setTimeout(function () {
            var el = document.getElementById('georeferencingModal');
            el.classList.remove('show');
            el.style.display = 'none';
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('padding-right');
            var bd = document.querySelector('.modal-backdrop');
            if (bd) bd.parentNode.removeChild(bd);
        }, 300);
    }

    function showError(title, body) {
        document.querySelector('#taskInfoModal .modal-title').textContent = title;
        document.querySelector('#taskInfoModal .modal-body').innerHTML = body;
        window.LAN.infoModal.show();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Main handler
    // ═══════════════════════════════════════════════════════════════════════

    function handleTryLocal() {
        var LAN = window.LAN;
        if (!LAN || !LAN.map) { alert('Map not ready yet.'); return; }

        var complete = LAN.iconList.filter(function (i) { return i.complete; });
        if (complete.length < 3) {
            showError('Few control points!', 'Please add at least three control points.');
            return;
        }

        showLoading();

        // Defer heavy work so the modal renders first
        setTimeout(function () {
            try {
                var tps = solveTPS(complete);
            } catch (e) {
                hideLoading();
                showError('TPS error', e.message);
                return;
            }

            var img = new Image();
            img.crossOrigin = 'anonymous';

            img.onerror = function () {
                hideLoading();
                showError('Image error', 'Could not load the original image.');
            };

            img.onload = function () {
                try {
                    var imgW = img.naturalWidth;
                    var imgH = img.naturalHeight;

                    // ── Sample grid: image pixels → geo coordinates ──────────
                    var GRID = 15;
                    var minLat =  Infinity, maxLat = -Infinity;
                    var minLon =  Infinity, maxLon = -Infinity;

                    // gridGeo[row][col] = [lat, lon]
                    var gridGeo = [];
                    for (var row = 0; row <= GRID; row++) {
                        var gRow = [];
                        for (var col = 0; col <= GRID; col++) {
                            var g = tpsEval(tps, (col/GRID)*imgW, (row/GRID)*imgH);
                            gRow.push(g);
                            if (g[0] < minLat) minLat = g[0];
                            if (g[0] > maxLat) maxLat = g[0];
                            if (g[1] < minLon) minLon = g[1];
                            if (g[1] > maxLon) maxLon = g[1];
                        }
                        gridGeo.push(gRow);
                    }

                    // ── Output canvas size (Mercator aspect ratio) ──────────
                    function latToMerc(lat) {
                        return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
                    }

                    var OUT_W = 2500;
                    var lonSpan = maxLon - minLon;
                    var mercMin = latToMerc(minLat);
                    var mercMax = latToMerc(maxLat);
                    var mercSpan = mercMax - mercMin;
                    var OUT_H   = Math.round(OUT_W * mercSpan / (lonSpan * Math.PI / 180));
                    if (!isFinite(OUT_H) || OUT_H < 50 || OUT_H > 3500) OUT_H = 1800;

                    var canvas = document.createElement('canvas');
                    canvas.width  = OUT_W;
                    canvas.height = OUT_H;
                    var ctx = canvas.getContext('2d');

                    function geoToCanvas(lat, lon) {
                        return [
                            (lon - minLon) / lonSpan * OUT_W,
                            (1 - (latToMerc(lat) - mercMin) / mercSpan) * OUT_H
                        ];
                    }

                    // ── Draw each grid cell as 2 textured triangles ──────────
                    var cellW = imgW / GRID;
                    var cellH = imgH / GRID;

                    for (var row = 0; row < GRID; row++) {
                        for (var col = 0; col < GRID; col++) {
                            var sx0 = col * cellW,       sy0 = row * cellH;
                            var sx1 = (col+1) * cellW,   sy1 = row * cellH;
                            var sx2 = (col+1) * cellW,   sy2 = (row+1) * cellH;
                            var sx3 = col * cellW,       sy3 = (row+1) * cellH;

                            var c0 = geoToCanvas(gridGeo[row][col][0],     gridGeo[row][col][1]);
                            var c1 = geoToCanvas(gridGeo[row][col+1][0],   gridGeo[row][col+1][1]);
                            var c2 = geoToCanvas(gridGeo[row+1][col+1][0], gridGeo[row+1][col+1][1]);
                            var c3 = geoToCanvas(gridGeo[row+1][col][0],   gridGeo[row+1][col][1]);

                            // Triangle: top-left, top-right, bottom-right
                            drawTriangle(ctx, img,
                                sx0, sy0, sx1, sy1, sx2, sy2,
                                c0[0], c0[1], c1[0], c1[1], c2[0], c2[1]);

                            // Triangle: top-left, bottom-right, bottom-left
                            drawTriangle(ctx, img,
                                sx0, sy0, sx2, sy2, sx3, sy3,
                                c0[0], c0[1], c2[0], c2[1], c3[0], c3[1]);
                        }
                    }

                    // ── Display as imageOverlay on the Leaflet map ───────────
                    var dataUrl = canvas.toDataURL('image/png');
                    var bounds  = [[minLat, minLon], [maxLat, maxLon]];

                    if (tryLocalLayer) LAN.map.removeLayer(tryLocalLayer);
                    tryLocalLayer = L.imageOverlay(dataUrl, bounds, { opacity: 0.8 });
                    tryLocalLayer.addTo(LAN.map);
                    LAN.map.fitBounds(bounds);
                    window.LAN.tryLocalLayer = tryLocalLayer;
                    window.LAN.applyMapFilters();

                    // Opacity slider in the map control panel
                    if (LAN.opacitySlidersDiv && LAN.makeSliderRow) {
                        var ex = document.getElementById('trylocal-slider-row');
                        if (ex) ex.remove();
                        LAN.opacitySlidersDiv.appendChild(
                            LAN.makeSliderRow('Georeferenced', tryLocalLayer, 0.8, 'trylocal-slider-row')
                        );
                    }

                    hideLoading();
                    document.getElementById('Submit').classList.remove('disabled');

                } catch (e) {
                    hideLoading();
                    console.error('TryLocal error:', e);
                    showError('Local warp failed', e.message);
                }
            };

            img.src = LAN.imageUrl;
        }, 50);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Insert "Try local" button next to "Try"
    // ═══════════════════════════════════════════════════════════════════════

    document.addEventListener('DOMContentLoaded', function () {
        var tryBtn = document.getElementById('Try');
        if (!tryBtn) return;

        var btn = document.createElement('button');
        btn.id          = 'TryLocal';
        btn.className   = tryBtn.className.replace('d-none', '').trim();
        btn.textContent = 'Try';
        tryBtn.insertAdjacentElement('afterend', btn);
        btn.addEventListener('click', handleTryLocal);
    });

}());
