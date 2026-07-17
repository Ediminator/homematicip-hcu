#!/usr/bin/env python3
"""
HCU Endpoint Discovery Tool
Probes the Homematic IP HCU to discover App User WebSocket and REST endpoints.

Usage:
  python3 hcu_probe.py <hcu_ip> <app_token> [sgtin] [plugin_token]

Example:
  python3 hcu_probe.py 10.121.121.202 AABBCC112233... 3014F711A0001234ABCD5678

Run this on any machine in the same network as the HCU (e.g., the HA host).
"""

import asyncio
import aiohttp
import hashlib
import json
import ssl
import sys
from dataclasses import dataclass, field
from typing import Optional

# ── Configuration ──────────────────────────────────────────────────────────────

HCU_HOST    = "10.121.121.202"
APP_TOKEN   = ""   # App User token (paste from HA config entry CONF_TOKEN or CONF_APP_TOKEN)
SGTIN       = ""   # HCU SGTIN / accessPointId (24 hex chars, e.g. 3014F711A0004EE269960815)
PLUGIN_TOKEN = ""  # Plugin User token (optional, for comparison)
PLUGIN_ID    = "de.homeassistant.hcu.integration"

# Ports to probe for open TCP
PORTS = [80, 443, 6969, 8080, 8443, 8888, 9001, 9002, 9443, 3000, 8765, 48335]

# REST paths to probe (POST + GET)
REST_PATHS = [
    "/hmip/getHost",
    "/hmip/auth/getHost",
    "/getHost",
    "/hmip/home/getCurrentState",   # App User state endpoint (cloud lib uses this)
    "/hmip/home/getSystemState",    # Plugin User WebSocket path (may also work via REST)
    "/hmip/home",
    "/hmip/",
    "/",
]

# WebSocket paths to probe
WS_PATHS = [
    "",          # wss://host:port  (bare)
    "/ws",
    "/hmip/ws",
    "/websocket",
    "/hmip",
]

# ── Helpers ─────────────────────────────────────────────────────────────────────

def client_auth(sgtin: str) -> str:
    return hashlib.sha512(
        (sgtin + "jiLpVitHvWnIGD1yo7MA").encode()
    ).hexdigest().upper()


def ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def ok(s): return f"\033[92m{s}\033[0m"
def warn(s): return f"\033[93m{s}\033[0m"
def err(s): return f"\033[91m{s}\033[0m"
def bold(s): return f"\033[1m{s}\033[0m"

# ── Port scan ────────────────────────────────────────────────────────────────────

async def port_open(host: str, port: int) -> bool:
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.5)
        w.close()
        try:
            await w.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


# ── REST probe ───────────────────────────────────────────────────────────────────

async def probe_rest(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict,
    body: Optional[dict] = None,
) -> tuple[Optional[int], str]:
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        if body is not None:
            async with session.post(url, headers=headers, json=body, ssl=ssl_ctx(), timeout=timeout) as r:
                text = await r.text()
                return r.status, text[:300].replace("\n", " ")
        else:
            async with session.get(url, headers=headers, ssl=ssl_ctx(), timeout=timeout) as r:
                text = await r.text()
                return r.status, text[:300].replace("\n", " ")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


# ── WebSocket probe ──────────────────────────────────────────────────────────────

async def probe_ws(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict,
) -> tuple[bool, str]:
    try:
        ws = await asyncio.wait_for(
            session.ws_connect(url, headers=headers, ssl=ssl_ctx(), heartbeat=5),
            timeout=5,
        )
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=2)
            detail = f"type={msg.type.name} data={str(msg.data)[:120]}"
        except asyncio.TimeoutError:
            detail = "connected, no initial message"
        await ws.close()
        return True, detail
    except aiohttp.WSServerHandshakeError as e:
        return False, f"WS handshake HTTP {e.status}: {str(e.message)[:120]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"


# ── Main ─────────────────────────────────────────────────────────────────────────

async def main(host: str, app_token: str, sgtin: str, plugin_token: str):
    ca = client_auth(sgtin) if sgtin else ""

    print(bold(f"\n{'='*60}"))
    print(bold(f"  HCU Endpoint Probe  →  {host}"))
    print(bold(f"{'='*60}"))
    print(f"  app_token  : {'✓ set' if app_token else '✗ NOT SET'}")
    print(f"  sgtin      : {sgtin or '✗ NOT SET'}")
    print(f"  client_auth: {ca[:16]}...  (first 16 chars)" if ca else "  client_auth: ✗ (no sgtin)")
    print(f"  plugin_tok : {'✓ set' if plugin_token else '—'}")

    # ── Header sets to try ───────────────────────────────────────────────────
    header_sets = {}
    if app_token and ca and sgtin:
        header_sets["App (AUTHTOKEN+CLIENTAUTH+ACCESSPOINT-ID)"] = {
            "AUTHTOKEN": app_token,
            "CLIENTAUTH": ca,
            "ACCESSPOINT-ID": sgtin,
            "VERSION": "12",
        }
        header_sets["App (AUTHTOKEN only)"] = {
            "AUTHTOKEN": app_token,
            "VERSION": "12",
        }
    if plugin_token:
        header_sets["Plugin (authtoken+plugin-id)"] = {
            "authtoken": plugin_token,
            "plugin-id": PLUGIN_ID,
            "hmip-system-events": "true",
        }

    gethost_body = {
        "clientCharacteristics": {
            "apiVersion": "10",
            "applicationIdentifier": "homematicip-hcu",
            "applicationVersion": "1.0",
            "deviceManufacturer": "none",
            "deviceType": "Computer",
            "language": "en_US",
            "osType": "Linux",
            "osVersion": "",
        },
        "id": sgtin or "",
    }

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # ── 1. Port scan ─────────────────────────────────────────────────────
        print(bold(f"\n{'─'*60}"))
        print(bold("  1. PORT SCAN"))
        print(bold(f"{'─'*60}"))
        open_ports = []
        tasks = {p: port_open(host, p) for p in PORTS}
        results = await asyncio.gather(*tasks.values())
        for port, is_open in zip(tasks.keys(), results):
            status = ok("OPEN") if is_open else err("closed")
            print(f"  :{port:<6} {status}")
            if is_open:
                open_ports.append(port)
        print(f"\n  Open ports: {open_ports}")

        # ── 2. REST probes on open ports ─────────────────────────────────────
        print(bold(f"\n{'─'*60}"))
        print(bold("  2. REST ENDPOINTS (GET + POST)"))
        print(bold(f"{'─'*60}"))

        for port in open_ports:
            scheme = "https" if port in (443, 6969, 8443, 9443) else "http"
            print(f"\n  Port {port} ({scheme})")
            for path in REST_PATHS:
                url = f"{scheme}://{host}:{port}{path}"
                for hname, hdrs in header_sets.items():
                    # GET
                    status, body_txt = await probe_rest(session, url, hdrs)
                    flag = ok(str(status)) if status and status < 400 else (warn(str(status)) if status else err("ERR"))
                    print(f"    GET  {path:<35} [{hname[:25]:<25}] → {flag}  {body_txt[:80]}")
                    # POST with appropriate body
                    post_body = None
                    if "getHost" in path or path == "/":
                        post_body = gethost_body
                    elif "getCurrentState" in path or "getSystemState" in path:
                        post_body = gethost_body  # clientCharacteristics + id
                    if post_body is not None:
                        status, body_txt = await probe_rest(session, url, hdrs, post_body)
                        flag = ok(str(status)) if status and status < 400 else (warn(str(status)) if status else err("ERR"))
                        print(f"    POST {path:<35} [{hname[:25]:<25}] → {flag}  {body_txt[:80]}")

        # ── 3. WebSocket probes on open ports ─────────────────────────────────
        print(bold(f"\n{'─'*60}"))
        print(bold("  3. WEBSOCKET ENDPOINTS"))
        print(bold(f"{'─'*60}"))

        for port in open_ports:
            scheme = "wss" if port in (443, 6969, 8443, 9001, 9443) else "ws"
            print(f"\n  Port {port} ({scheme})")
            for path in WS_PATHS:
                url = f"{scheme}://{host}:{port}{path}"
                for hname, hdrs in header_sets.items():
                    connected, detail = await probe_ws(session, url, hdrs)
                    flag = ok("✓ CONNECTED") if connected else err("✗ failed")
                    print(f"    {url:<50} [{hname[:25]:<25}] → {flag}")
                    print(f"      {detail}")

    print(bold(f"\n{'='*60}\n"))


if __name__ == "__main__":
    args = sys.argv[1:]
    host         = args[0] if len(args) > 0 else HCU_HOST
    app_token    = args[1] if len(args) > 1 else APP_TOKEN
    sgtin        = args[2] if len(args) > 2 else SGTIN
    plugin_token = args[3] if len(args) > 3 else PLUGIN_TOKEN

    if not host:
        print(f"Usage: {sys.argv[0]} <hcu_ip> <app_token> [sgtin] [plugin_token]")
        sys.exit(1)

    asyncio.run(main(host, app_token, sgtin, plugin_token))
