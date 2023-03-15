persona={
    "Nome": "Luca",
    "Cognome": "Rossi",
    "Età": 25
}

operazioni=("aggiungere", "modificare", "rimuovere")

def start():
    operazione=input("Scegliere operazione: ")
    if operazione==operazioni[0]:     #aggiungere chiave
        x=input("Inserire chiave e valore separati da virgola: ")
        aggiungi(x.split(","))       
        pass
    elif operazione==operazioni[1]: #modifica valore
        x=input("Inserire chiave da modificare: ")
        val=input("Inserire nuovo valore: ")
        modifica(x, val)
        pass
    elif operazione==operazioni[2]: #elimina valore
        x=input("Inserire chiave da rimuovere: ")
        rimuovi(x)



def aggiungi(param):
    chiave=param[0]
    valore=param[1]
    persona[chiave]=valore
        

def modifica(c, v):
    persona[c]=v

def rimuovi(x):
    del persona[x]

while True: 
    start()
    print(persona)



