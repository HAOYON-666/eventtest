import os, shutil, json, random, sys, logging, glob
import socket
import uuid
from .general import GlobalConfig
from pathlib import Path

class PrepareData:
    def __init__(self):
        self.count = 0
        self.test_dirs = []
        self.video_paths = []
        self.configs = []

        self._find_test_video()

        self.video_num = sum([len(i) for i in self.video_paths])
        self.event_num = len(self.test_dirs)
        assert self.video_num > 0,f"找到测试视频数量为0，请检查测试视频路径配置是否正确，视频后缀是否在{GlobalConfig.SUFFIXS}中"

    def _find_test_video(self):
        '''从test_dir中寻找要测试的视频 
        Args:
            test_dir : 搜寻的路径
        Outputs:
            out
        '''
        for root, _, files in os.walk(GlobalConfig.TESTPATHS):
            for file in files:
                if file != "configInfo.json":
                    continue
                self.configs.append(os.path.join(root, file))
                self.test_dirs.append(root[:-1] if root.endswith("/") else root)
                self.video_paths.append([i for i in glob.glob(os.path.join(root, "*.*")) if Path(i).suffix in GlobalConfig.SUFFIXS])

    def __iter__(self):
        return self
    
    def __next__(self):
        if self.count < len(self.test_dirs):
            self._show()
            self.count += 1
            return self.test_dirs[self.count-1], self.video_paths[self.count-1], self.configs[self.count-1]
        else:
            raise StopIteration
    
    def get_test_res_pair(self, result_dirs):
        '''在debug时，将测试文件夹和保存结果的文件夹相匹配 
        '''
        test2res = {}
        for test_dir in self.test_dirs:
            pair_flag = False
            for result_dir in result_dirs:
                position, sence = os.path.basename(result_dir).split("_")[-2:]
                if position in test_dir and test_dir.split('/')[-1] == sence: 
                    test2res[test_dir] = result_dir
                    pair_flag = True
                    break 
            if not pair_flag:
                logging.warning(f"{test_dir} 匹配结果目录失败")
        return test2res
        
    def _show(self):
        '''显示执行进度 '''
        logging.info("当前测试进度")
        for idx, test_dir in enumerate(self.test_dirs):
            if idx == self.count:
                print("\t", "/".join(test_dir.split(os.sep)[-3:]), "       <<<-----")
            else:
                print("\t", "/".join(test_dir.split(os.sep)[-3:]))

class PrepareCloudEagleEnv:
    def __init__(self, args):
        self.args = args 

    def __enter__(self,):
        self.new_exe_name = GlobalConfig.EXE_NAME + uuid.uuid4().hex
        self.args.exe_name = self.new_exe_name
        self.config_ini_path = os.path.join(GlobalConfig.EXE_DIR, "config.ini")
        self.config_ini_back_path = os.path.join(GlobalConfig.EXE_DIR, "config.ini.backup")

        # 获取空闲端口
        self.args.run_port = self.get_random_free_port(12000, 12500)
        self.args.event_port = self.get_random_free_port(12501, 13000)

        # 文件备份
        shutil.copy(os.path.join(GlobalConfig.EXE_DIR, GlobalConfig.EXE_NAME), os.path.join(GlobalConfig.EXE_DIR, self.new_exe_name))
        shutil.copy(self.config_ini_path, self.config_ini_back_path)

        self._change_config_ini(self.config_ini_path, "configInfoPath", "./configInfo_tmp.json")

        return self.args
        
    def __exit__(self, exc_type, exc_value, traceback):
        os.remove(os.path.join(GlobalConfig.EXE_DIR, self.new_exe_name))
        os.rename(self.config_ini_back_path, self.config_ini_path)
        # os.remove(os.path.join(GlobalConfig.EXE_DIR, "configInfo_tmp.json"))

    def _change_config_ini(self, file_path, key, value):
        lines = []
        n = 0
        with open(file_path, 'r') as f:
            for line in f.readlines():
                if line.startswith(key):
                    line = key + "=" + value + "\n"
                    n += 1
                lines.append(line)
        assert n == 1, f"在修改config.ini的{key}时，匹配到了{n}个值"

        with open(file_path, "w") as f:
            f.writelines(lines)

    def get_random_free_port(self, min_port, max_port):
        while True: 
            port = random.randint(min_port, max_port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return port 
                except OSError:
                    continue