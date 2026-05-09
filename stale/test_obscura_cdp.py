#!/usr/bin/env python3
"""Test script: Use obscura CDP server via raw websockets to intercept AH GraphQL calls."""

import asyncio
import json
import websockets


class CDPClient:
    """Simple CDP client using websockets."""
    
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.id = 0
        self.listeners = {}
    
    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)
        print(f"Connected to CDP: {self.ws_url}")
    
    async def send(self, method, **params):
        self.id += 1
        msg = {"id": self.id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        return self.id
    
    async def recv(self):
        msg = await self.ws.recv()
        return json.loads(msg)
    
    async def execute(self, method, **params):
        """Send a command and wait for the response with matching id."""
        msg_id = self.id + 1
        msg = {"id": msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        
        # Wait for response
        while True:
            resp = await self.recv()
            if resp.get("id") == msg_id:
                return resp
    
    async def listen(self, max_events=100):
        """Listen for events."""
        events = []
        for _ in range(max_events):
            msg = await self.recv()
            if "method" in msg and "id" not in msg:
                events.append(msg)
                method = msg["method"]
                print(f"[EVENT] {method}: {json.dumps(msg.get('params', {}))[:200]}")
            elif "id" in msg:
                # It's a response, put it back
                return events, msg
        return events, None


async def main():
    # Connect to browser
    client = CDPClient("ws://127.0.0.1:9222/devtools/browser")
    await client.connect()
    
    # Get existing tabs or create new one
    resp = await client.execute("Target.getTargets")
    print(f"Targets: {json.dumps(resp, indent=2)[:500]}")
    
    # Create a new target
    resp = await client.execute("Target.createTarget", url="about:blank")
    target_id = resp.get("result", {}).get("targetId")
    print(f"Created target: {target_id}")
    
    # Get the websocket URL for this target
    resp = await client.execute("Target.getTargets")
    for t in resp.get("result", {}).get("targetInfos", []):
        if t.get("targetId") == target_id:
            target_ws = t.get("webSocketDebuggerUrl")
            break
    
    if not target_ws:
        print("Could not find target websocket URL")
        return
    
    print(f"Target WS: {target_ws}")
    
    # Connect to the target
    tab = CDPClient(target_ws)
    await tab.connect()
    
    # Enable Network domain to capture requests
    await tab.execute("Network.enable")
    
    # Navigate to AH
    print("\n=== Navigating to https://www.ah.nl ===")
    await tab.execute("Page.navigate", url="https://www.ah.nl")
    
    # Collect network events
    print("\n=== Collecting network events (15s) ===")
    network_events = []
    
    for _ in range(200):
        try:
            msg = await asyncio.wait_for(tab.recv(), timeout=15)
            if "method" in msg and "id" not in msg:
                method = msg["method"]
                params = msg.get("params", {})
                if method.startswith("Network."):
                    url = params.get("request", {}).get("url", "") or params.get("response", {}).get("url", "")
                    if url:
                        status = params.get("response", {}).get("status", "?")
                        print(f"  [{status}] {url[:120]}")
                        network_events.append(msg)
        except asyncio.TimeoutError:
            print("Timeout - stopping event collection")
            break
    
    # Now evaluate JS to find GraphQL config
    print("\n=== Evaluating JS to find GraphQL client ===")
    
    result = await tab.execute("Runtime.evaluate", expression="""
        (function() {
            try {
                var el = document.querySelector('script[id=__NEXT_DATA__]');
                if (el) {
                    var data = JSON.parse(el.textContent);
                    return JSON.stringify({
                        buildId: data.buildId,
                        hasRuntimeConfig: !!data.runtimeConfig,
                        hasPublicConfig: !!data.publicRuntimeConfig,
                        publicConfig: data.publicRuntimeConfig || {},
                    });
                }
            } catch(e) {}
            return 'no __NEXT_DATA__';
        })()
    """)
    print(f"NEXT_DATA: {json.dumps(result.get('result', {}), indent=2)[:2000]}")
    
    # Check for fetch/XHR interception
    result = await tab.execute("Runtime.evaluate", expression="""
        (function() {
            var keys = Object.keys(window).filter(function(k) {
                return ['__APOLLO_CLIENT__', '__APOLLO__', 'apollo', 'gql', 'graphql', 
                        '__GRAPHQL__', 'client', '__CLIENT__'].some(function(v) {
                            return k.toLowerCase().includes(v);
                        });
            });
            return JSON.stringify(keys.slice(0, 20));
        })()
    """)
    print(f"GraphQL keys: {result.get('result', {}).get('value', 'none')}")
    
    # Navigate to a product page
    print("\n=== Navigating to product page ===")
    await tab.execute("Page.navigate", url="https://www.ah.nl/product/3000000000000")
    
    for _ in range(100):
        try:
            msg = await asyncio.wait_for(tab.recv(), timeout=10)
            if "method" in msg and "id" not in msg:
                method = msg["method"]
                params = msg.get("params", {})
                if method.startswith("Network."):
                    url = params.get("request", {}).get("url", "") or params.get("response", {}).get("url", "")
                    if url:
                        status = params.get("response", {}).get("status", "?")
                        print(f"  [{status}] {url[:120]}")
        except asyncio.TimeoutError:
            break
    
    # Close
    await tab.ws.close()
    await client.ws.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
