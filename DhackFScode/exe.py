import win32api

# Get the memory partitions
partitions=win32api.GetLogicalDriveStrings()
print(partitions)

part="Z: "
lista=list(part)
if lista[0] in partitions:
    print("NO.")
else:
    print("SI")




