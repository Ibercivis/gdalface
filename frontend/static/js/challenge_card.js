/* Lost At Night — shared behavior for Challenge cards.
   Renders the triple-target progress bar and wires up join/leave buttons. */
(function () {
    'use strict';

    function getCookie(name) {
        var v = null;
        if (document.cookie) {
            var parts = document.cookie.split(';');
            for (var i = 0; i < parts.length; i++) {
                var c = parts[i].trim();
                if (c.substring(0, name.length + 1) === name + '=') {
                    v = decodeURIComponent(c.substring(name.length + 1));
                    break;
                }
            }
        }
        return v;
    }

    function renderBar(bar) {
        var bronze = +bar.dataset.bronze;
        var silver = +bar.dataset.silver;
        var gold   = +bar.dataset.gold;
        var total  = +bar.dataset.total;
        if (!gold) return;
        var fill = bar.querySelector('.fill');
        if (fill) fill.style.width = Math.min(100, (total / gold) * 100) + '%';
        bar.querySelectorAll('.marker').forEach(function (m) {
            var pos = m.dataset.pos;
            var v = pos === 'bronze' ? bronze : pos === 'silver' ? silver : gold;
            m.style.left = ((v / gold) * 100) + '%';
        });
    }

    function postChallenge(action, id) {
        return fetch('/api/v1/challenges/' + id + '/' + action + '/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || '',
            },
        });
    }

    function L(key, fallback) { var T = window.LAN_I18N || {}; return T[key] || fallback; }

    function fmtDuration(ms, mode) {
        if (ms <= 0) return mode === 'starts' ? L('pill_soon', 'Soon') : L('pill_ended', 'Ended');
        var totalMin = Math.round(ms / 60000);
        var d = Math.floor(totalMin / (60 * 24));
        var h = Math.floor((totalMin / 60) % 24);
        var m = totalMin % 60;
        var unit;
        if (d >= 1) unit = d + 'd';
        else if (h >= 1) unit = h + 'h';
        else unit = m + 'm';
        return mode === 'starts' ? L('pill_starts_in', 'Starts in {t}').replace('{t}', unit)
                                 : L('pill_left', '{t} left').replace('{t}', unit);
    }

    function renderTimePills() {
        var now = Date.now();
        document.querySelectorAll('[data-time-pill]').forEach(function (el) {
            var row = el.closest('[data-end-at]');
            if (!row) return;
            var mode = el.dataset.mode || 'left';
            var iso = mode === 'starts' ? row.dataset.startAt : row.dataset.endAt;
            if (!iso) return;
            var t = new Date(iso).getTime();
            el.textContent = fmtDuration(t - now, mode);
        });
    }

    function renderProgress() {
        document.querySelectorAll('.ds-progress__fill[data-value]').forEach(function (el) {
            var v = +el.dataset.value, m = +el.dataset.max;
            if (!m) return;
            var pct = Math.min(100, Math.max(0, (v / m) * 100));
            requestAnimationFrame(function () {
                el.style.right = (100 - pct) + '%';
            });
        });
    }

    function init() {
        document.querySelectorAll('.triple-bar').forEach(renderBar);
        renderTimePills();
        renderProgress();

        function readJson(r) {
            return r.json().then(function (b) { return { ok: r.ok, body: b }; })
                .catch(function () { return { ok: r.ok, body: null }; });
        }
        // The page marks the viewer's current enrollment (card row or detail
        // page root) with .is-enrolled + data-challenge-name. Joining another
        // challenge leaves it, so ask first instead of telling afterwards.
        function currentEnrollmentName(excludeId) {
            var el = document.querySelector('.is-enrolled[data-challenge-name]');
            if (!el || String(el.dataset.challengeId) === String(excludeId)) return null;
            return el.dataset.challengeName;
        }
        document.querySelectorAll('[data-challenge-join]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.dataset.challengeJoin;
                var current = currentEnrollmentName(id);
                if (current) {
                    var q = L('confirm_switch', 'You are enrolled in “{current}”. Joining “{name}” leaves it (your points are kept). Continue?')
                        .replace('{current}', current).replace('{name}', btn.dataset.challengeName || '');
                    if (!confirm(q)) return;
                }
                btn.disabled = true;
                postChallenge('join', id).then(readJson).then(function (res) {
                    if (res.ok && typeof window.LAN_showJoinedModal === 'function') {
                        window.LAN_showJoinedModal(res.body || {});
                    } else if (res.ok) { window.location.reload(); }
                    else { alert((res.body && res.body.error) || L('join_error', 'Could not join the challenge.')); btn.disabled = false; }
                }).catch(function () {
                    alert(L('network_error', 'Network error.')); btn.disabled = false;
                });
            });
        });

        document.querySelectorAll('[data-challenge-leave]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.dataset.challengeLeave;
                if (!confirm(L('confirm_leave', 'Leave this challenge? Your contributions are preserved.'))) return;
                btn.disabled = true;
                postChallenge('leave', id).then(readJson).then(function (res) {
                    if (res.ok && typeof window.LAN_showLeftModal === 'function') {
                        window.LAN_showLeftModal(res.body || {});
                    } else if (res.ok) { window.location.reload(); }
                    else { alert(L('leave_error', 'Could not leave the challenge.')); btn.disabled = false; }
                }).catch(function () {
                    alert(L('network_error', 'Network error.')); btn.disabled = false;
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
