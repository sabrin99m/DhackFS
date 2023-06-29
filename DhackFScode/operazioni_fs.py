import threading
import logging
from functools import wraps
from pathlib import Path, PureWindowsPath
from sortedcontainers import SortedDict
import pickle

from winfspy import (
    BaseFileSystemOperations,
    FILE_ATTRIBUTE,
    CREATE_FILE_CREATE_OPTIONS,
    NTStatusObjectNameNotFound,
    NTStatusDirectoryNotEmpty,
    NTStatusNotADirectory,
    NTStatusObjectNameCollision,
    NTStatusAccessDenied,
    NTStatusMediaWriteProtected,
)
from winfspy.plumbing.win32_filetime import filetime_now
from winfspy.plumbing.security_descriptor import SecurityDescriptor

import file_folder
import encrypt_password


def operation(fn):

    name = fn.__name__

    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        head = args[0] if args else None
        tail = args[1:] if args else ()
        try:
            with self._thread_lock:
                result = fn(self, *args, **kwargs)
        except Exception as exc:
            logging.info(f" NOK | {name:20} | {head!r:20} | {tail!r:20} | {exc!r}")
            raise
        else:
            logging.info(f" OK! | {name:20} | {head!r:20} | {tail!r:20} | {result!r}")
            return result

    return wrapper

class operazioni(BaseFileSystemOperations):
    def __init__(self, volume_label, mountpoint, metadata_tree: SortedDict, persistent=True, read_only=False):
        super().__init__()
        if len(volume_label) > 31:
            raise ValueError("`volume_label` must be 31 characters long max")

        self.read_only = read_only

        if persistent:
            self.metadata_tree = metadata_tree
    
        max_file_nodes = 1024
        max_file_size = 16 * 1024 * 1024
        
        if len(metadata_tree)==0:               
            file_nodes = 1
            self._root_path = PureWindowsPath("/")
            self._root_obj = file_folder.Folder(
                self._root_path,
                FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
                SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
            )
            self._entries = {self._root_path: self._root_obj}
            self.metadata_tree[self._root_path] = self._root_obj.get_file_info()
        else:                                   
            file_nodes = len(metadata_tree)  
            folder_attributes = FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY 
            
            #initialize self._entries
            self._root_path = PureWindowsPath("/")
            self._root_obj = file_folder.Folder(                     
                self._root_path,
                FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
                SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
            )
            self._entries = {self._root_path: self._root_obj}

            for name in metadata_tree:
                if str(name).__contains__("\.~lock."):
                    del metadata_tree[name]

            for name in metadata_tree:
                file_info = metadata_tree[name]
                if name == "/":
                    self._root_obj = file_folder.Folder(
                        name,
                        file_info["file_attributes"],
                        SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
                        file_info["creation_time"],
                        file_info["last_write_time"],
                        file_info["change_time"],
                        file_info["index_number"],
                        file_info["file_size"]
                    )
                    del self._entries[self._root_path]
                    self._entries = {name: self._root_obj}
                else:
                    if file_info["file_attributes"] == folder_attributes:
                        f_obj = file_folder.Folder(
                            name,
                            file_info["file_attributes"],
                            SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
                            file_info["creation_time"],
                            file_info["last_write_time"],
                            file_info["change_time"],
                            file_info["index_number"],
                            file_info["file_size"]
                            )
                    else:
                        f_obj = file_folder.File(
                            name,
                            file_info["file_attributes"],
                            SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
                            file_info["allocation_size"],
                            file_info["creation_time"],
                            file_info["last_write_time"],
                            file_info["change_time"],
                            file_info["index_number"],
                            file_info["file_size"],
                            )
                        
                        encrypted_data = file_info["file_contents"]
                        with open('C://dhckfs/pw.txt', 'rb') as file:
                            access_info = pickle.load(file)

                        for mount in access_info:
                            if mount == mountpoint:
                                access_keys = access_info[mount]
                                key = access_keys["key"]

                        data = encrypt_password.decrypt_data(encrypted_data, key)
                        f_obj.write(bytearray(data), 0, True)
                                
                    self._entries[name] = f_obj 
                  
    
        self._volume_info = {
            "total_size": max_file_nodes * max_file_size,
            "free_size": (max_file_nodes - file_nodes) * max_file_size,
            "volume_label": volume_label,
        }
        
        self._thread_lock = threading.Lock()


    def _create_directory(self, path):
        path = self._root_path / path
        obj = file_folder.Folder(
            path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
            self._root_obj.security_descriptor,
        )
        self._entries[path] = obj
        self.metadata_tree[path] = obj.get_file_info()


    def _import_files(self, file_path):
        file_path = Path(file_path)
        path = self._root_path / file_path.name
        obj = file_folder.File(
            path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE,
            self._root_obj.security_descriptor,
        )

        data = file_path.read_bytes()

        self._entries[path] = obj
        obj.write(bytearray(data), 0, False)
        try:
            self.metadata_tree[path]=obj.get_file_info()
        except:
            pass

    # Winfsp operations

    @operation
    def get_volume_info(self):
        return self._volume_info

    @operation
    def set_volume_label(self, volume_label):
        self._volume_info["volume_label"] = volume_label

    @operation
    def get_security_by_name(self, file_name):
        file_name = PureWindowsPath(file_name)

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return (
            file_obj.attributes,
            file_obj.security_descriptor.handle,
            file_obj.security_descriptor.size,
        )

    @operation
    def create(
        self,
        file_name,
        create_options,
        granted_access,
        file_attributes,
        security_descriptor,
        allocation_size,
    ):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        file_name = PureWindowsPath(file_name)

        # `granted_access` is already handle by winfsp
        # `allocation_size` useless for us

        # Retrieve file
        try:
            parent_file_obj = self._entries[file_name.parent]
            if isinstance(parent_file_obj, file_folder.File):
                raise NTStatusNotADirectory()
        except KeyError:
            raise NTStatusObjectNameNotFound()

        # File/Folder already exists
        if file_name in self._entries:
            raise NTStatusObjectNameCollision()
        

        if create_options & CREATE_FILE_CREATE_OPTIONS.FILE_DIRECTORY_FILE:
            file_obj = self._entries[file_name] = file_folder.Folder(
                file_name, file_attributes, security_descriptor,
            )
        else:
            file_obj = self._entries[file_name] = file_folder.File(
                file_name,
                file_attributes,
                security_descriptor,
                allocation_size,
            )
        try:
            self.metadata_tree[file_name] = file_obj.get_file_info()
        except:
            pass
        return file_folder.openFF(file_obj)

    @operation
    def get_security(self, file_context):
        return file_context.file_obj.security_descriptor

    @operation
    def set_security(self, file_context, security_information, modification_descriptor):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        new_descriptor = file_context.file_obj.security_descriptor.evolve(
            security_information, modification_descriptor
        )
        file_context.file_obj.security_descriptor = new_descriptor

    @operation
    def rename(self, file_context, file_name, new_file_name, replace_if_exists):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        file_name = PureWindowsPath(file_name)
        new_file_name = PureWindowsPath(new_file_name)

        # Retrieve file
        try:
            file_obj = self._entries[file_name]

        except KeyError:
            raise NTStatusObjectNameNotFound()

        if new_file_name in self._entries:
            # Case-sensitive comparison
            if new_file_name.name != self._entries[new_file_name].path.name:
                pass
            elif not replace_if_exists:
                raise NTStatusObjectNameCollision()
            elif not isinstance(file_obj, file_folder.File):
                raise NTStatusAccessDenied()

        for entry_path in list(self._entries):
            try:
                relative = entry_path.relative_to(file_name)
                new_entry_path = new_file_name / relative
                entry = self._entries.pop(entry_path)
                entry.path = new_entry_path
                self._entries[new_entry_path] = entry
                try:
                    for path_key in self.metadata_tree:
                        if file_name == path_key:
                            file_metadata=self.metadata_tree[path_key]
                            del self.metadata_tree[path_key]
                            self.metadata_tree[new_entry_path] = file_metadata
                except:
                    pass

            except ValueError:
                continue
            

    @operation
    def open(self, file_name, create_options, granted_access):
        file_name = PureWindowsPath(file_name)

        # `granted_access` is already handle by winfsp

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return file_folder.openFF(file_obj)

    @operation
    def close(self, file_context):
        pass

    @operation
    def get_file_info(self, file_context):
        return file_context.file_obj.get_file_info()

    @operation
    def set_basic_info(
        self,
        file_context,
        file_attributes,
        creation_time,
        last_access_time,
        last_write_time,
        change_time,
        file_info,
    ) -> dict:
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        file_obj = file_context.file_obj
        if file_attributes != FILE_ATTRIBUTE.INVALID_FILE_ATTRIBUTES:
            file_obj.attributes = file_attributes
        if creation_time:
            file_obj.creation_time = creation_time
        if last_access_time:
            file_obj.last_access_time = last_access_time
        if last_write_time:
            file_obj.last_write_time = last_write_time
        if change_time:
            file_obj.change_time = change_time

        return file_obj.get_file_info()

    @operation
    def set_file_size(self, file_context, new_size, set_allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        if set_allocation_size:
            file_context.file_obj.set_allocation_size(new_size)
        else:
            file_context.file_obj.set_file_size(new_size)

    @operation
    def can_delete(self, file_context, file_name: str) -> None:
        file_name = PureWindowsPath(file_name)

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound

        if isinstance(file_obj, file_folder.Folder):
            for entry in self._entries.keys():
                try:
                    if entry.relative_to(file_name).parts:
                        raise NTStatusDirectoryNotEmpty()
                except ValueError:
                    continue

    @operation
    def read_directory(self, file_context, marker):
        entries = []
        file_obj = file_context.file_obj

        # Not a directory
        if isinstance(file_obj, file_folder.File):
            raise NTStatusNotADirectory()

        # The "." and ".." should ONLY be included if the queried directory is not root
        if file_obj.path != self._root_path:
            parent_obj = self._entries[file_obj.path.parent]
            entries.append({"file_name": ".", **file_obj.get_file_info()})
            entries.append({"file_name": "..", **parent_obj.get_file_info()})

        # Loop over all entries
        for entry_path, entry_obj in self._entries.items():
            try:
                relative = entry_path.relative_to(file_obj.path)
            # Filter out unrelated entries
            except ValueError:
                continue
            # Filter out ourself or our grandchildren
            if len(relative.parts) != 1:
                continue
            # Add direct chidren to the entry list
            entries.append({"file_name": entry_path.name, **entry_obj.get_file_info()})

        # Sort the entries
        entries = sorted(entries, key=lambda x: x["file_name"])

        # No filtering to apply
        if marker is None:
            return entries

        # Filter out all results before the marker
        for i, entry in enumerate(entries):
            if entry["file_name"] == marker:
                return entries[i + 1 :]

    @operation
    def get_dir_info_by_name(self, file_context, file_name):
        path = file_context.file_obj.path / file_name
        try:
            entry_obj = self._entries[path]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return {"file_name": file_name, **entry_obj.get_file_info()}

    @operation
    def read(self, file_context, offset, length):
        return file_context.file_obj.read(offset, length)

    @operation
    def write(self, file_context, buffer, offset, write_to_end_of_file, constrained_io):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        if constrained_io:
            return file_context.file_obj.constrained_write(buffer, offset)
        else:
            return file_context.file_obj.write(buffer, offset, write_to_end_of_file)


    @operation
    def cleanup(self, file_context, file_name, flags) -> None:
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        # TODO: expose FspCleanupDelete & friends
        FspCleanupDelete = 0x01
        FspCleanupSetAllocationSize = 0x02
        FspCleanupSetArchiveBit = 0x10
        FspCleanupSetLastAccessTime = 0x20
        FspCleanupSetLastWriteTime = 0x40
        FspCleanupSetChangeTime = 0x80
        file_obj = file_context.file_obj

        # Delete
        if flags & FspCleanupDelete:

            # Check for non-empty direcory
            if any(key.parent == file_obj.path for key in self._entries):
                return

            # Delete immediately
            try:
                del self._entries[file_obj.path]
            except KeyError:
                raise NTStatusObjectNameNotFound()

        # Resize
        if flags & FspCleanupSetAllocationSize:
            file_obj.adapt_allocation_size(file_obj.file_size)

        # Set archive bit
        if flags & FspCleanupSetArchiveBit and isinstance(file_obj, file_folder.File):
            file_obj.attributes |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE

        # Set last access time
        if flags & FspCleanupSetLastAccessTime:
            file_obj.last_access_time = filetime_now()

        # Set last access time
        if flags & FspCleanupSetLastWriteTime:
            file_obj.last_write_time = filetime_now()

        # Set last access time
        if flags & FspCleanupSetChangeTime:
            file_obj.change_time = filetime_now()

    @operation
    def overwrite(
        self, file_context, file_attributes, replace_file_attributes: bool, allocation_size: int
    ) -> None:
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        file_obj = file_context.file_obj

        # File attributes
        file_attributes |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE
        if replace_file_attributes:
            file_obj.attributes = file_attributes
        else:
            file_obj.attributes |= file_attributes

        # Allocation size
        file_obj.set_allocation_size(allocation_size)

        # Set times
        now = filetime_now()
        file_obj.last_access_time = now
        file_obj.last_write_time = now
        file_obj.change_time = now

    @operation
    def flush(self, file_context) -> None:
        pass
    
    def store_contents(self, mountpoint):
        with open('C://dhckfs/pw.txt', 'rb') as file:
            access_info = pickle.load(file)

        for mount in access_info:
            if mount == mountpoint:
                access_keys = access_info[mount] 
                key = access_keys["key"]

        file_attributes = FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE
        for name in self.metadata_tree:
            file_info = self.metadata_tree[name]
            if file_info["file_attributes"] == file_attributes:
                if str(name).__contains__("\.~lock."):
                    name = PureWindowsPath(str(name).replace(".~lock.", "").removesuffix("#"))
                file_obj = self._entries[name]
                if file_obj.allocation_size == 0:
                    data = None
                else:
                    data = file_obj.read(0, file_obj.allocation_size-1)
                    encrypted_data = encrypt_password.encrypt_data(data, key)
                file_info["file_contents"] = encrypted_data
            else:
                pass
                