import pymongo
from aioquant.utils import logger
from aioquant.configure import config

# from aioquant.utils.Dingtalk import Ding


class mongo:
    def __init__(self):
        self.host = config.mongodb.get("host", "localhost")
        self.port = config.mongodb.get("port", 27017)
        self.username = config.mongodb.get("username", "mongodb")
        self.password = config.mongodb.get("password", "admin")
        self.dbname = config.mongodb.get("dbname", "aioquant")
        logger.debug("host:", self.host, "port:", self.port, "dbname:", self.dbname, caller=self)
        self.client = pymongo.MongoClient(f"mongodb://{self.host}:{self.port}/", username=self.username, password=self.password)
        self.db = self.client[self.dbname]
    
    def reset(self, newDb:None):
        self.client = pymongo.MongoClient(f"mongodb://{self.host}:{self.port}/", username=self.username, password=self.password)
        self.db = self.client[newDb] if newDb else self.client[self.dbname]
    
    def up(self, path:str, data_dir:dir):
        """
        新增一条数据，字典格式
        """
        try:
            self.db[path].insert_one(data_dir)
        except Exception as e:
            logger.error("mongo_up_error : ", e, caller=self)
            # Ding.send_text(f"mongo_up_error : {e}")
            self.rest()
        
    def ups(self, path:str, data_list:list):
        """
        批量新增数据，列表格式
        """
        try:
            self.db[path].insert_many(data_list)
        except Exception as e:
            logger.error("mongo_ups_error : ", e, caller=self)
            # Ding.send_text(f"mongo_ups_error : {e}")
            self.rest()
    
    def update(self, path:str, old:dir, new:dir):
        """
        修改数据，old为条件，new为新数据
        """
        try:
            self.db[path].update_one(old, {"$set":new})
        except Exception as e:
            logger.error("mongo_update_error : ", e, caller=self)
            # Ding.send_text(f"mongo_update_error : {e}")
            self.rest()
        
    def del_all(self, path:str):
        """
        清空整个集合
        """
        try:
            self.db[path].delete_many({})
        except Exception as e:
            logger.error("mongo_del_all_error : ", e, caller=self)
            # Ding.send_text(f"mongo_del_all_error : {e}")
            self.rest()
    
    def load(self, path:str):
        """
        获取集合数据
        """
        try:
            res = self.db[path].find({},{"_id":0})
            # data = ([ r for r in res])
            data = list(res)
        except Exception as e:
            print("load db None")
            logger.error("mongo_load_error : ", e, caller=self)
            # Ding.send_text(f"mongo_load_error : {e}")
            return False, e
        return data, None if data else "is none"

Mongo = mongo()