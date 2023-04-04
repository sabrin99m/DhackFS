import sys
from pathlib import Path, PureWindowsPath

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

def creaFS (mountpoint):                   #il file system viene creato
    mountpoint = Path(mountpoint)
   
    pass

def main(mountpoint="X:"):                  #nel main il file system viene avviato e stoppato 
    vfs=creaFS(mountpoint) 
    vfs.start()                             #importato da file_system.py di winfspy
    print("VirtualFS started")
    quit=input("Want to quit? Y/N")
    if quit=="Y":
        vfs.stop()
        print("VirtualFS stopped")
    pass




