# Memory Baseline — 2026-04-20

Snapshot taken after restart at ~20:10 UTC on the Frankfurt DO droplet (1 GB RAM).

## System Overview

| Metric | Value |
|---|---|
| Total RAM | 961 MB |
| Used | 614 MB (64%) |
| Free | 73 MB (7.6%) |
| Buff/cache | 426 MB |
| Available | 346 MB (36%) |
| Swap used | 151 MB / 2 GB |

## Process Breakdown

| Process | PID | RSS | % RAM | Notes |
|---|---|---|---|---|
| `whaagent serve` (Python) | 152697 | 176 MB | 17.9% | FastAPI + LangGraph + all agents |
| Chromium (main) | 152744 | 137 MB | 13.9% | Playwright, started by Crawl4AI warmup |
| Chromium (network svc) | 152778 | 111 MB | 11.2% | Playwright subprocess |
| Chromium (zygote ×2) | 152753/54 | 133 MB | 13.5% | Playwright subprocesses |
| Playwright Node driver | 152731 | 64 MB | 6.4% | Node.js wrapper |
| Chromium (storage + GPU) | 152792/75 | 98 MB | ~10% | Playwright subprocesses |
| `whaagent-toolbox` (Python) | 121889 | 42 MB | 4.3% | MCP toolbox (Docker-free, long-running) |
| `whaagent-gateway` (Go) | 152811 | 25 MB | 2.5% | WhatsApp Go gateway |

## App Totals

| Group | RSS |
|---|---|
| Playwright + Chromium | ~543 MB |
| Python API (`whaagent serve`) | ~176 MB |
| Toolbox (Python MCP) | ~42 MB |
| Gateway (Go) | ~25 MB |
| **All apps** | **~786 MB** |

## Key Finding

Playwright/Chromium accounts for **~69% of all app memory** (~543 MB) from a persistent browser
instance started at server warmup for `DeepScrapeTool`. The browser stays resident permanently
even when `deep_scrape` is not in use.

## Runtime Validation (same snapshot)

The Bortoleto/Audi WhatsApp query was the first message after the restart and completed successfully:

- Path: `tool_use → web_search → direct-tool` (fast path, no sub-agent)
- Total latency: **15.2s** (router=5.5s, tool_exec=2.3s, llm_format=7.4s)
- Response: HTTP 200, tenant `primary`

## Improvement Targets

| Priority | Target | Expected saving |
|---|---|---|
| 1 | Playwright: lazy-init + ephemeral browser (PLAYWRIGHT_PERSISTENT=false) | ~540 MB |
| 2 | Python API: profile import-time overhead, lazy-load heavy deps | TBD |
| 3 | Toolbox: already minimal, no action needed | — |
| 4 | Gateway: already minimal (Go), no action needed | — |

## Next Snapshot

Take another snapshot after deploying `PLAYWRIGHT_PERSISTENT=false` to quantify the saving.
Use the same method: `ps aux --sort=-%mem | head -20` + `free -h` via SSH.
