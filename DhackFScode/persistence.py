import os, pickle
from sortedcontainers import SortedDict

import operazioni_fs
import encrypt_password

def create_metadata_tree(persistent, mountpoint):
    #non-persistent mode
    if not persistent:
        metadata_tree=None  
    #persistent mode
    else:
        #controllo esistenza dati relativi alla partizione
        try: 
            os.mkdir("C://dhckfs")              
        except:
            pass
        #mpinfo: file contenente i mountpoint a cui sono già associati metadati
        try:                                              
            filemp=open("C://dhckfs/mpinfo.txt", "x")      
            filemp.close()
        except FileExistsError:
             pass
        
        filemp=open("C://dhckfs/mpinfo.txt", "r")
        mdexists=False
        for letter in filemp:
            if str(mountpoint) in letter:
                mdexists=True
    
        if not mdexists:               
        #no metadati relativi alla partizione 
            #crea nuova password per la partizione
            master_password = encrypt_password.get_master_password()
            encrypt_pw = encrypt_password.generate_random_string(10)
            slt = encrypt_password.generate_random_string(10)
            key = encrypt_password.generate_key(encrypt_pw, slt)
            encrypt_password.save_master_password(master_password, key, mountpoint)

            filemp=open("C://dhckfs/mpinfo.txt", "w")
            filemp.write(str(mountpoint))
            filemp.close()

            #empty tree
            metadata_tree=SortedDict()      
            pathprefix="C://dhckfs/"+str(mountpoint)[0]
            file=open(pathprefix+"metadata_tree.pkl", "x")
            file.close()
        else:
            #inserimento password
            correct = False
            while correct == False:
                password = input("Insert password: ")
                correct = encrypt_password.verify_master_password(password, mountpoint)
                if correct:
                    print("Password ok.")
                else:
                    print("Incorrect password, try again.")

            #retrieve metadata_tree
            pathprefix="C://dhckfs/"+str(mountpoint)[0]
            with open(pathprefix+"metadata_tree.pkl", "rb") as file:
                metadata_tree = pickle.load(file)           
    
    return metadata_tree


def store_metadata(operations: operazioni_fs.operazioni, mountpoint):
    operations.store_contents(mountpoint)
    pathprefix="C://dhckfs/"+str(mountpoint)[0]
    with open(pathprefix+"metadata_tree.pkl", "wb") as file:
        pickle.dump(operations.metadata_tree, file)
    pass

