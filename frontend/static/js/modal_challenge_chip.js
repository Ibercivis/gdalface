/* Lost At Night — inject "Counts towards challenge" chip into the briefing
   modal when the user is enrolled in an applicable challenge.
   JS-only, no backend changes. */
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

    function fetchEnrollment(batchId) {
        var url = '/api/v1/challenges/mine/' + (batchId ? '?batch_id=' + encodeURIComponent(batchId) : '');
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCookie('csrftoken') || '' },
        }).then(function (r) { return r.ok ? r.json() : null; });
    }

    function renderChip(enrollment) {
        var chip = document.getElementById('ti-challenge-chip');
        if (!chip) return;
        if (!enrollment || !enrollment.enrolled) {
            chip.hidden = true;
            return;
        }
        var ch = enrollment.challenge;
        var rank = enrollment.my_rank;
        var trophySvg = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
            + 'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
            + 'stroke-linejoin="round" style="color:var(--accent);vertical-align:-2px;margin-right:5px;">'
            + '<path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4z"/>'
            + '<path d="M17 4h3v2a3 3 0 0 1-3 3M7 4H4v2a3 3 0 0 0 3 3"/></svg>';
        var html = trophySvg + '<a href="/challenges/' + ch.id + '/">' + escapeHtml(ch.name) + '</a>';
        if (rank) html += ' · #' + rank;
        chip.innerHTML = html;
        chip.hidden = false;
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
        });
    }

    function init() {
        var banner = document.getElementById('challenge-banner');
        if (!banner || banner.dataset.authenticated !== '1') return;
        var batchId = banner.dataset.batchId || '';
        // Defer until the modal is opening so the request lands at the right time.
        var modalEl = document.getElementById('taskInfoModal');
        if (!modalEl) return;
        var fired = false;
        modalEl.addEventListener('show.bs.modal', function () {
            if (fired) return;
            fired = true;
            fetchEnrollment(batchId).then(renderChip).catch(function () { /* best-effort */ });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
