import asyncio
import json
import sys
import logging
from aiohttp import ClientSession
from pathlib import Path

# Add component path to sys.path
sys.path.append(str(Path.cwd()))

from custom_components.welcomeeye.api import WelcomeEyeClient
from custom_components.welcomeeye.const import (
    CONF_AUTH_ACCOUNT, CONF_AUTH_PASSWORD, CONF_AUTH_BASE_URL, 
    CONF_VERIFY_SSL, CONF_AUTH_MODE, CONF_AUTH_TYPE, CONF_IP_REGION_ID,
    CONF_SCHEME, CONF_DEVICE_HOST, CONF_CGI_PORT, CONF_USERNAME, CONF_DEVICE_PASSWORD,
    CONF_DOOR, CONF_SECURITY, CONF_HS_DEVICE
)

# Setup logging to see what's happening
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

async def test_flow():
    # Load credentials
    bundle_path = Path("test_bundle.json")
    if not bundle_path.exists():
        print("Error: test_bundle.json not found")
        return
    
    with open(bundle_path, "r") as f:
        bundle = json.load(f)
    
    # Map bundle to integration config
    config = {
        CONF_AUTH_ACCOUNT: bundle["auth_account"],
        CONF_AUTH_PASSWORD: bundle["auth_password"],
        CONF_AUTH_BASE_URL: "https://shi-1-sec.qvcloud.net", # Default that should fail and trigger discovery
        CONF_VERIFY_SSL: False,
        CONF_AUTH_MODE: "user",
        CONF_AUTH_TYPE: bundle.get("auth_type", 0),
        CONF_IP_REGION_ID: bundle.get("ip_region_id", 0),
        # Local part (dummy for this cloud test)
        CONF_SCHEME: "https",
        CONF_DEVICE_HOST: "127.0.0.1",
        CONF_CGI_PORT: 443,
        CONF_USERNAME: "adminapp2",
        CONF_DEVICE_PASSWORD: "password",
        CONF_DOOR: 1,
        CONF_SECURITY: "username",
        CONF_HS_DEVICE: True,
    }

    async with ClientSession() as session:
        client = WelcomeEyeClient(session, config)
        
        print("\n--- STEP 1: Auth Login (Discovery) ---")
        success = await client.login_auth()
        if success:
            print(f"✅ Auth Login Success!")
            print(f"📍 Working Auth Base: {client._dynamic_auth_base}")
            print(f"🔑 Session ID: {client._auth_session_id}")
            print(f"👤 Account ID: {client._account_id}")
        else:
            print("❌ Auth Login Failed")
            return

        print("\n--- STEP 2: Alarm Login ---")
        success = await client.login_alarm()
        if success:
            print(f"✅ Alarm Login Success!")
            print(f"📍 Working Alarm Base: {client._dynamic_alarm_base}")
            print(f"🔑 Alarm Session ID: {client._alarm_session_id}")
        else:
            print("❌ Alarm Login Failed")
            return

        print("\n--- STEP 3: Query Alarms ---")
        items = await client.query_alarm_list()
        if items:
            print(f"✅ Successfully retrieved {len(items)} alarm items")
            print(f"📝 Latest item: {items[0]}")
        else:
            print("❌ Failed to retrieve alarm list (or list empty)")

if __name__ == "__main__":
    asyncio.run(test_flow())
