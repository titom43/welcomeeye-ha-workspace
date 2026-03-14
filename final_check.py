import asyncio
import json
import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import http.client
import ssl

class MockSession:
    def __init__(self, ssl_context):
        self.cookies = {}
        self.ssl_context = ssl_context
    async def request(self, method, url, data=None, headers=None, ssl=None, timeout=None):
        parsed = urlparse(url)
        print(f"\n[HTTP] {method} {url}")
        try:
            conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout, context=self.ssl_context)
            if self.cookies:
                if headers is None: headers = {}
                headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            conn.request(method, parsed.path + (f"?{parsed.query}" if parsed.query else ""), body=data, headers=headers)
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            cookie_header = resp.getheader("Set-Cookie")
            if cookie_header:
                for part in cookie_header.split(";"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        self.cookies[k.strip()] = v.strip()
            class MockResponse:
                def __init__(self, status, text, cookies):
                    self.status, self._text, self.cookies = status, text, cookies
                async def text(self): return self._text
            return MockResponse(resp.status, body, self.cookies)
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            raise

async def test_full_flow():
    from custom_components.welcomeeye.api import WelcomeEyeClient
    from custom_components.welcomeeye.const import (
        CONF_AUTH_ACCOUNT, CONF_AUTH_PASSWORD, CONF_AUTH_BASE_URL, 
        CONF_VERIFY_SSL, CONF_AUTH_MODE, CONF_AUTH_TYPE, CONF_IP_REGION_ID,
        CONF_SCHEME, CONF_DEVICE_HOST, CONF_CGI_PORT, CONF_USERNAME, CONF_DEVICE_PASSWORD,
        CONF_DOOR, CONF_SECURITY, CONF_HS_DEVICE, CONF_AUTH_CODE
    )
    with open("test_bundle.json", "r") as f:
        bundle = json.load(f)
    config = {
        CONF_AUTH_ACCOUNT: bundle["auth_account"],
        CONF_AUTH_PASSWORD: bundle["auth_password"],
        CONF_AUTH_BASE_URL: "https://shi-19-sec.qvcloud.net",
        CONF_AUTH_MODE: "user",
        CONF_AUTH_TYPE: bundle.get("auth_type", 0),
        CONF_IP_REGION_ID: bundle.get("ip_region_id", 0),
        CONF_AUTH_CODE: "",
        CONF_DEVICE_HOST: "127.0.0.1",
        CONF_CGI_PORT: 443,
        CONF_SCHEME: "https",
        CONF_VERIFY_SSL: False,
    }
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    client = WelcomeEyeClient(MockSession(ssl_context), config)
    print("--- STARTING TEST ---")
    if await client.login_auth():
        print(f"✅ Auth Success: {client._auth_session_id}")
        if await client.login_alarm():
            print(f"✅ Alarm Success: {client._alarm_session_id}")
            items = await client.query_alarm_list()
            if items:
                print(f"✅ Query Success: {len(items)} items")
                print(f"Latest: {items[0]['time']} - {items[0]['event']}")
    else:
        print("❌ Auth Failed")

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path.cwd()))
    asyncio.run(test_full_flow())
