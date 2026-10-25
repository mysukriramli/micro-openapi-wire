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
