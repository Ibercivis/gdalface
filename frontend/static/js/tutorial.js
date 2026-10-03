/* Lost At Night — first-time / anonymous tutorial.
   Driver.js v1 (loaded from CDN in gettask.html) */
(function () {
    'use strict';

    var STORAGE_KEY = 'gdalface_tutorial_seen_v2';

    function getCookie(name) {
        var v = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var c = cookies[i].trim();
                if (c.substring(0, name.length + 1) === (name + '=')) {
                    v = decodeURIComponent(c.substring(name.length + 1));
                    break;
                }
            }
        }
        return v;
    }

    function logEvent(event, step) {
        try {
            var body = { event: event };
            if (typeof step === 'number') body.step = step;
            fetch('/api/v1/tutorial-event/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || ''
                },
                body: JSON.stringify(body),
                keepalive: true
            }).catch(function () { /* best-effort */ });
        } catch (e) { /* best-effort */ }
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function videoLink(opts, variant) {
        if (!opts.videoUrl) return '';
        var href = escapeHtml(opts.videoUrl);
        if (variant === 'intro') {
            return '<p style="margin:10px 0 0;font-size:12px;color:var(--ink-2);">'
                + '<em>' + escapeHtml(opts.t.videoIntro) + '</em> '
                + '<a href="' + href + '" target="_blank" rel="noopener" '
                + 'style="color:var(--accent);text-decoration:none;font-weight:500;'
                + 'border-bottom:1px dashed oklch(0.95 0.13 113 / 0.5);">'
                + escapeHtml(opts.t.videoCta) + ' ▶</a></p>';
        }
        return '<p style="margin:14px 0 0;">'
            + '<a href="' + href + '" target="_blank" rel="noopener" '
            + 'style="display:inline-flex;align-items:center;gap:6px;'
            + 'padding:7px 14px;background:var(--accent);color:var(--accent-ink);'
            + 'text-decoration:none;border-radius:8px;font-weight:600;font-size:12px;">'
            + '▶ ' + escapeHtml(opts.t.videoCta) + '</a>'
            + '<br><small style="color:var(--ink-3);font-size:11px;">'
            + escapeHtml(opts.t.videoOutro) + '</small></p>';
    }

    function buildSteps(opts) {
        var anonNotice = opts.isAnonymous
            ? '<p class="mt-2 mb-0"><em>' + opts.t.anonCta + '</em></p>'
            : '';
        return [
            {
                popover: {
                    title: opts.t.s1Title,
                    description: opts.t.s1Body + anonNotice + videoLink(opts, 'intro'),
                    side: 'over', align: 'center'
                }
            },
            {
                element: '#map',
                popover: {
                    title: opts.t.s2Title,
                    description: opts.t.s2Body,
                    side: 'left', align: 'center'
                }
            },
            {
                element: '#column-photo',
                popover: {
                    title: opts.t.s3Title,
                    description: opts.t.s3Body,
                    side: 'over', align: 'center'
                }
            },
            {
                element: '#canvas-sliders',
                popover: {
                    title: opts.t.s4Title,
                    description: opts.t.s4Body,
                    side: 'over', align: 'center'
                }
            },
            {
                element: '#column-photo',
                popover: {
                    title: opts.t.s5Title,
                    description: opts.t.s5Body,
                    side: 'over', align: 'center'
                }
            },
            {
                element: '#map',
                popover: {
                    title: opts.t.s6Title,
                    description: opts.t.s6Body,
                    side: 'left', align: 'center'
                }
            },
            {
                element: '#Submit',
                popover: {
                    title: opts.t.s7Title,
                    description: opts.t.s7Body + anonNotice + videoLink(opts, 'outro'),
                    side: 'left', align: 'center'
                }
            }
        ];
    }

    function startTour(opts) {
        if (typeof window.driver === 'undefined' || typeof window.driver.js === 'undefined') {
            console.warn('[tutorial] Driver.js not loaded');
            return;
        }
        var steps = buildSteps(opts);
        var totalSteps = steps.length;
        var completedFlag = false;
        var lastIndex = 0;

        function setTutorialActive(on) {
            document.body.classList.toggle('tutorial-active', !!on);
            if (window.LAN) window.LAN.tutorialActive = !!on;
        }

        var d = window.driver.js.driver({
            showProgress: true,
            allowClose: true,
            nextBtnText: opts.t.next,
            prevBtnText: opts.t.prev,
            doneBtnText: opts.t.done,
            steps: steps,
            onHighlightStarted: function (el, step, ctx) {
                lastIndex = (ctx && ctx.state && typeof ctx.state.activeIndex === 'number')
                    ? ctx.state.activeIndex : lastIndex;
                logEvent('step', lastIndex + 1);
            },
            onDestroyed: function (el, step, ctx) {
                setTutorialActive(false);
                if (completedFlag) return;
                // driver.js has already reset ctx.state by the time onDestroyed
                // fires on "Done", so activeIndex is undefined there and every
                // finish used to be logged as "dismissed" at step 1. Use the
                // last highlighted index instead.
                var idx = (ctx && ctx.state && typeof ctx.state.activeIndex === 'number')
                    ? ctx.state.activeIndex : lastIndex;
                if (idx >= totalSteps - 1) {
                    completedFlag = true;
                    logEvent('completed');
                } else {
                    logEvent('dismissed', idx + 1);
                }
                try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) { }
            }
        });

        setTutorialActive(true);
        logEvent('started');
        d.drive();
    }

    function shouldAutoStart(showFromServer) {
        if (!showFromServer) return false;
        try {
            if (localStorage.getItem(STORAGE_KEY) === '1') return false;
        } catch (e) { /* localStorage may be disabled */ }
        return true;
    }

    function init() {
        var root = document.getElementById('tutorial-root');
        if (!root) return;

        var opts = {
            isAnonymous: root.dataset.anonymous === '1',
            showFromServer: root.dataset.showTutorial === '1',
            videoUrl: root.dataset.videoUrl || '',
            t: {
                s1Title: root.dataset.s1Title,
                s1Body: root.dataset.s1Body,
                s2Title: root.dataset.s2Title,
                s2Body: root.dataset.s2Body,
                s3Title: root.dataset.s3Title,
                s3Body: root.dataset.s3Body,
                s4Title: root.dataset.s4Title,
                s4Body: root.dataset.s4Body,
                s5Title: root.dataset.s5Title,
                s5Body: root.dataset.s5Body,
                s6Title: root.dataset.s6Title,
                s6Body: root.dataset.s6Body,
                s7Title: root.dataset.s7Title,
                s7Body: root.dataset.s7Body,
                anonCta: root.dataset.anonCta,
                videoIntro: root.dataset.videoIntro,
                videoOutro: root.dataset.videoOutro,
                videoCta: root.dataset.videoCta,
                next: root.dataset.next,
                prev: root.dataset.prev,
                done: root.dataset.done
            }
        };

        // Manual trigger (the "?" tour icon in the topbar of gettask).
        var trigger = document.getElementById('tutorial-trigger');
        if (trigger) {
            trigger.addEventListener('click', function (e) {
                e.preventDefault();
                startTour(opts);
            });
        }

        // Auto-start: wait for the task-info modal to be dismissed so the
        // user sees the photo/crew first, then drive the tour.
        if (!shouldAutoStart(opts.showFromServer)) return;

        var modalEl = document.getElementById('taskInfoModal');
        if (modalEl) {
            modalEl.addEventListener('hidden.bs.modal', function onHidden() {
                modalEl.removeEventListener('hidden.bs.modal', onHidden);
                setTimeout(function () { startTour(opts); }, 300);
            });
        } else {
            setTimeout(function () { startTour(opts); }, 600);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
