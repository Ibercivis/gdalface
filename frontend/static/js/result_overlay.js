/* Lost At Night — post-submit Result overlay (screen 08).
   Replaces the legacy Bootstrap "Thank you" modal. Mounted by main.js
   via window.LAN_showResult({ cpCount, imageName, imageCaption, result }).
   The `result` object carries the rich payload from the backend
   (delta / totals / rank / streak / challenge). */
(function () {
    'use strict';

    function injectStyles() {
        if (document.getElementById('lan-result-css')) return;
        var s = document.createElement('style');
        s.id = 'lan-result-css';
        s.textContent = [
            '#lan-result-overlay{',
            '  position:fixed;inset:0;z-index:1080;',
            '  background:oklch(0.05 0.02 280 / 0.78);',
            '  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);',
            '  display:flex;align-items:center;justify-content:center;',
            '  font-family:var(--font-ui,system-ui,sans-serif);',
            '  animation:lan-fade-in 200ms ease;',
            '  padding:16px;',
            '  overflow-y:auto;',
            '}',
            '@keyframes lan-fade-in{from{opacity:0}to{opacity:1}}',

            '.lan-result-card{',
            '  width:680px;max-width:100%;',
            '  background:var(--bg-1);',
            '  border:1px solid var(--line);',
            '  border-radius:14px;',
            '  box-shadow:0 18px 60px oklch(0 0 0 / 0.55);',
            '  color:var(--ink-1);',
            '  position:relative;overflow:hidden;',
            '  margin:auto;',
            '}',
            '.lan-result-card__close{',
            '  position:absolute;top:14px;right:14px;z-index:5;',
            '  width:28px;height:28px;border-radius:50%;',
            '  background:var(--bg-2)!important;border:1px solid var(--line)!important;',
            '  color:var(--ink-2)!important;cursor:pointer!important;',
            '  display:inline-flex;align-items:center;justify-content:center;',
            '  padding:0!important;',
            '  font-weight:400!important;',
            '}',
            '.lan-result-card__close:hover{color:var(--ink-0)!important;background:var(--bg-3)!important;transform:none!important;box-shadow:none!important;}',

            '.lan-result-card__top{',
            '  padding:32px 36px 20px;text-align:center;position:relative;',
            '}',
            '.lan-result-card__top::before{',
            '  content:"";position:absolute;top:-80px;left:50%;transform:translateX(-50%);',
            '  width:380px;height:200px;',
            '  background:radial-gradient(ellipse,oklch(0.95 0.13 113 / 0.18),transparent 70%);',
            '  pointer-events:none;',
            '}',
            '.lan-result-card__pill{',
            '  display:inline-flex;align-items:center;gap:6px;',
            '  padding:5px 12px;border-radius:999px;',
            '  background:var(--accent);color:var(--accent-ink);',
            '  font-size:12px;font-weight:600;',
            '  position:relative;z-index:1;',
            '}',
            '.lan-result-card__title{',
            '  font-size:28px;font-weight:700;color:var(--ink-0);',
            '  letter-spacing:-0.4px;line-height:1.15;',
            '  margin:14px 0 8px;position:relative;z-index:1;',
            '}',
            '.lan-result-card__sub{',
            '  font-size:13px;color:var(--ink-1);',
            '  margin:0 0 6px;position:relative;z-index:1;',
            '}',
            '.lan-result-card__loc{',
            '  font-size:12px;color:var(--ink-2);',
            '  margin:0 0 18px;position:relative;z-index:1;',
            '}',
            '.lan-result-card__loc svg{vertical-align:-3px;margin-right:4px;color:var(--accent);}',

            '.lan-result-card__hero{',
            '  display:flex;align-items:baseline;justify-content:center;gap:24px;',
            '  margin-top:12px;position:relative;z-index:1;flex-wrap:wrap;',
            '}',
            '.lan-result-card__hero .h-cp{',
            '  display:flex;align-items:baseline;gap:8px;',
            '}',
            '.lan-result-card__hero .h-cp .v{',
            '  font-family:var(--font-mono);font-size:48px;font-weight:600;',
            '  color:var(--accent);line-height:1;',
            '  text-shadow:0 4px 24px oklch(0.95 0.13 113 / 0.4);',
            '}',
            '.lan-result-card__hero .h-cp .l{',
            '  font-size:13px;color:var(--ink-2);text-transform:uppercase;letter-spacing:1px;font-weight:500;',
            '}',
            '.lan-result-card__hero .h-mini{',
            '  display:inline-flex;align-items:center;gap:6px;',
            '  font-size:12px;color:var(--ink-2);',
            '  padding:5px 10px;border-radius:999px;',
            '  background:var(--bg-2);border:1px solid var(--line-soft);',
            '}',
            '.lan-result-card__hero .h-mini b{color:var(--ink-0);font-weight:600;}',

            '.lan-result-card__impact{',
            '  margin:18px 36px 0;padding:10px 14px;',
            '  background:oklch(0.95 0.13 113 / 0.08);',
            '  border:1px solid oklch(0.95 0.13 113 / 0.25);',
            '  border-radius:10px;',
            '  font-size:12.5px;color:var(--ink-1);line-height:1.55;',
            '  text-align:center;',
            '  position:relative;z-index:1;',
            '}',
            '.lan-result-card__impact b{color:var(--ink-0);}',

            '.lan-result-card__strip{',
            '  display:grid;grid-template-columns:1fr 1px 1fr 1px 1fr;',
            '  border-top:1px solid var(--line);border-bottom:1px solid var(--line);',
            '  margin-top:24px;',
            '}',
            '.lan-result-card__strip > div:not(.sep){',
            '  padding:18px 14px;text-align:center;',
            '}',
            '.lan-result-card__strip .sep{background:var(--line-soft);}',
            '.lan-result-card__strip .v{',
            '  font-family:var(--font-mono);font-size:22px;font-weight:600;color:var(--ink-0);',
            '  letter-spacing:-0.3px;',
            '}',
            '.lan-result-card__strip .delta{',
            '  font-size:11px;color:var(--accent);font-weight:600;margin-left:4px;',
            '}',
            '.lan-result-card__strip .l{',
            '  font-size:11px;color:var(--ink-3);margin-top:6px;',
            '  text-transform:uppercase;letter-spacing:0.6px;',
            '}',

            '.lan-result-card__row{',
            '  display:flex;justify-content:center;align-items:center;gap:20px;flex-wrap:wrap;',
            '  padding:16px 24px;',
            '  border-bottom:1px solid var(--line);',
            '}',
            '.lan-result-card__row .chip{',
            '  display:inline-flex;align-items:center;gap:6px;',
            '  font-size:12.5px;color:var(--ink-1);',
            '  padding:6px 12px;border-radius:999px;',
            '  background:var(--bg-2);border:1px solid var(--line-soft);',
            '}',
            '.lan-result-card__row .chip b{color:var(--ink-0);font-weight:600;}',
            '.lan-result-card__row .chip .delta-up{',
            '  color:var(--good);font-weight:600;font-family:var(--font-mono);font-size:11px;',
            '}',
            '.lan-result-card__row .chip .delta-flat{color:var(--ink-3);font-size:11px;}',
            '.lan-result-card__row .chip svg{color:var(--accent);}',

            '.lan-result-card__challenge{',
            '  padding:18px 28px;',
            '  background:linear-gradient(180deg,oklch(0.16 0.045 290 / 0.6),transparent);',
            '  border-bottom:1px solid var(--line);',
            '}',
            '.lan-result-card__challenge-head{',
            '  display:flex;align-items:center;gap:8px;margin-bottom:10px;',
            '  font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);',
            '}',
            '.lan-result-card__challenge-head .name{color:var(--ink-0);font-weight:600;text-transform:none;letter-spacing:0;font-size:14px;}',
            '.lan-result-card__challenge-stats{',
            '  display:flex;gap:14px;font-size:12px;color:var(--ink-1);margin-bottom:10px;flex-wrap:wrap;',
            '}',
            '.lan-result-card__challenge-stats b{color:var(--ink-0);font-weight:600;}',
            '.lan-result-card__challenge-stats .accent{color:var(--accent);font-weight:600;}',
            '.lan-result-card__challenge-bar{',
            '  position:relative;height:10px;background:rgba(0,0,0,0.4);',
            '  border:1px solid var(--line-soft);border-radius:6px;overflow:visible;',
            '}',
            '.lan-result-card__challenge-bar .fill{',
            '  position:absolute;top:0;left:0;bottom:0;border-radius:inherit;',
            '  background:linear-gradient(90deg,#cd7f32 0%,#c0c0c0 50%,var(--accent) 100%);',
            '  transition:width 800ms cubic-bezier(0.16,1,0.3,1);',
            '}',
            '.lan-result-card__challenge-bar .tick{',
            '  position:absolute;top:-3px;bottom:-3px;width:2px;border-radius:1px;transform:translateX(-50%);',
            '}',
            '.lan-result-card__challenge-bar .tick--bronze{background:#cd7f32;}',
            '.lan-result-card__challenge-bar .tick--silver{background:#d8d8d8;}',
            '.lan-result-card__challenge-bar .tick--gold{background:var(--accent);}',
            '.lan-result-card__challenge-msg{',
            '  margin-top:8px;font-size:11.5px;color:var(--ink-2);',
            '}',

            '.lan-result-card__actions{',
            '  display:flex;gap:10px;align-items:center;',
            '  padding:18px 28px;',
            '}',
            '.lan-result-card__actions .right{margin-left:auto;display:flex;gap:10px;}',

            '@media (max-width:560px){',
            '  .lan-result-card__top{padding:28px 22px 16px;}',
            '  .lan-result-card__title{font-size:22px;}',
            '  .lan-result-card__strip{grid-template-columns:1fr;}',
            '  .lan-result-card__strip .sep{height:1px;width:100%;background:var(--line-soft);}',
            '  .lan-result-card__strip > div:not(.sep){padding:12px 14px;}',
            '  .lan-result-card__actions{flex-direction:column;align-items:stretch;}',
            '  .lan-result-card__actions .right{margin-left:0;flex-direction:column;}',
            '  .lan-result-card__actions .ds-btn{width:100%;}',
            '}',
        ].join('');
        document.head.appendChild(s);
    }

    function fmtInt(n) { return (n || 0).toLocaleString(); }

    // 7245 → "2h 0m 45s" / 134 → "2m 14s" / 8 → "8s"
    function fmtTime(s) {
        s = Math.max(0, Math.round(s || 0));
        var h = Math.floor(s / 3600);
        var m = Math.floor((s % 3600) / 60);
        var sec = s % 60;
        var parts = [];
        if (h) parts.push(h + 'h');
        if (m || h) parts.push(m + 'm');
        if (!h) parts.push(sec + 's');
        return parts.join(' ');
    }

    function escapeHtml(str) {
        return String(str == null ? '' : str).replace(/[&<>"']/g, function (c) {
            return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
        });
    }

    function deltaArrow(prev, curr) {
        // Lower rank number = better. Returns HTML span with arrow + delta.
        if (prev == null || curr == null) return '';
        if (curr < prev) {
            return ' <span class="delta-up">↑' + (prev - curr) + '</span>';
        }
        if (curr > prev) {
            return ' <span class="delta-flat">↓' + (curr - prev) + '</span>';
        }
        return ' <span class="delta-flat">·</span>';
    }

    window.LAN_showResult = function (payload) {
        injectStyles();
        var existing = document.getElementById('lan-result-overlay');
        if (existing) existing.remove();

        // Close any Bootstrap modal so backdrops don't pile up.
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            document.querySelectorAll('.modal.show').forEach(function (m) {
                var inst = bootstrap.Modal.getInstance(m);
                if (inst) inst.hide();
            });
        }
        document.querySelectorAll('.modal-backdrop').forEach(function (b) { b.remove(); });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');

        var cpCountClient = (payload && payload.cpCount) || 0;
        var imageName     = (payload && payload.imageName) || '—';
        var imageCaption  = (payload && payload.imageCaption) || '';
        var result        = (payload && payload.result) || {};

        var delta    = result.delta    || { cp: cpCountClient, tasks: 1, time_seconds: 0 };
        var totals   = result.totals   || null;
        var rank     = result.rank     || null;
        var streak   = result.streak_days || 0;
        var ch       = result.challenge || null;

        // ── Header / hero ────────────────────────────────────────────────
        var locHtml = '';
        if (imageCaption) {
            locHtml = ''
                + '<p class="lan-result-card__loc">'
                + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
                + '<path d="M12 22s7-7.58 7-12a7 7 0 0 0-14 0c0 4.42 7 12 7 12z"/><circle cx="12" cy="10" r="3"/></svg>'
                + escapeHtml(imageCaption) + '</p>';
        }

        var heroHtml = ''
            + '<div class="lan-result-card__hero">'
            + '<div class="h-cp"><span class="v">+' + fmtInt(delta.cp) + '</span><span class="l">CP</span></div>'
            + '<span class="h-mini">'
            + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="color:var(--accent)"><path d="M3 21V7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14"/><path d="M3 21h18M9 9h6M9 13h6M9 17h6"/></svg>'
            + '<b>+1</b> ' + (delta.tasks === 1 ? 'image' : 'images')
            + '</span>'
            + '<span class="h-mini">'
            + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="color:var(--accent)"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
            + '<b>' + escapeHtml(fmtTime(delta.time_seconds)) + '</b>'
            + '</span>'
            + '</div>';

        // ── Plain-language impact line ───────────────────────────────────
        var impactHtml = '';
        if (imageCaption) {
            impactHtml = ''
                + '<div class="lan-result-card__impact">'
                + 'Your contribution helps measure light pollution in <b>'
                + escapeHtml(imageCaption) + '</b>.'
                + '</div>';
        }

        // ── Lifetime totals strip ────────────────────────────────────────
        var stripHtml = '';
        if (totals) {
            stripHtml = ''
                + '<div class="lan-result-card__strip">'
                + '<div><div class="v">' + fmtInt(totals.cp)
                +   '<span class="delta">+' + fmtInt(delta.cp) + '</span></div>'
                +   '<div class="l">Total CP</div></div>'
                + '<div class="sep"></div>'
                + '<div><div class="v">' + fmtInt(totals.tasks)
                +   '<span class="delta">+' + fmtInt(delta.tasks) + '</span></div>'
                +   '<div class="l">Total tasks</div></div>'
                + '<div class="sep"></div>'
                + '<div><div class="v">' + escapeHtml(fmtTime(totals.time_seconds))
                +   '<span class="delta">+' + escapeHtml(fmtTime(delta.time_seconds)) + '</span></div>'
                +   '<div class="l">Total time</div></div>'
                + '</div>';
        }

        // ── Rank + streak chips row ──────────────────────────────────────
        var chipsHtml = '';
        var chips = [];
        if (rank) {
            chips.push(''
                + '<span class="chip">'
                + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4z"/></svg>'
                + 'Global rank <b>#' + fmtInt(rank.global) + '</b>'
                + deltaArrow(rank.previous_global, rank.global)
                + '</span>');
        }
        if (streak >= 2) {
            chips.push(''
                + '<span class="chip">'
                + '🔥 <b>' + streak + '</b> day' + (streak === 1 ? '' : 's') + ' streak'
                + '</span>');
        }
        if (chips.length) {
            chipsHtml = '<div class="lan-result-card__row">' + chips.join('') + '</div>';
        }

        // ── Challenge section (if enrolled and CPs counted) ──────────────
        var challengeHtml = '';
        if (ch) {
            var pct = ch.target_gold > 0
                ? Math.min(100, (ch.total_cp / ch.target_gold) * 100)
                : 0;
            var bronzePct = ch.target_gold > 0 ? (ch.target_bronze / ch.target_gold) * 100 : 33;
            var silverPct = ch.target_gold > 0 ? (ch.target_silver / ch.target_gold) * 100 : 66;

            var nextTarget, nextTargetLabel, nextTargetEmoji;
            if (ch.total_cp < ch.target_bronze) {
                nextTarget = ch.target_bronze; nextTargetLabel = 'Bronze'; nextTargetEmoji = '🥉';
            } else if (ch.total_cp < ch.target_silver) {
                nextTarget = ch.target_silver; nextTargetLabel = 'Silver'; nextTargetEmoji = '🥈';
            } else if (ch.total_cp < ch.target_gold) {
                nextTarget = ch.target_gold;   nextTargetLabel = 'Gold';   nextTargetEmoji = '🥇';
            } else {
                nextTarget = null; nextTargetLabel = ''; nextTargetEmoji = '';
            }
            var msg;
            if (nextTarget == null) {
                msg = 'Gold target reached!';
            } else {
                msg = nextTargetEmoji + ' ' + fmtInt(nextTarget - ch.total_cp) + ' CP to ' + nextTargetLabel
                    + ' · ' + fmtInt(ch.total_cp) + ' / ' + fmtInt(ch.target_gold) + ' total';
            }

            challengeHtml = ''
                + '<div class="lan-result-card__challenge">'
                + '<div class="lan-result-card__challenge-head">'
                +   '<svg class="ds-icon ds-icon--sm" style="color:var(--accent)"><use href="#ds-icon-trophy"/></svg>'
                +   'Challenge · <span class="name">' + escapeHtml(ch.name) + '</span>'
                + '</div>'
                + '<div class="lan-result-card__challenge-stats">'
                +   '<span><span class="accent">+' + fmtInt(ch.added_cp) + ' CP</span> added</span>'
                +   '<span>Your CP in this challenge: <b>' + fmtInt(ch.my_cp) + '</b></span>'
                +   '<span>Your rank: <b>#' + fmtInt(ch.my_rank) + '</b>'
                +     deltaArrow(ch.previous_rank, ch.my_rank) + '</span>'
                + '</div>'
                + '<div class="lan-result-card__challenge-bar">'
                +   '<div class="fill" style="width:' + pct.toFixed(2) + '%"></div>'
                +   '<div class="tick tick--bronze" style="left:' + bronzePct.toFixed(2) + '%"></div>'
                +   '<div class="tick tick--silver" style="left:' + silverPct.toFixed(2) + '%"></div>'
                +   '<div class="tick tick--gold"   style="left:100%"></div>'
                + '</div>'
                + '<div class="lan-result-card__challenge-msg">' + escapeHtml(msg) + '</div>'
                + '</div>';
        }

        // ── Team section (if the user is in a team) ──────────────────────
        var teamHtml = '';
        var tm = result.team || null;
        if (tm) {
            var TT = window.LAN_I18N || {};
            teamHtml = ''
                + '<div class="lan-result-card__challenge">'
                + '<div class="lan-result-card__challenge-head">'
                +   '<i class="fa-solid fa-people-group" style="color:var(--accent)"></i> '
                +   (TT.team_label || 'Team') + ' · <a class="name" href="/teams/' + encodeURIComponent(tm.slug) + '/" style="text-decoration:none">' + escapeHtml(tm.name) + '</a>'
                + '</div>'
                + '<div class="lan-result-card__challenge-stats">'
                +   '<span><span class="accent">+' + fmtInt(tm.added_cp) + ' CP</span></span>'
                +   '<span>' + (TT.team_yours || 'Yours for the team') + ': <b>' + fmtInt(tm.my_cp) + '</b></span>'
                +   '<span>' + (TT.team_total || 'Team total') + ': <b>' + fmtInt(tm.total_cp) + '</b></span>'
                + '</div>'
                + '</div>';
        }

        // ── Compose ──────────────────────────────────────────────────────
        var overlay = document.createElement('div');
        overlay.id = 'lan-result-overlay';
        overlay.innerHTML = ''
            + '<div class="lan-result-card" role="dialog" aria-modal="true">'
            +   '<button type="button" class="lan-result-card__close" id="lan-result-close" aria-label="Close">'
            +     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6l-12 12"/></svg>'
            +   '</button>'
            +   '<div class="lan-result-card__top">'
            +     '<span class="lan-result-card__pill">'
            +       '<svg class="ds-icon ds-icon--sm" style="color:currentColor;"><use href="#ds-icon-check"/></svg>'
            +       'Submitted</span>'
            +     '<h2 class="lan-result-card__title">Great work!</h2>'
            +     '<p class="lan-result-card__sub">Your guess for <span class="mono">' + escapeHtml(imageName) + '</span> has been submitted.</p>'
            +     locHtml
            +     heroHtml
            +     impactHtml
            +   '</div>'
            +   stripHtml
            +   chipsHtml
            +   challengeHtml
            + teamHtml
            +   '<div class="lan-result-card__actions">'
            +     '<button class="ds-btn ds-btn--ghost" id="lan-share-btn">'
            +       '<svg class="ds-icon"><use href="#ds-icon-share"/></svg> Share</button>'
            +     '<div class="right">'
            +       '<a class="ds-btn ds-btn--secondary" href="/">Back home</a>'
            +       '<button class="ds-btn ds-btn--primary" id="lan-next-btn">Next photo'
            +         '<svg class="ds-icon"><use href="#ds-icon-chevron-right"/></svg></button>'
            +     '</div>'
            +   '</div>'
            + '</div>';
        document.body.appendChild(overlay);

        document.getElementById('lan-next-btn').addEventListener('click', function () {
            window.location.reload();
        });
        document.getElementById('lan-result-close').addEventListener('click', function () {
            overlay.remove();
        });
        var sb = document.getElementById('lan-share-btn');
        if (sb) sb.addEventListener('click', function () {
            var shareText = 'I just georeferenced ' + imageName
                + (imageCaption ? ' (' + imageCaption + ')' : '')
                + ' on Lost at Night — earning ' + fmtInt(delta.cp) + ' CP. Join: ';
            if (navigator.share) {
                navigator.share({
                    title: 'Lost at Night',
                    text: shareText,
                    url: window.location.origin,
                }).catch(function () {});
            } else if (navigator.clipboard) {
                navigator.clipboard.writeText(shareText + window.location.origin);
                sb.textContent = 'Link copied!';
                setTimeout(function () {
                    sb.innerHTML = '<svg class="ds-icon"><use href="#ds-icon-share"/></svg> Share';
                }, 1500);
            }
        });
    };
})();
