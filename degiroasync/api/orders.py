from typing import Any, Union, List, Dict, Tuple
import functools
import datetime
import logging
import asyncio
import itertools

from jsonloader import JSONclass
from jsonloader import JSONWrapper

from .product import ProductBase
from .product import ProductFactory
from .. import webapi
from ..core import SessionCore
from ..core import ORDER
from ..core import LOGGER_NAME
from ..core import TRANSACTIONS
from ..core import camelcase_dict_to_snake


LOGGER = logging.getLogger(LOGGER_NAME)


@JSONclass(annotations=True, annotations_type=True)
class Order:
    created: str
    orderId: str
    productId: str
    size: Union[float, int]
    price: float
    buysell: ORDER.ACTION  # 'B' or 'S'
    orderTypeId: int
    orderTimeTypeId: int
    currentTradedSize: int
    totalTradedSize: int
    type: str  # 'CREATED' or ...?
    isActive: bool
    status: str  # 'REJECTED' or ...?
    # product: Union[ProductBase, None] = None  # do we want to reinstantiate
    # products here or let user?

# {'id': 182722888, 'productId': 65153, 'date': '2020-02-07T09:00:10+01:00', 'buysell': 'B', 'price': 36.07, 'quantity': 20, 'total': -721.4, 'orderTypeId': 0, 'counterParty': 'MK', 'transfered': False, 'fxRate': 0, 'totalInBaseCurrency': -721.4, 'feeInBaseCurrency': -0.29, 'totalPlusFeeInBaseCurrency': -721.69, 'transactionTypeId': 0, 'tradingVenue': 'XPAR'})


@JSONclass(annotations=True, annotations_type=True)
class Transaction:
    id: str
    product: ProductBase
    date: datetime.datetime
    buysell: ORDER.ACTION
    price: float
    quantity: float
    total: float
    transfered: bool
    fx_rate: float
    total_in_base_currency: float
    total_plus_fee_in_base_currency: float


async def submit_order():
    raise NotImplementedError


async def check_order(
        session: SessionCore,
        *,
        product: ProductBase,
        buy_sell: ORDER.ACTION,
        time_type: ORDER.TIME,
        order_type: ORDER.TYPE,
        size: int,
        price: Union[float, None] = None,
) -> Any:
    """
    This must be called to obtain a confirmation_id prior to confirming an
    order.

    This can also be used to get an order fees before confirming the order.

    >>>> ... # Get your products through search_product
    >>>> check_order(
    ...     product=product,
    ...     buy_sell=ORDER.ACTION.SELL,
    ...     time_type=ORDER.TIME,
    ...     order_type=ORDER.TYPE,
    ...     size=1,
    ...     price=100
    ... )
    ...

    This call is rate limited at the end-point level, tests would show the
    call to be rate limited at 1 per second. Users should throttle their calls
    to this function.
    """
    assert buy_sell in ("BUY", "SELL")

    response = await webapi.check_order(
        session=session,
        product_id=product.base.id,
        buy_sell=buy_sell,
        time_type=time_type,
        order_type=order_type,
        size=size,
        price=price
    )
    resp_json = response.json()
    return JSONWrapper(camelcase_dict_to_snake(resp_json['data']))


async def get_orders(
        session: SessionCore,
        from_date: Union[datetime.datetime, None] = None,
        to_date: Union[datetime.datetime, None] = None,
) -> Tuple[List[Order]]:
    """
    Get current orders and history.

    to_date:
        Request orders history up to `to_date`. Defaults to today.
    from_date:
        Request orders history from `from_date`. Defaults to today - 7 days.

    Return current_orders, historical_orders.

    """
    if to_date is None:
        to_date = datetime.datetime.today()
    if from_date is None:
        from_date = to_date - datetime.timedelta(days=7)

    orders_current_resp, orders_history_resp = await asyncio.gather(
        webapi.get_orders(session),
        webapi.get_orders_history(
            session,
            from_date=from_date.strftime(webapi.ORDER_DATE_FORMAT),
            to_date=to_date.strftime(webapi.ORDER_DATE_FORMAT))
    )

    orders_dict = orders_current_resp.json()['orders']['value']
    orders_history_dict = orders_history_resp.json()['data']
    LOGGER.debug("get_orders orders_dict| %s", orders_dict)
    LOGGER.debug("get_orders orders_history_dict| %s", orders_history_dict)
    for order in itertools.chain(orders_dict, orders_history_dict):
        order['productId'] = str(order['productId'])
        order['buysell'] = {
            'B': ORDER.ACTION.BUY,
            'S': ORDER.ACTION.SELL
        }[order['buysell']]
    return (
        [Order(o) for o in orders_dict],
        [Order(o) for o in orders_history_dict]
    )


async def get_transactions(
        session: SessionCore,
        from_date: Union[datetime.datetime, None] = None,
        to_date: Union[datetime.datetime, None] = None
) -> List[Order]:
    """
    Get transactions for `session`.

    from_date:
        Request transactions from `from_date`. Defaults to `to_date - 7 days`.

    to_date:
        Request transactions to `to_date`. Defaults to today.
    """
    to_date = to_date or datetime.datetime.today()
    from_date = from_date or to_date - datetime.timedelta(days=7)

    resp = await webapi.get_transactions(
        session,
        from_date=from_date.strftime(webapi.ORDER_DATE_FORMAT),
        to_date=to_date.strftime(webapi.ORDER_DATE_FORMAT)
    )
    data = resp.json()['data'].copy()
    products_gen = ProductFactory.init_batch(
        session,
        map(lambda t: {'id': str(t['productId'])}, data))
    products = [p async for p in products_gen]
    del products_gen

    async def _build_transaction(prod, trans):
        trans.update(dict(
            id=str(trans['id']),
            product=prod,
            date=datetime.datetime.fromisoformat(trans['date']),
            buysell={'B': ORDER.ACTION.BUY,
                     'S': ORDER.ACTION.SELL}[trans['buysell']],
        ))
        return Transaction(camelcase_dict_to_snake(trans))

    transactions = await asyncio.gather(*[_build_transaction(p, t)
                                          for p, t in zip(products, data)])
    return transactions
