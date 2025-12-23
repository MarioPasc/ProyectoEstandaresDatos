#!/usr/bin/env python3
"""
Generic SPARQL runner for an RDF graph (rdflib).

- Loads an RDF graph from a Turtle file (default: data/rdf/export.ttl)
- Discovers SPARQL query files (*.rq) in a folder (default: queries/sparql)
- Executes queries with rdflib
- Exports results per query (CSV + JSON for SELECT, JSON for ASK, TTL for CONSTRUCT/DESCRIBE)
- Generates a run index/summary with rows/cols/time per query

Designed for maximum portability and "standard paths + prefixes" compatibility.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.query import Result as RdflibResult
from rdflib.namespace import XSD
from rdflib.util import guess_format


try:
    import rdflib  # type: ignore
except Exception:  # pragma: no cover
    rdflib = None  # type: ignore


# -------------------------
# Domain errors
# -------------------------
class RunnerError(RuntimeError):
    """Base error for the SPARQL runner."""


class ConfigError(RunnerError):
    """Configuration/CLI input errors."""


class QueryError(RunnerError):
    """Query execution/parsing errors."""


# -------------------------
# Data structures
# -------------------------
@dataclass(frozen=True)
class PathsConfig:
    ttl_path: Path
    queries_dir: Path
    out_dir: Path
    prefixes_path: Optional[Path]


@dataclass(frozen=True)
class RunConfig:
    paths: PathsConfig
    formats: Tuple[str, ...]  # e.g. ("csv","json")
    recursive: bool
    fail_fast: bool
    dry_run: bool
    verbose: bool
    compat: str


@dataclass
class QueryReport:
    query_file: str
    query_name: str
    query_type: str
    ok: bool
    duration_ms: int
    rows: int
    cols: int
    outputs: List[str]
    error: Optional[str] = None


# -------------------------
# Helpers
# -------------------------
def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="level=%(levelname)s msg=%(message)s",
    )


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"No existe el fichero: {path}") from e
    except OSError as e:
        raise RunnerError(f"No se pudo leer el fichero: {path} ({e})") from e


def write_text(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, obj: Any, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_slug(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "query"


def discover_queries(root: Path, recursive: bool) -> List[Path]:
    if not root.exists():
        raise ConfigError(f"No existe el directorio de consultas: {root}")
    pattern = "**/*.rq" if recursive else "*.rq"
    return sorted(root.glob(pattern))


_PREFIX_LINE_RE = re.compile(r"^\s*PREFIX\s+([A-Za-z_][\w\-]*)\s*:\s*<([^>]+)>\s*$", re.IGNORECASE)


def parse_prefixes_from_file(prefixes_path: Path) -> Dict[str, str]:
    """
    Supports a simple .sparql/.rq-like file containing PREFIX lines.
    """
    txt = read_text(prefixes_path)
    prefixes: Dict[str, str] = {}
    for line in txt.splitlines():
        m = _PREFIX_LINE_RE.match(line)
        if m:
            prefixes[m.group(1)] = m.group(2)
    return prefixes


def parse_declared_prefixes_in_query(query_text: str) -> Dict[str, str]:
    prefixes: Dict[str, str] = {}
    for line in query_text.splitlines():
        m = _PREFIX_LINE_RE.match(line)
        if m:
            prefixes[m.group(1)] = m.group(2)
    return prefixes


def build_prefix_block(graph: Graph, extra_prefixes: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Collects prefixes from the graph namespace manager + optional extra prefixes.
    """
    out: Dict[str, str] = {}
    # graph prefixes
    for prefix, ns in graph.namespace_manager.namespaces():
        try:
            out[str(prefix)] = str(ns)
        except Exception:
            continue
    # optional file prefixes override/add
    if extra_prefixes:
        out.update(extra_prefixes)
    return out


def prepend_missing_prefixes(query_text: str, available: Dict[str, str]) -> str:
    """
    If the query already declares PREFIX lines, keep them.
    Otherwise, prepend a deterministic set of PREFIX lines from `available`.
    We also avoid duplicating any already declared prefixes.
    """
    declared = parse_declared_prefixes_in_query(query_text)
    missing = {p: iri for p, iri in available.items() if p not in declared}

    # If there are no prefixes available, return as-is.
    if not missing:
        return query_text

    # Deterministic ordering
    prefix_lines = [f"PREFIX {p}: <{missing[p]}>" for p in sorted(missing.keys())]

    # Insert before the first non-comment/non-empty line if query already has some PREFIXes,
    # or simply prepend at top otherwise.
    lines = query_text.splitlines()
    insert_at = 0
    while insert_at < len(lines):
        s = lines[insert_at].strip()
        if s == "" or s.startswith("#"):
            insert_at += 1
            continue
        # keep declared PREFIX lines at the top; we add our missing ones after existing PREFIX block
        if s.upper().startswith("PREFIX"):
            # advance until end of PREFIX block
            j = insert_at
            while j < len(lines) and lines[j].strip().upper().startswith("PREFIX"):
                j += 1
            insert_at = j
        break

    new_lines = lines[:insert_at] + prefix_lines + [""] + lines[insert_at:]
    return "\n".join(new_lines).strip() + "\n"


def guess_query_type(query_text: str) -> str:
    """
    Best-effort query type detection for reporting.
    """
    q = re.sub(r"#.*", "", query_text, flags=re.MULTILINE).strip().lower()
    for t in ("select", "ask", "construct", "describe"):
        if re.search(rf"^\s*{t}\b", q, flags=re.IGNORECASE | re.MULTILINE):
            return t.upper()
    return "UNKNOWN"


def term_to_str(graph: Graph, v: Any) -> str:
    if v is None:
        return ""
    try:
        # Prefer prefixed form if namespaces exist
        return v.n3(graph.namespace_manager)
    except Exception:
        return str(v)


def rdflib_result_to_table(graph: Graph, res: RdflibResult) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Converts a SELECT result into (columns, rows) where each row is a dict col->string.
    """
    cols = [str(v) for v in getattr(res, "vars", [])]
    rows: List[Dict[str, str]] = []
    for row in res:
        r: Dict[str, str] = {}
        for i, col in enumerate(cols):
            try:
                val = row[i]
            except Exception:
                val = None
            r[col] = term_to_str(graph, val)
        rows.append(r)
    return cols, rows


def export_select_csv(path: Path, cols: Sequence[str], rows: Sequence[Dict[str, str]], dry_run: bool) -> None:
    if dry_run:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cols))
        w.writeheader()
        for r in rows:
            w.writerow(r)


# -------------------------
# Core runner
# -------------------------
def load_graph(ttl_path: Path) -> Graph:
    if not ttl_path.exists():
        raise ConfigError(f"No existe el TTL de entrada: {ttl_path}")
    g = Graph()
    try:
        fmt = guess_format(str(ttl_path)) or "turtle"
        g.parse(str(ttl_path), format=fmt)
    except Exception as e:
        raise RunnerError(f"Error cargando TTL {ttl_path}: {e}") from e
    return g


def _has_any(graph: Graph, s: Any = None, p: Any = None, o: Any = None) -> bool:
    return next(graph.triples((s, p, o)), None) is not None


def apply_issue6_compat(graph: Graph, mode: str, verbose: bool) -> Dict[str, int]:
    """
    Compat layer (in-memory): NO modifica TTL ni .rq.
    Materializa lo mínimo para que el pack Issue-6 funcione sobre export.ttl:
      - bi:Project/bi:projectId
      - bi:Case/bi:caseId
      - bi:hasCase (Project -> Case)
      - bi:hasCaseMeasurement (Case -> Measurement)
      - bi:BioEntity typing (para q06)
    Deriva projectId/caseId desde IRIs de medición: expression/{gene}_{projectId}_{caseId}
    y/o desde bi:measuredCase.
    """
    if mode == "off":
        return {"applied": 0}

    BI = Namespace("http://example.org/biointegrate/")

    has_projects = _has_any(graph, None, RDF.type, BI.Project) or _has_any(graph, None, BI.projectId, None)
    has_cases = _has_any(graph, None, RDF.type, BI.Case) or _has_any(graph, None, BI.caseId, None)
    has_has_case = _has_any(graph, None, BI.hasCase, None)
    has_has_case_meas = _has_any(graph, None, BI.hasCaseMeasurement, None)
    has_bioentity = _has_any(graph, None, RDF.type, BI.BioEntity)
    has_expr = _has_any(graph, None, RDF.type, BI.ExpressionMeasurement)

    # auto: solo aplica si parece necesario
    if mode == "auto" and (has_projects and has_cases and has_has_case and has_has_case_meas and has_bioentity):
        return {"applied": 0}
    if not has_expr:
        return {"applied": 0}

    t0 = time.perf_counter()
    start_len = len(graph)

    created_projects = 0
    created_cases = 0
    added_has_case = 0
    added_case_in_project = 0
    added_has_case_meas = 0
    added_bioentity = 0

    seen_projects = set()
    seen_cases = set()
    case_to_project: Dict[URIRef, URIRef] = {}

    def _ensure_project(project_id: str) -> URIRef:
        nonlocal created_projects, added_bioentity
        project_uri = URIRef(BI[f"project/{project_id}"])
        if project_uri not in seen_projects:
            seen_projects.add(project_uri)
            graph.add((project_uri, RDF.type, BI.Project))
            # Añadimos literal plain y xsd:string para evitar líos de igualdad en rdflib
            graph.add((project_uri, BI.projectId, Literal(project_id)))
            graph.add((project_uri, BI.projectId, Literal(project_id, datatype=XSD.string)))
            graph.add((project_uri, RDF.type, BI.BioEntity))
            created_projects += 1
            added_bioentity += 1
        return project_uri

    def _ensure_case(case_uri: URIRef) -> URIRef:
        nonlocal created_cases, added_bioentity
        case_id = str(case_uri).rsplit("/", 1)[-1]
        if case_uri not in seen_cases:
            seen_cases.add(case_uri)
            graph.add((case_uri, RDF.type, BI.Case))
            graph.add((case_uri, BI.caseId, Literal(case_id)))
            graph.add((case_uri, BI.caseId, Literal(case_id, datatype=XSD.string)))
            graph.add((case_uri, RDF.type, BI.BioEntity))
            created_cases += 1
            added_bioentity += 1
        return case_uri

    # Recorre mediciones: deriva Project/Case + enlaces
    meas_i = 0
    for meas_uri in graph.subjects(RDF.type, BI.ExpressionMeasurement):
        meas_i += 1
        if verbose and meas_i % 50000 == 0:
            logging.info("compat_progress measurements=%d", meas_i)

        # (para q06)
        graph.add((meas_uri, RDF.type, BI.BioEntity))

        # Case desde measuredCase (preferible)
        case_obj = graph.value(meas_uri, BI.measuredCase)
        if isinstance(case_obj, URIRef):
            case_uri = case_obj
        else:
            # fallback: último token del ID de medición
            tail = str(meas_uri).rsplit("/", 1)[-1]
            try:
                _, case_id_tail = tail.rsplit("_", 1)
                case_uri = URIRef(BI[f"case/{case_id_tail}"])
            except Exception:
                continue

        case_uri = _ensure_case(case_uri)

        # Project desde IRI de medición: .../{gene}_{projectId}_{caseId}
        tail = str(meas_uri).rsplit("/", 1)[-1]
        project_id = None
        try:
            left, _ = tail.rsplit("_", 1)
            _, project_id = left.rsplit("_", 1)
        except Exception:
            project_id = None

        if project_id:
            project_uri = _ensure_project(project_id)

            prev = case_to_project.get(case_uri)
            if prev is None:
                case_to_project[case_uri] = project_uri
                graph.add((project_uri, BI.hasCase, case_uri))
                graph.add((case_uri, BI.caseInProject, project_uri))
                added_has_case += 1
                added_case_in_project += 1
            elif prev != project_uri and verbose:
                logging.warning("compat_conflict case=%s project_prev=%s project_new=%s", case_uri, prev, project_uri)

        # Inversa para q05
        graph.add((case_uri, BI.hasCaseMeasurement, meas_uri))
        added_has_case_meas += 1

    # Genes y proteínas como BioEntity (q06)
    for ent_type in (BI.Gene, BI.Protein):
        for ent in graph.subjects(RDF.type, ent_type):
            graph.add((ent, RDF.type, BI.BioEntity))
            added_bioentity += 1

    end_len = len(graph)
    duration_ms = int(round((time.perf_counter() - t0) * 1000))

    return {
        "applied": 1,
        "duration_ms": duration_ms,
        "added_triples": max(0, end_len - start_len),
        "created_projects": created_projects,
        "created_cases": created_cases,
        "added_hasCase": added_has_case,
        "added_caseInProject": added_case_in_project,
        "added_hasCaseMeasurement": added_has_case_meas,
        "added_bioentity_typed": added_bioentity,
    }



def run_one_query(
    graph: Graph,
    query_path: Path,
    out_dir: Path,
    formats: Tuple[str, ...],
    prefixes_available: Dict[str, str],
    dry_run: bool,
) -> QueryReport:
    q_text_raw = read_text(query_path)
    q_text = prepend_missing_prefixes(q_text_raw, prefixes_available)
    q_type = guess_query_type(q_text)

    query_name = safe_slug(query_path.stem)
    q_out_dir = out_dir / query_name
    ensure_dir(q_out_dir, dry_run=dry_run)

    t0 = time.perf_counter()
    outputs: List[str] = []
    ok = True
    err_msg: Optional[str] = None
    rows = 0
    cols_n = 0

    try:
        res = graph.query(q_text)

        # ASK
        if q_type == "ASK":
            # rdflib returns a boolean-like result
            try:
                answer = bool(getattr(res, "askAnswer", None))
            except Exception:
                # fallback: some versions use res.askAnswer
                answer = bool(res)  # type: ignore
            payload = {"type": "ASK", "query": query_path.name, "boolean": answer}
            out_json = q_out_dir / "result.json"
            write_json(out_json, payload, dry_run=dry_run)
            outputs.append(str(out_json))

        # SELECT
        elif q_type == "SELECT":
            cols, table = rdflib_result_to_table(graph, res)
            rows = len(table)
            cols_n = len(cols)

            if "json" in formats:
                out_json = q_out_dir / "result.json"
                write_json(out_json, {"columns": cols, "rows": table}, dry_run=dry_run)
                outputs.append(str(out_json))

            if "csv" in formats:
                out_csv = q_out_dir / "result.csv"
                export_select_csv(out_csv, cols, table, dry_run=dry_run)
                outputs.append(str(out_csv))

        # CONSTRUCT / DESCRIBE
        elif q_type in ("CONSTRUCT", "DESCRIBE"):
            # rdflib returns a Graph-like object for construct/describe
            out_graph = Graph()
            for prefix, ns in graph.namespace_manager.namespaces():
                out_graph.bind(prefix, ns)
            try:
                for triple in res:  # type: ignore
                    out_graph.add(triple)
            except Exception:
                # some rdflib versions: res.graph
                try:
                    out_graph = res.graph  # type: ignore
                except Exception as e:
                    raise QueryError(f"No se pudo materializar el grafo de salida ({q_type}): {e}") from e

            # "Rows/cols" for graph outputs: report triples count
            rows = len(out_graph)
            cols_n = 3

            out_ttl = q_out_dir / "result.ttl"
            if not dry_run:
                out_ttl.write_text(out_graph.serialize(format="turtle"), encoding="utf-8")
            outputs.append(str(out_ttl))

            if "json" in formats:
                # Minimal JSON summary (not full RDF dump)
                out_json = q_out_dir / "summary.json"
                write_json(out_json, {"type": q_type, "triples": rows}, dry_run=dry_run)
                outputs.append(str(out_json))

        else:
            # Fallback: attempt select-style if possible
            cols, table = rdflib_result_to_table(graph, res)
            rows = len(table)
            cols_n = len(cols)
            out_json = q_out_dir / "result.json"
            write_json(out_json, {"columns": cols, "rows": table}, dry_run=dry_run)
            outputs.append(str(out_json))

    except Exception as e:
        ok = False
        err_msg = str(e)

    t1 = time.perf_counter()
    duration_ms = int(round((t1 - t0) * 1000))

    return QueryReport(
        query_file=str(query_path),
        query_name=query_name,
        query_type=q_type,
        ok=ok,
        duration_ms=duration_ms,
        rows=rows,
        cols=cols_n,
        outputs=outputs,
        error=err_msg,
    )


def build_manifest(cfg: RunConfig, reports: List[QueryReport], graph: Graph) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp_utc": now,
        "cwd": str(Path.cwd()),
        "python": sys.version,
        "platform": platform.platform(),
        "rdflib_version": getattr(rdflib, "__version__", None),
        "input_ttl": str(cfg.paths.ttl_path),
        "queries_dir": str(cfg.paths.queries_dir),
        "out_dir": str(cfg.paths.out_dir),
        "query_count": len(reports),
        "triple_count": int(len(graph)),
        "reports": [asdict(r) for r in reports],
        "compat": {"mode": cfg.compat},
    }


def write_index_files(out_dir: Path, manifest: Dict[str, Any], dry_run: bool) -> None:
    ensure_dir(out_dir, dry_run=dry_run)

    index_json = out_dir / "index.json"
    write_json(index_json, manifest, dry_run=dry_run)

    # Lightweight human-readable index
    lines: List[str] = []
    lines.append("# RDFlib SPARQL Runner - Resumen\n")
    lines.append(f"- timestamp_utc: {manifest.get('timestamp_utc')}")
    lines.append(f"- input_ttl: `{manifest.get('input_ttl')}`")
    lines.append(f"- triple_count: {manifest.get('triple_count')}")
    lines.append(f"- queries_dir: `{manifest.get('queries_dir')}`")
    lines.append(f"- out_dir: `{manifest.get('out_dir')}`")
    lines.append("")
    lines.append("| query | type | ok | ms | rows | cols | outputs |")
    lines.append("|---|---:|:---:|---:|---:|---:|---|")

    for r in manifest.get("reports", []):
        outs = "<br/>".join([Path(p).name for p in r.get("outputs", [])]) or "-"
        lines.append(
            f"| {r.get('query_name')} | {r.get('query_type')} | "
            f"{'✅' if r.get('ok') else '❌'} | {r.get('duration_ms')} | "
            f"{r.get('rows')} | {r.get('cols')} | {outs} |"
        )

    index_md = out_dir / "index.md"
    write_text(index_md, "\n".join(lines) + "\n", dry_run=dry_run)


# -------------------------
# CLI
# -------------------------
def parse_args(argv: Optional[Sequence[str]] = None) -> RunConfig:
    p = argparse.ArgumentParser(
        prog="run_sparql.py",
        description="Run a pack of SPARQL queries (.rq) on an RDF graph (Turtle) using rdflib.",
    )
    p.add_argument("--ttl", default="data/rdf/export.ttl", help="Ruta al grafo RDF en Turtle (export.ttl).")
    p.add_argument("--queries", default="queries/sparql", help="Directorio con consultas .rq.")
    p.add_argument("--out", default="results/rdflib-sparql", help="Directorio de salida para resultados.")
    p.add_argument(
        "--prefixes",
        default=None,
        help="Fichero opcional con líneas PREFIX ... para inyectar (p.ej., queries/prefixes.sparql).",
    )
    p.add_argument(
    "--compat",
    choices=["off", "auto", "on"],
    default="auto",
    help="Compat en memoria (no toca TTL ni .rq). auto=solo si faltan Projects/Cases; on=forzar; off=desactivar.",
    )
    p.add_argument("--recursive", action="store_true", help="Buscar *.rq recursivamente.")
    p.add_argument(
        "--format",
        action="append",
        choices=["csv", "json"],
        default=[],
        help="Formato(s) de salida para SELECT. Repetible: --format csv --format json",
    )
    p.add_argument("--fail-fast", action="store_true", help="Abortar al primer error de consulta.")
    p.add_argument("--dry-run", action="store_true", help="No escribir ficheros en disco.")
    p.add_argument("--verbose", action="store_true", help="Más logging.")

    args = p.parse_args(argv)

    ttl_path = Path(args.ttl).expanduser().resolve()
    queries_dir = Path(args.queries).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    prefixes_path = Path(args.prefixes).expanduser().resolve() if args.prefixes else None

    formats = tuple(args.format) if args.format else ("csv", "json")

    paths = PathsConfig(
        ttl_path=ttl_path,
        queries_dir=queries_dir,
        out_dir=out_dir,
        prefixes_path=prefixes_path,
    )
    return RunConfig(
        paths=paths,
        formats=formats,
        recursive=bool(args.recursive),
        fail_fast=bool(args.fail_fast),
        dry_run=bool(args.dry_run),
        verbose=bool(args.verbose),
        compat=str(args.compat),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    cfg = parse_args(argv)
    setup_logging(cfg.verbose)

    logging.info("ttl=%s queries=%s out=%s dry_run=%s", cfg.paths.ttl_path, cfg.paths.queries_dir, cfg.paths.out_dir, cfg.dry_run)

    g = load_graph(cfg.paths.ttl_path)

    compat_report = apply_issue6_compat(g, mode=cfg.compat, verbose=cfg.verbose)
    logging.info("compat_applied=%s", compat_report.get("applied", 0))
    if compat_report.get("applied"):
        logging.info("compat_report=%s", compat_report)


    # Build prefixes: from graph + optional prefixes file
    extra_prefixes: Optional[Dict[str, str]] = None
    if cfg.paths.prefixes_path:
        extra_prefixes = parse_prefixes_from_file(cfg.paths.prefixes_path)
        logging.info("prefixes_file=%s prefixes_loaded=%d", cfg.paths.prefixes_path, len(extra_prefixes))

    prefixes_available = build_prefix_block(g, extra_prefixes=extra_prefixes)

    # Discover queries
    q_files = discover_queries(cfg.paths.queries_dir, recursive=cfg.recursive)
    if not q_files:
        raise ConfigError(f"No se encontraron consultas .rq en: {cfg.paths.queries_dir}")

    ensure_dir(cfg.paths.out_dir, dry_run=cfg.dry_run)

    reports: List[QueryReport] = []
    for qp in q_files:
        logging.info("running_query=%s", qp)
        rep = run_one_query(
            graph=g,
            query_path=qp,
            out_dir=cfg.paths.out_dir,
            formats=cfg.formats,
            prefixes_available=prefixes_available,
            dry_run=cfg.dry_run,
        )
        reports.append(rep)

        if not rep.ok:
            logging.error("query_failed=%s error=%s", rep.query_name, rep.error)
            if cfg.fail_fast:
                break

    manifest = build_manifest(cfg, reports, g)
    write_index_files(cfg.paths.out_dir, manifest, dry_run=cfg.dry_run)

    # Exit code: 0 if all ok, else 1
    all_ok = all(r.ok for r in reports) and len(reports) == len(q_files)
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunnerError as e:
        logging.error("runner_error=%s", e)
        raise SystemExit(2)