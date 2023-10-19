import asyncio
import sys
import random

import auth


RIOTCLIENT = 'xx.x.x.xxxxx'
RIOTCLIENT = ''.join([str(random.randint(0, 9)) if x == 'x' else x for x in RIOTCLIENT])
auth.RiotAuth.RIOT_CLIENT_USER_AGENT = f"ShooterGame/11 Windows/{RIOTCLIENT}.64bit"

# region asyncio.run() bug workaround for Windows, remove below 3.8 and above 3.10.6
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# endregion

CREDS = "osbirGrill", "4n6~EwvQUI"

auth1 = auth.RiotAuth()
asyncio.run(auth1.authorize(*CREDS))

print(f"Access Token Type: {auth1.token_type}\n")
print(f"Access Token: {auth1.access_token}\n")
print(f"Entitlements Token: {auth1.entitlements_token}\n")
print(f"User ID: {auth1.user_id}")

asyncio.run(auth1.reauthorize())
