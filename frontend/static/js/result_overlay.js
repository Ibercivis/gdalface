/* Lost At Night — post-submit Result overlay (screen 08).
   Replaces the legacy Bootstrap "Thank you" modal. Mounted by main.js
   via window.LAN_showResult({ cpCount, imageName }). */
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
            '  backdrop-filter:blur(6px);',
            '  display:flex;align-items:center;justify-content:center;',
            '  font-family:var(--font-ui,system-ui,sans-serif);',
            '  animation:lan-fade-in 200ms ease;',
            '}',
            '@keyframes lan-fade-in{from{opacity:0}to{opacity:1}}',
            '.lan-result-card{',
            '  width:720px;max-width:calc(100vw - 32px);',
            '  background:var(--bg-1);',
            '  border:1px solid var(--line);',
            '  border-radius:var(--radius-lg);',
            '  box-shadow:var(--shadow);',
            '  color:var(--ink-1);',
            '  position:relative;overflow:hidden;',
            '}',
            '.lan-result-card__top{',
            '  padding:36px 40px 28px;',
            '  text-align:center;',
            '  position:relative;',
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
            '  font-size:32px;font-weight:700;color:var(--ink-0);',
            '  letter-spacing:-0.5px;line-height:1.1;',
            '  margin:14px 0 8px;position:relative;z-index:1;',
            '}',
            '.lan-result-card__sub{',
            '  font-size:14px;color:var(--ink-2);',
            '  margin:0 0 16px;position:relative;z-index:1;',
            '}',
            '.lan-result-card__cp{',
            '  display:flex;align-items:baseline;justify-content:center;gap:10px;',
            '  margin-top:14px;position:relative;z-index:1;',
            '}',
            '.lan-result-card__cp .v{',
            '  font-family:var(--font-mono);font-size:56px;font-weight:600;',
            '  color:var(--accent);line-height:1;',
            '  text-shadow:0 4px 24px oklch(0.95 0.13 113 / 0.4);',
            '}',
            '.lan-result-card__cp .l{',
            '  font-size:14px;color:var(--ink-2);text-transform:uppercase;letter-spacing:1px;font-weight:500;',
            '}',
            '.lan-result-card__strip{',
            '  display:grid;grid-template-columns:1fr 1px 1fr 1px 1fr;',
            '  border-top:1px solid var(--line);border-bottom:1px solid var(--line);',
            '}',
            '.lan-result-card__strip > div:not(.sep){',
            '  padding:20px 16px;text-align:center;',
            '}',
            '.lan-result-card__strip .sep{background:var(--line-soft);}',
            '.lan-result-card__strip .v{',
            '  font-family:var(--font-mono);font-size:24px;font-weight:600;color:var(--ink-0);',
            '  letter-spacing:-0.3px;',
            '}',
            '.lan-result-card__strip .v small{font-size:14px;color:var(--ink-2);font-weight:400;}',
            '.lan-result-card__strip .l{font-size:12px;color:var(--ink-3);margin-top:6px;text-transform:uppercase;letter-spacing:0.6px;}',
            '.lan-result-card__strip .v.good{color:var(--good);}',
            '.lan-result-card__map{',
            '  margin:24px 32px;height:160px;',
            '  background:',
            '    repeating-linear-gradient(0deg,transparent,transparent 24px,var(--line-soft) 24px,var(--line-soft) 25px),',
            '    repeating-linear-gradient(90deg,transparent,transparent 32px,var(--line-soft) 32px,var(--line-soft) 33px),',
            '    var(--bg-2);',
            '  border:1px solid var(--line);border-radius:10px;',
            '  position:relative;',
            '}',
            '.lan-result-card__map .legend{',
            '  position:absolute;bottom:8px;left:12px;',
            '  display:flex;gap:14px;font-size:11px;color:var(--ink-2);',
            '}',
            '.lan-result-card__map .legend .dot{',
            '  display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle;',
            '}',
            '.lan-result-card__map .legend .dot.you{background:var(--accent);box-shadow:0 0 6px var(--accent);}',
            '.lan-result-card__map .legend .dot.real{background:var(--good);box-shadow:0 0 6px var(--good);}',
            '.lan-result-card__map svg{position:absolute;inset:0;width:100%;height:100%;}',
            '.lan-result-card__actions{',
            '  display:flex;gap:10px;align-items:center;',
            '  padding:18px 32px;border-top:1px solid var(--line);',
            '}',
            '.lan-result-card__actions .right{margin-left:auto;display:flex;gap:10px;}',
        ].join('');
        document.head.appendChild(s);
    }

    function format(n) { return (n || 0).toLocaleString(); }

    window.LAN_showResult = function (payload) {
        injectStyles();
        var existing = document.getElementById('lan-result-overlay');
        if (existing) existing.remove();

        // Close any Bootstrap modal first so the two backdrops don't mix.
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            document.querySelectorAll('.modal.show').forEach(function (m) {
                var inst = bootstrap.Modal.getInstance(m);
                if (inst) inst.hide();
            });
        }
        // Also remove any orphan Bootstrap backdrop just in case.
        document.querySelectorAll('.modal-backdrop').forEach(function (b) { b.remove(); });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');

        // Best-effort gamification numbers — we don't know real distance/accuracy,
        // so we synthesize CPs from the count of points placed and show "—" where
        // we don't have data.
        var cpCount = (payload && payload.cpCount) || 0;
        var earned = cpCount * 12; // arbitrary score; replace when backend returns one.
        var imageName = (payload && payload.imageName) || '—';
        var accuracy = '—';
        var distance = '—';
        var timeTaken = '—';

        var overlay = document.createElement('div');
        overlay.id = 'lan-result-overlay';
        overlay.innerHTML = ''
            + '<div class="lan-result-card">'
            +   '<div class="lan-result-card__top">'
            +     '<span class="lan-result-card__pill">'
            +       '<svg class="ds-icon ds-icon--sm" style="color:currentColor;"><use href="#ds-icon-check"/></svg>'
            +       'Submitted</span>'
            +     '<h2 class="lan-result-card__title">Great match!</h2>'
            +     '<p class="lan-result-card__sub">Your guess for <span class="mono">' + imageName + '</span> has been submitted.</p>'
            +     '<div class="lan-result-card__cp">'
            +       '<span class="v">+' + earned + '</span>'
            +       '<span class="l">CP</span>'
            +     '</div>'
            +   '</div>'
            +   '<div class="lan-result-card__strip">'
            +     '<div><div class="v good">' + accuracy + '</div><div class="l">Accuracy</div></div>'
            +     '<div class="sep"></div>'
            +     '<div><div class="v">' + distance + '</div><div class="l">Distance</div></div>'
            +     '<div class="sep"></div>'
            +     '<div><div class="v">' + timeTaken + '</div><div class="l">Time taken</div></div>'
            +   '</div>'
            +   '<div class="lan-result-card__map">'
            +     '<svg viewBox="0 0 600 160" preserveAspectRatio="none">'
            +       '<line x1="280" y1="80" x2="320" y2="92" stroke="currentColor" stroke-dasharray="4 4" opacity="0.4"/>'
            +       '<circle cx="280" cy="80" r="6" fill="oklch(0.95 0.13 113)"/>'
            +       '<circle cx="280" cy="80" r="12" fill="oklch(0.95 0.13 113 / 0.25)"/>'
            +       '<circle cx="320" cy="92" r="6" fill="oklch(0.78 0.16 150)"/>'
            +       '<circle cx="320" cy="92" r="12" fill="oklch(0.78 0.16 150 / 0.25)"/>'
            +     '</svg>'
            +     '<div class="legend">'
            +       '<span><span class="dot you"></span>Your guess</span>'
            +       '<span><span class="dot real"></span>Actual location</span>'
            +     '</div>'
            +   '</div>'
            +   '<div class="lan-result-card__actions">'
            +     '<button class="ds-btn ds-btn--ghost" id="lan-share-btn">'
            +       '<svg class="ds-icon"><use href="#ds-icon-share"/></svg> Share</button>'
            +     '<div class="right">'
            +       '<a class="ds-btn ds-btn--secondary" href="/challenges/">Back to challenges</a>'
            +       '<button class="ds-btn ds-btn--primary" id="lan-next-btn">Next photo'
            +         '<svg class="ds-icon"><use href="#ds-icon-chevron-right"/></svg></button>'
            +     '</div>'
            +   '</div>'
            + '</div>';
        document.body.appendChild(overlay);

        document.getElementById('lan-next-btn').addEventListener('click', function () {
            window.location.reload();
        });
        var sb = document.getElementById('lan-share-btn');
        if (sb) sb.addEventListener('click', function () {
            if (navigator.share) {
                navigator.share({ title: 'Lost at Night', text: 'I just earned ' + earned + ' CP locating a night photo!', url: window.location.origin }).catch(function(){});
            } else {
                navigator.clipboard && navigator.clipboard.writeText(window.location.origin);
            }
        });
    };
})();
