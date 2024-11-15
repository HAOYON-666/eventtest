from dataclasses import dataclass, field
import yaml 
import datetime
import logging 
import os

@dataclass
class GlobalConfig:
    TIME_NOW = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOGGING_LEVEL = "INFO"
    RESULT_DIR = "/event_result"
    SUFFIXS = ['.avi','.mkv', '.mov', '.mp4', ".dav"]
    TESTPATHS = ""
    TESTPATHS_LLM = ""

    EXE_DIR = ""
    EXE_NAME = ""

    EXCEPT_TIME_STAMPS = []
    WAIT_TIME = 5
    CONCURRENT_NUM = 10

def parse_yaml(file_path):
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
        for key in config.keys():
            setattr(GlobalConfig, key, config[key])

    logging.basicConfig(level=eval(f"logging.{GlobalConfig.LOGGING_LEVEL}"), format='%(asctime)s - %(levelname)s | %(message)s')
    logging.info("已经读取全局配置:")
    for k in sorted(GlobalConfig.__dict__):
        if k.startswith("_"):
            continue
        v = getattr(GlobalConfig, k)
        print(f"\t- {k}({type(v)}): {v}")


