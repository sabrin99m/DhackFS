import sys
import argparse
import threading
import logging
from pathlib import Path, PureWindowsPath
from winfspy.plumbing.win32_filetime import filetime_now

from winfspy import (
    FileSystem,
    BaseFileSystemOperations,
    enable_debug_log,
    FILE_ATTRIBUTE,
    CREATE_FILE_CREATE_OPTIONS,
    NTStatusObjectNameNotFound,
    NTStatusDirectoryNotEmpty,
    NTStatusNotADirectory,
    NTStatusObjectNameCollision,
    NTStatusAccessDenied,
    NTStatusEndOfFile,
)

class operazioni(BaseFileSystemOperations):
    def __init__(self, volume_label, read_only=False):
        super().__init__()
        max_file_nodes = 1024
        max_file_size = 16 * 1024 * 1024
        file_nodes = 1                                   #al momento della creazione c'è un file node, total size=17179869184

        self._volume_info = {
            "total_size": max_file_nodes * max_file_size,
            "free_size": (max_file_nodes - file_nodes) * max_file_size,
            "volume_label": volume_label,
        }

        self.read_only = read_only
        self._root_path = PureWindowsPath("/")
        #self._root_obj = FolderObj(
        #    self._root_path,
        #    FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
        #    SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
        #)
        self._entries = {self._root_path: self._root_obj}  
        self._thread_lock = threading.Lock()

    def create(self, nomefile, opzioni, accesso, attributi, sicurezza, allocationsize):
        BaseFileSystemOperations.create(self, nomefile, opzioni, accesso, attributi, sicurezza, allocationsize)
        pass
    def open(self, file_context):
        BaseFileSystemOperations.open(self, file_context)
        pass
    def close(self, file_context):
        BaseFileSystemOperations.close(self, file_context)
        pass 
    def read(self, file_context, offset, lenght):
        BaseFileSystemOperations.read(self, file_context, offset, lenght)
        pass
    def write(self, file_context, buffer, offset, to_the_end, vincoli):
        BaseFileSystemOperations.write(self, file_context, buffer, offset, to_the_end, vincoli)
        pass
    def rename(self, file_context, nomefile, nuovonome, exists):
        BaseFileSystemOperations.rename(self, file_context, nomefile, nuovonome, exists)
    


def creaFS (mountpoint, label, prefix, verbose, debug):               #il file system viene creato con il costruttore della classe FileSystem
    
    if verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    
    mountpoint = Path(mountpoint)
    operations= operazioni(label)
    vfs=FileSystem(mountpoint, operations, debug, 
        sector_size=512,                              #**volume_params
        sectors_per_allocation_unit=1,
        volume_creation_time=filetime_now(),
        volume_serial_number=0,
        file_info_timeout=1000,
        case_sensitive_search=1,
        case_preserved_names=1,
        unicode_on_disk=1,
        persistent_acls=1,
        post_cleanup_when_modified_only=1,
        um_file_context_is_user_context2=1,
        file_system_name=str(mountpoint),
        prefix=prefix,
        debug=debug,
    )
    return vfs

def main(mountpoint, label, prefix, verbose, debug):                               #nel main il file system viene avviato e stoppato 
    vfs=creaFS(mountpoint, label, verbose, prefix, debug=False) 
    #vfs.start()                                                                    #importato da file_system.py di winfspy
    print("VirtualFS started")
    quit=input("Want to quit? Y/N")
    if quit=="Y":
        vfs.stop()
        print("VirtualFS stopped")
    pass

if __name__ == "__main__":                                           #dalla linea di comando vengono letti il mountpoint e le proprietà di esecuzione
    parser = argparse.ArgumentParser()
    parser.add_argument("mountpoint")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-l", "--label", type=str, default="Dhackfs")
    parser.add_argument("-p", "--prefix", type=str, default="")
    args = parser.parse_args()
    main(args.mountpoint, args.label, args.prefix, args.verbose, args.debug)



