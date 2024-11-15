import os, shutil, json, logging
import copy
from .general import GlobalConfig
# from .infer_result import GatherRes

class ConfigInfo:
    def __init__(
            self, 
            args, 
            config_path, 
            video_paths, 
            batch_start, 
            result_dir 
        ):
        
        '''annotation 
        Args:
            config_path: 测试视频中的配置文件路径
            batch_start: 设置摄像头id的起始位置
        Outputs:
            out
        '''
        self.result_dir = result_dir
        self.video_paths = video_paths
        self.batch_start = batch_start
        self.args = args
        self.config = json.load(open(config_path))
        self.template = json.load(open(os.path.join(GlobalConfig.SCRIPT_DIR, "configInfo_template.json"), "r"))
        self.used_config_path = os.path.join(GlobalConfig.EXE_DIR, "configInfo_tmp.json")
        self.load_template()

    def load_template(self):
        '''将模板中配置的参数加载到将要使用的配置文件中，并且修改特定参数 
        Args:
            arg
        Outputs:
            out
        '''
        # 先将配置和模板中的对齐
        self.config["SystemInfo"] = self._update_dict(self.config["SystemInfo"], self.template["SystemInfo"])
        # for key in self.config["CameraInfo"][0].keys():
        #     template_conf = self.template["CameraInfo"][0].get(key, None)
        #     if template_conf is None:
        #         continue
        #     if key == "EventRuleInfo":
        #         continue
        #     else:
        for key in self.config["CameraInfo"][0]:
            if key == "EventRuleInfo":
                continue
            else:
                self.config["CameraInfo"][0][key] = self._update_dict(self.config["CameraInfo"][0][key], self.template["CameraInfo"][0][key])
        # print("修改后的配置文件：",self.config["CameraInfo"][0])
        # print("模板文件：",self.template["CameraInfo"][0])
 
        # 端口配置
        self.config["SystemInfo"]["OpenObject"] = 1
        new_info = copy.deepcopy(self.config["SendInfo"][0])
        new_info["SendIp"] = "127.0.0.1"
        # new_info["ObjectPort"] = str(self.args.run_port)
        # new_info["EventPort"] = str(self.args.event_port)
        self.config["SendInfo"][0] = new_info

        # 跑批视频设置
        new_video_info = []

        for sub_id, video_path in enumerate(self.video_paths):
            base = self.config['CameraInfo'][0]
            # print(base)
            base['VideoInfo']['URL'] = video_path
            # base['VideoInfo']['FPS'] = GatherRes.get_fps(video_path)
            base['VideoInfo']['DevNo'] = str(self.batch_start+sub_id)
            base['VideoInfo']['DevName'] = str(self.batch_start+sub_id)
            base['VideoInfo']['ChannelNum'] = int(self.batch_start+sub_id)
            base['VideoInfo']["EventImagesPath"] = self.result_dir
            base['VideoInfo']["EventVideosPath"] = self.result_dir 
            new_video_info.append(copy.deepcopy(base))
        # print(new_video_info)
        # print(self.config["CameraInfo"])
        self.config['CameraInfo'] = new_video_info
        self.config["SystemInfo"]["ChannelNum"] = len(self.video_paths)


    def _update_dict(self, use:dict, template:dict):
        '''通过模板配置更新要用的配置，如果模板中有就用模板的配置，模板没有就保留 
        Args:
            use:需要用的配置
            template:模板中的字段
        Outputs:
            use
        '''
        for key in use:  
            if key in template:  # 直接检查键是否在模板中  
                use[key] = template[key]  # 更新值 
        return use

    def get_sheet_config(self):
        '''获取配置文件中的配置信息,展示到汇总的表格中
        Args:
            arg
        Outputs:
            res:dict, 配置信息
        '''
        # print(self.config["CameraInfo"])
        test_config = {
                "SenceType" : self.config["CameraInfo"][0]["VideoInfo"]["SenceType"],
                "EventTime" : self.config["CameraInfo"][0]["RemoveInfo"]["EventTime"],
                "LocalTime" : self.config["CameraInfo"][0]["RemoveInfo"]["LocalTime"],
                "ObjectTime" : self.config["CameraInfo"][0]["RemoveInfo"]["ObjectTime"],
                "WholeTime" : self.config["CameraInfo"][0]["RemoveInfo"]["WholeTime"],
                "EventType" : self.config["CameraInfo"][0]["EventRuleInfo"][0]["EventType"],
                "ResponseRate" : self.config["CameraInfo"][0]["EventRuleInfo"][0]["ResponseRate"],
                "ThreshValue" : self.config["CameraInfo"][0]["EventRuleInfo"][0]["ThreshValue"],
                "TriggerTime" : self.config["CameraInfo"][0]["EventRuleInfo"][0]["TriggerTime"]
            }
        return test_config

    def save(self, save_path):
        '''保存修改过后的配置文件
        Args:
            arg
        Outputs:
            out
        '''
        with open(self.used_config_path, 'w', encoding='utf-8') as file:  
            json.dump(self.config, file, ensure_ascii=False, indent=4)  
        with open(save_path, 'w', encoding='utf-8') as file:  
            json.dump(self.config, file, ensure_ascii=False, indent=4)
        logging.info(f'实际使用json文件: {save_path}')

if __name__=='__main__':
    from easydict import EasyDict
    args = EasyDict(
        {
            "event_port" : 123,
            "run_port" : 456,
        }
    )
    config_path = "/eventtest/debug/configInfo实际使用.json"
    template_path = "/eventtest/debug/configInfo_template.json"
    video_paths = [
        "/1 .mp4",
        "/test/中文.mp4",
        "/P(test).mp4"
    ]

    c = ConfigInfo(args=args, 
                   config_path=config_path, 
                   video_paths=video_paths, 
                   batch_start=3, 
                   result_dir="/中文", 
                   template_path=template_path)
    c.save("../debug/config_test.json")