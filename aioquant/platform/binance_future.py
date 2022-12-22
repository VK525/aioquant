import time
import json
import copy
import hmac
import hashlib
from urllib.parse import urljoin
from urllib.parse import urlencode

from aioquant.error import Error
from aioquant.utils import tools
from aioquant.utils import logger
from aioquant.asset import Asset
from aioquant.order import Order
from aioquant.position import Position
from aioquant.tasks import SingleTask, LoopRunTask
from aioquant.utils.decorator import async_method_locker
from aioquant.utils.web import Websocket, AsyncHttpRequests
from aioquant.order import ORDER_ACTION_SELL, ORDER_ACTION_BUY, ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET
from aioquant.order import ORDER_STATUS_SUBMITTED, ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED, \
    ORDER_STATUS_CANCELED, ORDER_STATUS_FAILED


__all__ = ("BinanceRestAPI", "BinanceTrade", )


class BinanceRestAPI:
    """Binance REST API client.

    Attributes:
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        host: HTTP request host, default `https://fapi.binance.com`.
    """

    def __init__(self, access_key, secret_key, host=None):
        """Initialize REST API client."""
        self._host = host or "https://fapi.binance.com"
        self._access_key = access_key
        self._secret_key = secret_key

    async def ping(self):
        """Test connectivity.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/ping"
        success, error = await self.request("GET", uri)
        return success, error

    async def get_server_time(self):
        """Get server time.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/time"
        success, error = await self.request("GET", uri)
        return success, error
    
    async def get_local_time(self):
        t = time.time()
        return int(t * 1000)

    async def get_exchange_info(self):
        """Get exchange information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/exchangeInfo"
        success, error = await self.request("GET", uri)
        return success, error

    async def get_orderbook(self, symbol, limit=10):
        """Get latest orderbook information.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            limit: Number of results per request. (default 10, max 5000.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/depth"
        params = {
            "symbol": symbol,
            "limit": limit
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_trade(self, symbol, limit=500):
        """Get latest trade information.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            limit: Number of results per request. (Default 500, max 1000.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/trades"
        params = {
            "symbol": symbol,
            "limit": limit
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_kline(self, symbol, interval="1m", start=None, end=None, limit=500):
        """Get kline information.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            interval: Kline interval type, valid values: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
            start: Start timestamp(millisecond).
            end: End timestamp(millisecond).
            limit: Number of results per request. (Default 500, max 1000.)

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.

        Notes:
            If start and end are not sent, the most recent klines are returned.
        """
        uri = "/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start and end:
            params["startTime"] = start
            params["endTime"] = end
        success, error = await self.request("GET", uri, params=params)
        return success, error

    async def get_premium_index(self, symbol=None):
        # 最新标记价格和资金费率
        uri = "/fapi/v1/premiumIndex"
        params = {
            "symbol": symbol
        }
        success, error = await self.request("GET", uri, params=params)
        return success, error
        
    async def get_funding_rate(self, symbol=None, start=None, end=None, limit=100):
        # 查询资金费率历史
        uri = "/fapi/v1/fundingRate"
        params = {
            "limit": limit
        }
        if symbol:
            params["symbol"] = symbol
        if start:
            params["start"] = start
        if end:
            params["end"] = end
            
        success, error = await self.request("GET", uri, params=params)
        return success, error
    
    async def get_ticker(self, symbol=None):
        # 当前最优挂单 不发送交易对参数，则会返回所有交易对信息
        uri = "/fapi/v1/ticker/bookTicker"
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        success, error = await self.request("GET", uri, params=params)
        return success, error
        
    async def get_ticker_24hr(self, symbol=None):
        # 24h 全币种数据
        uri = "/fapi/v1/ticker/24hr"
        params = {}
        if symbol:
            params["symbol"] = symbol
            
        success, error = await self.request("GET", uri, params=params)
        return success, error
    
    
    async def get_user_balance(self):
        uri = "/fapi/v2/balance"
        params = {
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params, auth=True)
        return success, error
    
    
    async def get_user_account(self):
        """Get user account information.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v2/account"
        params = {
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params, auth=True)
        return success, error
        
    async def order_plus(self, orders):
        uri = "/fapi/v1/batchOrders"
        data = {
            "recvWindow": "5000",
            "timestamp": tools.get_cur_timestamp_ms()
            }
            
        query_string = urlencode(orders)
        query_string = query_string.replace('%27', '%22')
        data['batchOrders'] = query_string[12:]
            
        success, error = await self.request("POST", uri, body=data, auth=True)
        return success, error

    async def create_order(self, action, symbol, quantity, price=None, reduceOnly=False, client_order_id=None, timeInForce="GTC", test=False):
        """Create an order.
        Args:
            action: Trade direction, `BUY` or `SELL`.
            symbol: Symbol name, e.g. `BTCUSDT`.
            price: Price of each contract.
            quantity: The buying or selling quantity.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/order/test" if test else "/fapi/v1/order"
        data = {
            "symbol": symbol,
            "side": action,
            "type": "MARKET",
            "quantity": quantity,
            "recvWindow": "5000",
            "reduceOnly": reduceOnly,
            "newOrderRespType": "ACK",
            "timestamp": int(time.time() * 1000)
        }
        # "timestamp": tools.get_cur_timestamp_ms()
        if price:
            data["type"] = "LIMIT"
            data["price"] = price
            data["timeInForce"] = timeInForce
        
        if client_order_id:
            data["newClientOrderId"] = client_order_id
        success, error = await self.request("POST", uri, body=data, auth=True)
        return success, error

    async def revoke_order(self, symbol, order_id, client_order_id=None):
        # 撤销订单 
        """Cancelling an unfilled order.
        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            order_id: Order id.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/order"
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        success, error = await self.request("DELETE", uri, params=params, auth=True)
        return success, error

    async def get_order_status(self, symbol, order_id, client_order_id=None):
        # 查询订单
        """Get order details by order id.

        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.
            order_id: Order id.
            client_order_id: Client order id.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/order"
        params = {
            "symbol": symbol,
            "orderId": str(order_id),
            "timestamp": tools.get_cur_timestamp_ms()
        }
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_all_orders(self, symbol):
        # 查询所有订单(包括历史订单)
        """Get all account orders; active, canceled, or filled.
        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/allOrders"
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def get_open_orders(self, symbol):
        # 查看当前全部挂单
        """Get all open order information.
        Args:
            symbol: Symbol name, e.g. `BTCUSDT`.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/openOrders"
        params = {
            "symbol": symbol,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error
    
    async def set_leverage(self, symbol, leverage):
        # 调整开仓杠杆
        uri = "/fapi/v1/leverage"
        params = {
            "symbol": symbol,
            "leverage": leverage,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("POST", uri, params=params, auth=True)
        return success, error
    
    # POS 
    async def set_positionSide_dual(self, dual):
        # 更改持仓模式(TRADE)
        uri = "/fapi/v1/positionSide/dual"
        data = {
            "dualSidePosition": dual,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("POST", uri, body=data, auth=True)
        return success, error
    
    async def get_listen_key(self):
        # 生成listenKey 
        """Get listen key, start a new user data stream.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/listenKey"
        success, error = await self.request("POST", uri)
        return success, error

    async def put_listen_key(self, listen_key):
        # 延长listenKey有效期
        """Keepalive a user data stream to prevent a time out.

        Args:
            listen_key: Listen key.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/listenKey"
        success, error = await self.request("PUT", uri)
        return success, error

    async def delete_listen_key(self, listen_key):
        # 关闭listenKey
        """Delete a listen key.

        Args:
            listen_key: Listen key.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        uri = "/fapi/v1/listenKey"
        success, error = await self.request("DELETE", uri)
        return success, error
    
    async def get_income(self,symbol=None,incomeType=None,startTime=None,endTime=None,limit=1000):
        """获取资金流水
        Args:
            symbol: "btcusdt"
            incomeType: "REALIZED_PNL"已实现盈亏，"FUNDING_FEE"资金费用，"COMMISSION"手续费
            startTime: 开始时间
            endTime: 结束时间
            limit: 返回的结果集数量 默认值:100 最大值:1000
        """
        uri = "/fapi/v1/income"
        params = {
            "symbol": symbol,
            "incomeType":incomeType,
            "startTime":startTime,
            "endTime":endTime,
            "limit":limit,
            "timestamp": tools.get_cur_timestamp_ms()
        }
        success, error = await self.request("GET", uri, params=params, auth=True)
        return success, error

    async def request(self, method, uri, params=None, body=None, headers=None, auth=False):
        """Do HTTP request.

        Args:
            method: HTTP request method. `GET` / `POST` / `DELETE` / `PUT`.
            uri: HTTP request uri.
            params: HTTP query params.
            body:   HTTP request body.
            headers: HTTP request headers.
            auth: If this request requires authentication.

        Returns:
            success: Success results, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        url = urljoin(self._host, uri)
        data = {}
        if params:
            data.update(params)
        if body:
            data.update(body)

        if data:
            query = "&".join(["=".join([str(k), str(v)]) for k, v in data.items()])
        else:
            query = ""
        if auth and query:
            signature = hmac.new(self._secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
            query += "&signature={s}".format(s=signature)
        if query:
            url += ("?" + query)

        if not headers:
            headers = {}
        headers["X-MBX-APIKEY"] = self._access_key
        _, success, error = await AsyncHttpRequests.fetch(method, url, headers=headers, timeout=10, verify_ssl=False)
        return success, error


class BinanceFutureTrade:
    """Binance Trade module. You can initialize trade object with some attributes in kwargs.

    Attributes:
        account: Account name for this trade exchange.
        strategy: What's name would you want to created for your strategy.
        symbol: Symbol name for your trade.
        host: HTTP request host. (default "https://fapi.binance.com")
        wss: Websocket address. (default "wss://stream.binance.com:9443")
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
        if not kwargs.get("level"):
            kwargs["level"] = 20
        if not kwargs.get("symbol"):
            e = Error("param symbol miss")
        if not kwargs.get("host"):
            kwargs["host"] = "https://fapi.binance.com"
        if not kwargs.get("wss"):
            kwargs["wss"] = "wss://fstream.binance.com"
        if not kwargs.get("access_key"):
            e = Error("param access_key miss")
        if not kwargs.get("secret_key"):
            e = Error("param secret_key miss")
        if e:
            logger.error(e, caller=self)
            SingleTask.run(kwargs["error_callback"], e)
            SingleTask.run(kwargs["init_callback"], False)


        self._account = kwargs["account"]
        self._strategy = kwargs["strategy"]
        self._platform = kwargs["platform"]
        self._symbol = kwargs["symbol"]
        self._level = kwargs["level"]
        self._host = kwargs["host"]
        self._wss = kwargs["wss"]
        self._access_key = kwargs["access_key"]
        self._secret_key = kwargs["secret_key"]
        
        self._asset_update_callback = kwargs.get("asset_update_callback")
        self._order_update_callback = kwargs.get("order_update_callback")
        self._position_update_callback = kwargs.get("position_update_callback")
        self._init_callback = kwargs.get("init_callback")
        self._error_callback = kwargs.get("error_callback")

        # self._raw_symbol = self._symbol.replace(["/","-"], ["",""])  # Row symbol name, same as Binance Exchange.
        self._listen_key = None  # Listen key for Websocket authentication.
        self._assets = Asset(self._platform, self._account)  # Asset data. e.g. {"BTC": {"free": "1.1", "locked": "2.2", "total": "3.3"}, ... }
        self._orders = {}  # Order data. e.g. {order_id: order, ... }
        self._positions = {}

        # Initialize our REST API client.
        self._rest_api = BinanceRestAPI(self._access_key, self._secret_key, self._host)

        # Create a loop run task to reset listen key every 30 minutes.
        LoopRunTask.register(self._reset_listen_key, 60 * 30)

        # Create a coroutine to initialize Websocket connection.
        SingleTask.run(self._init_websocket)

        # LoopRunTask.register(self._send_heartbeat_msg, 5)

    async def _send_heartbeat_msg(self, *args, **kwargs):
        await self._ws.ping()

    @property
    def orders(self):
        return copy.copy(self._orders)
        
    @property
    def positions(self):
        return copy.copy(self._positions)

    @property
    def rest_api(self):
        return self._rest_api

    async def _init_websocket(self):
        """Initialize Websocket connection."""
        # Get listen key first.
        success, error = await self._rest_api.get_listen_key()
        if error:
            e = Error("get listen key failed: {}".format(error))
            logger.error(e, caller=self)
            SingleTask.run(self._error_callback, e)
            SingleTask.run(self._init_callback, False)
            return
        self._listen_key = success["listenKey"]
        uri = "/ws/" + self._listen_key
        url = urljoin(self._wss, uri)
        
        self._ws = Websocket(url, self.connected_callback, process_callback=self.process)
        LoopRunTask.register(self._send_heartbeat_msg, 5)

    async def _reset_listen_key(self, *args, **kwargs):
        """Reset listen key."""
        if not self._listen_key:
            logger.error("listen key not initialized!", caller=self)
            return
        await self._rest_api.put_listen_key(self._listen_key)
        logger.info("reset listen key success!", caller=self)

    async def connected_callback(self):
        """After websocket connection created successfully, pull back all open order information."""
        #logger.info("Websocket connection authorized successfully.", caller=self)
        if self._order_update_callback:
            logger.info("---[ order_callback ]---", caller=self)
            order_infos, error = await self._rest_api.get_open_orders(self._symbol) 
            if error:
                e = Error("get open orders error: {}".format(error))
                SingleTask.run(self._error_callback, e)
                SingleTask.run(self._init_callback, False)
                return
            for order_info in order_infos:
                if order_info["status"] == "NEW":
                    status = ORDER_STATUS_SUBMITTED
                elif order_info["status"] == "PARTIALLY_FILLED":
                    status = ORDER_STATUS_PARTIAL_FILLED
                elif order_info["status"] == "FILLED":
                    status = ORDER_STATUS_FILLED
                elif order_info["status"] == "CANCELED":
                    status = ORDER_STATUS_CANCELED
                elif order_info["status"] == "REJECTED":
                    status = ORDER_STATUS_FAILED
                elif order_info["status"] == "EXPIRED":
                    status = ORDER_STATUS_FAILED
                else:
                    logger.warn("unknown status:", order_info, caller=self)
                    SingleTask.run(self._error_callback, "order status error.")
                    continue

                order_id = str(order_info["orderId"])
                info = {
                    "platform": self._platform,
                    "account": self._account,
                    "strategy": self._strategy,
                    "symbol": self._symbol,
                    "order_id": order_id,
                    "client_order_id": order_info["clientOrderId"],
                    "status": status,
                    "action": order_info["side"],
                    "price": float(order_info["price"]),
                    "quantity": float(order_info["origQty"]),
                    "remain": float(order_info["origQty"]) - float(order_info["executedQty"]),
                    "avg_price": float(order_info["avgPrice"]),
                    "order_type" : order_info["origType"],
                    "trade_type" : order_info["type"],
                    "ctime": order_info["time"],
                    "utime": order_info["updateTime"]
                }
                order = Order(**info)
                self._orders[order_id] = order
                SingleTask.run(self._order_update_callback, copy.copy(order))
        
        # account position update
        if self._position_update_callback and self._asset_update_callback:
            logger.info("---[ position_callback  &  assets_callback ]---", caller=self)
            acc_infos, error = await self._rest_api.get_user_account()
            if error:
                e = Error("get position error: {}".format(error))
                SingleTask.run(self._error_callback, e)
                SingleTask.run(self._init_callback, False)
                return
            
            # account callback
            for bl in acc_infos["assets"]:
                self._assets.assets[bl["asset"]] = {"wb": float(bl["walletBalance"]),"cw": float(bl["crossWalletBalance"])}
            self._assets.timestamp = acc_infos["assets"][0]["updateTime"]
            self._assets.update = True
            SingleTask.run(self._asset_update_callback, copy.copy(self._assets))
            
            # position callback
            for pos in acc_infos["positions"]:
                # 跳过持仓为零
                if float(pos["positionAmt"]) == 0.0:
                    continue
                info = {
                    "platform": self._platform,
                    "account": self._account,
                    "strategy": self._strategy,
                    "symbol": pos["symbol"],
                    "amount": float(pos["positionAmt"]),
                    "price": float(pos["entryPrice"]),
                    "unfit": float(pos["unrealizedProfit"]),
                    "timestamp": pos["updateTime"]
                }
                position = Position(**info)
                self._positions[pos["symbol"]] = position
                SingleTask.run(self._position_update_callback, copy.copy(position))
            
        SingleTask.run(self._init_callback, True)


    @async_method_locker("BinanceTrade.process.locker")
    async def process(self, msgs):
        """Process message that received from Websocket connection.

        Args:
            msg: message received from Websocket connection.
        """
        logger.debug("msgs:", msgs, caller=self)
        e = msgs.get("e")
        if e == "ORDER_TRADE_UPDATE" and self._order_update_callback: 
            # Order update.
            msg = msgs["o"]
            order_id = str(msg["i"])
            if msg["X"] == "NEW":
                status = ORDER_STATUS_SUBMITTED
            elif msg["X"] == "PARTIALLY_FILLED":
                status = ORDER_STATUS_PARTIAL_FILLED
            elif msg["X"] == "FILLED":
                status = ORDER_STATUS_FILLED
            elif msg["X"] == "CANCELED":
                status = ORDER_STATUS_CANCELED
            elif msg["X"] == "REJECTED":
                status = ORDER_STATUS_FAILED
            elif msg["X"] == "EXPIRED":
                status = ORDER_STATUS_FAILED
            else:
                logger.warn("unknown status:", msg, caller=self)
                SingleTask.run(self._error_callback, "order status error.")
                return
            order = self._orders.get(order_id)
            if not order:
                info = {
                    "platform": self._platform,
                    "account": self._account,
                    "strategy": self._strategy,
                    "symbol": msg["s"],
                    "order_id": order_id,
                    "client_order_id": msg["c"],
                    "action": msg["S"],
                    "order_type": msg["ot"],
                    "trade_type" : msg["o"],
                    "price": float(msg["p"]),
                    "quantity": float(msg["q"]),
                    "ctime": msgs["T"]
                }
                order = Order(**info)
                self._orders[order_id] = order
            order.remain = float(msg["q"]) - float(msg["z"])
            order.status = status
            order.avg_price = float(msg["ap"])
            order.last_price = float(msg["L"])
            order.last_size = float(msg["l"])
            order.pnl = float(msg["rp"])
            order.utime = msgs["E"]
            if order.status in [ORDER_STATUS_PARTIAL_FILLED, ORDER_STATUS_FILLED]:
                order.fee = float(msg["n"])

            SingleTask.run(self._order_update_callback, copy.copy(order))
            if status in [ORDER_STATUS_FAILED, ORDER_STATUS_CANCELED, ORDER_STATUS_FILLED]:
                self._orders.pop(order_id)
        
        elif e == "ACCOUNT_UPDATE":
            #  Position update 
            posInfo = msgs["a"]["P"]
            for pos in posInfo:
                symbol = pos["s"]
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
                
                position.amount = float(pos["pa"])
                position.price = float(pos["ep"])
                position.unfit = float(pos["up"])
                position.timestamp = msgs["E"]
                SingleTask.run(self._position_update_callback, copy.copy(position))
                """
                if position.amount == 0:
                    self._positions.pop(symbol)
                """
                
            # Account update
            acc = msgs["a"]["B"]
            for bl in acc:
                self._assets.assets[bl["a"]] = {"wb": float(bl["wb"]),"cw":float(bl["cw"])}
            self._assets.timestamp = msgs["E"]
            self._assets.update = True
            
            SingleTask.run(self._asset_update_callback, copy.copy(self._assets))
    
    async def create_order(self, action, quantity, price=None, *args, **kwargs):
        """Create an order.

        Args:
            action: Trade direction, `BUY` or `SELL`.
            price: Price of each order.
            quantity: The buying or selling quantity.

        Returns:
            order_id: Order id if created successfully, otherwise it's None.
            error: Error information, otherwise it's None.
        """
        result, error = await self._rest_api.create_order(action, self._symbol, quantity, price, *args, **kwargs)
        if error:
            SingleTask.run(self._error_callback, error)
            return None, error
        order_id = str(result["orderId"])
        return order_id, None

    async def revoke_order(self, *args, **kwargs):
        """Revoke (an) order(s).

        Args:
            order_ids: Order id list, you can set this param to 0 or multiple items. If you set 0 param, you can cancel
                all orders for this symbol(initialized in Trade object). If you set 1 param, you can cancel an order.
                If you set multiple param, you can cancel multiple orders. Do not set param length more than 100.

        Returns:
            Success or error, see bellow.
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
            success, error = await self._rest_api.revoke_order(self._symbol, args[0])
            if error:
                SingleTask.run(self._error_callback, error)
                return args[0], error
            else:
                return args[0], None
        if kwargs:
            success, error = [], []
            for order_id in kwargs["ids"]:
                _, e = await self._rest_api.revoke_order(self._symbol, order_id)
                if e:
                    SingleTask.run(self._error_callback, e)
                    error.append((order_id, e))
                else:
                    success.append(order_id)
            return success, error

    async def get_open_order_ids(self):
        """Get open order id list.
        """
        success, error = await self._rest_api.get_open_orders(self._symbol)
        if error:
            SingleTask.run(self._error_callback, error)
            return None, error
        else:
            order_ids = []
            for order_info in success:
                order_id = str(order_info["orderId"])
                order_ids.append(order_id)
            return order_ids, None
    
    async def set_level(self, lv=None):
        if not lv:
            lv =self._level
        success, error = await self._rest_api.set_leverage(self._symbol, lv)
        if error:
            SingleTask.run(self._error_callback, {"setleve error":error})
        return success, None