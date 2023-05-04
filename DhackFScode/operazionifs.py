import threading
from pathlib import PureWindowsPath
from winfspy import FILE_ATTRIBUTE

import fileandfolder

#operazioni supportate dal file system

class operazioni:
    def __init__(self, volume_label, read_only=False):
        self._opened_objs = {}
        
        max_file_nodes = 1024
        max_file_size = 16 * 1024 * 1024
        file_nodes = 1                                                             #al momento della creazione c'è un file node, total size=17179869184

        self._volume_info = {
            "total_size": max_file_nodes * max_file_size,
            "free_size": (max_file_nodes - file_nodes) * max_file_size,
            "volume_label": volume_label,
        }

        self.read_only = read_only
        self._root_path = PureWindowsPath("/")
        self._root_obj = fileandfolder.Folder(
            self._root_path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
        )
        self._entries = {self._root_path: self._root_obj}  
        self._thread_lock = threading.Lock()

    #operazioni su directory
    def crea_dir(self, path):
        path=self._root_path / path
        dir=fileandfolder.Folder(path, FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY)
        self._entries[path]=dir
        pass

    
    

