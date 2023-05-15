import argparse
from pathlib import Path
import win32api

from winfspy.plumbing.win32_filetime import filetime_now

import file_sys
import operazionifs

def freedisk(mountpoint):
    # Get memory partitions
    partitions=win32api.GetLogicalDriveStrings()
    mlist=list(mountpoint)
    if mlist[0] in partitions:
        mountpoint=print("Partizione occupata, scegliere nuovo mountpoint: ")
        freedisk(mountpoint)
    else:
        print("Partizione libera.")

    return mountpoint

#main e creazione del file system

def creaFS (mountpoint, label, persistent):                   
   
    mountpoint = Path(mountpoint)
    operations = operazionifs.operazioni(label)

    #verifica se ci sono metadati relativi alla partizione, se sì li rimonta
    filemp=open("mpinfo.txt", "x")
    for riga in filemp:
        if str(mountpoint) in riga:
            #carica dati
            pass
        else:
            #crea fs nuovo
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
            )
            if persistent:
                filemp.write(mountpoint)
    
    filemp.close()
    
    return vfs

#nel main il file system viene avviato e stoppato   
def main(mountpoint, label, persistent):  

    #verifica se la partizione è libera
    mountpoint=freedisk(mountpoint)

    vfs=creaFS(mountpoint, label, persistent)    
    vfs.start()                                                                    
    print("VirtualFS started.")

    #read-only mode
    accessmode=input("Read-only mode? Y/N" )                                                
    if accessmode=="Y":
        vfs.restart(read_only_volume=True)
        print("VirtualFS restarted in read-only mode.")   
    else:
        print("Working in w-mode.")                              
    
    quit=input("Want to quit?" )
    if quit=="Y":
        #if persistent:
            #vfs.flush(underlyingdir)
        vfs.stop()
        print("VirtualFS stopped")
    pass

#dalla linea di comando viene letto il mountpoint, etichetta col nome del fs di default o stabilita dall'utente e 
# modalità persistent o non-persistent
if __name__ == "__main__":                                                         
    parser = argparse.ArgumentParser()
    parser.add_argument("mountpoint")
    parser.add_argument("-l", "--label", type=str, default="Dhackfs")
    parser.add_argument("-p", "--persistent", type=bool, default=True)
    args = parser.parse_args()
    main(args.mountpoint, args.label, args.persistent)



