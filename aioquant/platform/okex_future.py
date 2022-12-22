import time
import json
import copy
import hmac
import zlib
import base64
from urllib.parse import urljoin

from aioquant.error import Error
from aioquant.utils import tools
from aioquant.utils import logger
from aioquant.order import Order
from aioquant.position import Position
from aioquant.asset import Asset
from aioquant.tasks import SingleTask, LoopRunTask
from aioquant.utils.decorator import async_method_locker
from aioquant.utils.web import Websocket, AsyncHttpRequests
from aioquant.order import ORDER_ACTION_BUY, ORDER_ACTION_SELL
from aioquant.order import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from aioquant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("OKExRestAPI", "OKExTrade", )


class OKExRestAPI:
    """ OKEx REST API client.

    Attributes:
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        passphrase: API KEY Passphrase.
        host: HTTP request host, default `https://www.okex.com`
    """

    def __init__(self, access_key, secret_key, passphrase, host=None):
        """Initialize."""
        self._host = host if host else "https://www.okx.com"
        self._access_key = access_key
        self._secret_key = secret_key
        self._passphrase = passphrase

    async def get_orderbook(self, symbol, limit=5):
        """Get latest orderbook information.

        Args:
            symbol: Symbol name, e.g. `BTC-USDT`.
            depth: Aggregation of the order book. e.g . 0.1, 0.001.
            limit: Number of results per request. (default 10, max 200.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v5/market/books"
        params = {
            "instId": symbol,
            "size": limit
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_trade(self, symbol, limit=10):
        """Get latest trade information.

        Args:
            symbol: Symbol name, e.g. `BTC-USDT`.
            limit: Number of results per request. (Default 10, max 60.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v5/market/trades"
        params = {
            "instId": symbol,
            "size": limit
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_kline(self, symbol, interval="4H", start=None, end=None):
        """Get kline information.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            interval: Kline interval type, valid values: 60/180/300/900/1800/3600/7200/14400/21600/43200/86400/604800.
            start: Start time in ISO 8601. e.g. 2019-03-19T16:00:00.000Z
            end: End time in ISO 8601. e.g. 2019-03-19T16:00:00.000Z

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Notes:
            Both parameters will be ignored if either one of start or end are not provided. The last 200 records of
            data will be returned if the time range is not specified in the request.
        """
        uri = "/api/v5/market/candles"
        params = {
            "instId": symbol,
            "bar": interval
        }
        if start and end:
            params["before"] = start
            params["after"] = end
        success, error = await self.request("GET", uri, params=params)
        return success, error
    
    async def set_level(self, symbol, lv=20):
        """
        @mgnMode : isolated：逐仓 cross：全仓
        @posSide : long：双向持仓多头 short：双向持仓空头  net：单向持仓
        """
        uri = "/api/v5/account/set-leverage"
        data = {
            "instId":symbol,
            "lever":lv,
            "mgnMode":"cross",
            "posSide":"net"
        }
        
        result, error = await self.request("POST", uri, body=data, auth=True)
        return result, error
    
    async def get_user_account(self,ccy="USDT"):
        """Get account asset information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v5/account/balance"
        data = {
            "ccy":ccy
        }
        result, error = await self.request("GET", uri, params=data, auth=True)
        return result, error

    async def create_order(self, action, symbol, quantity, price=None, client_order_id=None,tdMode="cross",reduceOnly=False):
        """Create an order.
        Args:
            action: Action type, `BUY` or `SELL`.
            symbol: Trading pair, e.g. `BTC-USDT`.
            price: Order price.
            quantity: Order quantity.
            order_type: Order type, `MARKET` or `LIMIT`.
            client_oid: Client order id, default is `None`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v5/trade/order"
        data = {
            "side": "buy" if action == ORDER_ACTION_BUY else "sell",
            "instId": symbol,
            "sz" : quantity,
            "tdMode": tdMode,
            "reduceOnly":reduceOnly
        }
        if price:
            data["ordType"] = "limit"
            data["px"] = price
        else:
            data["ordType"] = "market"

        if client_order_id:
            data["clOrdId"] = client_order_id
            
        result, error = await self.request("POST", uri, body=data, auth=True)
        
        oid = result["data"][0]["ordId"]
        if error or result["data"][0]["sCode"] != "0":
            return oid, result["data"][0]["sMsg"]
        else:
            return oid, None
    
    async def create_orders(self, data):
        """
        [
            {
                "instId":"BTC-USDT",
                "tdMode":"cash",
                "clOrdId":"b15",
                "side":"buy",
                "ordType":"limit",
                "px":"2.15",
                "sz":"2"
            },
            {
                "instId":"BTC-USDT",
                "tdMode":"cash",
                "clOrdId":"b15",
                "side":"buy",
                "ordType":"limit",
                "px":"2.15",
                "sz":"2"
            }
        ]
        """
        uri = "/api/v5/trade/batch-orders"
        
        result, error = await self.request("POST", uri, body=data, auth=True)
        return result, error
        
    async def revoke_order(self, symbol, order_id=None, client_oid=None):
        """Cancelling an unfilled order.
        Args:
            symbol: Trading pair, e.g. `BTC-USDT`.
            order_id: Order id, default is `None`.
            client_oid: Client order id, default is `None`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Notes:
            `order_id` and `order_oid` must exist one, using order_id first.
        """
        uri = "/api/v5/trade/cancel-order"
        data = {
            "instId":symbol,
        }
        if order_id:
            data["ordId"] = order_id
        if client_oid:
            data["clOrdId"] = client_oid
        
        result, error = await self.request("POST", uri, body=data, auth=True)
        result = result["data"][0]
        if error:
            return result["clOrdId"], error
        if not result["sCode"] == "0":
            return result["clOrdId"], result["sMsg"]
        return result["clOrdId"], None

    async def revoke_orders(self, symbol, order_ids=None, client_oids=None):
        """Cancelling multiple open orders with order_id，Maximum 10 orders can be cancelled at a time for each
            trading pair.

        Args:
            symbol: Trading pair, e.g. `BTC-USDT`.
            order_ids: Order id list, default is `None`.
            client_oids: Client order id list, default is `None`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Notes:
            `order_ids` and `order_oids` must exist one, using order_ids first.
        """
        uri = "/api/v5/trade/cancel-batch-orders"
        if order_ids:
            if len(order_ids) > 20:
                logger.warn("only revoke 20 orders per request!", caller=self)
                order_ids = order_ids[:20]
            body = []
            for id in order_ids:
                body.append({"instId":symbol,"ordId":id})
        elif client_oids:
            if len(client_oids) > 20:
                logger.warn("only revoke 20 orders per request!", caller=self)
                client_oids =client_oids[:20]
            body = []
            for id in client_oids:
                body.append({"instId":symbol,"clOrdId":id})
        else:
            return None, "order id list error!"
        result, error = await self.request("POST", uri, body=body, auth=True)
        return result, error

    async def get_open_orders(self, symbol, limit=100):
        """Get order details by order id.

        Args:
            symbol: Trading pair, e.g. `BTC-USDT`.
            limit: order count to return, max is 100, default is 100.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/api/v5/trade/orders-pending"
        params = {
            "instId": symbol,
            "limit": limit
        }
        result, error = await self.request("GET", uri, params=params, auth=True)
        return result, error

    async def get_order_status(self, symbol, order_id=None, client_oid=None):
        """Get order status.
        Args:
            symbol: Trading pair, e.g. `BTC-USDT`.
            order_id: Order id.
            client_oid: Client order id, default is `None`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Notes:
            `order_id` and `order_oid` must exist one, using order_id first.
        """
        uri = "/api/v5/trade/order"
        params = {
            "instrument_id": symbol
        }
        
        if order_id:
            params["ordId"] = order_id
        elif client_oid:
            params["clOrdId"] = client_oid
        else:
            return None, "order id error!"
        
        result, error = await self.request("GET", uri, params=params, auth=True)
        return result, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body: HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        if params:
            query = "&".join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
            uri += "?" + query
        url = urljoin(self._host, uri)

        if auth:
            timestamp = str(time.time()).split(".")[0] + "." + str(time.time()).split(".")[1][:3]
            if body:
                body = json.dumps(body)
            else:
                body = ""
            message = str(timestamp) + str.upper(method) + uri + str(body)
            mac = hmac.new(bytes(self._secret_key, encoding="utf8"), bytes(message, encoding="utf-8"), digestmod="sha256")
            d = mac.digest()
            sign = base64.b64encode(d)

            if not headers:
                headers = {}
            headers["Content-Type"] = "application/json"
            headers["OK-ACCESS-KEY"] = self._access_key.encode().decode()
            headers["OK-ACCESS-SIGN"] = sign.decode()
            headers["OK-ACCESS-TIMESTAMP"] = str(timestamp)
            headers["OK-ACCESS-PASSPHRASE"] = self._passphrase
        _, success, error = await AsyncHttpRequests.fetch(method, url, body=body, headers=headers, timeout=10)
        return success, error


class OKExFutureTrade:
    """OKEx Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for your strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default "https://www.okex.com")
        wss: Websocket address. (default "wss://real.okex.com:8443")
        access_key: Account's ACCESS KEY.
        secret_key Account's SECRET KEY.
        passphrase API KEY Passphrase.
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
        """Initialize."""
        e = None
        if not kwargs.get("account"):
            e = Error("param account miss")
        if not kwargs.get("strategy"):
            e = Error("param strategy miss")
        if not kwargs.get("level"):
            kwargs["level"] = 20
        if not kwargs.get("host"):
            kwargs["host"] = "https://www.okx.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://ws.okx.com:8443"
        if not kwargs.get("access_key"):
            e = Error("param access_key miss")
        if not kwargs.get("secret_key"):
            e = Error("param secret_key miss")
        if not kwargs.get("passphrase"):
            e = Error("param passphrase miss")
        if e:
            logger.error(e, caller=self)
            SingleTask.run(kwargs["error_callback"], e)
            SingleTask.run(kwargs["init_callback"], False)
            return

        self._account = kwargs["account"]
        self._strategy = kwargs["strategy"]
        self._platform = kwargs["platform"]
        self._symbol = kwargs["symbol"]
        self._level = kwargs["level"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        self._passphrase = kwargs["passphrase"]
        
        self._assets_update_callback = kwargs.get("assets_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._position_update_callback = kwargs.get("position_update_callback")
        self._init_callback = kwargs.get("init_callback")
        self._error_callback = kwargs.get("error_callback")

        self._assets = Asset(self._platform, self._account, update=False)  # Asset object. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order objects. e.g. {"order_id": Order, ... }
        self._positions = {}
        
        # Initializing our REST API client.
        self._rest_api = OKExRestAPI(self._access_key, self._secret_key, self._passphrase)
        # 订阅多个频道成功 只运行一次
        self.hold = True
        
        self._subscribe_channel = [{"channel":"orders","instType":"SWAP"},{"channel":"balance_and_position"}] 
        url = self._wss + "/ws/v5/private"
        self._ws = Websocket(url, self.connected_callback, process_callback=self.process)
        
        # Create a loop run task to send ping message to server per 5 seconds.
        LoopRunTask.register(self._send_heartbeat_msg, 5)
    @property
    def ws(self):
        return self._ws
    
    @property
    def rest_api(self):
        return self._rest_api
        
    @property
    def orders(self):
        return copy.copy(self._orders)
        
    @property
    def positions(self):
        return copy.copy(self._positions)
        
    @property
    def assets(self):
        return copy.copy(self._assets)
        
    async def connected_callback(self):
        """After websocket connection created successfully, we will send a message to server for authentication."""
        timestamp = str(time.time()).split(".")[0] + "." + str(time.time()).split(".")[1][:3]
        message = str(timestamp) + "GET" + "/users/self/verify"
        mac = hmac.new(bytes(self._secret_key, encoding="utf8"), bytes(message, encoding="utf8"), digestmod="sha256")
        d = mac.digest()
        signature = base64.b64encode(d).decode()
        data = {
            "op": "login",
            "args": [{"apiKey":self._access_key, "passphrase":self._passphrase, "timestamp":timestamp, "sign":signature}]
        }
        await self._ws.send(data)

    async def _send_heartbeat_msg(self, *args, **kwargs):
        """Send ping to server."""
        hb = "ping"
        await self._ws.send(hb)

    @async_method_locker("OKExTrade.process.locker")
    async def process(self, msg):
        """Process binary message that received from websocket.

        Args:
            raw: Binary message received from websocket.
        """
        # print(msg)
        if msg == "pong":
            return
        logger.debug("msg:", msg, caller=self)
        # Authorization message received.
        if msg.get("event"):
            if msg.get("event") ==  "error":
                e = Error("Websocket connection authorized failed: {}".format(msg))
                logger.error(e, caller=self)
                SingleTask.run(self._error_callback, {"ws error":e})
                SingleTask.run(self._init_callback, False)
                return

            if msg.get("event") == "login":
                logger.debug("Websocket connection authorized successfully.", caller=self)
                
                """
                # Fetch orders from server. (open + partially filled)
                order_infos, error = await self._rest_api.get_open_orders(self._symbol)
                if error:
                    e = Error("get open orders error: {}".format(error))
                    SingleTask.run(self._error_callback, e)
                    SingleTask.run(self._init_callback, False)
                    return
                if len(order_infos["data"]) > 100:
                    logger.warn("order length too long! (more than 100)", caller=self)

                for info in order_infos["data"]:
                    self._update_order(info)
                """


                # Subscribe order channel.
                data = {
                    "op": "subscribe",
                    "args": self._subscribe_channel
                }
                await self._ws.send(data)
                return
            
            # Subscribe response message received.
            if msg.get("event") == "subscribe":
                logger.info("subscribe :", msg, caller=self)
                if self.hold:
                    # 订阅多个频道成功 只运行一次
                    self.hold = False
                    SingleTask.run(self._init_callback, True)
            else:
                e = Error("subscribe event error: {}".format(msg))
                SingleTask.run(self._error_callback, {"subscribe error":e})
                SingleTask.run(self._init_callback, False)
                return
        # Order update message received.
        elif msg.get("arg"):
            if msg["arg"]["channel"] == "orders":
                self._update_order(msg["data"][0])
            if msg["arg"]["channel"] == "balance_and_position":
                self._update_account(msg["data"][0]["balData"])
                self._update_positions(msg["data"][0]["posData"])
                
    async def ws_order(self, action, quantity, price, ordType="limit",clOrdId=None ,reduceOnly=False):
        OrderData = {
            "id": "3333",
            "op": "order",
            "args": [{
                "instId": self._symbol,
                "tdMode": "cross",
                "ordType": ordType,
                "side": action,
                "sz": quantity,
                "px": price,
                "clOrdId": clOrdId,
                "reduceOnly":reduceOnly
            }]
        }
        
        result = await self._ws.send( OrderData )
        return result

    async def create_order(self, action, quantity, price=None, *args, **kwargs):
        """Create an order.
        Args:
            action: Trade direction, `BUY` or `SELL`.
            price: Price of each order.
            quantity: The buying or selling quantity.

        """
        result, error = await self._rest_api.create_order(action, self._symbol, quantity, price, *args, **kwargs)
        if error:
            SingleTask.run(self._error_callback, {"create_order error":error})
        return result, error
    
    async def create_orders(self, data, *args, **kwargs):
        result, error = await self._rest_api.create_orders(data)
        if error:
            SingleTask.run(self._error_callback, {"create_orders error":error})
        return result, error

    async def revoke_order(self, *args, **kwargs):
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
        if not args and not kwargs:
            order_ids, error = await self.get_open_order_ids()
            if error:
                SingleTask.run(self._error_callback, {"re_all_Od error":error})
                return False, error
            kwargs["ids"] = order_ids

        # If len(order_ids) == 1, you will cancel an order.
        if args:
            if len(args) >1:
                success, error = await self._rest_api.revoke_order(self._symbol, client_oid=args[1])
            else: 
                success, error = await self._rest_api.revoke_order(self._symbol, args[0])
            if error:
                SingleTask.run(self._error_callback, {"re_Od error":error,"id":success})
                return args[0], error
            else:
                return args[0], None
        if kwargs:
            success, error = await self._rest_api.revoke_orders(self._symbol, order_ids=kwargs["ids"])
            if error:
                SingleTask.run(self._error_callback, {"re_Ods error":error,"id":success})
                return False, error
            return success, None

    async def get_open_order_ids(self):
        """Get open order id list.

        Args:
            None.

        Returns:
            order_ids: Open order id list, otherwise it's None.
            error: Error information, otherwise it's None.
        """

        success, error = await self._rest_api.get_open_orders(self._symbol)
        if error:
            SingleTask.run(self._error_callback, {"get_open order_ids error":error})
            return success, error
        else:
            if len(success) > 100:
                logger.warn("order length too long! (more than 100)", caller=self)
            order_ids = ([ id for id in success["data"]["ordId"] ])
            return order_ids, None
    
    async def set_level(self, lv=None):
        if not lv:
            lv =self._level
        success, error = await self._rest_api.set_level(self._symbol, lv)
        if error:
            SingleTask.run(self._error_callback, {"setleve error":error})
        return success, None
    
    def _update_order(self, order_info):
        """Order update.

        Args:
            order_info: Order information.

        Returns:
            None.
        """
        order_id = str(order_info["ordId"])
        state = order_info["state"]
        remain = int(order_info["sz"]) - int(order_info["accFillSz"])
        avg_price = order_info.get("avgPx")
        # avg_price if avg_price else 0
        # ctime = tools.utctime_str_to_ms(order_info["cTime"])
        # utime = tools.utctime_str_to_ms(order_info["uTime"])

        if state == "-2":
            status = ORDER_STATUS_FAILED
        elif state == "canceled":
            status = ORDER_STATUS_CANCELED
        elif state == "live":
            status = ORDER_STATUS_SUBMITTED
        elif state == "partially_filled":
            status = ORDER_STATUS_PARTIAL_FILLED
        elif state == "filled":
            status = ORDER_STATUS_FILLED
        else:
            logger.error("status error! order_info:", order_info, caller=self)
            SingleTask.run(self._error_callback, "order status error.")
            return None

        order = self._orders.get(order_id)
        if not order:
            info = {
                "platform": self._platform,
                "account": self._account,
                "strategy": self._strategy,
                "symbol": order_info["instId"],
                "order_id": int(order_id),
                "client_order_id": order_info["clOrdId"],
                "action": ORDER_ACTION_BUY if order_info["side"] == "buy" else ORDER_ACTION_SELL,
                "price": order_info["px"],
                "quantity": order_info["sz"],
                "ctime": int(order_info["cTime"])
            }
            order = Order(**info)
            self._orders[order_id] = order
        order.remain = remain
        order.status = status
        order.avgPx = order_info["avgPx"]
        order.lastPx = order_info["fillPx"]
        order.lastSz = order_info["fillSz"]
        order.lastFee = order_info["fillFee"]
        order.fee = order_info["fee"]
        order.pnl = order_info["pnl"]
        order.utime = int(order_info["uTime"])

        SingleTask.run(self._order_update_callback, copy.copy(order))
        if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
            self._orders.pop(order_id)
    
    def _update_positions(self, pos_info):
        for pos in pos_info:
            symbol = pos["instId"]
            position = self._positions.get(symbol)
            if not position:
                info = {
                    "platform": self._platform,
                    "account": self._account,
                    "strategy": self._strategy,
                    "symbol": symbol
                }
                position = Position(**info)
                self._positions[symbol] = position

            position.amount = int(pos["pos"])
            position.price = float(pos["avgPx"])
            position.timestamp = int(pos["uTime"])
            SingleTask.run(self._position_update_callback, copy.copy(position))
            """
            if position.amount == 0:
                self._positions.pop(symbol)
            """
    
    def _update_account(self, acc_info):
        for acc in acc_info:
            self._assets.assets[acc["ccy"]] = {acc["cashBal"]}
            self._assets.timestamp = int(acc["uTime"])
        self._assets.update = True

