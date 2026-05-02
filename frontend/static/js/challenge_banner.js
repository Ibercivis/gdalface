/* Lost At Night — challenge banner for the gettask page.
   Polls /api/v1/challenges/mine/ and renders a fixed top banner with the
   user's rank and a triple-target progress bar. */
(function () {
    'use strict';

    var POLL_MS = 60000;
    var pollTimer = null;

    function injectStyles() {
        if (document.getElementById('challenge-banner-styles')) return;
        var s = document.createElement('style');
        s.id = 'challenge-banner-styles';
        s.textContent = [
            '#challenge-banner.cb-active{',
            '  position:fixed;top:0;left:0;right:0;z-index:1050;',
            '  background:linear-gradient(90deg,#2c1158,#7639ba);',
            '  color:#fff;padding:22px 16px 8px;font-family:Inter,system-ui,sans-serif;',
            '  box-shadow:0 2px 8px rgba(0,0,0,0.3);',
            '  border-bottom:1px solid rgba(233,249,144,0.2);',
            '  display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:13px;',
            '}',
            '#challenge-banner .cb-name{',
            '  font-weight:700;font-size:14px;display:inline-flex;align-items:center;gap:6px;',
            '}',
            '#challenge-banner .cb-name .cb-trophy{color:#e9f990;}',
            '#challenge-banner .cb-status{',
            '  font-size:10px;text-transform:uppercase;padding:2px 9px;letter-spacing:.5px;',
            '  border-radius:999px;background:rgba(255,255,255,0.18);font-weight:600;',
            '}',
            '#challenge-banner .cb-status.paused{background:#fd7e14;}',
            '#challenge-banner .cb-rank{',
            '  display:inline-flex;align-items:center;gap:4px;',
            '  background:rgba(255,255,255,0.12);padding:3px 10px;border-radius:6px;',
            '}',
            '#challenge-banner .cb-rank b{color:#e9f990;}',
            '#challenge-banner .cb-leader{',
            '  display:inline-flex;align-items:center;gap:4px;',
            '  background:rgba(233,249,144,0.18);color:#e9f990;',
            '  padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600;',
            '}',
            '#challenge-banner .cb-leader-you{background:#e9f990;color:#2c1158;}',
            '#challenge-banner .cb-link{',
            '  color:#e9f990;text-decoration:none;font-size:12px;font-weight:500;',
            '  border:1px solid rgba(233,249,144,0.4);padding:3px 10px;border-radius:6px;',
            '  transition:background .15s ease;white-space:nowrap;',
            '}',
            '#challenge-banner .cb-link:hover{background:rgba(233,249,144,0.15);}',

            /* Bar inline in the same row, taking the remaining space */
            '#challenge-banner .cb-bar-wrap{flex:1;min-width:200px;}',
            '#challenge-banner .cb-bar{',
            '  position:relative;height:22px;',
            '  background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.15);',
            '  border-radius:11px;overflow:hidden;',
            '}',
            '#challenge-banner .cb-fill{',
            '  height:100%;',
            '  background:linear-gradient(90deg,#cd7f32 0%,#c0c0c0 50%,#ffd700 100%);',
            '  box-shadow:0 0 12px rgba(255,215,0,0.4);',
            '  transition:width .5s ease;',
            '}',
            '#challenge-banner.cb-paused .cb-fill{filter:grayscale(0.6) opacity(0.6);box-shadow:none;}',
            '#challenge-banner .cb-marker{',
            '  position:absolute;top:0;bottom:0;width:2px;background:rgba(255,255,255,0.7);',
            '}',
            '#challenge-banner .cb-marker::after{',
            '  content:attr(data-label);position:absolute;top:-18px;left:50%;',
            '  transform:translateX(-50%);font-size:11px;color:#e9f990;',
            '  white-space:nowrap;font-weight:600;',
            '}',
            '#challenge-banner .cb-progress-text{',
            '  position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);',
            '  font-size:11px;font-weight:700;color:#fff;letter-spacing:0.3px;',
            '  text-shadow:0 1px 3px rgba(0,0,0,0.85),0 0 4px rgba(0,0,0,0.6);',
            '  white-space:nowrap;pointer-events:none;',
            '}',

            '@media (max-width:900px){',
            '  #challenge-banner .cb-bar-wrap{order:99;flex-basis:100%;margin-top:18px;}',
            '}',
            '@media (max-width:600px){',
            '  #challenge-banner.cb-active{padding:18px 10px 6px;font-size:12px;gap:8px;}',
            '  #challenge-banner .cb-marker::after{font-size:10px;}',
            '}',
        ].join('');
        document.head.appendChild(s);
    }

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

    function fmt(num) {
        return (num || 0).toLocaleString();
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
        });
    }

    function render(banner, payload, t) {
        var ch = payload.challenge;
        var myRank = payload.my_rank;
        var myCp = payload.my_cp || 0;
        var total = ch.total_cp || 0;
        var gold = ch.target_gold || 1;
        var fillPct = Math.min(100, (total / gold) * 100);
        var leader = payload.leader;
        var participants = payload.participants_count || 0;

        var bronzeLeft = Math.min(100, (ch.target_bronze / gold) * 100);
        var silverLeft = Math.min(100, (ch.target_silver / gold) * 100);

        var leaderHtml = '';
        if (leader) {
            if (leader.is_you) {
                leaderHtml =
                    '<span class="cb-leader cb-leader-you" title="' + escapeHtml(t.youAreLeading) + '">'
                    + '🥇 ' + escapeHtml(t.youAreLeading)
                    + '</span>';
            } else {
                leaderHtml =
                    '<span class="cb-leader" title="' + escapeHtml(t.leader) + '">'
                    + '🥇 <b>' + escapeHtml(leader.username) + '</b> · ' + fmt(leader.cp_count) + ' CP'
                    + '</span>';
            }
        }

        banner.classList.toggle('cb-paused', !!ch.is_paused);
        banner.innerHTML = ''
            + '<span class="cb-name"><span class="cb-trophy">🏆</span>' + escapeHtml(ch.name) + '</span>'
            + '<span class="cb-status ' + (ch.is_paused ? 'paused' : '') + '">'
            +   (ch.is_paused ? t.paused : ch.status)
            + '</span>'
            + '<span class="cb-rank">'
            +   escapeHtml(t.rank) + ' <b>#' + (myRank || '—') + '</b>'
            +   (participants ? ' / ' + participants : '')
            +   ' · ' + fmt(myCp) + ' CP'
            + '</span>'
            + leaderHtml
            + '<div class="cb-bar-wrap">'
            +   '<div class="cb-bar">'
            +     '<div class="cb-fill" style="width:' + fillPct.toFixed(1) + '%"></div>'
            +     '<div class="cb-marker" data-label="🥉 ' + fmt(ch.target_bronze) + '" style="left:' + bronzeLeft.toFixed(1) + '%"></div>'
            +     '<div class="cb-marker" data-label="🥈 ' + fmt(ch.target_silver) + '" style="left:' + silverLeft.toFixed(1) + '%"></div>'
            +     '<div class="cb-marker" data-label="🥇 ' + fmt(ch.target_gold)   + '" style="left:100%"></div>'
            +     '<div class="cb-progress-text">' + fmt(total) + ' / ' + fmt(gold) + ' CP</div>'
            +   '</div>'
            + '</div>'
            + '<a class="cb-link" href="/challenges/' + ch.id + '/">'
            +   escapeHtml(t.leaderboard) + ' →'
            + '</a>';

        banner.classList.add('cb-active');
        banner.hidden = false;
        // Push the layout down by the banner height so the topbar tools row
        // is not hidden underneath it.
        document.body.style.paddingTop = banner.offsetHeight + 'px';
    }

    function fetchAndRender(banner) {
        var batchId = banner.dataset.batchId;
        var url = '/api/v1/challenges/mine/' + (batchId ? '?batch_id=' + encodeURIComponent(batchId) : '');
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCookie('csrftoken') || '' },
        }).then(function (r) {
            if (!r.ok) return null;
            return r.json();
        }).then(function (data) {
            if (!data || !data.enrolled) {
                banner.hidden = true;
                banner.classList.remove('cb-active');
                document.body.style.paddingTop = '';
                return;
            }
            render(banner, data, {
                rank: banner.dataset.i18nRank,
                paused: banner.dataset.i18nPaused,
                progress: banner.dataset.i18nProgress,
                leader: banner.dataset.i18nLeader || 'Leader',
                leaderboard: banner.dataset.i18nLeaderboard || 'Leaderboard',
                youAreLeading: banner.dataset.i18nLeading || 'You are leading!',
            });
        }).catch(function () { /* best-effort */ });
    }

    function init() {
        var banner = document.getElementById('challenge-banner');
        if (!banner) return;
        if (banner.dataset.authenticated !== '1') return;

        injectStyles();
        fetchAndRender(banner);
        pollTimer = setInterval(function () { fetchAndRender(banner); }, POLL_MS);

        // Public hook so the submit flow in main.js can refresh us instantly.
        window.LAN_refreshChallenge = function () { fetchAndRender(banner); };
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
