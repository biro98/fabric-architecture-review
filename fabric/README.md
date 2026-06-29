# Running the Review Inside Microsoft Fabric

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Runs: In-Fabric](https://img.shields.io/badge/runs-In--Fabric-00BCF2.svg)](#-deploy-it-from-inside-fabric-no-workstation-needed)
[![Pattern: single--notebook](https://img.shields.io/badge/pattern-single--notebook-blueviolet.svg)](#-deploy-it-from-inside-fabric-no-workstation-needed)
[![Data: metadata-only](https://img.shields.io/badge/data-metadata--only-success.svg)](../README.md#-data-safety-read-this-first)

Run the **Fabric Architecture Review Accelerator** entirely **from inside a Microsoft Fabric
workspace** — no workstation, no local install. You import **one** setup notebook, run it once,
and it deploys a Lakehouse, four stage notebooks, an orchestration pipeline, and a Direct Lake
governance report for you. Then you trigger the pipeline (on demand or on a schedule) and read a
client-ready `report.md` plus an interactive Power BI report.

This guide complements the [main README](../README.md), which covers the **local (PowerShell)**
workflow, the full collector/role matrix, the rule catalog, and the data-safety contract. Read
that first if you have not yet — everything there applies here too.

> **Data safety:** like every run mode, the in-Fabric pipeline reads **metadata, configuration,
> inventory, and metrics only** — never customer business data. See
> [Data safety](../README.md#-data-safety-read-this-first) in the main README.

---

## 📑 Table of contents

- [Which tenant can each run mode reach?](#-which-tenant-can-each-run-mode-reach)
- [Deploy it from inside Fabric (no workstation needed)](#-deploy-it-from-inside-fabric-no-workstation-needed)
- [Pipeline parameters (selectable at run time)](#-pipeline-parameters-selectable-at-run-time)
- [The gold layer + Direct Lake governance report](#-the-gold-layer--direct-lake-governance-report)
- [Optional: Azure (ARM) auth for capacity Pause/Resume detection](#-optional-azure-arm-auth-for-capacity-pauseresume-detection)
- [Troubleshooting](#-troubleshooting)

---

## 🧭 Which tenant can each run mode reach?

The two run modes differ in **which tenant you can review**, because they authenticate differently:

| | **Local (PowerShell)** | **In Fabric (notebook / pipeline)** |
| --- | --- | --- |
| Identity | Your signed-in user (`az login` / browser), via `azure.identity` | The notebook's executing identity, via `notebookutils` |
| Tenant targeted | **Any tenant** you have guest/member access to — set by `TENANT_ID` in `.env` | **Only the tenant that owns the Fabric workspace** — `TENANT_ID` is a label, it cannot redirect the token |
| Cross-tenant review | ✅ Yes — `az login --tenant <client>` then set `TENANT_ID=<client>` | ❌ No — run the notebook *inside the client's tenant* |
| Best for | Consultant reviewing a client tenant from their own machine | Client running it themselves, or a tenant-resident reviewer; unattended/scheduled runs |

**Key point:** locally you can point the framework at any tenant where your account is a guest/member
with the right Fabric roles (the `TENANT_ID` env var drives `az login`/the token). In Fabric, the
token is always issued for the workspace's home tenant — so to review a client tenant you import and
run the notebook **inside that client's Fabric workspace** with an identity that holds the roles there.

> The one exception is the opt-in Azure (ARM) Pause/Resume scan — see
> [Optional: Azure (ARM) auth](#-optional-azure-arm-auth-for-capacity-pauseresume-detection) below.

---

## 🚀 Deploy it from inside Fabric (no workstation needed)

This uses a single-notebook deploy pattern: you import **one** setup
notebook, run it once, and it deploys everything else for you. The only prerequisite you create by
hand is the **Fabric workspace** itself. Remember: the review targets the tenant that owns the
workspace (see the table above).

1. **Import the setup notebook** — Fabric workspace → *New* → *Import notebook* → upload [setup.ipynb](setup.ipynb).
2. **Set its parameters** (parameters cell): the GitHub repo/branch to clone, `WORKSPACE_ID` (leave blank to use the current workspace), and the baked-in pipeline defaults (`TENANT_ID`, `CLIENT_NAME`, `ENGAGEMENT_NAME`, `REVIEWER_NAME`, optional `WORKSPACE_IDS`, the `CAPACITY_*` flags). These become the **pipeline's default parameter values** — every one stays overridable at run time (see [Pipeline parameters](#-pipeline-parameters-selectable-at-run-time)). The repo is public, so the clone needs no token.
3. **Run all cells.** Using the Fabric REST API, the setup notebook:
   - creates (or reuses) the Lakehouse `fabric_arch_review_lh` that holds the run output,
   - deploys the four stage notebooks — `FabricArchReview_01_Collect`, `FabricArchReview_02_Analyze`, `FabricArchReview_03_Report`, `FabricArchReview_04_Gold` — each pre-attached to that Lakehouse,
   - creates (or updates) the **Fabric Arch Review Pipeline** that chains *Collect → Analyze → Gold → Report* (each step depends on the previous one succeeding), passing a shared `RUN_ID` so all stages read/write the same run folder,
   - deploys a **Direct Lake semantic model + Power BI report** named *Fabric Arch Review - Governance* over the gold-layer Delta tables. Set `DEPLOY_GOLD_REPORT="false"` to skip this.

   It is idempotent — re-running it upserts the notebooks, pipeline, model and report instead of duplicating them.
4. **Run the pipeline.** Open *Fabric Arch Review Pipeline* → *Run*. The Run dialog lists every parameter (pre-filled with the defaults you set in step 2) so you can adjust scope per run, or *Schedule* it for unattended runs. The collect stage clones this repo, installs `requirements.txt`, authenticates as the **executing identity** via `notebookutils` (no `az login`), gathers metadata into the Lakehouse, then analyze, gold, and report stages run in turn.
5. **Read the output** two ways: the consultant-style **`report.md`** in `Files/fabric-arch-review/<run-id>/` (raw JSON alongside in `raw/`), and the interactive **Fabric Arch Review - Governance** report (open it from the workspace).

> **Auth in Fabric:** the executing identity needs the same roles the framework documents (Fabric Administrator for tenant-wide collectors; Workspace Member+ for per-workspace ones). The Power BI token audience covers both the Fabric and Power BI admin REST endpoints.
>
> **PDF stage:** the branded PDF needs Node.js + Puppeteer and is **skipped** in Fabric — the pipeline produces `report.md`. Generate the PDF later on a workstation with `python reports/_generate_pdf.py` if you need it.

---

## 🎛️ Pipeline parameters (selectable at run time)

The setup notebook promotes every engagement value to a **pipeline-level parameter** with a default,
so you do **not** have to redeploy to re-scope a run. Open *Fabric Arch Review Pipeline* → *Run* and the
dialog pre-fills these (and the same parameters are available on a *Schedule* trigger). Each stage reads
them via `@pipeline().parameters.*`, exactly the way the shared `RUN_ID` is resolved.

| Parameter | Default | What it does |
| --- | --- | --- |
| `GITHUB_REPO_URL` | this repo's clone URL | Repo the stages clone to get the analyzer code — change it if you forked |
| `GITHUB_BRANCH` | `main` | Branch to clone |
| `SP_CLIENT_ID` / `SP_CONNECTION_NAME` | blank / `sp-fabric-arch-review` | *Optional* read-only **service principal** for unattended/scheduled baselines. You create the cloud connection **manually** (setup just prints a reminder); the secret never touches setup or pipeline params. Optionally use `SP_SECRET_KEYVAULT` + `SP_SECRET_NAME` for a Key Vault secret instead. Blank = run as the notebook's executing identity. See [auth-setup.md](../docs/auth-setup.md). |
| `TENANT_ID` | blank | Label recorded in the report (does **not** redirect the token in Fabric) |
| `WORKSPACE_IDS` | blank | Comma-separated workspace GUIDs to restrict the review to (blank = tenant-wide) |
| `ACTIVITY_DAYS_LOG` | `7` | Admin Activity Log lookback window in days (1–30 per Fabric Admin API) |
| `CLIENT_NAME` | `Contoso` | Client name on the report cover |
| `ENGAGEMENT_NAME` | `Fabric Architecture Review` | Engagement title on the report cover |
| `REVIEWER_NAME` | blank | Reviewer name on the report cover |
| `CAPACITY_METRICS_APP_INSTALLED` | `false` | `true` enables the opt-in Capacity Metrics App DAX collector |
| `CAPACITY_AUTO_PAUSE_CONFIGURED` | `false` | Keep `false` in Fabric (ARM scan is local-only — see below) |
| `VERTIPAQ_STATS_READ_DATA` | `false` | `true` adds exact column cardinality (aggregate COUNT DAX); default = sizes/encoding metadata only |

> **Tip:** the defaults baked in at deploy time are the safe, generic ones above. Override only what a
> given run needs (e.g. set `WORKSPACE_IDS` to scope a spot-check) and leave the rest.
>
> **Threshold tuning:** every numeric pass/fail boundary (the ~16 keys documented in
> [../config/thresholds.yaml](../config/thresholds.yaml)) is *also* promoted to an optional pipeline
> parameter — leave them blank to use the curated defaults, or set one to re-tune the review to a
> client's SLOs without redeploying. See
> [Tuning pass/fail thresholds](../README.md#tuning-passfail-thresholds) in the main README.

---

## 🥇 The gold layer + Direct Lake governance report

The `04_Gold` stage turns each run's `findings.json` + raw metadata into **gold-layer Delta tables** in
the Lakehouse `Tables/` folder, and **appends** one partition of history per run so you can trend
best-practice posture over time. The tables (built by [../reports/gold_layer.py](../reports/gold_layer.py)
from the shared schema in [../reports/powerbi/schema.py](../reports/powerbi/schema.py)) are:

| Table | Grain | Backs |
| --- | --- | --- |
| `gold_findings` | one row per evaluated rule per run | every page (cards, findings table, measures) |
| `gold_run_summary` | one row per run | the run slicer + headline scorecard |
| `gold_dimension_summary` | one row per dimension per run | the *Overview* maturity radar + severity heatmap |
| `gold_capacities` | capacities at scan time | *Cost* / *Performance* pages |
| `gold_workspaces` | workspaces in scope | *Governance* page |
| `gold_semantic_models` | models + storage mode + VertiPaq size / column counts | *Architecture* + *Semantic Models* pages |
| `gold_model_tables` | one row per model table (VertiPaq) | *Model detail* page |
| `gold_model_columns` | one row per model column (size, encoding, data type, cardinality) | *Model detail* page |
| `gold_model_partitions` | one row per model partition (mode, record/segment counts) | *Model internals* page |
| `gold_model_relationships` | one row per model relationship (cardinality, used size) | *Model internals* page |
| `gold_model_hierarchies` | one row per user hierarchy | *Model internals* page |
| `gold_notebook_smells` | per-notebook NBCODE matches | *Notebooks* page |
| `gold_workspace_risk` | one row per workspace (item mix, issue/risk score, status) | *Overview* top-risk bar + *Estate Map* |
| `gold_severity_matrix` | one row per dimension × severity | *Overview* + *Estate Map* severity heatmap |
| `gold_bpa_violations` | one row per individual BPA / Direct Lake / Delta / health violation | *Best Practices* page |
| `gold_graph_nodes` | estate entities (capacity, workspace, items, owners) | *Estate Map* inventory |
| `gold_graph_edges` | relationships between estate entities | *Estate Map* relationships |

The `gold_semantic_models`, `gold_model_*` tables are populated from `vertipaq_stats.json` (the
**Fabric-only** `collectors.vertipaq_stats` collector). When that collector did not run — or no models
were resident — those per-model tables are simply empty and the *Semantic Models* / *Model detail* /
*Model internals* pages render without data. The estate-graph and risk tables (`gold_graph_*`,
`gold_workspace_risk`, `gold_severity_matrix`) are derived from the scanner inventory + findings, so
they populate on every run.

The **Best Practices** dimension (`BPA-001..007` — model/report BPA, Direct Lake fallback, Delta health,
unused objects, capacity SKU readiness) is Fabric-only via `semantic-link-labs`; it feeds
`gold_dimension_summary`, `gold_severity_matrix`, and `gold_bpa_violations`, and gets its own report
page automatically. Outside Fabric the collector degrades to `available:false` and the page renders as
informational.

The **Fabric Arch Review - Governance** semantic model
([../reports/powerbi/semantic_model.py](../reports/powerbi/semantic_model.py)) binds to these tables in
**Direct Lake** mode (no import, no scheduled refresh) and the report
([../reports/powerbi/report.py](../reports/powerbi/report.py)) is a **15-page platform-assessment
dashboard**:

| Page | What it shows |
| --- | --- |
| **Home** | Branded navigation hero — click through to any page |
| **Overview** | Executive cockpit: platform-maturity **radar** by dimension, best-practice-score **gauge**, fails-by-severity **donut**, dimension × severity **heatmap**, top-risk-workspace **ranked bar**, and the full findings table |
| **Trends** | Run-over-run history — best-practice score, fails by severity, and per-dimension posture trended across every pipeline run |
| **Estate Map** | Workspace-risk hotspots (scatter), failures by dimension & severity, and the estate inventory / relationships tables |
| **Architecture, Performance, Cost, Governance, Security, Tenant Settings** | One page per review dimension — KPI cards, a severity donut, a ranked bar of failing checks, a dimension-specific detail table, and the dimension-filtered findings list |
| **Best Practices** | Fabric-only BPA outcomes — a violation-count KPI and a breakdown of model/report BPA, Direct Lake fallback, Delta health, unused objects, and capacity SKU readiness |
| **Semantic Models** | Per-model VertiPaq burden (size, column / calculated-column counts, storage mode) with a size-by-model bar and a model-hotspot **scatter** (size vs. refresh, sized by columns) |
| **Model detail** | Pick a model + table from slicers and inspect every column the way DAX Studio's VertiPaq Analyzer does — data type, encoding, cardinality, size |
| **Model internals** | Per-model partitions, relationships, and user hierarchies |
| **Notebooks** | NBCODE code-smell matches with a severity donut and a top-notebooks ranked bar |

> **Custom visual note:** the *Overview* maturity radar uses the Microsoft-certified **Radar Chart**
> public custom visual (declared via `publicCustomVisuals`). If your tenant blocks custom visuals it
> renders a placeholder — every other visual on every page uses standard core visuals, so the rest of the
> report is unaffected.

> **First run:** the model + report are deployed empty. They light up after the pipeline runs **once**
> (the `04_Gold` stage creates the Delta tables the Direct Lake model reads). On a brand-new Lakehouse the
> setup notebook waits for the SQL analytics endpoint to provision before deploying the model.

---

## ⚙️ Optional: Azure (ARM) auth for capacity Pause/Resume detection

The opt-in Pause/Resume scan
([../collectors/azure_capacity_automation.py](../collectors/azure_capacity_automation.py), enabled with
`CAPACITY_AUTO_PAUSE_CONFIGURED=true`) reads **Azure Resource Manager** — subscriptions,
`Microsoft.Fabric/capacities`, Automation runbooks, and Logic App workflows — to verify that an
auto-pause/auto-resume schedule exists. That control plane is **not** reachable with the Fabric/Power BI
token, so it needs an Azure identity with *Reader* on the subscription that hosts the capacity.

> **⚠️ This scan only works when you run the framework on a local machine** (the CLI /
> `scripts/powershell/01_collect.ps1` flow), **not inside Fabric.** Microsoft Fabric's notebook identity cannot mint
> an Azure ARM token — `notebookutils.credentials.getToken("azuremanagement")` returns
> `400 REQUEST_INVALID_RESOURCE_NONRETRIABLE` ("azuremanagement is not a valid resource"). Fabric only
> issues `pbi`, `storage`, and `keyvault` audience tokens. **In Fabric, leave
> `CAPACITY_AUTO_PAUSE_CONFIGURED=false`** — the collector then skips cleanly. Run the local CLI flow if
> you need the Pause/Resume (COST-002) verification.

**On a local machine the framework uses an Azure identity you sign in with** (e.g. `az login` /
`DefaultAzureCredential`) — there is no service principal and no Key Vault secret. Grant that identity
Azure **Reader** on the capacity's subscription, set `CAPACITY_AUTO_PAUSE_CONFIGURED=true`, and the local
collect stage acquires the ARM token automatically.

> If you do **not** run the Pause/Resume scan (`CAPACITY_AUTO_PAUSE_CONFIGURED` stays `false`), no Azure
> ARM access is needed at all.

**Grant Reader to the signing-in identity:**

```bash
az role assignment create \
  --assignee <identity-object-id> \
  --role "Reader" \
  --scope /subscriptions/<subscription-id>
```

Scope it to the capacity's resource group instead of the whole subscription if the capacity, Automation
accounts, and Logic Apps all live in one RG. **Reader** is enough because the collector issues only `GET`
ARM calls (including `runbooks/.../content` and `workflows`) — no write/contributor role and no
data-plane (storage/DB) access is involved.

> **Cross-subscription / cross-tenant note:** your local Azure sign-in (`az login`) determines which
> tenant/subscriptions the ARM token can read. If the capacity lives in a subscription that identity
> cannot read, sign in to the tenant that owns it before running the local collect. The framework does
> not ship a separate ARM service principal.

---

## 🩺 Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| pip prints a dependency-resolver warning, then continues | Harmless — Fabric's `trident_env` ships pinned packages. pip still exits 0; the next line confirms "Repo + deps ready". |
| *Semantic Models* / *Model detail* / *Model internals* pages are empty | The `vertipaq_stats` collector did not run, or no models were resident in memory at scan time. |
| *Overview* maturity radar shows a "can't display this visual" placeholder | Your tenant blocks custom visuals. The radar is the only custom visual; every other visual still renders. Allow the Microsoft-certified *Radar Chart* in **Admin portal → Tenant settings → custom visuals**, or ignore it. |
| Model + report show no data after deploy | Expected on first deploy — they light up after the pipeline runs **once** (the `04_Gold` stage fills the Delta tables). |
| Pause/Resume (COST-002) shows "skipped" | Expected in Fabric — the ARM scan is local-only. Run the local CLI flow for that check. |

---

For the local workflow, configuration reference, rule catalog, and contribution guide, see the
[main README](../README.md). Microsoft, Fabric, and Power BI are trademarks of the Microsoft group of
companies.
