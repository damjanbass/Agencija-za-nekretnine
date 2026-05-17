// ============================================================
// PlanGate — centralni helper za plan-based gating u web UI-u.
//
// Korišćenje:
//   await PlanGate.load(sb, agencyId);
//   if (!PlanGate.requireOrUpgrade('pdf_export', msgEl)) return;
//   const { ok, max, current } = PlanGate.limit('agents');
//
// Server (Postgres) je istina — JS samo daje brzi feedback i CTA.
// ============================================================

(function (global) {
  const NEXT_TIER = { free: 'Basic', basic: 'Pro', pro: 'Premium', premium: 'Premium' };

  // Lokalizovana imena za poruke o limitima
  const RESOURCE_LABEL = {
    agents:          'agenata',
    listings:        'oglasa',
    custom_branding: 'custom branding',
  };

  // Pretty imena za feature-e (za upgrade CTA)
  const FEATURE_LABEL = {
    ai_analysis:     'AI analiza',
    email_send:      'slanje mejlova',
    monthly_report:  'mesečni izveštaj',
    daily_report:    'dnevni izveštaj',
    pdf_export:      'PDF export',
    custom_branding: 'custom branding',
    benchmark:       'benchmark',
    agent_reports:   'agent izveštaji',
  };

  const state = {
    sb: null,
    agencyId: null,
    plan: null,            // ceo red iz plans tabele
    rawPlanId: null,       // šta korisnik plaća (ne effective)
    status: null,          // trial | active | past_due | canceled | expired
    trialEndsAt: null,
    currentPeriodEnd: null,
    agentsCount: 0,
    listingsCount: 0,
  };

  async function load(sb, agencyId) {
    state.sb = sb;
    state.agencyId = agencyId;

    const { data: agency, error } = await sb
      .from('agencies')
      .select(`
        plan_id, subscription_status, trial_ends_at, current_period_end,
        plans (
          id, name, max_agents, max_listings, history_months,
          ai_analysis, email_send, weekly_report, monthly_report, daily_report,
          pdf_export, custom_branding, benchmark
        )
      `)
      .eq('id', agencyId)
      .single();

    if (error || !agency) {
      console.error('[PlanGate] load failed', error);
      state.plan = freeFallback();
      return state;
    }

    state.rawPlanId        = agency.plan_id;
    state.status           = agency.subscription_status || 'trial';
    state.trialEndsAt      = agency.trial_ends_at ? new Date(agency.trial_ends_at) : null;
    state.currentPeriodEnd = agency.current_period_end ? new Date(agency.current_period_end) : null;

    // Effective plan: ako pretplata nije active/trial, vrati free.
    const effective = (state.status === 'trial' || state.status === 'active')
      ? agency.plans
      : null;
    state.plan = effective || freeFallback();

    await refreshCounts();
    return state;
  }

  async function refreshCounts() {
    if (!state.sb || !state.agencyId) return;
    const [{ count: ac }, { count: lc }] = await Promise.all([
      state.sb.from('agents').select('id', { count: 'exact', head: true })
        .eq('agency_id', state.agencyId).eq('active', true),
      state.sb.from('listings').select('id', { count: 'exact', head: true })
        .eq('agency_id', state.agencyId).eq('active', true),
    ]);
    state.agentsCount   = ac || 0;
    state.listingsCount = lc || 0;
  }

  function freeFallback() {
    return {
      id: 'free', name: 'Free',
      max_agents: 3, max_listings: 5, history_months: 1,
      ai_analysis: true, email_send: true,
      weekly_report: true, monthly_report: false, daily_report: false,
      pdf_export: false, custom_branding: false, benchmark: false,
    };
  }

  function allows(feature) {
    if (!state.plan) return false;
    return !!state.plan[feature];
  }

  function limit(resource) {
    const map = { agents: 'max_agents', listings: 'max_listings' };
    const key = map[resource];
    if (!key || !state.plan) return { ok: false, max: 0, current: 0 };
    const max = state.plan[key];
    const current = resource === 'agents' ? state.agentsCount : state.listingsCount;
    const ok = max === -1 || current < max;
    return { ok, max, current };
  }

  function planName()      { return state.plan?.name || 'Free'; }
  function status()        { return state.status; }
  function trialDaysLeft() {
    if (!state.trialEndsAt) return null;
    const ms = state.trialEndsAt.getTime() - Date.now();
    return Math.max(0, Math.ceil(ms / 86400000));
  }

  function upgradeCta() {
    const next = NEXT_TIER[state.plan?.id || 'free'] || 'Premium';
    return `<a href="pricing.html" style="color:#2563eb;text-decoration:underline;">pređite na ${next}</a>`;
  }

  function requireOrUpgrade(feature, msgEl) {
    if (allows(feature)) return true;
    const label = FEATURE_LABEL[feature] || feature;
    const html = `${planName()} plan ne uključuje ${label}. Za pristup, ${upgradeCta()}.`;
    if (msgEl) writeMsg(msgEl, html, true);
    return false;
  }

  function requireLimitOrUpgrade(resource, msgEl) {
    const { ok, max } = limit(resource);
    if (ok) return true;
    const label = RESOURCE_LABEL[resource] || resource;
    const html = `${planName()} plan dozvoljava do ${max} ${label}. Za više, ${upgradeCta()}.`;
    if (msgEl) writeMsg(msgEl, html, true);
    return false;
  }

  // Parsira server-side greške oblika: LIMIT_EXCEEDED:<resource>:<max>
  function handleDbError(err, msgEl) {
    const msg = err?.message || String(err || '');
    const m = msg.match(/LIMIT_EXCEEDED:([a-z_]+):(-?\d+)/i);
    if (!m) {
      if (msgEl) writeMsg(msgEl, `Greška: ${msg}`, true);
      return false;
    }
    const resource = m[1];
    const max      = parseInt(m[2], 10);
    const label    = RESOURCE_LABEL[resource] || resource;
    const html = resource === 'custom_branding'
      ? `${planName()} plan ne uključuje ${label}. Za pristup, ${upgradeCta()}.`
      : `${planName()} plan dozvoljava do ${max} ${label}. Za više, ${upgradeCta()}.`;
    if (msgEl) writeMsg(msgEl, html, true);
    return true;
  }

  function writeMsg(el, html, isError) {
    if (typeof el === 'string') el = document.getElementById(el);
    if (!el) return;
    el.innerHTML = `<div class="msg ${isError ? 'error' : 'success'}">${html}</div>`;
  }

  function statusBannerHtml() {
    if (state.status === 'trial') {
      const d = trialDaysLeft();
      if (d === null) return '';
      const tone = d <= 3 ? 'warn' : 'info';
      return `<div class="plan-banner ${tone}">Trial — još ${d} ${d === 1 ? 'dan' : 'dana'} do isteka. <a href="pricing.html">Izaberite plan</a></div>`;
    }
    if (state.status === 'past_due') {
      return `<div class="plan-banner warn">Plaćanje nije prošlo. <a href="checkout.html">Ažurirajte podatke</a> da nastavite sa ${state.rawPlanId} planom.</div>`;
    }
    if (state.status === 'canceled' || state.status === 'expired') {
      return `<div class="plan-banner warn">Pretplata nije aktivna — koristite Free plan. <a href="pricing.html">Aktivirajte plan</a></div>`;
    }
    return '';
  }

  global.PlanGate = {
    load, refreshCounts,
    allows, limit, planName, status, trialDaysLeft,
    requireOrUpgrade, requireLimitOrUpgrade, handleDbError,
    statusBannerHtml,
    get state() { return state; },
  };
})(window);
