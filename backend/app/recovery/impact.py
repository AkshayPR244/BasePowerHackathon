"""Trace known disruptions; never infer a unique cause from a tight resource."""

from app.contracts.models import CascadeStep, ImpactAnalysis
from app.contracts.visits import all_jobs
from app.planning.edits import apply_edits, appointment_windows


def analyze(base, edits, original, no_action):
    edited = apply_edits(base, edits).scenario
    before = {(c.crew_id, c.date): c.available_min for c in base.crew_days}
    after = {(c.crew_id, c.date): c.available_min for c in edited.crew_days}
    lost = sum(max(0, n - after.get(slot, 0)) for slot, n in before.items())
    sites = {s.site_id: s for s in edited.sites}
    windows = appointment_windows(edits)
    direct = set()
    for a in original.assignments:
        jid = a.job_id or a.site_id
        slot = (a.crew_id, a.date)
        win = windows.get(jid)
        if (
            after.get(slot, 0) < before.get(slot, 0)
            or a.date < sites[a.site_id].ready_date
            or (win and (a.date < win[0] or (win[1] and a.date > win[1])))
        ):
            direct.add(jid)
    # For inventory disruptions identify changed final bookings, not every home of that type.
    at = {(a.job_id or a.site_id): (a.crew_id, a.date) for a in no_action.assignments}
    if any(e.kind == "delay_inventory" for e in edits):
        direct.update(
            a.job_id or a.site_id
            for a in original.assignments
            if a.visit_type != "install" and at.get(a.job_id or a.site_id) != (a.crew_id, a.date)
        )
    jobs = all_jobs(base)
    homes = {jobs[j].site_id for j in direct if j in jobs and not jobs[j].final}
    pushed = {j.job_id for j in jobs.values() if j.final and j.site_id in homes}
    ontime = {
        a.site_id for a in no_action.assignments if a.visit_type != "install" and not a.days_late
    }
    threatened = sorted(
        j.job_id
        for j in jobs.values()
        if j.final and j.site_id not in ontime and (j.job_id in direct or j.job_id in pushed)
    )
    return ImpactAnalysis(
        headline=f"{len(direct)} visits affected; {lost} capacity minutes lost; "
        f"{len(threatened)} commitments at risk under no action.",
        affected_job_ids=sorted(direct),
        lost_capacity_min=lost,
        deadlines_at_risk=len(threatened),
        cascade=[
            CascadeStep(
                kind="disruption", label=f"{len(edits)} known operational changes", job_ids=[]
            ),
            CascadeStep(
                kind="direct",
                label="Visits using changed resources or availability",
                job_ids=sorted(direct),
            ),
            CascadeStep(
                kind="pushed", label="Dependent battery days to review", job_ids=sorted(pushed)
            ),
            CascadeStep(
                kind="commitment", label="Commitments missed under no action", job_ids=threatened
            ),
        ],
    )
