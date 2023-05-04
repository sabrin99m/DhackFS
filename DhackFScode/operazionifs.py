import threading
from pathlib import PureWindowsPath
from winfspy import BaseFileSystemOperations, FILE_ATTRIBUTE
from winfspy.plumbing.security_descriptor import SecurityDescriptor

import fileandfolder

#operazioni supportate dal file system

class operazioni(BaseFileSystemOperations):
    def __init__(self, volume_label, read_only=False):
        super().__init__()
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
            SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
        )
        self._entries = {self._root_path: self._root_obj}  
        self._thread_lock = threading.Lock()

    #operazioni su directory
    def crea_dir(self, path):
        path=self._root_path / path
        dir=fileandfolder.Folder(path, FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY, self._root_obj.security_descriptor)
        self._entries[path]=dir
        pass

    
    

