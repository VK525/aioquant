import json

class Asset:
    def __init__(self, platform=None, account=None, assets={}, timestamp=None, update=None):
        self.platform = platform
        self.account = account
        self.assets = assets
        self.timestamp = timestamp
        self.update = update
        
    @property
    def data(self):
        d = {
            "platform": self.platform,   # 交易平台名称
            "account": self.account,   # 交易账户
            "assets":self.assets,   # 资产详细信息
            "timestamp":self.timestamp,   # 资产更新时间戳(毫秒)
            "update":self.update     # 资产是否有更新
            }
        return d
        
    def __str__(self):
        info = json.dumps(self.data)
        return info

    def __repr__(self):
        return str(self)
        
        

"""
self.assets:
    {
    "BTC": {
        "free": "1.10000",
        "locked": "2.20000",
        "total": "3.30000"
    },
    "ETH": {
        "free": "1.10000",
        "locked": "2.20000",
        "total": "3.30000"
    }
}
"""