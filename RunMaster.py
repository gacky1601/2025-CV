from System.Data.CONSTANTS import *
from System.Node import *

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 忽略 TensorFlow info 與 warning 訊息


Node(NodeType.Master,MASTERPORT).run()