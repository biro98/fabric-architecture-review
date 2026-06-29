"""Generate the Direct Lake governance semantic model as TMSL (``model.bim``).

We emit TMSL (one JSON object) rather than multi-file TMDL because a single
``model.bim`` part is much easier to generate deterministically and validate,
and the Fabric *Update Semantic Model Definition* API accepts it directly as a
``model.bim`` part (no ``format`` field needed).

The model binds to the Lakehouse SQL analytics endpoint in **Direct Lake**
mode, so it reads the gold Delta tables live with no import/refresh. The
table + column list is generated from :mod:`reports.powerbi.schema`, the same
source of truth the gold-layer builder uses, so they can never drift.

DATA SAFETY: builds metadata only.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from reports.powerbi.schema import GOLD_TABLES, tmdl_type

_NS = uuid.UUID("6f3b1c2a-0d4e-4a5b-9c7d-1e2f3a4b5c6d")

# Fact table that carries the explicit measures + the run dimension key.
FACT_TABLE = "gold_findings"
RUN_TABLE = "gold_run_summary"
# Table that carries the VertiPaq model-burden measures.
MODEL_TABLE = "gold_semantic_models"
# Tables that carry the estate-graph / workspace-risk measures.
RISK_TABLE = "gold_workspace_risk"
GRAPH_NODE_TABLE = "gold_graph_nodes"
GRAPH_EDGE_TABLE = "gold_graph_edges"
# Table that carries the notebook code-smell count measure.
NOTEBOOK_TABLE = "gold_notebook_smells"
PARTITION_TABLE = "gold_model_partitions"
RELATIONSHIP_TABLE = "gold_model_relationships"
HIERARCHY_TABLE = "gold_model_hierarchies"
# Table that carries the Best Practice Analyzer violation count measure.
BPA_TABLE = "gold_bpa_violations"
# Table that carries the severity heatmap data + its colour measure.
SEVERITY_MATRIX_TABLE = "gold_severity_matrix"

# Columns that hold http(s) links; flagged as Web URLs so report tables render
# them as clickable hyperlinks.
_WEB_URL_COLUMNS = {"microsoft_learn_url", "notebook_url"}


def _lineage(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "|".join(parts)))


def _column(table: str, name: str, kind: str) -> Dict[str, Any]:
    col: Dict[str, Any] = {
        "name": name,
        "dataType": tmdl_type(kind),
        "sourceColumn": name,
        "summarizeBy": "none",
        "lineageTag": _lineage(table, "col", name),
    }
    if kind in ("int64", "double"):
        col["formatString"] = "0" if kind == "int64" else "0.0"
    if name in _WEB_URL_COLUMNS:
        col["dataCategory"] = "WebUrl"
    return col


def _measures() -> List[Dict[str, Any]]:
    defs = [
        ("Total Findings", "COUNTROWS(gold_findings)", "0",
         "Number of checklist rules evaluated in the current filter context."),
        ("Fail Count", 'COALESCE(CALCULATE(COUNTROWS(gold_findings), gold_findings[status] = "fail"), 0)', "0",
         "Rules that did not meet the best-practice bar (status = fail) in context; 0 (not blank) when none fail."),
        ("Pass Count", 'COALESCE(CALCULATE(COUNTROWS(gold_findings), gold_findings[status] = "pass"), 0)', "0",
         "Rules that met the best-practice bar (status = pass) in context; 0 (not blank) when none pass."),
        ("Info Count", 'CALCULATE(COUNTROWS(gold_findings), gold_findings[status] = "info")', "0",
         "Informational findings that neither pass nor fail."),
        ("Best Practice Score",
         "DIVIDE([Pass Count], [Pass Count] + [Fail Count]) * 100", "0.0",
         "Percent of pass/fail rules that passed: Pass / (Pass + Fail) x 100."),
        ("Critical & High Fails",
         'CALCULATE([Fail Count], gold_findings[severity] IN {"critical", "high"})', "0",
         "Failing rules whose severity is critical or high - the items to fix first."),
        ("Score Target", "80", "0",
         "Target best-practice score (the green/healthy threshold) - drives the gauge target line."),
        ("Score Max", "100", "0",
         "Maximum best-practice score - fixes the gauge scale to a 0-100 range."),
        ("Weighted Risk Score",
         'SUMX(FILTER(gold_findings, gold_findings[is_fail] = 1), '
         'SWITCH(gold_findings[severity], "critical", 100, "high", 75, '
         '"medium", 50, "low", 25, 10))', "#,0",
         "Sum of failing-rule severity weights (Critical 100 / High 75 / Medium 50 / Low 25 / Info 10) - one risk number for the estate."),
        ("Health Score", "[Best Practice Score]", "0.0",
         "Platform health: pass-rate %. 80+ healthy, 50-79 needs review, under 50 poor."),
        ("Assessed Assets", "DISTINCTCOUNT(gold_findings[dimension])", "0",
         "Number of assessment dimensions evaluated this run."),
        ("Severity Color",
         'SWITCH(LOWER(SELECTEDVALUE(gold_findings[severity])), "critical", "#A4262C", '
         '"high", "#D13438", "medium", "#E8702A", "low", "#2B88D8", "#605E5C")', "",
         "Hex colour for the row's severity (critical = deep red, high = red, medium = orange, low = blue, info = grey; green is reserved for pass) - drives data-colour-by-value on charts."),
        ("Status Color",
         'SWITCH(LOWER(SELECTEDVALUE(gold_findings[status])), "pass", "#107C10", '
         '"fail", "#D13438", "info", "#605E5C", "#605E5C")', "",
         "Hex colour for the row's status (pass = green, fail = red, info / not-evaluated = grey) - drives data-colour-by-value on charts."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _model_measures() -> List[Dict[str, Any]]:
    """VertiPaq model-burden measures placed on ``gold_semantic_models``."""
    defs = [
        ("Model Count", "DISTINCTCOUNT(gold_semantic_models[model_id])", "0",
         "Number of semantic models in the current filter context."),
        ("Total Model Size", "SUM(gold_semantic_models[total_size])", "#,0",
         "Sum of in-memory VertiPaq size (bytes) across the models in context."),
        ("Total Model Size (MB)",
         "DIVIDE(SUM(gold_semantic_models[total_size]), 1048576)", "#,0.0",
         "In-memory VertiPaq size in megabytes (size / 1024 / 1024)."),
        ("Import Models",
         'CALCULATE(DISTINCTCOUNT(gold_semantic_models[model_id]), '
         'NOT(gold_semantic_models[storage_mode] IN {"DirectLake", "DirectQuery"}))', "0",
         "Models that load data into memory (Import / Abf) and so carry a VertiPaq footprint."),
        ("Calculated Columns",
         "SUM(gold_semantic_models[calc_column_count])", "0",
         "Total calculated columns across models - a common refresh + memory cost driver."),
        ("Total Columns", "SUM(gold_semantic_models[column_count])", "0",
         "Total columns materialized across the models in context."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _risk_measures() -> List[Dict[str, Any]]:
    """Workspace-risk + estate measures placed on ``gold_workspace_risk``."""
    defs = [
        ("Workspace Count", "DISTINCTCOUNT(gold_workspace_risk[workspace_id])", "0",
         "Number of workspaces in the current filter context."),
        ("Workspaces at Risk",
         "CALCULATE(DISTINCTCOUNT(gold_workspace_risk[workspace_id]), "
         "gold_workspace_risk[status_rank] >= 2) + 0", "0",
         "Workspaces whose risk status is amber or red (status_rank >= 2)."),
        ("Average Risk Score", "AVERAGE(gold_workspace_risk[risk_score])", "0.0",
         "Mean 0-100 risk score across the workspaces in context."),
        ("Max Risk Score", "MAX(gold_workspace_risk[risk_score])", "0.0",
         "Highest workspace risk score in context - the worst hotspot."),
        ("Workspace Issues", "SUM(gold_workspace_risk[issue_count])", "0",
         "Total failing findings attributed to workspaces in context."),
        ("Total Items", "SUM(gold_workspace_risk[item_count])", "0",
         "Total Fabric items (models, reports, notebooks, pipelines, lakehouses) in context."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _graph_measures(table_name: str) -> List[Dict[str, Any]]:
    if table_name == GRAPH_NODE_TABLE:
        defs = [
            ("Node Count", "COUNTROWS(gold_graph_nodes)", "0",
             "Number of estate nodes (any type) in the current filter context."),
        ]
    else:
        defs = [
            ("Relationship Count", "COUNTROWS(gold_graph_edges)", "0",
             "Number of relationships (edges) between estate nodes in context."),
        ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _run_measures() -> List[Dict[str, Any]]:
    """Trend measures on ``gold_run_summary`` (one row per run -> plot over time)."""
    defs = [
        ("Run Score", "AVERAGE(gold_run_summary[score])", "0.0",
         "Best-practice score for each run - plot over run_timestamp to see the trend."),
        ("Run Fails", "SUM(gold_run_summary[fail_count])", "0",
         "Failing rules per run - the issue trend across reviews."),
        ("Run Critical & High",
         "SUM(gold_run_summary[critical_fail]) + SUM(gold_run_summary[high_fail])", "0",
         "Critical + high fails per run - severity trend across reviews."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _notebook_measures() -> List[Dict[str, Any]]:
    """Code-smell count measure placed on ``gold_notebook_smells``."""
    defs = [
        ("Notebook Smell Count", "COUNTROWS(gold_notebook_smells)", "0",
         "Number of notebook code-smell matches (NBCODE rule hits) in context."),
        ("Smell Severity Color",
         'SWITCH(LOWER(SELECTEDVALUE(gold_notebook_smells[severity])), "critical", "#A4262C", '
         '"high", "#D13438", "medium", "#E8702A", "low", "#2B88D8", "#605E5C")', "",
         "Hex colour for the smell's severity (critical deep red -> low blue; green = pass only) - drives data-colour-by-value on charts."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _internals_measures(table_name: str) -> List[Dict[str, Any]]:
    """Count measures for the VertiPaq internals frames so the Model internals
    page reads as an investigation dashboard, not a raw table dump."""
    if table_name == PARTITION_TABLE:
        defs = [("Partition Count", "COUNTROWS(gold_model_partitions)", "0",
                 "Number of model partitions in context - many small segments hint at refresh cost.")]
    elif table_name == RELATIONSHIP_TABLE:
        defs = [("Model Relationship Count", "COUNTROWS(gold_model_relationships)", "0",
                 "Number of model relationships in context; missing rows flag data-quality smells.")]
    else:
        defs = [("Hierarchy Count", "COUNTROWS(gold_model_hierarchies)", "0",
                 "Number of user hierarchies in context and the extra memory they cost.")]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _bpa_measures() -> List[Dict[str, Any]]:
    """BPA violation count measure placed on ``gold_bpa_violations``."""
    defs = [
        ("BPA Violation Count", "COUNTROWS(gold_bpa_violations)", "0",
         "Number of individual Best Practice Analyzer / health violations in context."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _severity_matrix_measures() -> List[Dict[str, Any]]:
    """Severity colour measure placed on ``gold_severity_matrix`` (heatmap series)."""
    defs = [
        ("Matrix Severity Color",
         'SWITCH(LOWER(SELECTEDVALUE(gold_severity_matrix[severity])), "critical", "#A4262C", '
         '"high", "#D13438", "medium", "#E8702A", "low", "#2B88D8", "#605E5C")', "",
         "Hex colour for the severity series - drives data-colour-by-value on the dimension chart."),
    ]
    out = []
    for name, expr, fmt, desc in defs:
        out.append({
            "name": name,
            "expression": expr,
            "formatString": fmt,
            "description": desc,
            "lineageTag": _lineage("measure", name),
        })
    return out


def _table(table) -> Dict[str, Any]:
    t: Dict[str, Any] = {
        "name": table.name,
        "lineageTag": _lineage("table", table.name),
        "columns": [_column(table.name, c.name, c.kind) for c in table.columns],
        "partitions": [{
            "name": table.name,
            "mode": "directLake",
            "source": {
                "type": "entity",
                "entityName": table.name,
                "schemaName": "dbo",
                "expressionSource": "DatabaseQuery",
            },
        }],
    }
    if table.name == FACT_TABLE:
        t["measures"] = _measures()
    if table.name == MODEL_TABLE:
        t["measures"] = _model_measures()
    if table.name == RISK_TABLE:
        t["measures"] = _risk_measures()
    if table.name == RUN_TABLE:
        t["measures"] = _run_measures()
    if table.name in (GRAPH_NODE_TABLE, GRAPH_EDGE_TABLE):
        t["measures"] = _graph_measures(table.name)
    if table.name == NOTEBOOK_TABLE:
        t["measures"] = _notebook_measures()
    if table.name == BPA_TABLE:
        t["measures"] = _bpa_measures()
    if table.name == SEVERITY_MATRIX_TABLE:
        t["measures"] = _severity_matrix_measures()
    if table.name in (PARTITION_TABLE, RELATIONSHIP_TABLE, HIERARCHY_TABLE):
        t["measures"] = _internals_measures(table.name)
    return t


def _relationships() -> List[Dict[str, Any]]:
    rels = []
    for table in GOLD_TABLES:
        if table.name == RUN_TABLE:
            continue
        if not any(c.name == "run_id" for c in table.columns):
            continue
        rels.append({
            "name": _lineage("rel", table.name),
            "fromTable": table.name,
            "fromColumn": "run_id",
            "toTable": RUN_TABLE,
            "toColumn": "run_id",
            "crossFilteringBehavior": "oneDirection",
        })
    return rels


def build_bim(model_name: str, sql_endpoint: str, database_id: str) -> Dict[str, Any]:
    """Build the TMSL model object.

    ``sql_endpoint`` is the Lakehouse SQL analytics endpoint host
    (e.g. ``xxxxx.datawarehouse.fabric.microsoft.com``); ``database_id`` is the
    SQL endpoint id (or Lakehouse name) used as the database in ``Sql.Database``.
    """
    m_expr = (
        "let\n"
        f'    database = Sql.Database("{sql_endpoint}", "{database_id}")\n'
        "in\n"
        "    database"
    )
    return {
        "name": model_name,
        "compatibilityLevel": 1604,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "expressions": [{
                "name": "DatabaseQuery",
                "kind": "m",
                "expression": m_expr,
                "lineageTag": _lineage("expression", "DatabaseQuery"),
            }],
            "tables": [_table(t) for t in GOLD_TABLES],
            "relationships": _relationships(),
            "annotations": [
                {"name": "PBI_QueryOrder", "value": '["DatabaseQuery"]'},
            ],
        },
    }


def build_model_bim_json(model_name: str, sql_endpoint: str, database_id: str) -> str:
    return json.dumps(build_bim(model_name, sql_endpoint, database_id), indent=2)
