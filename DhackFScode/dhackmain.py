import sys
import argparse
import logging
from pathlib import Path
from winfspy.plumbing.win32_filetime import filetime_now

from winfspy import (
    enable_debug_log,
    CREATE_FILE_CREATE_OPTIONS,
    NTStatusObjectNameNotFound,
    NTStatusDirectoryNotEmpty,
    NTStatusNotADirectory,
    NTStatusObjectNameCollision,
    NTStatusAccessDenied,
)

import operazionifs
import file_sys

#main e creazione del file system

def creaFS (mountpoint, label, prefix="", verbose=True, debug=False):                            #il file system viene creato con il costruttore della classe FileSystem
    
    if verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    if debug:
        enable_debug_log()
   
    testing=False
    mountpoint = Path(mountpoint)
    operations= operazionifs.operazioni(label)
    is_drive = mountpoint.parent == mountpoint
    reject_irp_prior_to_transact0 = not is_drive and not testing

    vfs=file_sys.VFileSys(
        str(mountpoint),
        operations,
        sector_size=512,
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
        reject_irp_prior_to_transact0=reject_irp_prior_to_transact0,
        # security_timeout_valid=1,
        # security_timeout=10000,
    )
    return vfs


def main(mountpoint, label, prefix, verbose, debug):                               #nel main il file system viene avviato e stoppato 
    vfs=creaFS(mountpoint, label, prefix, verbose, debug) 
    vfs.start()                                                                    #importato da file_system.py di winfspy
    print("VirtualFS started")
    quit=input("Want to quit? Y/N: ")
    if quit=="Y":
        vfs.stop()
        print("VirtualFS stopped")
    pass

if __name__ == "__main__":                                                         #dalla linea di comando vengono letti il mountpoint e le proprietà di esecuzione
    parser = argparse.ArgumentParser()
    parser.add_argument("mountpoint")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-l", "--label", type=str, default="Dhackfs")
    parser.add_argument("-p", "--prefix", type=str, default="")
    args = parser.parse_args()
    main(args.mountpoint, args.label, args.prefix, args.verbose, args.debug)



