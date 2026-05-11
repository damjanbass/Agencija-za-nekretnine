from dataclasses import dataclass, field


@dataclass
class Plan:
    id:              str
    name:            str
    price_eur:       int
    max_agencies:    int         # -1 = neograničeno
    max_agents:      int         # -1 = neograničeno
    history_months:  int         # -1 = neograničeno
    ai_analysis:     bool
    email_send:      bool
    weekly_report:   bool
    monthly_report:  bool
    daily_report:    bool
    pdf_export:      bool
    custom_branding: bool
    benchmark:       bool
    agent_reports:   bool
    market_sites:    list[str] = field(default_factory=list)

    def allows_ai(self)            -> bool: return self.ai_analysis
    def allows_email(self)         -> bool: return self.email_send
    def allows_monthly(self)       -> bool: return self.monthly_report
    def allows_daily(self)         -> bool: return self.daily_report
    def allows_pdf(self)           -> bool: return self.pdf_export
    def allows_branding(self)      -> bool: return self.custom_branding
    def allows_market(self)        -> bool: return len(self.market_sites) > 0
    def allows_benchmark(self)     -> bool: return self.benchmark
    def allows_agent_reports(self) -> bool: return self.agent_reports

    def agent_limit_ok(self, count: int) -> bool:
        return self.max_agents == -1 or count <= self.max_agents

    def agency_limit_ok(self, count: int) -> bool:
        return self.max_agencies == -1 or count <= self.max_agencies


PLANS: dict[str, Plan] = {
    "basic": Plan(
        id="basic", name="Basic", price_eur=69,
        max_agencies=1, max_agents=5, history_months=3,
        ai_analysis=True, email_send=True,
        weekly_report=True, monthly_report=False, daily_report=False,
        pdf_export=False, custom_branding=False,
        benchmark=False, agent_reports=True,
        market_sites=["Halo oglasi"],
    ),
    "pro": Plan(
        id="pro", name="Pro", price_eur=49,
        max_agencies=3, max_agents=15, history_months=12,
        ai_analysis=True, email_send=True,
        weekly_report=True, monthly_report=True, daily_report=False,
        pdf_export=True, custom_branding=False,
        benchmark=True, agent_reports=True,
        market_sites=["Halo oglasi", "4zida", "Nekretnine.rs"],
    ),
    "premium": Plan(
        id="premium", name="Premium", price_eur=199,
        max_agencies=-1, max_agents=-1, history_months=-1,
        ai_analysis=True, email_send=True,
        weekly_report=True, monthly_report=True, daily_report=True,
        pdf_export=True, custom_branding=True,
        benchmark=True, agent_reports=True,
        market_sites=["Halo oglasi", "4zida", "Nekretnine.rs", "CityExpert"],
    ),
}


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id, PLANS["basic"])
