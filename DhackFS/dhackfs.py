import sys
import argparse
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
    vfs=FileSystem.__init__(mountpoint)
    return vfs

def main():                               #nel main il file system viene avviato e stoppato 
    parser=argparse.ArgumentParser()      
    parser.add_argument("mountpoint")      
    args=parser.parse_args
    vfs=creaFS(args.mountpoint) 
    vfs.start()                             #importato da file_system.py di winfspy
    print("VirtualFS started")
    quit=input("Want to quit? Y/N")
    if quit=="Y":
        vfs.stop()
        print("VirtualFS stopped")
    pass




