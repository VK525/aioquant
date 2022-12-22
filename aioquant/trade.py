import copy

from aioquant import const
from aioquant.utils import tools
from aioquant.error import Error
from aioquant.utils import logger
from aioquant.tasks import SingleTask
from aioquant.order import ORDER_TYPE_LIMIT
from aioquant.asset import Asset
from aioquant.order import Order
from aioquant.position import Position



class Trade:
    """ Trade Module.

    Attributes:
        strategy: What's name would you want to created for your strategy.
        platform: Exchange platform name. e.g. `binance` / `okex` / `bitmex`.
        symbol: Symbol name for your trade. e.g. `BTC/USDT`.
        host: HTTP request host.
        wss: Websocket address.
        account: Account name for this trade exchange.
        access_key: Account's ACCESS KEY.
        secret_key: Account's SECRET KEY.
        passphrase: API KEY Passphrase. (Only for `OKEx`)
        asset_update_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `asset_update_callback` is like `async def on_asset_update_callback(asset: Asset): pass` and this
            callback function will be executed asynchronous when received AssetEvent.
        order_update_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `order_update_callback` is like `async def on_order_update_callback(order: Order): pass` and this
            callback function will be executed asynchronous when some order state updated.
        position_update_callback: You can use this param to specific a async callback function when you initializing
            Trade object. `position_update_callback` is like `async def on_position_update_callback(position: Position): pass`
            and this callback function will be executed asynchronous when position updated.
        init_success_callback: You can use this param to specific a async callback function when you initializing Trade
            object. `init_success_callback` is like `async def on_init_success_callback(success: bool, error: Error, **kwargs): pass`
            and this callback function will be executed asynchronous after Trade module object initialized successfully.
    """

    def __init__(self, strategy=None, platform=None, symbol=None, level=20,host=None, wss=None, account=None, access_key=None,
                 secret_key=None, passphrase=None, asset_update_callback=None, order_update_callback=None,
                 position_update_callback=None, init_callback=None, error_callback=None, **kwargs):
        """initialize trade object."""
        kwargs["strategy"] = strategy
        kwargs["platform"] = platform
        kwargs["symbol"] = symbol
        kwargs["level"] = level
        kwargs["host"] = host
        kwargs["wss"] = wss
        kwargs["account"] = account
        kwargs["access_key"] = access_key
        kwargs["secret_key"] = secret_key
        kwargs["passphrase"] = passphrase
        kwargs["asset_update_callback"] = self._on_asset_update_callback
        kwargs["order_update_callback"] = self._on_order_update_callback
        kwargs["position_update_callback"] = self._on_position_update_callback
        kwargs["init_callback"] = self._on_init_callback
        kwargs["error_callback"] = self._on_error_callback

        self._raw_params = copy.copy(kwargs)
        self._asset_update_callback = asset_update_callback
        self._order_update_callback = order_update_callback
        self._position_update_callback = position_update_callback
        self._init_callback = init_callback
        self._error_callback = error_callback

        
        if platform == const.OKEX_FUTURE:
            from aioquant.platform.okex_future import OKExFutureTrade as T
        elif platform == const.BINANCE_FUTURE:
            from aioquant.platform.binance_future import BinanceFutureTrade as T
        else:
            logger.error("platform error:", platform, const.OKEX_FUTURE, caller=self)
            e = Error("platform error")
            SingleTask.run(self._init_callback, False, e)
            return
        #kwargs.pop("platform")
        self._t = T(**kwargs)

    @property
    def assets(self):
        return self._t.assets

    @property
    def orders(self):
        return self._t.orders

    @property
    def positions(self):
        return self._t.positions

    @property
    def rest_api(self):
        return self._t.rest_api
    
    async def set_level(self, lv=None):
        success, error = await self._t.set_level(lv)
        return success, error
    
    async def ws_order(self, action, quantity, price, ordType="limit",clOrdId=None ,reduceOnly=False):
        success = await self._t.ws_order(action.lower(), quantity, price, ordType, clOrdId ,reduceOnly)
        
    # action, quantity, price=None, reduceOnly=False, timeInForce="GTC", client_order_id=None, test=False
    async def create_order(self, action, quantity, price=None, *args, **kwargs):
        """ Create an order.
        """
        success, error = await self._t.create_order(action, quantity, price, *args, **kwargs)
        return success, error
    
    async def create_orders(self, buysymbol, buyprice, buyamount, sellsymbol, sellprice, sellamount, clid, *args, **kwargs):
        
        data=[{"instId":sellsymbol,"tdMode":"cross","clOrdId":clid,"side":"sell","ordType":"limit","px":sellprice,"sz":sellamount},
              {"instId":buysymbol,"tdMode":"cross","clOrdId":clid,"side":"buy","ordType":"limit","px":buyprice,"sz":buyamount}]
        success, error = await self._t.create_orders(data, *args, **kwargs)
        return success, error

    async def revoke_order(self, *args, **kwargs):
        """ Revoke (an) order(s).
        """
        success, error = await self._t.revoke_order(*args, **kwargs)
        return success, error

    async def get_open_order_ids(self,*args, **kwargs):
        """ Get open order id list.
        """
        success, error = await self._t.get_open_order_ids(*args, **kwargs)
        return success, error
    
    async def _on_asset_update_callback(self, asset:Asset):
        """Asset information update callback.
        """
        if self._asset_update_callback:
            SingleTask.run(self._asset_update_callback, asset)
    
    async def _on_order_update_callback(self, order: Order):
        """ Order information update callback.
        """
        if self._order_update_callback:
            SingleTask.run(self._order_update_callback, order)
    
    async def _on_position_update_callback(self, position: Position):
        """ Position information update callback.
        """
        if self._position_update_callback:
            SingleTask.run(self._position_update_callback, position)

    async def _on_init_callback(self, success: bool) -> None:
        """ Callback function when initialize Trade module finished.
        """
        if self._init_callback:
            params = {
                "strategy": self._raw_params["strategy"],
                "platform": self._raw_params["platform"],
                "symbol": self._raw_params["symbol"],
                "account": self._raw_params["account"]
            }
            await self._init_callback(success, **params)
    
    async def _on_error_callback(self, error: Error) -> None:
        """ Callback function when some error occur while Trade module is running.
        """
        if self._error_callback:
            params = {
                "strategy": self._raw_params["strategy"],
                "platform": self._raw_params["platform"],
                "symbol": self._raw_params["symbol"],
                "account": self._raw_params["account"]
            }
            await self._error_callback(error, **params)