"""
End-to-end verifikacija plan-limit infrastrukture.

Pokretanje:
    python -X utf8 -m scripts.verify_limits

Šta proverava:
  1. effective_plan_id() RPC postoji i radi
  2. enforce_agent_limit trigger blokira preko max_agents
  3. enforce_listing_limit trigger blokira preko max_listings
  4. enforce_branding trigger blokira logo_url upis kada custom_branding=false
  5. expire_stale_trials() spušta backdated trial na 'expired'

Test koristi PRVU agenciju u bazi i pravi PRIVREMENE redove sa imenom
"__test_limit_<ts>" — sve se briše na kraju (uključujući kod neuspeha).
"""
import sys
import time
import uuid

from data.supabase_client import get_client

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TAG = f"__test_limit_{int(time.time())}"
PASS = "[✓]"
FAIL = "[✗]"
results = []


def check(name: str, ok: bool, detail: str = ""):
    mark = PASS if ok else FAIL
    print(f"  {mark} {name}{(' — ' + detail) if detail else ''}")
    results.append((name, ok))


def main():
    sb = get_client()

    # ── 0. Probna agencija ──────────────────────────────────────
    agencies = (
        sb.table("agencies")
        .select("id, name, plan_id, subscription_status, logo_url, plans(max_agents, max_listings, custom_branding)")
        .limit(5)
        .execute()
        .data
    )
    if not agencies:
        print(f"{FAIL} Nema agencija u bazi.")
        return 1

    ag = agencies[0]
    agency_id = ag["id"]
    plan = ag.get("plans") or {}
    print(f"[i] Test agencija: {ag['name']} ({agency_id})")
    print(f"    plan_id={ag['plan_id']}  status={ag['subscription_status']}  "
          f"max_agents={plan.get('max_agents')}  max_listings={plan.get('max_listings')}  "
          f"branding={plan.get('custom_branding')}")
    original_logo = ag.get("logo_url")

    # ── 1. effective_plan_id RPC ────────────────────────────────
    try:
        r = sb.rpc("effective_plan_id", {"p_agency_id": agency_id}).execute()
        check("effective_plan_id() RPC vraća string", isinstance(r.data, str), f"vratio: {r.data}")
    except Exception as e:
        check("effective_plan_id() RPC vraća string", False, str(e))

    # ── 2. enforce_agent_limit ──────────────────────────────────
    created_agent_ids: list[str] = []
    max_agents = plan.get("max_agents") or 0
    try:
        if max_agents == -1:
            check("enforce_agent_limit: blokira preko limita", True, "premium plan — neograničeno, preskočeno")
        else:
            # Saznaj koliko ih trenutno ima
            cnt = (
                sb.table("agents")
                .select("id", count="exact")
                .eq("agency_id", agency_id)
                .eq("active", True)
                .execute()
            )
            current = cnt.count or 0
            to_create = max(0, max_agents - current)
            for i in range(to_create):
                ins = sb.table("agents").insert({
                    "agency_id": agency_id, "name": f"{TAG}_agent_{i}"
                }).execute()
                created_agent_ids.append(ins.data[0]["id"])

            # Sada smo tačno na limitu — sledeći mora pući
            try:
                ins = sb.table("agents").insert({
                    "agency_id": agency_id, "name": f"{TAG}_overflow"
                }).execute()
                # Ako nije puklo — neuspeh
                created_agent_ids.append(ins.data[0]["id"])
                check("enforce_agent_limit: blokira preko limita", False,
                      f"insert je prošao — count je sada {current + to_create + 1}")
            except Exception as e:
                msg = str(e)
                ok = "LIMIT_EXCEEDED:agents" in msg
                check("enforce_agent_limit: blokira preko limita", ok,
                      f"err: {msg[:120]}")
    finally:
        for aid in created_agent_ids:
            try:
                sb.table("agents").delete().eq("id", aid).execute()
            except Exception:
                pass

    # ── 3. enforce_listing_limit ────────────────────────────────
    created_listing_ids: list[str] = []
    max_listings = plan.get("max_listings") or 0
    try:
        if max_listings == -1:
            check("enforce_listing_limit: blokira preko limita", True, "neograničeno, preskočeno")
        else:
            cnt = (
                sb.table("listings")
                .select("id", count="exact")
                .eq("agency_id", agency_id)
                .eq("active", True)
                .execute()
            )
            current = cnt.count or 0
            to_create = max(0, max_listings - current)
            base = {
                "agency_id": agency_id,
                "type": "stan", "transaction": "prodaja",
                "title": f"{TAG}_listing", "price": 1, "area_m2": 1,
                "city": "Test",
            }
            for i in range(to_create):
                ins = sb.table("listings").insert({**base, "ref_number": f"{TAG}-{i}"}).execute()
                created_listing_ids.append(ins.data[0]["id"])

            try:
                ins = sb.table("listings").insert({**base, "ref_number": f"{TAG}-overflow"}).execute()
                created_listing_ids.append(ins.data[0]["id"])
                check("enforce_listing_limit: blokira preko limita", False,
                      f"insert prošao na count={current + to_create + 1}")
            except Exception as e:
                msg = str(e)
                ok = "LIMIT_EXCEEDED:listings" in msg
                check("enforce_listing_limit: blokira preko limita", ok, f"err: {msg[:120]}")
    finally:
        for lid in created_listing_ids:
            try:
                sb.table("listings").delete().eq("id", lid).execute()
            except Exception:
                pass

    # ── 4. enforce_branding ─────────────────────────────────────
    try:
        if plan.get("custom_branding"):
            check("enforce_branding: blokira logo_url na ne-premium", True,
                  "ova agencija JE premium — preskočeno")
        else:
            try:
                sb.table("agencies").update({
                    "logo_url": "https://example.com/test.png"
                }).eq("id", agency_id).execute()
                # Ako je prošlo — vraćamo i prijavljujemo neuspeh
                sb.table("agencies").update({
                    "logo_url": original_logo
                }).eq("id", agency_id).execute()
                check("enforce_branding: blokira logo_url na ne-premium", False,
                      "update je prošao")
            except Exception as e:
                msg = str(e)
                ok = "LIMIT_EXCEEDED:custom_branding" in msg
                check("enforce_branding: blokira logo_url na ne-premium", ok,
                      f"err: {msg[:120]}")
    except Exception as e:
        check("enforce_branding: blokira logo_url na ne-premium", False, str(e))

    # ── 5. expire_stale_trials ──────────────────────────────────
    # Pravimo privremenu agenciju u trial-u sa trial_ends_at u prošlosti
    test_email = f"{TAG}@verify.local"
    temp_id = None
    try:
        ins = sb.table("agencies").insert({
            "name": f"{TAG}_agency",
            "email": test_email,
            "plan_id": "pro",
            "revenue_goal": 1000,
            "active": True,
            "subscription_status": "trial",
            "trial_ends_at": "2020-01-01T00:00:00Z",
        }).execute()
        temp_id = ins.data[0]["id"]

        before = (
            sb.table("agencies").select("subscription_status")
            .eq("id", temp_id).single().execute().data["subscription_status"]
        )

        sb.rpc("expire_stale_trials").execute()

        after = (
            sb.table("agencies").select("subscription_status")
            .eq("id", temp_id).single().execute().data["subscription_status"]
        )
        check("expire_stale_trials: backdated trial → expired",
              before == "trial" and after == "expired",
              f"{before} → {after}")

        # effective_plan_id sada mora vratiti 'free'
        eff = sb.rpc("effective_plan_id", {"p_agency_id": temp_id}).execute().data
        check("effective_plan_id: expired → 'free'", eff == "free", f"vratio: {eff}")

    except Exception as e:
        check("expire_stale_trials: backdated trial → expired", False, str(e))
    finally:
        if temp_id:
            try:
                sb.table("agencies").delete().eq("id", temp_id).execute()
            except Exception:
                pass

    # ── Rezime ──────────────────────────────────────────────────
    print()
    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    print(f"[=] {passed}/{total} provera prošlo.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
