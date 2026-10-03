/* Lost At Night — modals shown after Join / Leave a challenge.
   Exposes:
     window.LAN_showJoinedModal(payload)   ← join response body
     window.LAN_showLeftModal(payload)     ← leave response body
   Both render a self-contained overlay (independent of any Bootstrap
   modal so they don't collide with #taskInfoModal etc.). When the user
   dismisses the modal we reload the host page so the join/leave state
   propagates to the rest of the UI. */
(function () {
    'use strict';

    function injectStyles() {
        if (document.getElementById('lan-cj-css')) return;
        var s = document.createElement('style');
        s.id = 'lan-cj-css';
        s.textContent = [
            '#lan-cj-overlay{',
            '  position:fixed;inset:0;z-index:1090;',
            '  background:oklch(0.05 0.02 280 / 0.78);',
            '  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);',
            '  display:flex;align-items:center;justify-content:center;',
            '  font-family:var(--font-ui,system-ui,sans-serif);',
            '  animation:lan-cj-fade 200ms ease;padding:16px;overflow-y:auto;',
            '}',
            '@keyframes lan-cj-fade{from{opacity:0}to{opacity:1}}',
            '.lan-cj-card{',
            '  width:520px;max-width:100%;',
            '  background:var(--bg-1);border:1px solid var(--line);',
            '  border-radius:14px;color:var(--ink-1);',
            '  box-shadow:0 18px 60px oklch(0 0 0 / 0.55);',
            '  overflow:hidden;margin:auto;',
            '  position:relative;',
            '}',
            '.lan-cj-close{',
            '  position:absolute;top:12px;right:12px;z-index:5;',
            '  width:28px;height:28px;border-radius:50%;',
            '  background:var(--bg-2)!important;border:1px solid var(--line)!important;',
            '  color:var(--ink-2)!important;cursor:pointer!important;',
            '  display:inline-flex;align-items:center;justify-content:center;',
            '  padding:0!important;font-weight:400!important;',
            '}',
            '.lan-cj-close:hover{color:var(--ink-0)!important;background:var(--bg-3)!important;transform:none!important;box-shadow:none!important;}',
            '.lan-cj-top{padding:32px 32px 22px;text-align:center;position:relative;}',
            '.lan-cj-top::before{',
            '  content:"";position:absolute;top:-80px;left:50%;transform:translateX(-50%);',
            '  width:380px;height:200px;',
            '  background:radial-gradient(ellipse,oklch(0.95 0.13 113 / 0.20),transparent 70%);',
            '  pointer-events:none;',
            '}',
            '.lan-cj-pill{',
            '  display:inline-flex;align-items:center;gap:6px;',
            '  padding:5px 12px;border-radius:999px;',
            '  background:var(--accent);color:var(--accent-ink);',
            '  font-size:12px;font-weight:600;position:relative;z-index:1;',
            '}',
            '.lan-cj-pill.muted{background:var(--bg-3);color:var(--ink-1);border:1px solid var(--line);}',
            '.lan-cj-title{',
            '  font-size:26px;font-weight:700;color:var(--ink-0);',
            '  letter-spacing:-0.4px;line-height:1.15;',
            '  margin:14px 0 6px;position:relative;z-index:1;',
            '}',
            '.lan-cj-name{',
            '  font-size:15px;color:var(--ink-1);font-weight:500;',
            '  margin:0 0 14px;position:relative;z-index:1;',
            '}',
            '.lan-cj-name b{color:var(--ink-0);}',
            '.lan-cj-targets{',
            '  display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;',
            '  padding:14px 24px;',
            '  border-top:1px solid var(--line);border-bottom:1px solid var(--line);',
            '}',
            '.lan-cj-target{text-align:center;padding:6px 4px;}',
            '.lan-cj-target .lab{font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);}',
            '.lan-cj-target .val{font-family:var(--font-mono);font-size:18px;font-weight:600;color:var(--ink-0);margin-top:4px;}',
            '.lan-cj-target.bronze .val{color:#cd7f32;}',
            '.lan-cj-target.silver .val{color:#d8d8d8;}',
            '.lan-cj-target.gold   .val{color:var(--accent);}',
            '.lan-cj-meta{',
            '  display:flex;justify-content:center;gap:18px;flex-wrap:wrap;',
            '  padding:14px 24px;border-bottom:1px solid var(--line);',
            '  font-size:12.5px;color:var(--ink-1);',
            '}',
            '.lan-cj-meta .chip{',
            '  display:inline-flex;align-items:center;gap:6px;',
            '  background:var(--bg-2);border:1px solid var(--line-soft);',
            '  border-radius:999px;padding:5px 12px;',
            '}',
            '.lan-cj-meta .chip b{color:var(--ink-0);font-weight:600;}',
            '.lan-cj-meta .chip svg{color:var(--accent);}',
            '#lan-cj-map{height:160px;border-bottom:1px solid var(--line);background:var(--bg-2);}',
            '.lan-cj-actions{',
            '  display:flex;gap:10px;padding:18px 24px;justify-content:flex-end;flex-wrap:wrap;',
            '}',
            '@media (max-width:520px){',
            '  .lan-cj-actions{justify-content:stretch;}',
            '  .lan-cj-actions .ds-btn{flex:1;}',
            '  .lan-cj-targets{grid-template-columns:1fr;}',
            '}',
        ].join('');
        document.head.appendChild(s);
    }

    function fmtInt(n) { return (n || 0).toLocaleString(); }
    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
        });
    }

    function L_(key, fallback) {
        var T = window.LAN_I18N || {};
        return T[key] || fallback;
    }

    function close() {
        var el = document.getElementById('lan-cj-overlay');
        if (el) el.remove();
    }

    function invalidateChipCache() {
        try { sessionStorage.removeItem('lan_active_challenge_v1'); } catch (e) {}
    }

    function buildOverlay(html) {
        injectStyles();
        var existing = document.getElementById('lan-cj-overlay');
        if (existing) existing.remove();
        var ov = document.createElement('div');
        ov.id = 'lan-cj-overlay';
        ov.innerHTML = '<div class="lan-cj-card" role="dialog" aria-modal="true">'
            + '<button type="button" class="lan-cj-close" id="lan-cj-close" aria-label="Close">'
            + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6l-12 12"/></svg>'
            + '</button>'
            + html
            + '</div>';
        document.body.appendChild(ov);
        document.getElementById('lan-cj-close').addEventListener('click', function () {
            close();
            // Reload so the host page picks up the new enrollment state.
            try { window.location.reload(); } catch (e) {}
        });
        return ov;
    }

    // ── Joined modal ─────────────────────────────────────────────────
    window.LAN_showJoinedModal = function (payload) {
        invalidateChipCache();
        var ch = (payload && payload.challenge) || {};
        var name = ch.name || '';
        var nameLabel = L_('joined_chal_name', 'You’re in <b>{name}</b>');
        nameLabel = nameLabel.replace('{name}', '<b>' + escapeHtml(name) + '</b>');

        var batchInfo = '';
        if (ch.batch_id && ch.batch_name) {
            batchInfo = '<span class="chip">'
                + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>'
                + L_('chip_batch', 'Batch') + ' <b>' + escapeHtml(ch.batch_name) + '</b></span>';
        }
        var bboxInfo = '';
        if (ch.has_bbox) {
            bboxInfo = '<span class="chip">'
                + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 12h16M12 4v16"/></svg>'
                + L_('chip_bbox', 'Region defined') + '</span>';
        }
        var imgInfo = '<span class="chip">'
            + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 14l5-5 4 4 3-3 6 6"/></svg>'
            + '<b>' + fmtInt(ch.cached_image_count) + '</b> '
            + L_('chip_images', 'images') + '</span>';
        var taskInfo = '<span class="chip">'
            + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>'
            + '<b>' + fmtInt(ch.cached_task_count) + '</b> '
            + L_('chip_tasks', 'tasks') + '</span>';

        var replaced = (payload && payload.replaced_other_enrollment)
            ? '<p style="margin:6px 0 0;color:var(--ink-2);font-size:12px;">'
              + L_('joined_replaced', 'Your previous active challenge was automatically left.')
              + '</p>'
            : '';

        var inner = ''
            + '<div class="lan-cj-top">'
            +   '<span class="lan-cj-pill">'
            +     '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>'
            +     L_('joined_pill', 'Joined') + '</span>'
            +   '<h2 class="lan-cj-title">' + L_('joined_title', 'You’re in!') + '</h2>'
            +   '<p class="lan-cj-name">' + nameLabel + '</p>'
            +   replaced
            + '</div>'
            + '<div class="lan-cj-targets">'
            +   '<div class="lan-cj-target bronze"><div class="lab">' + L_('tgt_bronze','Bronze') + '</div><div class="val">' + fmtInt(ch.target_bronze) + '</div></div>'
            +   '<div class="lan-cj-target silver"><div class="lab">' + L_('tgt_silver','Silver') + '</div><div class="val">' + fmtInt(ch.target_silver) + '</div></div>'
            +   '<div class="lan-cj-target gold"  ><div class="lab">' + L_('tgt_gold',  'Gold')   + '</div><div class="val">' + fmtInt(ch.target_gold)   + '</div></div>'
            + '</div>'
            + '<div class="lan-cj-meta">' + imgInfo + taskInfo + batchInfo + bboxInfo + '</div>'
            + '<div class="lan-cj-actions">'
            +   '<a href="/challenges/' + ch.id + '/" class="ds-btn ds-btn--secondary">'
            +     L_('btn_view_challenge', 'View challenge') + '</a>'
            +   '<a href="/gettask" class="ds-btn ds-btn--primary">'
            +     L_('btn_start_now', 'Start contributing') + '</a>'
            + '</div>';
        buildOverlay(inner);
    };

    // ── Left modal ───────────────────────────────────────────────────
    window.LAN_showLeftModal = function (payload) {
        invalidateChipCache();
        var ch = (payload && payload.challenge) || {};
        var kept = (payload && payload.cp_count_kept) || 0;
        var subtitle = L_('left_kept', 'Your <b>{n} CPs</b> are kept; you can rejoin any time.')
            .replace('{n}', fmtInt(kept));

        var inner = ''
            + '<div class="lan-cj-top">'
            +   '<span class="lan-cj-pill muted">'
            +     '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l-6 6 6 6"/><path d="M3 12h18"/></svg>'
            +     L_('left_pill', 'Left') + '</span>'
            +   '<h2 class="lan-cj-title">' + L_('left_title', 'You’ve left the challenge') + '</h2>'
            +   '<p class="lan-cj-name"><b>' + escapeHtml(ch.name || '') + '</b></p>'
            +   '<p style="color:var(--ink-2);font-size:13px;line-height:1.5;margin:0;">' + subtitle + '</p>'
            + '</div>'
            + '<div class="lan-cj-actions">'
            +   '<a href="/" class="ds-btn ds-btn--ghost">'
            +     L_('btn_go_home', 'Go home') + '</a>'
            +   '<a href="/#challenges-section" class="ds-btn ds-btn--primary">'
            +     L_('btn_browse_challenges', 'Browse challenges') + '</a>'
            + '</div>';
        buildOverlay(inner);
    };
})();
