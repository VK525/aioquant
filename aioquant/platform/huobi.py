# -*- coding:utf-8 -*-

"""
Huobi Trade module.
https://huobiapi.github.io/docs/spot/v1/cn

Author: HuangTao
Date:   2018/08/30
Email:  huangtao@ifclover.com
"""

import json
import hmac
import copy
import gzip
import base64
import urllib
import hashlib
import datetime
from urllib import parse
from urllib.parse import urljoin

from aioquant.error import Error
from aioquant.utils import logger
from aioquant.order import Order
from aioquant.tasks import SingleTask
from aioquant.utils.decorator import async_method_locker
from aioquant.utils.web import AsyncHttpRequests, Websocket
from aioquant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from aioquant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from aioquant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("HuobiRestAPI", "HuobiTrade", )


class HuobiRestAPI:
    """Huobi REST API client.

    Attributes:
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        host: HTTP request host, default `https://api.huobi.pro`.
    """

    def __init__(self, access_key, secret_key, host=None):
        """Initialize REST API client."""
        self._host = host or "https://api.huobi.pro"
        self._access_key = access_key
        self._secret_key = secret_key
        self._account_id = None

    async def get_server_time(self):
        """This endpoint returns the current system time in milliseconds adjusted to Singapore time zone.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/common/timestamp"
        success, error = await self.request("GET", uri)
        return success, error

    async def get_exchange_info(self):
        """Get exchange information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/common/symbols"
        success, error = await self.request("GET", uri)
        return success, error

    async def get_orderbook(self, symbol, depth=20, step="step0"):
        """Get latest orderbook information.

        Args:
            symbol: Symbol name, e.g. `ethusdt`.
            depth: The number of market depth to return on each side, `5` / `10` / `20`, default is 10.
            step: Market depth aggregation level, `step0` / `step1` / `step2` / `step3` / `step4` / `step5`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Note:
            When type is set to `step0`, the default value of `depth` is 150 instead of 20.
        """
        uri = "/market/depth"
        params = {
            "symbol": symbol,
            "depth": depth,
            "type": step
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_trade(self, symbol):
        """Get latest trade information.

        Args:
            symbol: Symbol name, e.g. `ethusdt`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/market/trade"
        params = {
            "symbol": symbol
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_kline(self, symbol, interval="1min", limit=150):
        """Get kline information.

        Args:
            symbol: Symbol name, e.g. `ethusdt`.
            interval: Kline interval type, `1min` / `5min` / `15min` / `30min` / `60min` / `4hour` / `1day` / `1mon` / `1week` / `1year`.
            limit: Number of results per request. (default 150, max 2000.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Notes:
            If start and end are not sent, the most recent klines are returned.
        """
        uri = "/market/history/kline"
        params = {
            "symbol": symbol,
            "period": interval,
            "size": limit
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_user_accounts(self):
        """This endpoint returns a list of accounts owned by this API user.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/account/accounts"
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def _get_account_id(self):
        if self._account_id:
            return self._account_id
        success, error = await self.get_user_accounts()
        if error:
            return None
        for item in success["data"]:
            if item["type"] == "spot":
                self._account_id = item["id"]
                return self._account_id
        return None

    async def get_account_balance(self):
        """This endpoint returns the balance of an account specified by account id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        account_id = await self._get_account_id()
        uri = "/v1/account/accounts/{account_id}/balance".format(account_id=account_id)
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def get_balance_all(self):
        """This endpoint returns the balances of all the sub-account aggregated.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/subuser/aggregate-balance"
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def create_order(self, symbol, price, quantity, order_type, client_order_id=None):
        """Create an order.
        Args:
            symbol: Symbol name, e.g. `ethusdt`.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            order_type: Order type, `buy-market` / `sell-market` / `buy-limit` / `sell-limit`.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/order/orders/place"
        account_id = await self._get_account_id()
        info = {
            "account-id": account_id,
            "price": price,
            "amount": quantity,
            "source": "api",
            "symbol": symbol,
            "type": order_type
        }
        if order_type == "buy-limit" or order_type == "sell-limit":
            info["price"] = price
        if client_order_id:
            info["client-order-id"] = client_order_id
        success, error = await self.request("POST", uri, body=info, auth=True)
        return success, error

    async def revoke_order(self, order_id):
        """Cancelling an unfilled order.
        Args:
            order_id: Order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/order/orders/{order_id}/submitcancel".format(order_id=order_id)
        success, error = await self.request("POST", uri, auth=True)
        return success, error

    async def revoke_orders(self, order_ids):
        """Cancelling unfilled orders.
        Args:
            order_ids: Order id list.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/order/orders/batchcancel"
        body = {
            "order-ids": order_ids
        }
        success, error = await self.request("POST", uri, body=body, auth=True)
        return success, error

    async def get_open_orders(self, symbol, limit=500):
        """Get all open order information.

        Args:
            symbol: Symbol name, e.g. `ethusdt`.
            limit: The number of orders to return, [1, 500].

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/order/openOrders"
        account_id = await self._get_account_id()
        params = {
            "account-id": account_id,
            "symbol": symbol,
            "size": limit
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_order_status(self, order_id):
        """Get order details by order id.

        Args:
            order_id: Order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/v1/order/orders/{order_id}".format(order_id=order_id)
        success, error = await self.request("GET", uri, auth=True)
        return success, error

    async def request(self, method, uri, params=None, body=None, auth=False):
        """Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body:   HTTP request body.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        if auth:
            timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            params = params if params else {}
            params.update({"AccessKeyId": self._access_key,
                           "SignatureMethod": "HmacSHA256",
                           "SignatureVersion": "2",
                           "Timestamp": timestamp})

            host_name = urllib.parse.urlparse(self._host).hostname.lower()
            params["Signature"] = self.generate_signature(method, params, host_name, uri)

        if method == "GET":
            headers = {
                "Content-type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/39.0.2171.71 Safari/537.36"
            }
        else:
            headers = {
                "Accept": "application/json",
                "Content-type": "application/json"
            }
        _, success, error = await AsyncHttpRequests.fetch(method, url, params=params, data=body, headers=headers,
                                                          timeout=10)
        if error:
            return success, error
        if not isinstance(success, dict):
            success = json.loads(success)
        if success.get("status") != "ok":
            return None, success
        return success, None

    def generate_signature(self, method, params, host_url, request_path):
        query = "&".join(["{}={}".format(k, parse.quote(str(params[k]))) for k in sorted(params.keys())])
        payload = [method, host_url, request_path, query]
        payload = "\n".join(payload)
        payload = payload.encode(encoding="utf8")
        secret_key = self._secret_key.encode(encoding="utf8")
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature


class HuobiTrade:
    """Huobi Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for your strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default "https://api.huobi.pro")
        wss: Websocket address. (default "wss://api.huobi.pro")
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
        order_update_callback: You can use this param to specify a async callback function when you initializing Trade
            module. `order_update_callback` is like `async def on_order_update_callback(order: Order): pass` and this
            callback function will be executed asynchronous when some order state updated.
        init_callback: You can use this param to specify a async callback function when you initializing Trade
            module. `init_callback` is like `async def on_init_callback(success: bool, **kwargs): pass`
            and this callback function will be executed asynchronous after Trade module object initialized done.
        error_callback: You can use this param to specify a async callback function when you initializing Trade
            module. `error_callback` is like `async def on_error_callback(error: Error, **kwargs): pass`
            and this callback function will be executed asynchronous when some error occur while trade module is running.
    """

    def __init__(self, **kwargs):
        """Initialize Trade module."""
        e = None
        if not kwargs.get("account"):
            e = Error("param account miss")
        if not kwargs.get("strategy"):
            e = Error("param strategy miss")
        if not kwargs.get("symbol"):
            e = Error("param symbol miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://api.huobi.pro"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://api.huobi.pro"
        if not kwargs.get("access_key"):
            e = Error("param access_key miss")
        if not kwargs.get("secret_key"):
            e = Error("param secret_key miss")
        if e:
            logger.error(e, caller=self)
            SingleTask.run(self._error_callback, e)
            SingleTask.run(kwargs["init_callback"], False)
            return

        self._account = kwargs["account"]
        self._strategy = kwargs["strategy"]
        self._platform = kwargs["platform"]
        self._symbol = kwargs["symbol"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._order_update_callback = kwargs.get("order_update_callback")
        self._init_callback = kwargs.get("init_callback")
        self._error_callback = kwargs.get("error_callback")

        self._raw_symbol = self._symbol.replace("/", "").lower()
        self._order_channel = "orders.{}".format(self._raw_symbol)
        self._assets = {}
        self._orders = {}

        # Initialize our REST API client.
        self._rest_api = HuobiRestAPI(self._access_key, self._secret_key, self._host, )

        url = self._wss + "/ws/v1"
        self._ws = Websocket(url, self.connected_callback, process_binary_callback=self.process_binary)

    @property
    def orders(self):
        return copy.copy(self._orders)

    @property
    def rest_api(self):
        return self._rest_api

    async def connected_callback(self):
        """After websocket connection created successfully, we will send a message to server for authentication."""
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        params = {
            "AccessKeyId": self._access_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": timestamp
        }
        signature = self._rest_api.generate_signature("GET", params, "api.huobi.pro", "/ws/v1")
        params["op"] = "auth"
        params["Signature"] = signature
        await self._ws.send(params)

    async def _auth_success_callback(self):
        # Get current open orders.
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            e = Error("get open orders error: {}".format(error))
            SingleTask.run(self._error_callback, e)
            SingleTask.run(self._init_callback, False)
            return
        for order_info in success["data"]:
            data = {
                "order-id": order_info["id"],
                "order-type": order_info["type"],
                "order-state": order_info["state"],
                "unfilled-amount": float(order_info["amount"]) - float(order_info["filled-amount"]),
                "order-price": float(order_info["price"]),
                "price": float(order_info["price"]),
                "order-amount": float(order_info["amount"]),
                "created-at": order_info["created-at"],
                "utime": order_info["created-at"],
            }
            self._update_order(data)

        # Subscript order channel.
        params = {
            "op": "sub",
            "topic": self._order_channel
        }
        await self._ws.send(params)

    @async_method_locker("HuobiTrade.process_binary.locker")
    async def process_binary(self, raw):
        """Process binary message that received from websocket.

        Args:
            raw: Binary message received from websocket.

        Returns:
            None.
        """
        msg = json.loads(gzip.decompress(raw).decode())
        logger.debug("msg:", msg, caller=self)

        op = msg.get("op")

        if op == "auth":
            if msg["err-code"] != 0:
                e = Error("Websocket connection authorized failed: {}".format(msg))
                logger.error(e, caller=self)
                SingleTask.run(self._error_callback, e)
                SingleTask.run(self._init_callback, False)
                return
            logger.info("Websocket connection authorized successfully.", caller=self)
            await self._auth_success_callback()
        elif op == "ping":  # ping
            params = {
                "op": "pong",
                "ts": msg["ts"]
            }
            await self._ws.send(params)
        elif op == "sub":
            if msg["topic"] != self._order_channel:
                return
            if msg["err-code"] != 0:
                e = Error("subscribe order event error: {}".format(msg))
                SingleTask.run(self._error_callback, e)
                SingleTask.run(self._init_callback, False)
            else:
                SingleTask.run(self._init_callback, True)
        elif op == "notify":
            if msg["topic"] != self._order_channel:
                return
            data = msg["data"]
            data["utime"] = msg["ts"]
            self._update_order(data)

    async def create_order(self, action, price, quantity, *args, **kwargs):
        """Create an order.

        Args:
            action: Trade direction, `BUY` or `SELL`.
            price: Price of each order.
            quantity: The buying or selling quantity.
            kwargs:
                order_type: Order type, `LIMIT` / `MARKET`, default is `LIMIT`.

        Returns:
            order_id: Order id if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        order_type = kwargs.get("order_type", ORDER_TYPE_LIMIT)
        client_order_id = kwargs.get("client_order_id")
        if action == ORDER_ACTION_BUY:
            if order_type == ORDER_TYPE_LIMIT:
                t = "buy-limit"
            elif order_type == ORDER_TYPE_MARKET:
                t = "buy-market"
            else:
                e = Error("order_type error! order_type: {}".format(order_type))
                logger.error(e, caller=self)
                SingleTask.run(self._error_callback, e)
                return None, "order type error"
        elif action == ORDER_ACTION_SELL:
            if order_type == ORDER_TYPE_LIMIT:
                t = "sell-limit"
            elif order_type == ORDER_TYPE_MARKET:
                t = "sell-market"
            else:
                e = Error("order_type error! order_type:: {}".format(order_type))
                logger.error(e, caller=self)
                SingleTask.run(self._error_callback, e)
                return None, "order type error"
        else:
            logger.error("action error! action:", action, caller=self)
            e = Error("action error! action:: {}".format(action))
            logger.error(e, caller=self)
            SingleTask.run(self._error_callback, e)
            return None, "action error"
        result, error = await self._rest_api.create_order(self._raw_symbol, price, quantity, t, client_order_id)
        if error:
            SingleTask.run(self._error_callback, error)
            return None, error
        order_id = result["data"]
        return order_id, None

    async def revoke_order(self, *order_ids):
        """Revoke (an) order(s).

        Args:
            order_ids: Order id list, you can set this param to 0 or multiple items. If you set 0 param, you can cancel
                all orders for this symbol(initialized in Trade object). If you set 1 param, you can cancel an order.
                If you set multiple param, you can cancel multiple orders. Do not set param length more than 100.

        Returns:
            Success or error, see bellow.

        NOTEs:
            DO NOT INPUT MORE THAT 10 ORDER IDs, you can invoke many times.
        """
        # If len(order_ids) == 0, you will cancel all orders for this symbol(initialized in Trade object).
        if len(order_ids) == 0:
            success, error = await self._rest_api.get_open_orders(self._raw_symbol)
            if error:
                SingleTask.run(self._error_callback, error)
                return False, error
            order_infos = success["data"]
            if len(order_infos) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            order_ids = []
            for order_info in order_infos:
                order_id = str(order_info["id"])
                order_ids.append(order_id)
            if not order_ids:
                return True, None
            _, error = await self._rest_api.revoke_orders(order_ids)
            if error:
                SingleTask.run(self._error_callback, error)
                return False, error
            return True, None

        # If len(order_ids) == 1, you will cancel an order.
        if len(order_ids) == 1:
            success, error = await self._rest_api.revoke_order(order_ids[0])
            if error:
                SingleTask.run(self._error_callback, error)
                return order_ids[0], error
            else:
                return order_ids[0], None

        # If len(order_ids) > 1, you will cancel multiple orders.
        if len(order_ids) > 1:
            _, error = await self._rest_api.revoke_orders(order_ids)
            if error:
                SingleTask.run(self._error_callback, error)
                return False, error
            return True, None

    async def get_open_order_ids(self):
        """Get open order id list.

        Args:
            None.

        Returns:
            order_ids: Open order id list, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        success, error = await self._rest_api.get_open_orders(self._raw_symbol)
        if error:
            SingleTask.run(self._error_callback, error)
            return None, error
        else:
            order_infos = success["data"]
            if len(order_infos) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            order_ids = []
            for order_info in order_infos:
                order_ids.append(str(order_info["id"]))
            return order_ids, None

    def _update_order(self, order_info):
        """Order update.

        Args:
            order_info: Order information.

        Returns:
            None.
        Note:
            order-state: Order status, `submitting` / `submitted` / `partial-filled` / `partial-canceled` / `filled` / `canceled`
        """
        order_id = str(order_info["order-id"])
        action = ORDER_ACTION_BUY if order_info["order-type"] in ["buy-market", "buy-limit"] else ORDER_ACTION_SELL
        state = order_info["order-state"]
        remain = "%.8f" % float(order_info["unfilled-amount"])
        avg_price = "%.8f" % float(order_info["price"])
        ctime = order_info["created-at"]
        utime = order_info["utime"]

        if state == "canceled":
            status = ORDER_STATUS_CANCELED
        elif state == "partial-canceled":
            status = ORDER_STATUS_CANCELED
        elif state == "submitting":
            status = ORDER_STATUS_SUBMITTED
        elif state == "submitted":
            status = ORDER_STATUS_SUBMITTED
        elif state == "partial-filled":
            status = ORDER_STATUS_PARTIAL_FILLED
        elif state == "filled":
            status = ORDER_STATUS_FILLED
        else:
            e = Error("status error! order_info: {}".format(order_info))
            logger.error(e, caller=self)
            SingleTask.run(self._error_callback, e)
            return None

        order = self._orders.get(order_id)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "order_id": order_id,
                "action": action,
                "symbol": self._symbol,
                "price": "%.8f" % float(order_info["order-price"]),
                "quantity": "%.8f" % float(order_info["order-amount"]),
                "remain": remain,
                "status": status
            }
            order = Order(**info)
            self._orders[order_id] = order
        order.remain = remain
        order.status = status
        order.avg_price = avg_price
        order.ctime = ctime
        order.utime = utime

        SingleTask.run(self._order_update_callback, copy.copy(order))
        if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_id)
