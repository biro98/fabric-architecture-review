# Auth Setup — Interactive User

This framework authenticates **as you** (interactive user, OAuth 2.0
authorization-code flow with PKCE). There is no service principal, no client
secret, and nothing needs to be registered in the client tenant.

Every API call shows up in the Fabric audit log as a normal sign-in by your
account, identical to what a Fabric administrator would see if they used the
admin portal or the Power BI REST `Try It` console.

## Authentication modes

The framework acquires tokens for **two separate planes**, and how each is
obtained depends on where you run it. Both planes always use the **same
identity** - your interactive user locally, or the notebook's executing
identity in Fabric. There is no service principal anywhere in the framework.

| Plane | Collectors it serves | Local (PowerShell) | In Fabric (notebook / pipeline) |
|---|---|---|---|
| **Fabric + Power BI** | tenant settings, scanner, workspaces, semantic models, pipelines, gateways, activity logs… (most of the review) | your interactive **user** (`az login` / browser) | the **notebook's executing identity** |
| **Azure ARM** | the opt-in `azure_capacity_automation` (Pause/Resume scan) | the same interactive **user** | **not available** — the scan is local-only |

Key points:

- **One identity, two planes.** The same identity serves both the Fabric/Power BI
  plane and the Azure ARM plane. Locally that is your interactive user; in Fabric
  it is the notebook's executing identity. The Fabric admin / scanner APIs require
  that delegated user (local) or notebook identity (Fabric) - there is no way to
  run the review as a bare service principal.
- **Azure ARM is an opt-in add-on.** Only the opt-in `azure_capacity_automation`
  (Pause/Resume) scan touches Azure ARM. Grant the same identity Azure **Reader**
  on the capacity's subscription and it works; skip the scan
  (`CAPACITY_AUTO_PAUSE_CONFIGURED=false`) and no ARM access is needed at all.
- **Cross-tenant:** locally you can target **any** tenant you are a guest/member
  of (set `TENANT_ID`, then `az login --tenant <id>`). In Fabric the token is
  always the workspace's home tenant - run the notebook *inside the tenant you
  are reviewing*. If the Fabric capacity lives in a subscription that identity
  cannot read, run the review from inside the tenant that owns it.

> **What does the notebook set up in Fabric?** Nothing permanent. It does **not**
> create the workspace, a connection, or any role
> assignment — those are prerequisites you configure once (below). At run time it
> clones the repo into the session, installs dependencies, acquires tokens, runs
> the collectors + analyzers, renders `report.md`, and writes the outputs to the
> attached Lakehouse under `Files/fabric-arch-review/<run-stamp>/`. The only
> lasting artifact is those output files.

## Standing / unattended mode — service principal (optional)

For a permanent, scheduled governance baseline where no human is in
the loop, run as a dedicated **read-only service principal** instead of a user.
This is **opt-in and additive** — leave it unset and the framework stays fully
interactive / notebook-identity. The secret is never stored in code, the setup
notebook, or pipeline parameters: it lives **only** inside a Fabric cloud
connection, which is write-only — once pasted, nothing (not even the notebook)
can read it back.

**Prerequisite (once, before setup):**
1. Create an app registration (the SP) — note its **client ID** + tenant.
2. Add the SP to a security group; a Fabric admin enables **"Service principals
   can use Fabric/Power BI read-only admin APIs"** scoped to that group.
3. Grant the SP Azure **Reader** on the capacity subscription only if you keep
   `capacity_metrics`.

**Setup never touches the secret.** Set `SP_CLIENT_ID` (+ optional
`SP_CONNECTION_NAME`, default `sp-fabric-arch-review`) in the setup params. Setup
deploys everything and just prints a reminder to create the connection — it does
not create it, because Fabric will not store a service-principal connection
without a secret.

**Create the connection yourself** (once, after setup): **Manage connections and
gateways → New → Cloud**, type = **Web v2**, base URL `https://api.fabric.microsoft.com`,
authentication = **Service principal**, fill tenant/client/secret, name it
`SP_CONNECTION_NAME`. To run unattended as the SP, schedule the Collect notebook
with that service principal as its owner. Blank `SP_CLIENT_ID` = run as the
notebook's executing identity (default).

## What you need in the client tenant

You must be a **member or guest** in the client's Microsoft Entra tenant, and
depending on which collectors you want to run, you need one of the following
role / permission combinations:

| Collector | Required role |
|---|---|
| `tenant_settings` (admin) | **Fabric Administrator** or **Power BI Administrator** in the client tenant |
| `scanner_api` (admin) | Same as above |
| `workspace_inventory` — admin view (all workspaces) | Same as above |
| `activity_logs` (admin) | Same as above |
| `capacity_metrics` — capacity-level Azure Monitor metrics | **Reader** on the Fabric capacity resource in Azure |
| `workspace_inventory` — workspace-scoped | Workspace **Member** (or higher) on each in-scope workspace |
| `lakehouse_warehouse` — metadata only | Workspace **Member** (or higher) |
| `semantic_models` — DMV schema | Workspace **Member** (or higher); the workspace must be on a Fabric / Premium capacity to expose the XMLA endpoint |
| `semantic_model_definitions` — TMDL/BIM via `getDefinition` | Workspace **Member** (or higher); `getDefinition` requires write access, so **Viewer** is not enough |
| `pipelines_notebooks` — run history | Workspace **Member** (or higher) |
| `pipeline_definitions` — pipeline / notebook source via `getDefinition` | Workspace **Member** (or higher); `getDefinition` requires write access |
| `realtime_intelligence` — RTI + mirroring inventory | Workspace **Viewer** (or higher) |
| `git_integration` | Workspace **Admin** |
| `deployment_pipelines` — Deployment Pipelines inventory | **Admin** on each Power BI Deployment Pipeline (or Fabric Administrator); returns only pipelines you can see |
| `gateways` — data gateway inventory | **Gateway admin** on each on-prem / VNet gateway; returns only gateways you administer |
| `capacity_metrics_app` *(opt-in)* — DAX vs. Capacity Metrics App | **Build** permission on the Fabric Capacity Metrics App semantic model |
| `azure_capacity_automation` *(opt-in)* — ARM scan for Pause/Resume | Azure **Reader** on the subscription(s) hosting the capacity, Automation account, and Logic App |

> **No Fabric Admin role?** You can still complete a workspace-scoped review.
> The framework will surface `401`/`403` from the tenant-wide endpoints; mark
> those checklist items as "evidence not available — request Fabric Admin
> review meeting" in the final report.

## Tenant settings (must be enabled by the client's Fabric admin)

For the XMLA / DMV based collector (`semantic_models`) to work, the Fabric
admin must enable, for either the whole org or a security group containing
your user:

- **XMLA endpoint** -> *Read* or *Read/Write* (Capacity settings -> Power BI
  workload), and
- **Allow XMLA endpoints and Analyze in Excel with on-premises datasets**
  (Tenant settings).

The Scanner / Admin REST endpoints do **not** require any tenant setting
change for a user-context call — they only require the admin role.

## Local setup

### 1. Fill `.env`

```text
TENANT_ID=<client-tenant-id>     # the GUID of the customer's Entra tenant
# CLIENT_ID=                     # leave blank to use the Azure CLI public client
```

### 2. (Recommended) Sign in via Azure CLI

```powershell
az login --tenant <client-tenant-id>
```

When `az login` has already produced a valid token for the tenant, the
framework picks it up silently (`AzureCliCredential`). This is the smoothest
experience and means there's nothing visible to the client beyond a normal
interactive sign-in event in the audit log.

### 3. First run

If no CLI session is available, the framework falls back to
`InteractiveBrowserCredential`. A browser window opens, you sign in once, and
your refresh token is cached on disk (encrypted on Windows via DPAPI when
available, otherwise plaintext under `%LOCALAPPDATA%\.IdentityService\`).

```powershell
.\.venv\Scripts\Activate.ps1
python -m collectors.tenant_settings
```

Expected output:
```
Tenant settings written to: output/raw/tenant_settings.json
```

If you see `AADSTS50105` (`The signed in user is not assigned to a role for
the application`) or HTTP `401 Unauthorized` from the Fabric endpoint, your
account does not hold the Fabric Administrator role in the client tenant —
work around it as described above.

## Footprint in the client's audit log

Every collector call appears in the **Fabric Activity Log** as your UPN, with
the operation name matching the API endpoint (e.g. `GetTenantSettings`,
`GetWorkspacesAsAdmin`, `GetScanResultAsAdmin`). This is by design — it is
the same trail any admin user would leave. The client can audit exactly what
you accessed.

## Conditional Access caveats

If the client tenant enforces Conditional Access policies that require:

- a managed device,
- a compliant device,
- a specific named network location,

...then the interactive sign-in will fail until you meet the policy. The
common workaround is to run the framework from a customer-issued jump host
or a session host inside their tenant.

## Cross-engagement isolation

The token cache is keyed by `TENANT_ID`, so cloning the repo per engagement
(as recommended) keeps each client's tokens isolated. To purge a cached
session, delete the matching file under `%LOCALAPPDATA%\.IdentityService\`.

## Azure (ARM) Reader for the Pause/Resume scan (local only)

The opt-in `azure_capacity_automation` (Pause/Resume) scan is the only collector
that reads **Azure Resource Manager**. It runs **only on a local machine** —
Fabric's notebook identity cannot mint an ARM token, so leave
`CAPACITY_AUTO_PAUSE_CONFIGURED=false` in Fabric and it skips cleanly. Locally it
needs an Azure identity with **Reader** on the subscription that hosts the
capacity — your own `az login` user; there is no service principal and no Key
Vault secret.

```bash
az role assignment create --assignee <your-user-object-id> \
  --role "Reader" --scope /subscriptions/<subscription-id>
```

Scope it to the capacity's resource group instead of the whole subscription if
the capacity, Automation accounts, and Logic Apps all live in one RG. **Reader**
is enough because the scan issues only `GET` ARM calls - list capacities, read
Automation runbook content, read Logic App workflow definitions. No
write/contributor role and no data-plane access is involved.

Then set the local environment variable / `.env` value:

| Setting | Value |
| --- | --- |
| `CAPACITY_AUTO_PAUSE_CONFIGURED` | `true` |

When enabled, the local collect stage acquires the ARM token from your `az login`
session automatically. Sign in to the tenant that owns the capacity first if it
lives elsewhere.
