# Publish the local Wayfinder ledger to GitHub

Status: blocked
Type: task (HITL)
Blocked by: `gh auth status` still reports invalid saved credentials

## Question

How can the shared Wayfinder map and its tickets be published to the configured GitHub issue tracker?

## Work required

The user ran the refresh command, but the subsequent `gh auth status` check still reported the saved token as invalid. Once authentication is valid, publish this map as a `wayfinder:map` issue, publish each ticket as a child issue with its `wayfinder:<type>` label, add dependency edges, and record issue links in the local ledger. Until then, continue project work in this local ledger and do not attempt GitHub writes.

