import json
import time
from aioquant.configure import config
from aioquant.market import ConfigSet
from aioquant.event import EventConfigSet
from aioquant.tasks import SingleTask, LoopRunTask
# from aioquant.utils.dingtalk import ding

class ConfigSet1:

    def __init__(self, platform=None, strategy=None):
        self._platform = platform if platform else config.accounts["platform"]
        self._strategy = strategy if strategy else config.name
        self._event_config_set = EventConfigSet(ConfigSet(self._platform, self._strategy))
    
    def run(self, data:dir):
        info = {
            "platform": self._platform,
            "strategy" : self._strategy,
            "msg" : data,
            "timestamp":int(time.time())
        }
        self._event_config_set._data = ConfigSet(**info).smart
        self._event_config_set.publish()
        
        print("发送参数指令成功！")