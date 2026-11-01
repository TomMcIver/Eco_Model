# Local Wayfinder ledger

This directory temporarily mirrors the Wayfinder issue map because GitHub CLI authentication is currently invalid. The configured tracker remains GitHub. Each ticket is a Markdown file under `tickets/`; its `Status` and `Blocked by` fields represent state and dependencies until the issues can be published.

List open tickets with:

```powershell
rg -l '^Status: (open|blocked)' .scratch/new-zealand-economic-digital-twin/tickets
```

When GitHub access is restored, publish the map and tickets to the configured repository, create parent-child links and dependency edges, then add issue URLs to the local records.

