import argparse
from pathlib import Path

from winfspy.plumbing.win32_filetime import filetime_now
import file_sys
import operazionifs

#main e creazione del file system

def creaFS (mountpoint, label):                            #il file system viene creato con il costruttore della classe FileSystem
   
    mountpoint = Path(mountpoint)
    operations = operazionifs.operazioni(label)

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
    return vfs

#nel main il file system viene avviato e stoppato   
def main(mountpoint, label):                               
    vfs=creaFS(mountpoint, label)
    
    vfs.start()                                                                    
    print("VirtualFS started.")
    
    #read-only mode
    mode=input("Read-only mode? Y/N" )                                                
    if mode=="Y":
        vfs.restart(read_only_volume=True)
        print("VirtualFS restarted in read-only mode.")   
    else:
        print("Working in w-mode.")                              
    
    quit=input("Want to quit?" )
    if quit=="Y" or "Yes":
        vfs.stop()
        print("VirtualFS stopped")
    pass

#dalla linea di comando viene letto il mountpoint, etichetta col nome del fs di default o stabilita dall'utente
if __name__ == "__main__":                                                         
    parser = argparse.ArgumentParser()
    parser.add_argument("mountpoint")
    parser.add_argument("-l", "--label", type=str, default="Dhackfs")
    args = parser.parse_args()
    main(args.mountpoint, args.label)



