#!/usr/bin/env python3
"""Use obscura CDP to intercept AH GraphQL calls."""

import asyncio
import json
import websockets


async def main():
    # Connect directly to obscura CDP server
    uri = "ws://127.0.0.1:9222/devtools/browser"
    
    async with websockets.connect(uri) as ws:
        print(f"Connected to {uri}")
        
        # Init
        await ws.send(json.dumps({"__init": True}))
        resp = await ws.recv()
        print(f"Init: {resp}")
        
        # Enable Page domain
        msg_id = 1
        await ws.send(json.dumps({"id": msg_id, "method": "Page.enable"}))
        resp = await ws.recv()
        print(f"Page.enable: {resp}")
        
        # Enable Network domain
        msg_id = 2
        await ws.send(json.dumps({"id": msg_id, "method": "Network.enable"}))
        resp = await ws.recv()
        print(f"Network.enable: {resp}")
        
        # Navigate to AH
        msg_id = 3
        await ws.send(json.dumps({"id": msg_id, "method": "Page.navigate", "params": {"url": "https://www.ah.nl"}}))
        
        # Collect events for 20 seconds
        print("\n=== Collecting events ===")
        pending = {msg_id: None}  # Track pending responses
        gql_requests = []
        
        for _ in range(500):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                
                if "id" in msg:
                    # Response
                    if msg["id"] in pending:
                        print(f"[RESP {msg['id']}]: {json.dumps(msg).get('result', {}) if 'result' in msg else msg.get('error', {})}")
                        del pending[msg["id"]]
                elif "method" in msg:
                    # Event
                    method = msg["method"]
                    params = msg.get("params", {})
                    
                    if method == "Network.requestWillBeSent":
                        req = params.get("request", {})
                        url = req.get("url", "")
                        if "gql" in url or "graphql" in url:
                            print(f"\n*** GraphQL Request Found! ***")
                            print(f"  URL: {url}")
                            print(f"  Method: {req.get('method')}")
                            print(f"  Headers: {json.dumps(req.get('headers', {}), indent=2)}")
                            post_data = req.get("postData", "")
                            if post_data:
                                print(f"  Body: {post_data[:500]}")
                            gql_requests.append(params)
                    elif method == "Network.responseReceived":
                        resp_info = params.get("response", {})
                        url = resp_info.get("url", "")
                        if "gql" in url:
                            print(f"\n*** GraphQL Response ***")
                            print(f"  Status: {resp_info.get('status')}")
                            print(f"  URL: {url}")
                    elif method == "Network.loadingFinished":
                        pass  # Ignore
                    elif method == "Page.loadEventFired":
                        print("[Page loaded]")
                    elif method == "Page.frameNavigated":
                        frame = params.get("frame", {})
                        print(f"[Frame navigated: {frame.get('url', '')}]")
                    else:
                        print(f"[{method}]")
                        
            except asyncio.TimeoutError:
                print("\nTimeout - stopping")
                break
        
        print(f"\n=== Found {len(gql_requests)} GraphQL requests ===")
        
        # Now try to evaluate JS to find Apollo client
        msg_id = 4
        await ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "Object.keys(window).filter(k => k.toLowerCase().includes('apollo') || k.toLowerCase().includes('gql')).join(',')",
                "awaitPromise": True
            }
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if "id" in resp and resp["id"] == msg_id:
                result = resp.get("result", {})
                print(f"\nApollo keys: {result.get('value', 'none')}")
        except:
            pass
        
        # Try to get __NEXT_DATA__
        msg_id = 5
        await ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": """
                    (function() {
                        var scripts = document.querySelectorAll('script');
                        for (var i = 0; i < scripts.length; i++) {
                            if (scripts[i].id === '__NEXT_DATA__') {
                                return scripts[i].textContent.substring(0, 2000);
                            }
                        }
                        return 'NOT_FOUND';
                    })()
                """,
                "awaitPromise": False
            }
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if "id" in resp and resp["id"] == msg_id:
                result = resp.get("result", {})
                val = result.get("value", "none")
                print(f"\nNEXT_DATA: {val[:500] if val else 'none'}")
        except:
            pass


if __name__ == "__main__":
    # Start obscura server first
    import subprocess
    import time
    
    print("Starting obscura server...")
    proc = subprocess.Popen(
        ["obscura", "serve", "--port", "9222", "--stealth"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(2)
    
    try:
        asyncio.run(main())
    finally:
        proc.terminate()
        proc.wait()
