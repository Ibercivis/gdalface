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

    function init() {
        document.querySelectorAll('.triple-bar').forEach(renderBar);

        document.querySelectorAll('[data-challenge-join]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.dataset.challengeJoin;
                btn.disabled = true;
                postChallenge('join', id).then(function (r) {
                    if (r.ok) window.location.reload();
                    else { alert('Could not join challenge.'); btn.disabled = false; }
                }).catch(function () {
                    alert('Network error.'); btn.disabled = false;
                });
            });
        });

        document.querySelectorAll('[data-challenge-leave]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.dataset.challengeLeave;
                if (!confirm('Leave this challenge? Your contributions are preserved.')) return;
                btn.disabled = true;
                postChallenge('leave', id).then(function (r) {
                    if (r.ok) window.location.reload();
                    else { alert('Could not leave.'); btn.disabled = false; }
                }).catch(function () {
                    alert('Network error.'); btn.disabled = false;
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
