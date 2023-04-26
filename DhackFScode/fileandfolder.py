from winfspy import FILE_ATTRIBUTE

#classi per la definizione di file e cartelle

class Base:                                                                        #le classi File e Folder sono sottoclassi di Base
    def nome(self):
        return self.path.nome
    
    def getinfo(self):
        return self.attributes

class Folder(Base):
    def __init__(self, path, attributes, security_descriptor):
        super().__init__(path, attributes, security_descriptor)
        self.allocation_size = 0
        assert self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY                             

class File(Base):
    pass

