/* Lost At Night — challenge segment inside the in-task topbar.
   Renders enrolled state (challenge name + status + bar + rank + leader)
   or promo state (active challenges available — Join / Sign in) inside
   the existing #challenge-banner slot of .ds-task-bar. JS-only. */
(function () {
    'use strict';

    var POLL_MS = 60000;
    var pollTimer = null;

    function injectStyles() {
        if (document.getElementById('challenge-banner-styles')) return;
        var s = document.createElement('style');
        s.id = 'challenge-banner-styles';
        s.textContent = [
            /* The slot lives inside .ds-task-bar — flex item that grows and
               centers its content as a tight group. */
            '.ds-task-bar__challenge{',
            '  flex:1;display:flex;align-items:center;justify-content:center;',
            '  gap:10px;min-width:0;padding:0 8px;',
            '}',
            '.ds-task-bar__challenge:empty{display:none;}',

            /* Enrolled state */
            '.cb-name{',
            '  display:inline-flex;align-items:center;gap:6px;',
            '  padding:0 10px;height:26px;border-radius:999px;',
            '  background:var(--bg-2);border:1px solid var(--line);',
            '  color:var(--ink-1);font-weight:500;font-size:12px;',
            '  max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:0;',
            '  text-decoration:none;',
            '}',
            '.cb-name:hover{text-decoration:none;border-color:var(--accent);}',
            '.cb-name .cb-trophy{color:var(--accent);flex-shrink:0;}',
            '.cb-name__label{',
            '  color:var(--ink-3);font-weight:500;text-transform:uppercase;',
            '  letter-spacing:0.5px;font-size:10px;',
            '}',
            '.cb-name__sep{color:var(--ink-3);}',
            '.cb-name__title{color:var(--ink-0);font-weight:600;overflow:hidden;text-overflow:ellipsis;}',
            '.cb-status{',
            '  display:inline-flex;align-items:center;height:22px;padding:0 9px;',
            '  font-size:10px;text-transform:uppercase;letter-spacing:0.6px;font-weight:600;',
            '  border-radius:999px;flex-shrink:0;',
            '  background:oklch(0.32 0.12 150 / 0.35);color:oklch(0.92 0.16 150);',
            '  border:1px solid oklch(0.5 0.16 150 / 0.5);',
            '}',
            '.cb-status.paused{',
            '  background:oklch(0.35 0.14 75 / 0.35);color:oklch(0.92 0.17 75);',
            '  border-color:oklch(0.55 0.17 75 / 0.5);',
            '}',
            '.cb-bar-wrap{flex:1;min-width:140px;max-width:380px;display:flex;align-items:center;gap:8px;}',
            '.cb-bar-label{font-family:var(--font-mono);font-size:10px;color:var(--ink-3);text-transform:uppercase;letter-spacing:0.5px;}',
            '.cb-bar{flex:1;position:relative;height:8px;background:rgba(0,0,0,0.35);border:1px solid var(--line-soft);border-radius:4px;overflow:visible;}',
            '.cb-fill{position:absolute;top:0;left:0;bottom:0;border-radius:inherit;transition:right .5s ease;background:linear-gradient(90deg,#cd7f32 0%,#c0c0c0 50%,var(--accent) 100%);}',
            '.cb-paused .cb-fill{filter:grayscale(0.6) opacity(0.6);}',
            '.cb-tick{position:absolute;top:-3px;bottom:-3px;width:2px;border-radius:1px;transform:translateX(-50%);}',
            '.cb-tick--bronze{background:#cd7f32;box-shadow:0 0 4px rgba(205,127,50,0.5);}',
            '.cb-tick--silver{background:#d8d8d8;box-shadow:0 0 4px rgba(216,216,216,0.4);}',
            '.cb-tick--gold{background:var(--accent);box-shadow:0 0 4px rgba(233,249,144,0.5);}',
            '.cb-tick.is-reached{height:14px;top:-3px;width:3px;}',
            '.cb-bar-num{font-family:var(--font-mono);font-size:11px;color:var(--ink-1);white-space:nowrap;}',
            '.cb-rank-mini{display:inline-flex;align-items:center;gap:4px;font-family:var(--font-mono);font-size:11px;color:var(--ink-2);white-space:nowrap;flex-shrink:0;}',
            '.cb-rank-mini b{color:var(--ink-0);}',
            '.cb-leader{',
            '  display:inline-flex;align-items:center;gap:4px;height:22px;padding:0 8px;',
            '  background:rgba(233,249,144,0.18);color:var(--accent);',
            '  border:1px solid rgba(233,249,144,0.4);',
            '  border-radius:999px;font-size:11px;font-weight:600;',
            '  max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:0;',
            '}',
            '.cb-leaderboard-link{',
            '  display:inline-flex;align-items:center;gap:4px;',
            '  color:var(--ink-2);text-decoration:none;font-size:11px;font-weight:500;',
            '  white-space:nowrap;flex-shrink:0;',
            '  transition:color .15s ease;',
            '}',
            '.cb-leaderboard-link:hover{color:var(--accent);}',

            /* Promo state */
            '.cb-promo-row{display:inline-flex;align-items:center;gap:10px;}',
            '.cb-promo-text{color:var(--ink-1);font-size:12px;}',
            '.cb-promo-text b{color:var(--ink-0);}',
            '.cb-promo-cta{',
            '  display:inline-flex;align-items:center;gap:5px;',
            '  height:26px;padding:0 12px;border-radius:999px;',
            '  background:var(--accent);color:var(--accent-ink);',
            '  text-decoration:none;font-size:11px;font-weight:600;',
            '}',
            '.cb-promo-cta:hover{filter:brightness(1.05);}',

            '@media (max-width:1100px){',
            '  .cb-bar-wrap{max-width:200px;}',
            '  .cb-leader{display:none;}',
            '}',
            '@media (max-width:900px){',
            '  .cb-bar-wrap,.cb-rank-mini{display:none;}',
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

    function fmt(num) { return (num || 0).toLocaleString(); }
    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
        });
    }

    function trophySvg(size) {
        size = size || 14;
        return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
             + '<path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4z"/>'
             + '<path d="M17 4h3v2a3 3 0 0 1-3 3M7 4H4v2a3 3 0 0 0 3 3"/>'
             + '</svg>';
    }

    function renderEnrolled(slot, payload, t) {
        var ch = payload.challenge;
        var myRank = payload.my_rank;
        var total = ch.total_cp || 0;
        var gold = ch.target_gold || 1;
        var fillPct = Math.min(100, (total / gold) * 100);
        var leader = payload.leader;

        var leaderHtml = '';
        if (leader && !leader.is_you) {
            var medalSvg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
                + 'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
                + 'stroke-linejoin="round" style="flex-shrink:0;">'
                + '<circle cx="12" cy="15" r="6"/>'
                + '<path d="M8.5 3l3.5 6 3.5-6"/>'
                + '<path d="M8.5 3l-2 4M15.5 3l2 4"/></svg>';
            leaderHtml =
                '<span class="cb-leader" title="' + escapeHtml(t.leader) + ': ' + escapeHtml(leader.username) + ' · ' + fmt(leader.cp_count) + ' CP">'
                + medalSvg + '<b>' + escapeHtml(leader.username) + '</b></span>';
        }

        slot.classList.toggle('cb-paused', !!ch.is_paused);
        slot.innerHTML = ''
            + '<a href="/challenges/' + ch.id + '/" class="cb-name" title="' + escapeHtml(ch.name) + '">'
            +   '<span class="cb-trophy">' + trophySvg(13) + '</span>'
            +   '<span class="cb-name__label">' + escapeHtml(t.challengeLabel) + '</span>'
            +   '<span class="cb-name__sep">·</span>'
            +   '<span class="cb-name__title">' + escapeHtml(ch.name) + '</span>'
            + '</a>'
            + '<span class="cb-status ' + (ch.is_paused ? 'paused' : '') + '">'
            +   (ch.is_paused ? t.paused : ch.status)
            + '</span>'
            + '<div class="cb-bar-wrap">'
            +   '<span class="cb-bar-label">CP</span>'
            +   '<div class="cb-bar">'
            +     '<div class="cb-fill" style="right:' + (100 - fillPct).toFixed(1) + '%"></div>'
            +     '<div class="cb-tick cb-tick--bronze' + (total >= ch.target_bronze ? ' is-reached' : '') + '" '
            +       'style="left:' + ((ch.target_bronze / gold) * 100).toFixed(1) + '%" '
            +       'title="🥉 Bronze: ' + fmt(ch.target_bronze) + ' CP"></div>'
            +     '<div class="cb-tick cb-tick--silver' + (total >= ch.target_silver ? ' is-reached' : '') + '" '
            +       'style="left:' + ((ch.target_silver / gold) * 100).toFixed(1) + '%" '
            +       'title="🥈 Silver: ' + fmt(ch.target_silver) + ' CP"></div>'
            +     '<div class="cb-tick cb-tick--gold' + (total >= gold ? ' is-reached' : '') + '" '
            +       'style="left:100%" '
            +       'title="🥇 Gold: ' + fmt(gold) + ' CP"></div>'
            +   '</div>'
            +   '<span class="cb-bar-num">' + fmt(total) + ' / ' + fmt(gold) + '</span>'
            + '</div>'
            + '<span class="cb-rank-mini">'
            +   escapeHtml(t.rank) + ' <b>#' + (myRank || '—') + '</b>'
            + '</span>'
            + leaderHtml;
    }

    function renderPromo(slot, opts) {
        slot.classList.remove('cb-paused');
        slot.innerHTML = ''
            + '<div class="cb-promo-row">'
            +   '<span class="cb-trophy" style="color:var(--accent);display:inline-flex;">' + trophySvg(14) + '</span>'
            +   '<span class="cb-promo-text">' + opts.text + '</span>'
            +   '<a class="cb-promo-cta" href="' + opts.href + '">'
            +     opts.cta
            +     ' <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>'
            +   '</a>'
            + '</div>';
    }

    function clearSlot(slot) {
        slot.classList.remove('cb-paused');
        slot.innerHTML = '';
    }

    function fetchActiveCount() {
        return fetch('/api/v1/challenges/', {
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCookie('csrftoken') || '' },
        }).then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
              if (!data) return 0;
              var grouped = data.grouped || {};
              return (grouped.active || []).length;
          })
          .catch(function () { return 0; });
    }

    function showPromoOrClear(slot, isAuth) {
        return fetchActiveCount().then(function (n) {
            if (!n) { clearSlot(slot); return; }
            var T = window.LAN_I18N || {};
            function txt(one, many) {
                var s = n === 1 ? (T[one] || one) : (T[many] || many);
                return s.replace('{n}', '<b>' + n + '</b>');
            }
            if (isAuth) {
                renderPromo(slot, {
                    text: txt('promo_one', 'promo_many'),
                    cta: T.cta_join || 'Join one',
                    href: '/#challenges-section',
                });
            } else {
                renderPromo(slot, {
                    text: txt('promo_one_anon', 'promo_many_anon'),
                    cta: T.cta_sign_in || 'Sign in',
                    href: '/accounts/login/?next=/gettask',
                });
            }
        });
    }

    function fetchAndRender(slot) {
        var isAuth = slot.dataset.authenticated === '1';
        if (!isAuth) return showPromoOrClear(slot, false);

        var batchId = slot.dataset.batchId;
        var url = '/api/v1/challenges/mine/' + (batchId ? '?batch_id=' + encodeURIComponent(batchId) : '');
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCookie('csrftoken') || '' },
        }).then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
              if (!data || !data.enrolled) return showPromoOrClear(slot, true);
              renderEnrolled(slot, data, {
                  rank: slot.dataset.i18nRank,
                  paused: slot.dataset.i18nPaused,
                  progress: slot.dataset.i18nProgress,
                  leader: slot.dataset.i18nLeader || 'Leader',
                  leaderboard: slot.dataset.i18nLeaderboard || 'Leaderboard',
                  youAreLeading: slot.dataset.i18nLeading || 'You are leading!',
                  challengeLabel: slot.dataset.i18nChallenge || 'Challenge',
              });
          }).catch(function () { /* best-effort */ });
    }

    function init() {
        var slot = document.getElementById('challenge-banner');
        if (!slot) return;
        injectStyles();
        fetchAndRender(slot);
        pollTimer = setInterval(function () { fetchAndRender(slot); }, POLL_MS);
        window.LAN_refreshChallenge = function () { fetchAndRender(slot); };
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
