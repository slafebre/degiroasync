"""
Async API for Degiro. This module is close to Degiro Web API structure:
responses are provided (almost) as-is with minimum abstraction
and verification.

For a higher level api, see `api` module.
"""
import json
import base64
import struct
import hmac
import hashlib
import time
import logging
from typing import Union, Any, List, Dict

import httpx


from ..core import Credentials, SessionCore, URLs, Config, PAClient
from ..core import join_url
from ..core import check_session_config
from ..core.constants import LOGGER_NAME
from ..core.constants import PriceConst
from ..core.constants import ProductConst
from ..core.constants import DegiroStatus
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

        if response_load['status'] == DegiroStatus.TOTP_NEEDED:
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


async def get_portfolio(session: SessionCore) -> httpx.Response:
    """
    Get portfolio web call.

    Example return:

        {'portfolio': {'isAdded': True,
         'lastUpdated': 1088,
         'name': 'portfolio',
         'value': [
            {'id': '8614787',
             'isAdded': True,
             'name': 'positionrow',
             'value': [
                 {'isAdded': True,
                  'name': 'id',
                  'value': '8614787'},
                 {'isAdded': True,
                  'name': 'positionType',
                  'value': 'PRODUCT'},
                 {'isAdded': True,
                  'name': 'size',
                  'value': 100},
                 {'isAdded': True,
                  'name': 'price',
                  'value': 73.0},
                 {'isAdded': True,
                  'name': 'value',
                  'value': 7300.0},
                 {'isAdded': True,
                  'name': 'accruedInterest'},
                 {'isAdded': True,
                  'name': 'plBase',
                  'value': {'EUR': -6716.901595272}},
                 {'isAdded': True,
                  'name': 'todayPlBase',
                  'value': {'EUR': -7300.0}},
                 {'isAdded': True,
                  'name': 'portfolioValueCorrection',
                  'value': 0},
                 {'isAdded': True,
                  'name': 'breakEvenPrice',
                  'value': 68.15},
                 {'isAdded': True,
                  'name': 'averageFxRate',
                  'value': 1},
                 {'isAdded': True,
                  'name': 'realizedProductPl',
                  'value': 98.098404728},
                 {'isAdded': True,
                  'name': 'realizedFxPl',
                  'value': 0},
                 {'isAdded': True,
                  'name': 'todayRealizedProductPl',
                  'value': 0.0},
                 {'isAdded': True,
                  'name': 'todayRealizedFxPl',
                  'value': 0}
                  ]
            },
                    ...
        },
         {'id': 'EUR',
          'isAdded': True,
          'name': 'positionrow',
          'value': [
            {'isAdded': True,
            'name': 'id',
            'value': 'EUR'},
            {'isAdded': True,
            'name': 'positionType',
            'value': 'CASH'},
            {'isAdded': True,
            'name': 'size',
            'value': -53676.25},
            {'isAdded': True,
            'name': 'price',
            'value': 1},
            {'isAdded': True,
            'name': 'value',
            'value': -53676.25},
            {'isAdded': True,
            'name': 'accruedInterest'},
            {'isAdded': True,
            'name': 'plBase',
            'value': {'EUR': 53676.2467863145}},
            {'isAdded': True,
            'name': 'todayPlBase',
            'value': {'EUR': 53676.2467863145}},
            {'isAdded': True,
            'name': 'portfolioValueCorrection',
            'value': 0},
            {'isAdded': True,
            'name': 'breakEvenPrice',
            'value': 0},
            {'isAdded': True,
            'name': 'averageFxRate',
            'value': 1},
            {'isAdded': True,
            'name': 'realizedProductPl',
            'value': 0},
            {'isAdded': True,
            'name': 'realizedFxPl',
            'value': 0},
            {'isAdded': True,
            'name': 'todayRealizedProductPl',
            'value': 0},
            {'isAdded': True,
            'name': 'todayRealizedFxPl',
            'value': 0}]
         },
         {'id': 'USD',
          'isAdded': True,
          'name': 'positionrow',
          'value': [{'isAdded': True,
          'name': 'id',
          'value': 'USD'},
         {'isAdded': True,
          'name': 'positionType',
          'value': 'CASH'},
         {'isAdded': True,
          'name': 'size',
          'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': -4.216892111}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0.0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]},
         {'id': 'PLN',
         'isAdded': True,
         'name': 'positionrow',
         'value': [{'isAdded': True,
         'name': 'id',
         'value': 'PLN'},
         {'isAdded': True,
         'name': 'positionType',
         'value': 'CASH'},
         {'isAdded': True,
         'name': 'size',
         'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': 1.8128205}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0.0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]},
         {'id': 'GBP',
         'isAdded': True,
         'name': 'positionrow',
         'value': [{'isAdded': True,
         'name': 'id',
         'value': 'GBP'},
         {'isAdded': True,
         'name': 'positionType',
         'value': 'CASH'},
         {'isAdded': True,
         'name': 'size',
         'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': 0.0}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0.0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]},
         {'id': 'FLATEX_EUR',
         'isAdded': True,
         'name': 'positionrow',
         'value': [{'isAdded': True,
         'name': 'id',
         'value': 'FLATEX_EUR'},
         {'isAdded': True,
         'name': 'positionType',
         'value': 'CASH'},
         {'isAdded': True,
         'name': 'size',
         'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': 0.0}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0.0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]},
         {'id': 'FLATEX_USD',
         'isAdded': True,
         'name': 'positionrow',
         'value': [{'isAdded': True,
         'name': 'id',
         'value': 'FLATEX_USD'},
         {'isAdded': True,
         'name': 'positionType',
         'value': 'CASH'},
         {'isAdded': True,
         'name': 'size',
         'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': 0}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]},
         {'id': 'FLATEX_PLN',
         'isAdded': True,
         'name': 'positionrow',
         'value': [{'isAdded': True,
         'name': 'id',
         'value': 'FLATEX_PLN'},
         {'isAdded': True,
         'name': 'positionType',
         'value': 'CASH'},
         {'isAdded': True,
         'name': 'size',
         'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': 0}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]},
         {'id': 'FLATEX_GBP',
         'isAdded': True,
         'name': 'positionrow',
         'value': [{'isAdded': True,
         'name': 'id',
         'value': 'FLATEX_GBP'},
         {'isAdded': True,
         'name': 'positionType',
         'value': 'CASH'},
         {'isAdded': True,
         'name': 'size',
         'value': 0.0},
         {'isAdded': True,
         'name': 'price',
         'value': 1},
         {'isAdded': True,
         'name': 'value',
         'value': 0.0},
         {'isAdded': True,
         'name': 'accruedInterest'},
         {'isAdded': True,
         'name': 'plBase',
         'value': {'EUR': 0}},
         {'isAdded': True,
         'name': 'todayPlBase',
         'value': {'EUR': 0}},
         {'isAdded': True,
         'name': 'portfolioValueCorrection',
         'value': 0},
         {'isAdded': True,
         'name': 'breakEvenPrice',
         'value': 0},
         {'isAdded': True,
         'name': 'averageFxRate',
         'value': 1},
         {'isAdded': True,
         'name': 'realizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'realizedFxPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedProductPl',
         'value': 0},
         {'isAdded': True,
         'name': 'todayRealizedFxPl',
         'value': 0}]}]},
         'totalPortfolio': {'isAdded': True,
         'lastUpdated': 22,
         'name': 'totalPortfolio',
         'value': [{'isAdded': True,
         'name': 'degiroCash',
         'value': -53676.25},
         {'isAdded': True,
         'name': 'flatexCash',
         'value': 0.0},
         {'isAdded': True,
         'name': 'totalCash',
         'value': -53676.25},
         {'isAdded': True,
         'name': 'totalDepositWithdrawal',
         'value': 63950.27},
         {'isAdded': True,
         'name': 'todayDepositWithdrawal',
         'value': 0},
         {'isAdded': True,
         'name': 'cashFundCompensationCurrency',
         'value': 'EUR'},
         {'isAdded': True,
         'name': 'cashFundCompensation',
         'value': 0},
         {'isAdded': True,
         'name': 'cashFundCompensationWithdrawn',
         'value': 28.79},
         {'isAdded': True,
         'name': 'cashFundCompensationPending',
         'value': 0},
         {'isAdded': True,
         'name': 'todayNonProductFees',
         'value': 0},
         {'isAdded': True,
         'name': 'totalNonProductFees',
         'value': -657.242202735},
         {'isAdded': True,
         'name': 'freeSpaceNew',
         'value': {'EUR': 35136.647442}},
         {'isAdded': True,
         'name': 'reportMargin',
         'value': 35136.647442},
         {'isAdded': True,
         'name': 'reportCreationTime',
         'value': '12:48:31'},
         {'isAdded': True,
         'name': 'reportPortfValue',
         'value': 149223.516559},
         {'isAdded': True,
         'name': 'reportCashBal',
         'value': -53676.2465},
         {'isAdded': True,
         'name': 'reportNetliq',
         'value': 95547.270059},
         {'isAdded': True,
         'name': 'reportOverallMargin',
         'value': 60410.622617},
         {'isAdded': True,
         'name': 'reportTotalLongVal',
         'value': 104456.461592},
         {'isAdded': True,
         'name': 'reportDeficit',
         'value': 50780.215092},
         {'isAdded': True,
         'name': 'marginCallStatus',
         'value': 'NO_MARGIN_CALL'},
         {'isAdded': True, 'name': 'marginCallDeadline'}]}
        }
    """
    return await get_trading_update(
            session,
            params={'portfolio': 0, 'totalPortfolio': 0})


async def get_products_info(
        session: SessionCore,
        products_ids: List[str]) -> httpx.Response:
    """
    Get Product info Web API call.
    """
    if session.config.productSearchUrl is None:
        raise AssertionError("productSearchUrl is None:"
                             " have you called get_config?")

    url = join_url(session.config.productSearchUrl,
                   'v5/products/info')
    async with httpx.AsyncClient() as client:
        response = await client.post(
                url,
                cookies=session.cookies,
                params={
                    'intAccount': session.client.intAccount,
                    'sessionId': session.config.sessionId
                    },
                json=products_ids
                )
        check_response(response)
        LOGGER.debug(response.json())
        return response


async def get_company_profile(
        session: SessionCore,
        isin: str) -> httpx.Response:
    """
    Get company profile.

    Example return
    """
    # should this url be taken from config as well?

    # Look for dgtbxdsservice in network logs for financial statements etc.
    # might have intraday data as well
    url = join_url(URLs.BASE, 'dgtbxdsservice/company-profile/v2', isin)
    async with httpx.AsyncClient() as client:
        response = await client.get(
                url,
                cookies=session.cookies,
                params={
                    'intAccount': session.client.intAccount,
                    'sessionId': session.config.sessionId
                    })
    check_response(response)
    LOGGER.debug(response.json())
    return response


async def get_news_by_company(
        session: SessionCore,
        isin: str,
        limit: int = 10,
        languages: List[str] = ['en'],
        offset: int = 0
        ):
    """
    Get news for a company.
    """
    url = URLs.get_news_by_company_url(session)
    async with httpx.AsyncClient() as client:
        response = await client.get(url,
                cookies=session.cookies,
                params={
                    'isin': isin,
                    'limit': limit,
                    'languages': languages,
                    'offset': offset,
                    'intAccount': session.client.intAccount,
                    'sessionId': session.config.sessionId
                    })
    check_response(response)
    LOGGER.debug(response.json())
    return response


async def get_price_data(
        session: SessionCore,
        vwdId: str,
        vwdIdentifierType: str,
        resolution: PriceConst.Resolution = PriceConst.Resolution.PT1M,
        period: PriceConst.Period = PriceConst.Period.P1DAY,
        timezone: str = 'Europe/Paris',
        culture: str = 'fr-FR',
        data_type: PriceConst.Type = PriceConst.Type.PRICE
        ) -> httpx.Response:
    """
    Get price data for a company.

    data_type = 'ohlc' provides access to 'Open', 'High', 'Low', 'Close' in
    that order for each period, instead of price data.

    vwdIdentifierType can be 'issueid' or 'vwdkey'

    Example returned JSON:
    {
        "requestid": "1",
        "start": "2022-01-20T00:00:00",
        "end": "2022-01-20T14:12:24",
        "resolution": "PT1M",
        "series": [
            {
                "expires": "2022-01-20T10:12:56+01:00",
                "data": {
                    "issueId": 360114899,
                    "companyId": 1001,
                    "name": "AIRBUS",
                    "identifier": "issueid:360114899",
                    "isin": "NL0000235190",
                    "alfa": "AIR15598",
                    "market": "XPAR",
                    "currency": "EUR",
                    "type": "AAN",
                    "quality": "REALTIME",
                    "lastPrice": 113.1,
                    "lastTime": "2022-01-21T14:12:24",
                    "absDiff": -2.62,
                    "relDiff": -0.02264,
                    "highPrice": 114.46,
                    "highTime": "2022-01-21T10:31:14",
                    "lowPrice": 112.78,
                    "lowTime": "2022-01-21T13:56:36",
                    "openPrice": 114.0,
                    "openTime": "2022-01-21T09:00:19",
                    "closePrice": 114.0,
                    "closeTime": "2022-01-21T09:00:19",
                    "cumulativeVolume": 857092.0,
                    "previousClosePrice": 115.72,
                    "previousCloseTime": "2022-01-20T17:35:03",
                    "tradingStartTime": "09:00:00",
                    "tradingEndTime": "17:40:00",
                    "tradingAddedTime": "00:10:00",
                    "lowPriceP1Y": 81.84,
                    "highPriceP1Y": 121.1,
                    "windowStart": "2022-01-20T00:00:00",
                    "windowEnd": "2022-01-20T10:11:22",
                    "windowFirst": "2022-01-20T09:00:00",
                    "windowLast": "2022-01-20T10:11:00",
                    "windowHighTime": "2022-01-20T10:11:00",
                    "windowHighPrice": 114.46,
                    "windowLowTime": "2022-01-20T10:16:00",
                    "windowLowPrice": 112.78,
                    "windowOpenTime": "2022-01-20T09:00:19",
                    "windowOpenPrice": 114.0,
                    "windowPreviousCloseTime": "2022-01-19T17:35:03",
                    "windowPreviousClosePrice": 115.72,
                    "windowTrend": -0.02264
                },
                "id": "issueid:360114899",
                "type": "object"
              
             
                "times": "2022-01-20T00:00:00",
                "expires": "2022-01-20T10:12:56+01:00",
                "data": [
                    [
                	540,
                	114.0
                    ],
                    [
                	541,
                	114.08
                    ],
                    [
                	542,
                	113.62
                    ],
                    [
                	543,
                	113.8
                    ],
                    ...
                    [
                	552,
                	113.7
                    ]],
            "id":"price:issueid:360114899",
            "type":"time"}]
        }
    """
    if vwdIdentifierType not in ('issueid', 'vwdkey'):
        raise ValueError("vwdIdentifierType must be 'issueid' or 'vwdkey'")

    check_session_config(session)
    url = URLs.get_price_data_url(session)
    LOGGER.debug('get_price_data url| %s', url)
    params = {
            'requestid': 1,
            'resolution': resolution,
            'culture': culture,
            'period': period,
            'series': f'price:{vwdIdentifierType}:{vwdId}',
            'format': 'json',
            'userToken': session.config.clientId
            }
    LOGGER.debug('get_price_data params| %s', params)
    async with httpx.AsyncClient() as client:
        response = await client.get(url,
                                    cookies=session.cookies,
                                    params=params)
    check_response(response)
    LOGGER.debug('get_price_data response| %s', response.json())
    return response


async def get_order(session: SessionCore) -> httpx.Response:
    """
    Get current and historical orders
    """
    return await get_trading_update(
            session,
            params={'orders': 0, 'historicalOrders': 0, 'transactions': 0})


async def get_trading_update(
        session: SessionCore,
        params: Dict[str, int]
        ) -> httpx.Response:
    """
    Common call to target {tradingUrl}/v5/update/{intAccount}

    This is used by other calls leveraging the same endpoint in webapi.

    Known params:
    - 'portfolio': 0
        Current portfolio information.
    - 'totalPortfolio': 0
        Aggregate values about portfolio.
    - 'orders': 0
        Current orders.
    - 'historicalOrders': 0
        Closed orders.
    - 'transactions': 0
        Executed transactions.
    """
    url = URLs.get_portfolio_url(session)
    async with httpx.AsyncClient() as client:
        response = await client.get(url, cookies=session._cookies,
                params=params)

    check_response(response)
    LOGGER.debug(response.json())
    return response


async def search_product(
        session: SessionCore,
        search_txt: str,
        product_type_id: Union[ProductConst.TypeId, None] = None,
        limit: int = 10,
        offset: int = 0) -> httpx.Response:
    """
    Access `product_search` endpoint.

    Example JSON response:
    {
        "offset": 0,
        "products": [
            {
                "active": true,
                "buyOrderTypes": [
                    "LIMIT",
                    "MARKET",
                    "STOPLOSS",
                    "STOPLIMIT"
                ],
                "category": "B",
                "closePrice": 113.3,
                "closePriceDate": "2022-02-02",
                "contractSize": 1.0,
                "currency": "EUR",
                "exchangeId": "710",
                "feedQuality": "R",
                "feedQualitySecondary": "CX",
                "id": "96008",
                "isin": "NL0000235190",
                "name": "AIRBUS",
                "onlyEodPrices": false,
                "orderBookDepth": 0,
                "orderBookDepthSecondary": 0,
                "orderTimeTypes": [
                    "DAY",
                    "GTC"
                ],
                "productBitTypes": [],
                "productType": "STOCK",
                "productTypeId": 1,
                "qualitySwitchFree": false,
                "qualitySwitchFreeSecondary": false,
                "qualitySwitchable": false,
                "qualitySwitchableSecondary": false,
                "sellOrderTypes": [
                    "LIMIT",
                    "MARKET",
                    "STOPLOSS",
                    "STOPLIMIT"
                ],
                "strikePrice": -0.0001,
                "symbol": "AIR",
                "tradable": true,
                "vwdId": "360114899",
                "vwdIdSecondary": "955000256",
                "vwdIdentifierType": "issueid",
                "vwdIdentifierTypeSecondary": "issueid",
                "vwdModuleId": 1,
                "vwdModuleIdSecondary": 2
            }
        ]
    }

    """
    check_session_config(session)
    url = URLs.get_product_search_url(session)
    params = dict(
        offset=offset,
        limit=limit,
        searchText=search_txt,
        intAccount=session.client.intAccount,
        sessionId=session.config.sessionId
            )
    if product_type_id is not None:
        params['productTypeId'] = product_type_id
    LOGGER.debug("webapi.search_product params| %s", params)
    async with httpx.AsyncClient() as client:
        response = await client.get(url,
                                    cookies=session._cookies,
                                    params=params)
    check_response(response)
    LOGGER.debug("webapi.search_product response| %s", response.json())
    return response


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


async def set_order(session: SessionCore):
    raise NotImplementedError


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


__name__ = [
    login.__name__,
    get_config.__name__,
    get_client_info.__name__,
    get_portfolio.__name__,
    get_account_info.__name__,
    get_news_by_company.__name__,
    get_company_profile.__name__,
    get_price_data.__name__,
    get_order.__name__,
    set_order.__name__
        ]
