import os
import time
from aioquant.utils import logger
from aioquant.configure import config

class Pid():
    def __init__(self):
        #print("Pid init ...")
        pass
        
    def Save(self, path=None):
        if not path:
            return
        pid = os.getpid()
        config.save({"pid":pid}, path)
        # print('当前进程ID：', pid, "保存路径：",path)
        logger.info("当前进程ID:", pid, "保存路径:", path, caller=self)


    def Kill(self, path=None):
        # 本函数用于中止传入pid所对应的进程
        if not path:
            return
        
        if type(path) is int:
            pid = path
        else: 
            try:
                pid_dict = config.read(path)
                pid = pid_dict["pid"]
            except Exception as e:
                logger.error("PID Read Error :", path, caller=self)
                return
            
        logger.info("PID Kill 5s ... :", pid, caller=self)
        time.sleep(5)
        if os.name == 'nt':
            # Windows系统
            cmd = 'taskkill /pid ' + str(pid) + ' /f'
            try:
                os.system(cmd)
                logger.info("PID Kill OK ! ", pid, caller=self)
            except Exception as e:
                logger.error("PID Kill ERROR !  error:", e, caller=self)
        elif os.name == 'posix':
            # Linux系统
            cmd = 'kill ' + str(pid)
            try:
                os.system(cmd)
                logger.info("PID Kill OK ! ", pid, caller=self)
            except Exception as e:
                logger.error("PID Kill ERROR !  error:", e, caller=self)
        else:
            logger.error("PID Kill Error :", "Undefined os.name", caller=self)
            
Pid = Pid()