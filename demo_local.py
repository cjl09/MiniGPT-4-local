import argparse
import os
import random
import glob
import logging
import time
import numpy as np
import torch
import torch.backends.cudnn as cudnn

from minigpt4.common.config import Config
from minigpt4.common.dist_utils import get_rank
from minigpt4.common.registry import registry
from minigpt4.conversation.conversation import Chat, CONV_VISION

# imports modules for registration
from minigpt4.datasets.builders import *
from minigpt4.models import *
from minigpt4.processors import *
from minigpt4.runners import *
from minigpt4.tasks import *
from PIL import Image

def parse_args():
    parser = argparse.ArgumentParser(description="Demo")
    parser.add_argument("--cfg-path",
                        required=True,
                        help="path to configuration file.")
    parser.add_argument("--gpu-id",
                        type=int,
                        default=0,
                        help="specify the gpu to load the model.")
    parser.add_argument("--temperature",
                        type=float,
                        default=0.1,
                        help="can not use 0.0 due to limitations")
    parser.add_argument(
        "--img-dir",
        default = '/images/test/',
        help="path to the directory containing images to be processed.")
    parser.add_argument(
        "--user-message",
        default = 'Describe the content of the image.',
        help = "question you want to ask")
    parser.add_argument(
        "--options",
        nargs="+",
        help="override some settings in the used config, the key-value pair "
        "in xxx=yyy format will be merged into config file (deprecate), "
        "change to --cfg-options instead.",
    )
    args = parser.parse_args()
    return args


def setup_seeds(config):
    seed = config.run_cfg.seed + get_rank()

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    cudnn.benchmark = False
    cudnn.deterministic = True


# ========================================
#             Model Initialization
# ========================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    file_handler = logging.FileHandler(
        os.path.join('COCO_MiniGPT4_Caption' + "_log.txt"))
    logger = logging.getLogger()
    logger.addHandler(file_handler)

    logging.info('=======Initializing Chat=======')
    args = parse_args()
    cfg = Config(args)
    model_config = cfg.model_cfg
    model_config.device_8bit = args.gpu_id
    model_cls = registry.get_model_class(model_config.arch)
    model = model_cls.from_config(model_config).to('cuda:{}'.format(
        args.gpu_id))

    vis_processor_cfg = cfg.datasets_cfg.cc_sbu_align.vis_processor.train
    vis_processor = registry.get_processor_class(
        vis_processor_cfg.name).from_config(vis_processor_cfg)
    chat = Chat(model, vis_processor, device='cuda:{}'.format(args.gpu_id))
    logging.info('=======Initialization Finished=======')

    logging.info('=======Load images=======')
    image_paths = sorted(glob.glob(os.path.join(args.img_dir, '*')))  # read all images in img_dir

    user_message = args.user_message
    logging.info('your question: ' + user_message)

    for image_path in image_paths:
        img = Image.open(image_path)
        image_id = os.path.basename(image_path).split('.')[0]
        logging.info('ImageID: ' + image_id)
        img_list = []
        chat_state = CONV_VISION.copy()
        llm_message = chat.upload_img(img, chat_state, img_list)
        chat.ask(user_message, chat_state)
        llm_message = chat.answer(conv=chat_state,
                                  img_list=img_list,
                                  num_beams=1,
                                  temperature=args.temperature,
                                  max_new_tokens=300,
                                  max_length=2000)[0]
        
        logging.info('MiniGPT4 Answer: '+ llm_message)
        # print(llm_message)

        with open('output.txt', 'a', encoding='utf-8') as file:
            file.write('ImageID: ' + image_id + ',' )  
            file.write('Answer is :' + llm_message)  
            file.write("\n")
