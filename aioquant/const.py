# Exchange Names
BINANCE = "binance"  # Binance https://www.binance.com
BINANCE_FUTURE = "binance_future"  # https://www.binance-cn.com/cn/futures/BTCUSDT
BITFINEX = "bitfinex"


OKEX = "okex"  # OKEx SPOT https://www.okex.me/spot/trade
OKEX_FUTURE = "okex_future"  # OKEx FUTURE https://www.okex.me/future/trade

SYSTEM_STATUS = "system_status"

# Market Types
CONFIG_SET = "config_set"
MARKET_TYPE_TRADE = "trade"
MARKET_TYPE_ORDERBOOK = "orderbook"
MARKET_TYPE_KLINE = "kline"
MARKET_TYPE_KLINE_3M = "kline_3m"
MARKET_TYPE_KLINE_5M = "kline_5m"
MARKET_TYPE_KLINE_15M = "kline_15m"
MARKET_TYPE_KLINE_30M = "kline_30m"
MARKET_TYPE_KLINE_1H = "kline_1h"
MARKET_TYPE_KLINE_3H = "kline_3h"
MARKET_TYPE_KLINE_6H = "kline_6h"
MARKET_TYPE_KLINE_12H = "kline_12h"
MARKET_TYPE_KLINE_1D = "kline_1d"
MARKET_TYPE_KLINE_3D = "kline_3d"
MARKET_TYPE_KLINE_1W = "kline_1w"
MARKET_TYPE_KLINE_15D = "kline_15d"
MARKET_TYPE_KLINE_1MON = "kline_1mon"
MARKET_TYPE_KLINE_1Y = "kline_1y"


class OrderData:
    
    def __init__(self, symbol, side, quanty, price, ordType="limit"):
        
        {
            "id": "1512",
            "op": "order",
            "args": [{
                "side": "buy",
                "instId": "BTC-USDT",
                "tdMode": "isolated",
                "ordType": "market",
                "sz": "100"
            }]
        }