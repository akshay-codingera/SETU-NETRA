# सेतु-नेत्र (Setu-Netra) — Adaptive AI Request Path Decider

An AI Operating System / AI Gateway that sits between millions of users and multiple AI
models — API Gateway + Load Balancer + Intelligent Router + Scheduler, unified.

**Core idea:** understand every incoming request, estimate its requirements, monitor
load, and route it to the cheapest capable model while maintaining quality and latency.

## Problems this solves
1. GPU overload — millions of users share a limited pool of GPUs
2. Cost — large models cost far more per token than small models
3. Latency — bigger models take much longer per token than small models
4. Energy conservation

## Folder structure
Each pipeline stage has its own folder with three subfolders:
- `papers/`   — drop research paper PDFs here
- `datasets/` — drop or link benchmark/dataset files here
- `notes/`    — your own notes, summaries, experiment logs

| # | Stage | Folder |
|---|-------|--------|
| 1 | Input Analyzer | `01_Input_Analyzer/` |
| 2 | Task Classifier | `02_Task_Classifier/` |
| 3 | Complexity Analyzer | `03_Complexity_Analyzer/` |
| 4 | Capability Matcher | `04_Capability_Matcher/` |
| 5 | Cost Estimator | `05_Cost_Estimator/` |
| 6 | Load Analyzer | `06_Load_Analyzer/` |
| 7 | Path Decision Engine (+ Confidence Validation) | `07_Path_Decision_Engine/` |
| 8 | Scheduler | `08_Scheduler/` |
| 9 | Model Serving | `09_Model_Serving/` |
| 10 | Output Validator | `10_Output_Validator/` |
| 11 | Escalating Engine | `11_Escalating_Engine/` |
| 12 | Monitoring System | `12_Monitoring_System/` |

See each folder's own `README.md` for the models/papers/datasets already identified
for that stage, and open gaps still to fill.

## Prototype status
A working v0 prototype now exists in `prototype/` — a runnable Complexity
Classifier + Path Decision Engine that routes prompts to mock EASY/MEDIUM/HARD
model tiers and estimates cost savings vs. an always-frontier-model baseline.
See `prototype/README.md` for what's built, what's mocked, and what's next.
