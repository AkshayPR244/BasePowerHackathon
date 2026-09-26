# Requests from Lane R

- Recovery service is implemented on lane/R-engine; integration pending checks/review.
- Lowest modeled cost may be no_action: rank across all four cards, not only action options.
- Check option.status before showing economics/approval: infeasible and timeout options are not cost-ranked. Their zero-dollar placeholder is labeled Not evaluated, not a free intervention.
- EvaluateRequest now accepts optional economics_overrides; forward edited assumptions to both options and evaluate.
- Approval accepts unchanged server-issued options at the evaluated revision; changing inputs requires re-evaluation. Option expiry or tampering returns422.
- ApproveResult adds effective_scenario to preserve temporary crew availability/bookings for export. HTTP approval chaining is deferred; do not feed just the approved bookings back to an unchanged roster.
- Appointment windows remain in result.edits and must be retained if future approval chaining is added.
