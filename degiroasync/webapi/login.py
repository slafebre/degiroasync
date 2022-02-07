from typing import Union, List, Dict, Any
import logging
import json
import base64
import struct
import hmac
import hashlib
import time

import httpx

from ..core.constants import LOGGER_NAME
from ..core.constants import LOGIN
from ..core import Credentials, SessionCore, URLs, Config, PAClient
from ..core import check_session_config
from ..core.helpers import check_response

LOGGER = logging.getLogger(LOGGER_NAME)


async def login(
        credentials: Credentials,
        session: Union[SessionCore, None] = None) -> SessionCore:
    """
    Authentify with Degiro API.
    `session` will be updated with required data for further connections.
    If no `session` is provided, create one.
    """
    url = URLs.LOGIN
    session = session or SessionCore()
    payload = {
        "username": credentials.username,
        "password": credentials.password,
        "isRedirectToMobile": False,
        "isPassCodeReset": '',
        "queryParams": {"reason": "session_expired"}
            }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=json.dumps(payload))
        LOGGER.debug(response.__dict__)

        response_load = response.json()

        if response_load['status'] == LOGIN.TOTP_NEEDED:
            # totp needed
            if (credentials.totp_secret is None and
                    credentials.one_time_password is None):
                raise AssertionError(
                        "Account has TOTP enabled, but no TOTP secret"
                        " nor one_time_password was provided.")
            elif credentials.totp_secret is not None:
                payload["oneTimePassword"] = _get_totp_token(
                        credentials.totp_secret)
            elif credentials.one_time_password is not None:
                payload["oneTimePassword"] = credentials.one_time_password

            url = URLs.LOGIN_TOTP
            LOGGER.debug("run totp login at %s", url)
            response = await client.post(
                    url,
                    data=json.dumps(payload),
                    cookies=response.cookies)
            LOGGER.debug(response.__dict__)
            LOGGER.debug(response.json())

        check_response(response)
        session._cookies = response.cookies

        if SessionCore.JSESSIONID not in session._cookies:
            LOGGER.error("No JSESSIONID in response: %s", response)
            LOGGER.error("No JSESSIONID in response cookies: %s",
                         response.cookies)
            raise AssertionError("No JSESSIONID in response.")

        return session


async def get_config(session: SessionCore) -> SessionCore:
    """
    Populate session with configuration
    """
    _check_active_session(session)
    async with httpx.AsyncClient() as client:
        res = await client.get(URLs.CONFIG, cookies=session._cookies)

    check_response(res)
    config = Config(res.json()['data'])

    session.config = config

    return session


async def get_client_info(session: SessionCore) -> SessionCore:
    """
    Get client information.
    """
    url = URLs.get_client_info_url(session)
    async with httpx.AsyncClient() as client:
        res = await client.get(
                url,
                params={'sessionId': session._cookies[session.JSESSIONID]},
                cookies=session._cookies)

    check_response(res)
    session.client = PAClient(res.json()['data'])
    return session


async def get_account_info(session: SessionCore) -> SessionCore:
    """

    """
    _check_active_session(session)
    join_url(URLs.ACCOUNT_INFO, session.client.intAccount)
    #url = '/'.join((URLs.ACCOUNT_INFO, session.client.intAccount))
    raise NotImplementedError
    async with httpx.AsyncClient() as client:
        res = await client.get(U)


async def get_product_dictionary(session: SessionCore) -> Dict[str, Any]:
    """
    Get product dictionary information from server.

    This is needed to provide human-redeable product data for products:

    - Bonds, CFD Exchange places.
    - ETF fees types.
    - Countries.
    """
    check_session_config(session)
    url = URLs.get_product_dictionary_url(session)
    params = dict(
        intAccount=session.client.intAccount,
        sessionId=session.config.sessionId
            )
    async with httpx.AsyncClient() as client:
        response = await client.get(url,
                                    cookies=session._cookies,
                                    params=params
                                    )
    check_response(response)
    LOGGER.debug("webapi.get_product_dictionary response| %s", response.json())
    return response


###########
# Helpers #
###########

def _check_active_session(session: SessionCore):
    """
    Check that session id has been populated. Raise AssertionError if not.
    """
    if SessionCore.JSESSIONID not in session._cookies:
        raise AssertionError("No JSESSIONID in session.cookies")


def _get_totp_token(secret_key: str) -> str:
    "Get one-time-password from secret key"
    key = base64.b32decode(secret_key)
    message = struct.pack(">Q", int(time.time()) // 30)
    message_hash = hmac.new(key, message, hashlib.sha1).digest()
    o = message_hash[19] & 15
    message_hash = (struct.unpack(">I",
                    message_hash[o:o+4])[0] & 0x7fffffff) % 1000000
    return message_hash


__all__ = [
    login.__name__,
    get_account_info.__name__,
    get_config.__name__
        ]
