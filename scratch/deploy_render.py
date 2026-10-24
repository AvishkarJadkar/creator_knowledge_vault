"""Create the Render web service for Vaulty and wait for the first deploy.

Reads secrets from the local .env file (never printed). Requires:
  RENDER_API_KEY  - Render API key
  DATABASE_URL    - Neon connection string

Usage:
  python scratch/deploy_render.py
"""
import json
import os
import secrets
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

API = "https://api.render.com/v1"
OWNER_ID = "tea-d6c7c43nv86c73ct0cc0"
SERVICE_NAME = "vaulty"
REPO = "https://github.com/AvishkarJadkar/creator_knowledge_vault"
BRANCH = "main"
REGION = "singapore"
PLAN = "free"

ROOT = Path(__file__).resolve().parent.parent
env = dotenv_values(ROOT / ".env")

token = os.environ["RENDER_API_KEY"]
database_url = os.environ["DATABASE_URL"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def call(method, path, **kwargs):
    resp = requests.request(method, API + path, headers=headers, timeout=90, **kwargs)
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    return resp.status_code, body


def env_var(key, value, generate=False):
    item = {"key": key}
    if generate:
        item["generateValue"] = True
    else:
        item["value"] = value
    return item


def build_env_vars():
    required = {
        "FLASK_ENV": "production",
        "PYTHON_VERSION": "3.11.6",
        "DATABASE_URL": database_url,
    }
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "FIREBASE_API_KEY"):
        value = env.get(key)
        if not value:
            sys.exit(f"{key} is missing from .env")
        required[key] = value
    for key in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
        if env.get(key):
            required[key] = env[key]
    vars_ = [env_var(k, v) for k, v in required.items()]
    vars_.append(env_var("SECRET_KEY", secrets.token_urlsafe(48)))
    return vars_


def find_service():
    status, body = call("GET", "/services?limit=100")
    if status != 200:
        sys.exit(f"listing services failed: {status} {body}")
    for entry in body:
        svc = entry.get("service", entry)
        if svc.get("name") == SERVICE_NAME:
            return svc
    return None


def create_service():
    payload = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "ownerId": OWNER_ID,
        "repo": REPO,
        "branch": BRANCH,
        "autoDeploy": "yes",
        "envVars": build_env_vars(),
        "serviceDetails": {
            "env": "python",
            "plan": PLAN,
            "region": REGION,
            "healthCheckPath": "/health",
            "numInstances": 1,
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": (
                    "gunicorn app:app --bind 0.0.0.0:$PORT "
                    "--workers 1 --threads 8 --timeout 120 --preload"
                ),
            },
        },
    }
    status, body = call("POST", "/services", data=json.dumps(payload))
    if status not in (200, 201):
        sys.exit(f"create service failed: {status} {json.dumps(body)[:1200]}")
    return body.get("service", body)


def latest_deploy(service_id):
    status, body = call("GET", f"/services/{service_id}/deploys?limit=1")
    if status != 200 or not body:
        return None
    entry = body[0]
    return entry.get("deploy", entry)


def main():
    svc = find_service()
    if svc:
        print(f"service already exists: {svc['id']} ({svc.get('suspended')=})")
    else:
        print("creating service ...")
        svc = create_service()
        print(f"created service: {svc['id']}")

    service_id = svc["id"]
    url = (svc.get("serviceDetails") or {}).get("url") or f"https://{SERVICE_NAME}.onrender.com"
    print(f"url: {url}")

    print("waiting for deploy ...")
    deadline = time.time() + 15 * 60
    last = None
    while time.time() < deadline:
        deploy = latest_deploy(service_id)
        if deploy:
            state = deploy.get("status")
            if state != last:
                print(f"  deploy {deploy.get('id')}: {state}")
                last = state
            if state == "live":
                print("deploy is live")
                break
            if state in ("build_failed", "update_failed", "canceled", "deactivated"):
                print(f"deploy failed: {state}")
                print(json.dumps(deploy, indent=2)[:2000])
                sys.exit(1)
        time.sleep(15)
    else:
        print("timed out waiting for deploy")
        sys.exit(1)

    print(json.dumps({"serviceId": service_id, "url": url}, indent=2))


if __name__ == "__main__":
    main()
