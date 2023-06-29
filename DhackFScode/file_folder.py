from winfspy import FILE_ATTRIBUTE, NTStatusEndOfFile
from winfspy.plumbing.win32_filetime import filetime_now


#classi per la definizione di file e cartelle, file and folder sono sottoclassi di FF


class FF:
    @property
    def name(self):
        """File name, without the path"""
        return self.path.name

    @property
    def file_name(self):
        """File name, including the path"""
        return str(self.path)

    def __init__(self, path, attributes, security_descriptor, creation_time=filetime_now(),
                 last_write_time=filetime_now(), change_time=filetime_now(), index_number=0, file_size=0):
        self.path = path
        self.attributes = attributes
        self.security_descriptor = security_descriptor
        self.creation_time = creation_time
        self.last_access_time = filetime_now()
        self.last_write_time = last_write_time
        self.change_time = change_time
        self.index_number = index_number
        self.file_size = file_size


    def get_file_info(self):
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

    def __repr__(self):
        return f"{type(self).__name__}:{self.file_name}"



class File(FF):

    allocation_unit = 4096

    def __init__(self, path, attributes, security_descriptor, allocation_size=0, creation_time=filetime_now(),
                 last_write_time=filetime_now(), change_time=filetime_now(), index_number=0, file_size=0):
        super().__init__(path, attributes, security_descriptor, creation_time,
                 last_write_time, change_time, index_number, file_size)
        self.data = bytearray(allocation_size)
        self.attributes |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE
        assert not self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

    @property
    def allocation_size(self):
        return len(self.data)

    def set_allocation_size(self, allocation_size):
        if allocation_size < self.allocation_size:
            self.data = self.data[:allocation_size]
        if allocation_size > self.allocation_size:
            self.data += bytearray(allocation_size - self.allocation_size)
        assert self.allocation_size == allocation_size
        self.file_size = min(self.file_size, allocation_size)

    def adapt_allocation_size(self, file_size):
        units = (file_size + self.allocation_unit - 1) // self.allocation_unit
        self.set_allocation_size(units * self.allocation_unit)

    def set_file_size(self, file_size):
        if file_size < self.file_size:
            zeros = bytearray(self.file_size - file_size)
            self.data[file_size : self.file_size] = zeros
        if file_size > self.allocation_size:
            self.adapt_allocation_size(file_size)
        self.file_size = file_size

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

    def constrained_write(self, buffer, offset):
        if offset >= self.file_size:
            return 0
        end_offset = min(self.file_size, offset + len(buffer))
        transferred_length = end_offset - offset
        self.data[offset:end_offset] = buffer[:transferred_length]
        return transferred_length


class Folder(FF):
    def __init__(self, path, attributes, security_descriptor, creation_time=filetime_now(),
                 last_write_time=filetime_now(), change_time=filetime_now(), index_number=0, file_size=0):
        super().__init__(path, attributes, security_descriptor, creation_time,
                 last_write_time, change_time, index_number, file_size)
        self.allocation_size = 0
        assert self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY


class openFF:
    def __init__(self, file_obj):
        self.file_obj = file_obj

    def __repr__(self):
        return f"{type(self).__name__}:{self.file_obj.file_name}"


