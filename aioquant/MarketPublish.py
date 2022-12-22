from multiprocessing.connection import wait
import time
from aioquant import const
from aioquant.error import Error
from aioquant.utils import logger
from aioquant.utils.web import Websocket
from aioquant.tasks import SingleTask, LoopRunTask
from aioquant.utils.decorator import async_method_locker
from aioquant.order import ORDER_ACTION_SELL, ORDER_ACTION_BUY
from aioquant.market import Orderbook, Trade, Kline, Status, ConfigSet
import pandas as pd


class MarketPublish:
    """Subscribe Market.

    Args:
        market_type: Market data type,
            MARKET_TYPE_TRADE = "trade"
            MARKET_TYPE_ORDERBOOK = "orderbook"
            MARKET_TYPE_KLINE = "kline"
            MARKET_TYPE_KLINE_5M = "kline_5m"
            MARKET_TYPE_KLINE_15M = "kline_15m"
        platform: Exchange platform name, e.g. `binance` / `bitmex`.
        symbol: Trade pair name, e.g. `ETH/BTC`.
        callback: Asynchronous callback function for market data update.
                e.g. async def on_event_kline_update(kline: Kline):
                        pass
    """

    def __init__(self, market_type, platform, symbol, wss):
    
        self._platform = platform
        self._symbol = symbol
        self._wss = wss
        self._event_orderbook = None
        self._event_trade = None
        self._event_status = None
        self._event_config_set = None
        
        SingleTask.run(self._init_websocket, market_type)

        LoopRunTask.register(self._send_heartbeat_msg, 5)

    async def _send_heartbeat_msg(self, *args, **kwargs):
        await self._ws.ping()
        
    async def _init_websocket(self, market_type):
        """Initialize Websocket connection."""
        okex_params = {"op": "subscribe","args": []}
        binance_params = {"method": "SUBSCRIBE","params":[],"id": 111}
        """Initialize."""
        if self._platform == "#" or self._symbol == "#":
            multi = True
        else:
            multi = False
        
        if market_type == const.MARKET_TYPE_ORDERBOOK:
            from aioquant.event import EventOrderbook
            self._event_orderbook = EventOrderbook(Orderbook(self._platform, self._symbol))
            if self._platform == const.OKEX_FUTURE:
                okex_params["args"].append({"channel": "books5","instId":self._symbol})
            elif self._platform == const.BINANCE_FUTURE:
                binance_params["params"].append(self._symbol+"@depth5@100ms")
            elif self._platform == const.BINANCE:
                binance_params["params"].append(self._symbol+"@depth5@100ms")
        
        elif market_type == const.MARKET_TYPE_TRADE:
            from aioquant.event import EventTrade
            self._event_trade = EventTrade(Trade(self._platform, self._symbol))
            if self._platform == const.OKEX_FUTURE:
                okex_params["args"].append({"channel": "trades","instId":self._symbol})
            elif self._platform == const.BINANCE_FUTURE:
                binance_params["params"].append(self._symbol+"@aggTrade")
        
        elif market_type == const.SYSTEM_STATUS:
            from aioquant.event import EventStatus
            self._event_status = EventStatus(Status(self._platform))
            if self._platform == const.OKEX_FUTURE:
                okex_params["args"].append({"channel": "status"})
            elif self._platform == const.BINANCE_FUTURE:
                logger.error("market_type error: binance not ", market_type, caller=self)
        else:
            logger.error("market_type error:", market_type, caller=self)
            
        if self._platform == const.OKEX_FUTURE:
            url = self._wss + "/ws/v5/public"
            self._ws = Websocket(url, process_callback=self.process_okex)
            logger.info("subscribe :", okex_params, caller=self)
            SingleTask.call_later(self._ws.send, 3, okex_params)
        
        elif self._platform == const.BINANCE_FUTURE:
            url = self._wss + "/ws/"
            self._ws = Websocket(url, process_callback=self.process_binance_future)
            logger.info("subscribe :", binance_params, caller=self)
            SingleTask.call_later(self._ws.send, 3, binance_params)

        elif self._platform == const.BINANCE:
            url = self._wss + "/ws/" + str(self._symbol) + "@depth5@100ms"
            self._ws = Websocket(url, process_callback=self.process_binance)
            logger.info("subscribe :", binance_params, caller=self)
            SingleTask.call_later(self._ws.send, 3, binance_params)

    @async_method_locker("process_okex", wait=True, timeout=5)
    async def process_okex(self, msg):
        if msg == "pong" or msg.get("event"):
            return
        logger.debug("msg:", msg, caller=self)
        if msg.get("arg"):
            if msg["arg"]["channel"] == "books5":
                #print(msg["data"][0])
                depth = msg["data"][0]
                info = {
                    "platform": self._platform,
                    "symbol": msg["arg"]["instId"],
                    "asks": depth["asks"],
                    "bids": depth["bids"],
                    "timestamp":int(depth["ts"])
                }
                self._event_orderbook._data = Orderbook(**info).smart
                self._event_orderbook.publish()
                #EventOrderbook(Orderbook(**info)).publish()
            
            elif msg["arg"]["channel"] == "trades":
                trades = msg["data"][0]
                info = {
                    "platform" : self._platform,
                    "symbol" : msg["arg"]["instId"],
                    "action" : ORDER_ACTION_BUY if trades["side"] == "buy" else ORDER_ACTION_SELL,
                    "price" : float(trades["px"]),
                    "quantity" :int(trades["sz"]),
                    "timestamp" : int(trades["ts"])
                }
                self._event_trade._data = Trade(**info).smart
                self._event_trade.publish()
            
            elif msg["arg"]["channel"] == "status":
                info = msg["data"][0]
                # 系统状态
                state = None
                if info["state"] == "scheduled":
                    state = "Holding"
                elif info["state"] == "ongoing":
                    state = "UpDateing"
                elif info["state"] == "completed":
                    state = "End"
                else:
                    state = "Cancel"
                
                # 升级服务类型
                serviceType = None
                if info["serviceType"] =="0":
                    serviceType = "WebSocket"
                elif info["serviceType"] =="1":
                    serviceType = "Spot"
                elif info["serviceType"] =="2":
                    serviceType = "Dley"
                elif info["serviceType"] =="3":
                    serviceType = "Swap"
                elif info["serviceType"] =="4":
                    serviceType = "Option"
                else:
                    serviceType = "TradeServer"
                          
                begin = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(info["begin"])/1000))
                end = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(info["end"])/1000))
                msg = {
                    "title": info["title"],
                    "state": state,
                    "begin": begin,
                    "end": end,
                    "serviceType": serviceType,
                    "scheDesc": info["scheDesc"],
                    "beginTimestamp":info["begin"]
                }
                obj = {"platform":self._platform, "msg":msg, "timestamp":info["ts"]}
               
                self._event_status._data = Status(**obj).smart
                self._event_status.publish()
            
    @async_method_locker("process_binance_future", wait=True, timeout=5)
    async def process_binance_future(self, msg):
        logger.debug("msg:", msg, caller=self)
        if msg.get("e"):
            if msg["e"] == "depthUpdate":
                info = {
                    "platform": self._platform,
                    "symbol": msg["s"],
                    "asks": msg["a"],
                    "bids": msg["b"],
                    "timestamp":msg["E"]
                }
                self._event_orderbook._data = Orderbook(**info).smart
                self._event_orderbook.publish()
            
            elif msg["e"] == "aggTrade":
                info = {
                    "platform" : self._platform,
                    "symbol" : msg["s"],
                    "action" : ORDER_ACTION_SELL if msg["m"] else ORDER_ACTION_BUY,
                    "price" : float(msg["p"]),
                    "quantity" : float(msg["q"]),
                    "timestamp" : msg["E"]
                }
                self._event_trade._data = Trade(**info).smart
                self._event_trade.publish()
            
    @async_method_locker("process_binance", wait=True, timeout=5)
    async def process_binance(self, msg):
        logger.debug("msg:",msg,caller=self)
        if msg.get("lastUpdateId"):
            info = {
                "platform": self._platform,
                "symbol": self._symbol,
                "asks": msg["asks"],
                "bids": msg["bids"],
                "timestamp":msg["lastUpdateId"]
            }
            self._event_orderbook._data = Orderbook(**info).smart
            self._event_orderbook.publish()