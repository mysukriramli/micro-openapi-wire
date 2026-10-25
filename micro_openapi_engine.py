import os
import json
import hashlib
import duckdb
import requests
import yaml
from datetime import datetime, timezone

DB_FILE = "data/micro_openapi.db"
HISTORY_DIR = "data/history"
EXPORT_DIR = "public"
API_DIR = os.path.join(EXPORT_DIR, "v1")

TARGET_APIS = {
    "github_rest_api": "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json",
    "stripe_api": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
    "cloudflare_api": "https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.json",
    "kubernetes_api": "https://raw.githubusercontent.com/kubernetes/kubernetes/master/api/openapi-spec/swagger.json"
}

def compute_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def simplify_schema(schema: dict) -> str:
    """Recursively resolves OpenAPI data types down to ultra-dense strings."""
    if not isinstance(schema, dict):
        return "any"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    
    t = schema.get("type", "any")
    
    if t == "object":
        props = schema.get("properties", {})
        if not props:
            return "dict"
        simplified_props = {}
        for k, v in props.items():
            simplified_props[k] = simplify_schema(v)
        return simplified_props
    elif t == "array":
        items = schema.get("items", {})
        return f"[{simplify_schema(items)}]"
    else:
        return t

def prune_openapi(spec: dict) -> dict:
    """Strips all human descriptions, examples, and metadata from an OpenAPI AST."""
    micro_spec = {}
    paths = spec.get("paths", {})
    
    for path, methods in paths.items():
        if path.startswith("/"):
            micro_spec[path] = {}
        
        for method, operation in methods.items():
            if method not in ["get", "post", "put", "patch", "delete"]:
                continue
                
            sig = {"req": {}, "res": {}}
            
            # Prune Parameters
            params = operation.get("parameters", [])
            for p in params:
                if isinstance(p, dict) and "name" in p:
                    req_type = "opt" if not p.get("required", False) else "req"
                    schema_type = simplify_schema(p.get("schema", {}))
                    sig["req"][p["name"]] = f"({p.get('in', 'query')}:{req_type}) {schema_type}"
                    
            # Prune Request Body
            req_body = operation.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                json_body = content.get("application/json", {}).get("schema", {})
                if json_body:
                    sig["req"]["BODY"] = simplify_schema(json_body)
                    
            # Prune Responses (Focus on 200/201 Success paths only)
            responses = operation.get("responses", {})
            success_res = responses.get("200") or responses.get("201") or {}
            res_content = success_res.get("content", {}).get("application/json", {}).get("schema", {})
            if res_content:
                sig["res"] = simplify_schema(res_content)
                
            micro_spec[path][method.upper()] = sig
            
    return micro_spec
def fetch_spec(url: str) -> dict:
    headers = {"User-Agent": "MicroOpenAPIWire/1.0 (Machine-First Token Optimizer)"}
    try:
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "yaml" in content_type or url.endswith(".yaml") or url.endswith(".yml"):
                return yaml.safe_load(resp.text)
            return resp.json()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
    return {}

def build_static_api(conn):
    os.makedirs(os.path.join(API_DIR, "schemas"), exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cur = conn.execute("SELECT api_name, original_size_bytes, minified_size_bytes, token_reduction_pct, last_updated_utc, minified_json FROM api_schemas")
    rows = cur.fetchall()
    
    catalog = []
    lines = [
        "# Micro-OpenAPI Pruned Schema Wire",
        f"> Last Sync: {now_iso} UTC",
        "> Optimization: Verbose descriptions, examples, and metadata stripped (Avg 85-95% token savings).",
        "",
        "## Available Micro-Schemas"
    ]
    
    for row in rows:
        name, orig_sz, min_sz, reduction, updated, min_json = row
        catalog.append({
            "api_name": name,
            "original_bytes": orig_sz,
            "minified_bytes": min_sz,
            "token_reduction_pct": round(reduction, 2),
            "updated_utc": updated,
            "endpoint": f"v1/schemas/{name}.min.json"
        })
        
        # Write individual minified JSON spec
        with open(os.path.join(API_DIR, "schemas", f"{name}.min.json"), "w", encoding="utf-8") as f:
            f.write(min_json)
            
        lines.append(f"- **{name}**: {reduction:.1f}% reduction ({orig_sz // 1024} KB -> {min_sz // 1024} KB) | Endpoint: `v1/schemas/{name}.min.json`")

    with open(os.path.join(API_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"metadata": {"updated_at": now_iso, "count": len(catalog)}, "apis": catalog}, f, indent=2)

    with open(os.path.join(EXPORT_DIR, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    html = f"""<!DOCTYPE html><html><head><title>Micro-OpenAPI Wire</title></head>
    <body style='font-family:system-ui,sans-serif;max-width:850px;margin:2rem auto;line-height:1.6;padding:0 1rem;'>
    <h1>⚡ Micro-OpenAPI Pruned Wire</h1>
    <p>Ultra-dense, token-pruned API function signatures for autonomous LLM agents.</p>
    <h3>Machine Feeds</h3>
    <ul>
      <li><a href='v1/index.json'>/v1/index.json</a> (Catalog &amp; Token Metrics)</li>
      <li><a href='llms.txt'>llms.txt</a> (Token-Efficient LLM Digest)</li>
      <li><a href='schemas.parquet'>schemas.parquet</a> (Columnar Parquet Snapshot)</li>
    </ul>
    <h3>Pruned Specs</h3>
    <ul>
      {"".join([f"<li><a href='v1/schemas/{c['api_name']}.min.json'>{c['api_name']}.min.json</a> ({c['token_reduction_pct']}% smaller)</li>" for c in catalog])}
    </ul>
    </body></html>"""
    with open(os.path.join(EXPORT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

def run():
    os.makedirs("data", exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    conn = duckdb.connect(DB_FILE)
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.execute(f.read())

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")

    month_dir = os.path.join(HISTORY_DIR, year_str, month_str)
    os.makedirs(month_dir, exist_ok=True)
    daily_history_file = os.path.join(month_dir, f"{date_str}.jsonl")

    conn.execute("BEGIN TRANSACTION")

    for api_name, url in TARGET_APIS.items():
        spec = fetch_spec(url)
        if not spec:
            continue

        orig_json = json.dumps(spec)
        orig_size = len(orig_json.encode("utf-8"))

        pruned = prune_openapi(spec)
        min_json = json.dumps(pruned, separators=(",", ":"))
        min_size = len(min_json.encode("utf-8"))

        reduction_pct = ((orig_size - min_size) / orig_size) * 100.0 if orig_size > 0 else 0.0
        content_hash = hashlib.sha256(min_json.encode("utf-8")).hexdigest()

        existing = conn.execute(f"SELECT content_hash FROM api_schemas WHERE api_name = '{api_name}'").fetchone()

        escaped_min_json = min_json.replace("'", "''")

        if not existing:
            conn.execute(f"""
                INSERT INTO api_schemas (
                    api_name, source_url, original_size_bytes, minified_size_bytes,
                    token_reduction_pct, minified_json, content_hash, last_updated_utc
                ) VALUES (
                    '{api_name}', '{url}', {orig_size}, {min_size},
                    {reduction_pct}, '{escaped_min_json}', '{content_hash}', '{now_iso}'
                )
            """)

            commit_id = conn.execute("SELECT nextval('seq_commit_id')").fetchone()[0]
            conn.execute(f"""
                INSERT INTO ledger (commit_id, timestamp_utc, operation, api_name, endpoint_drift_summary)
                VALUES ({commit_id}, '{now_iso}', 'INIT_SCHEMA', '{api_name}', 'Initial pruned schema generated')
            """)

            ledger_entry = {
                "commit_id": commit_id,
                "timestamp_utc": now_iso,
                "operation": "INIT_SCHEMA",
                "api_name": api_name,
                "original_bytes": orig_size,
                "minified_bytes": min_size,
                "reduction_pct": reduction_pct,
                "content_hash": content_hash
            }
            with open(daily_history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(ledger_entry) + "\n")

        elif existing[0] != content_hash:
            conn.execute(f"""
                UPDATE api_schemas SET
                    original_size_bytes = {orig_size},
                    minified_size_bytes = {min_size},
                    token_reduction_pct = {reduction_pct},
                    minified_json = '{escaped_min_json}',
                    content_hash = '{content_hash}',
                    last_updated_utc = '{now_iso}'
                WHERE api_name = '{api_name}'
            """)

            commit_id = conn.execute("SELECT nextval('seq_commit_id')").fetchone()[0]
            conn.execute(f"""
                INSERT INTO ledger (commit_id, timestamp_utc, operation, api_name, endpoint_drift_summary)
                VALUES ({commit_id}, '{now_iso}', 'SCHEMA_DRIFT', '{api_name}', 'Endpoint signatures updated')
            """)

            ledger_entry = {
                "commit_id": commit_id,
                "timestamp_utc": now_iso,
                "operation": "SCHEMA_DRIFT",
                "api_name": api_name,
                "original_bytes": orig_size,
                "minified_bytes": min_size,
                "reduction_pct": reduction_pct,
                "content_hash": content_hash
            }
            with open(daily_history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(ledger_entry) + "\n")

    conn.execute("COMMIT")

    conn.execute(f"COPY (SELECT api_name, source_url, original_size_bytes, minified_size_bytes, token_reduction_pct, content_hash, last_updated_utc FROM api_schemas) TO '{EXPORT_DIR}/schemas.parquet' (FORMAT PARQUET)")
    build_static_api(conn)
    conn.close()

if __name__ == "__main__":
    run()

