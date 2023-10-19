import ctypes
import json
import ssl
import sys
import warnings
import random
from loguru import logger
from base64 import urlsafe_b64decode
from secrets import token_urlsafe
from typing import Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import parse_qsl, urlsplit
import urllib
from bs4 import BeautifulSoup
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import aiohttp

from auth_exceptions import (
    RiotAuthenticationError,
    RiotAuthError,
    RiotMultifactorError,
    RiotMultifactorAttemptError,
    RiotRatelimitError,
    RiotUnknownErrorTypeError,
    RiotUnknownResponseTypeError,
)

__all__ = (
    "RiotAuthenticationError",
    "RiotAuthError",
    "RiotMultifactorError",
    "RiotMultifactorAttemptError",
    "RiotRatelimitError",
    "RiotUnknownErrorTypeError",
    "RiotUnknownResponseTypeError",
    "RiotAuth",
)


class RiotAuth:
    RIOTCLIENT = 'xx.x.x.xxxxx'
    RIOTCLIENT = ''.join([str(random.randint(0, 9)) if x == 'x' else x for x in RIOTCLIENT])

    RIOT_CLIENT_USER_AGENT = (
        # https://dash.valorant-api.com/endpoints/version RiotClient/63.0.9.4909983.4789131 %s (Windows;10;;Professional, x64)
        f"ShooterGame/11 Windows/{RIOTCLIENT}.64bit"
    )

    CIPHERS13 = ":".join(  # https://docs.python.org/3/library/ssl.html#tls-1-3
        (
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
        )
    )
    CIPHERS = ":".join(
        (
            "ECDHE-ECDSA-CHACHA20-POLY1305",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-ECDSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-ECDSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-ECDSA-AES128-SHA",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-ECDSA-AES256-SHA",
            "ECDHE-RSA-AES256-SHA",
            "AES128-GCM-SHA256",
            "AES256-GCM-SHA384",
            "AES128-SHA",
            "AES256-SHA",
            "DES-CBC3-SHA",  # most likely not available
        )
    )
    SIGALGS = ":".join(
        (
            "ecdsa_secp256r1_sha256",
            "rsa_pss_rsae_sha256",
            "rsa_pkcs1_sha256",
            "ecdsa_secp384r1_sha384",
            "rsa_pss_rsae_sha384",
            "rsa_pkcs1_sha384",
            "rsa_pss_rsae_sha512",
            "rsa_pkcs1_sha512",
            "rsa_pkcs1_sha1",  # will get ignored and won't be negotiated
        )
    )

    def __init__(self) -> None:
        self._auth_ssl_ctx = RiotAuth.create_riot_auth_ssl_ctx()
        self._cookie_jar = aiohttp.CookieJar()
        self.access_token: Optional[str] = None
        self.scope: Optional[str] = None
        self.id_token: Optional[str] = None
        self.token_type: Optional[str] = None
        self.expires_at: int = 0
        self.user_id: Optional[str] = None
        self.entitlements_token: Optional[str] = None

    @staticmethod
    def create_riot_auth_ssl_ctx() -> ssl.SSLContext:
        ssl_ctx = ssl.create_default_context()

        addr = id(ssl_ctx) + sys.getsizeof(object())
        ssl_ctx_addr = ctypes.cast(addr, ctypes.POINTER(ctypes.c_void_p)).contents

        if sys.platform.startswith("win32"):
            libssl = ctypes.CDLL("libssl-1_1.dll")
        elif sys.platform.startswith(("linux", "darwin")):
            libssl = ctypes.CDLL(ssl._ssl.__file__)
        else:
            raise NotImplementedError(
                "Only Windows (win32), Linux (linux) and macOS (darwin) are supported."
            )

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1  # deprecated since 3.10
        ssl_ctx.set_alpn_protocols(["http/1.1"])
        ssl_ctx.options |= 1 << 19  # SSL_OP_NO_ENCRYPT_THEN_MAC
        libssl.SSL_CTX_set_ciphersuites(ssl_ctx_addr, RiotAuth.CIPHERS13.encode())
        libssl.SSL_CTX_set_cipher_list(ssl_ctx_addr, RiotAuth.CIPHERS.encode())
        # setting SSL_CTRL_SET_SIGALGS_LIST
        libssl.SSL_CTX_ctrl(ssl_ctx_addr, 98, 0, RiotAuth.SIGALGS.encode())

        # print([cipher["name"] for cipher in ssl_ctx.get_ciphers()])
        return ssl_ctx

    async def authorize(
        self,
        username: str,
        password: str,
        email: str,
        use_query_response_mode: bool = False,
        ) -> None:
        """
        Authenticate using username and password.
        """
        if username and password:
            self._cookie_jar.clear()

        conn = aiohttp.TCPConnector(ssl=self._auth_ssl_ctx)
        session = aiohttp.ClientSession(
                connector=conn, raise_for_status=True, cookie_jar=self._cookie_jar
            )
        headers = {
            "Accept-Encoding": "deflate, gzip, zstd",
            "user-agent": RiotAuth.RIOT_CLIENT_USER_AGENT,
            "Cache-Control": "no-cache",
            "Accept": "application/json",
        }

        # region Begin auth/Reauth
        body = {
            "acr_values": "urn:riot:gold",
            "client_id": "accountodactyl-prod",
            "redirect_uri": "https://account.riotgames.com/oauth2/log-in",
            "response_type": "code",
            "scope": "openid email profile riot:/riot.atlas/accounts.edit riot:/riot.atlas/accounts/password.edit riot:/riot.atlas/accounts/email.edit riot:/riot.atlas/accounts.auth riot://third_party.revoke riot://third_party.query riot://forgetme/notify.write riot:/riot.authenticator/auth.code riot:/riot.authenticator/authz.edit riot:/rso/mfa/device.write riot:/riot.authenticator/identity.add",
            "state": "374010f6-23fb-4fd4-a80d-825b3adc1552"
        }
        if use_query_response_mode:
            body["response_mode"] = "query"
        async with session.post(
                "https://auth.riotgames.com/api/v1/authorization",
                json=body,
                headers=headers,
        ) as r:
            data: Dict = await r.json()
            print(data)
            resp_type = data["type"]
        # endregion

        if resp_type != "response":  # not reauth
            # region Authenticate
            body = {
                "language": "ru_RU",
                "password": password,
                "remember": False,
                "type": "auth",
                "username": username,
            }
            async with session.put(
                    "https://auth.riotgames.com/api/v1/authorization",
                    json=body,
                    headers=headers,
            ) as r:
                data: Dict = await r.json()
                print(data)
                resp_type = data["type"]
                if resp_type == "response":
                    await session.close()
                    return {'ok': 'true'}                    
                elif resp_type == "auth":
                    err = data.get("error")
                    if err == "auth_failure":
                        await session.close()
                        raise RiotAuthenticationError(
                            f"Failed to authenticate. Make sure username and password are correct. `{err}`."
                        )
                    elif err == "rate_limited":
                        await session.close()
                        raise RiotRatelimitError()
                    else:
                        await session.close()
                        raise RiotUnknownErrorTypeError(
                            f"Got unknown error `{err}` during authentication."
                        )
                elif resp_type == "multifactor":                
                    return {'ok': resp_type, 'session': session, 'headers': headers, 'sent': data['multifactor']['email'], 'email': email}
                else:
                    await session.close()
                    raise RiotUnknownResponseTypeError(
                        f"Got unknown response type `{resp_type}` during authentication."
                    )
            # endregion

        self._cookie_jar = session.cookie_jar

    async def handle_multifactor(
            self,
            session: aiohttp.client.ClientSession,
            headers: dict,
            email: str,
            multifactor_code: str,  # Add multifactor_code as an argument
        ) -> None:
            """
            Handle multi-factor authentication.
            """
            multiFactorBody = {
                "type": "multifactor",
                "rememberDevice": "false",
                "code": multifactor_code,
            }
            async with session.put(
                "https://auth.riotgames.com/api/v1/authorization",
                json=multiFactorBody,
                headers=headers,
            ) as r:
                data: Dict = await r.json()
                print(data)
                if ("error" in data.keys() and data["error"] == "multifactor_attempt_failed"):
                    raise RiotMultifactorAttemptError(
                        "Multi-factor attempt failed, please try again."
                    )
                json_data = {
                    'email': email,
                }

                async with session.get(
                        f"{data['response']['parameters']['uri']}", headers=headers,
                        json=json_data) as response1:
                    ...
                    async with session.get(f"https://account.riotgames.com/", headers=headers, json=json_data) as response2:
                        data2 = await response2.text()
                        soup = BeautifulSoup(data2, 'html.parser')
                        csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
                        print(csrf_token)

                        try:
                            async with session.get(f"https://account.riotgames.com/", headers=headers, json=json_data) as response2:
                                data2 = await response2.text()
                                soup = BeautifulSoup(data2, 'html.parser')
                                csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
                                headers["csrf-token"] = csrf_token
                                headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
                                headers["Accept"] = "application/json, text/plain, */*"
                                headers["Content-Type"] = "application/json"
                                headers["referer"] = "https://account.riotgames.com/"
                                print(headers)
                        except Exception as e:
                            logger.error(e)


                        try:
                            async with session.get("https://account.riotgames.com/api/account/v1/user/email", headers=headers) as response3:
                                a = await response3.text()
                                logger.debug(a)
                        except Exception as e:
                            logger.error(e)


                        try:
                            async with session.post("https://account.riotgames.com/api/account/v1/user/email", headers=headers, json={'email': email}) as response3:
                                data = await response3.json()
                                print(data)
                        except Exception as e:
                            logger.error(e)


                        try:
                            for service in ['google', 'xbox', 'apple', 'facebook']:
                                try:
                                    await session.delete(f"https://account.riotgames.com/api/links/v1/federated-identities/{service}", headers=headers)
                                except Exception as e:
                                    logger.error(e)
                            await session.post(f"https://account.riotgames.com/api/mfa/v2/purge-and-signout", headers=headers)
                            await session.close()
                        except Exception as e:
                            logger.error(e)



    async def reauthorize(self) -> bool:
        """
        Reauthenticate using cookies.

        Returns a ``bool`` indicating success or failure.
        """
        try:
            await self.authorize("", "")
            return True
        except RiotAuthenticationError:  # because credentials are empty
            return False
