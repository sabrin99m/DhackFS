from winfspy import FILE_ATTRIBUTE, NTStatusEndOfFile
from winfspy.plumbing.win32_filetime import filetime_now


#classi per la definizione di file e cartelle

class FF:                                                                        #le classi File e Folder sono sottoclassi di Base
    
    def __init__(self, path, attributes):
        self.path = path
        self.attributes = attributes
        now = filetime_now()
        self.creation_time = now
        self.last_access_time = now
        self.last_write_time = now
        self.change_time = now
        self.index_number = 0
        self.file_size = 0  
        pass

    def get_path(self):
        return self.path

    def get_info(self):
        return {
            "file_attributes": self.attributes,
            "allocation_size": self.allocation_size,
            "file_size": self.file_size,
            "creation_time": self.creation_time,
            "last_access_time": self.last_access_time,
            "last_write_time": self.last_write_time,
            "change_time": self.change_time,
            "index_number": self.index_number,
        }


class Folder(FF):

    def __init__(self, path, attributes):
        super().__init__(path, attributes)
        self.allocation_size=0
        assert self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY                             


class File(FF):

    def __init__(self, path, attributes, allocation_size=0):
        super().__init__(path, attributes, allocation_size)
        self.data = bytearray(allocation_size)
        self.attributes |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE
        assert not self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY


    def read(self, offset, length):
        if offset >= self.file_size:
            raise NTStatusEndOfFile()
        end_offset = min(self.file_size, offset + length)
        return self.data[offset:end_offset]

    def write(self, buffer, offset, write_to_end_of_file):
        if write_to_end_of_file:
            offset = self.file_size
        end_offset = offset + len(buffer)
        if end_offset > self.file_size:
            self.set_file_size(end_offset)
        self.data[offset:end_offset] = buffer
        return len(buffer)

    

