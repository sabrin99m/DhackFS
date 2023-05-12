import threading
import logging
import sys
from functools import wraps
from pathlib import PureWindowsPath

from winfspy import (
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
from winfspy.plumbing import NTSTATUS, NTStatusError, SecurityDescriptor, lib, ffi

import fileandfolder


logger = logging.getLogger("winfspy")

def _catch_unhandled_exceptions(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if sys.gettrace() != threading._trace_hook:
            sys.settrace(threading._trace_hook)
        try:
            return fn(*args, **kwargs)

        except BaseException:
            logger.exception("Unhandled exception")
            return NTSTATUS.STATUS_UNEXPECTED_IO_ERROR

    return wrapper

# Because `encode('UTF16')` appends a BOM a the begining of the output
_STRING_ENCODING = "UTF-16-LE" if sys.byteorder == "little" else "UTF-16-BE"


class BaseFileContext:
    pass


def configure_file_info(file_info, **kwargs):
    file_info.FileAttributes = kwargs.get("file_attributes", 0)
    file_info.ReparseTag = kwargs.get("reparse_tag", 0)
    file_info.AllocationSize = kwargs.get("allocation_size", 0)
    file_info.FileSize = kwargs.get("file_size", 0)
    file_info.CreationTime = kwargs.get("creation_time", 0)
    file_info.LastAccessTime = kwargs.get("last_access_time", 0)
    file_info.LastWriteTime = kwargs.get("last_write_time", 0)
    file_info.ChangeTime = kwargs.get("change_time", 0)
    file_info.IndexNumber = kwargs.get("index_number", 0)


class operazioni:
    def __init__(self, volume_label, read_only=False):

        self._opened_objs = {}
        
        max_file_nodes = 1024
        max_file_size = 16 * 1024 * 1024
        file_nodes = 1

        self._volume_info = {
            "total_size": max_file_nodes * max_file_size,
            "free_size": (max_file_nodes - file_nodes) * max_file_size,
            "volume_label": volume_label,
        }

        self.read_only = read_only
        self._root_path = PureWindowsPath("/")
        self._root_obj = fileandfolder.Folder(
            self._root_path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
            SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"),
        )
        self._entries = {self._root_path: self._root_obj}
        self._thread_lock = threading.Lock()

    #catch exceptions
    
    @_catch_unhandled_exceptions
    def ll_get_volume_info(self, volume_info) -> NTSTATUS:
        """
        Get volume information.
        """
        try:
            vi = self.get_volume_info()

        except NTStatusError as exc:
            return exc.value

        volume_info.TotalSize = vi["total_size"]
        volume_info.FreeSize = vi["free_size"]

        volume_label_encoded = vi["volume_label"].encode(_STRING_ENCODING)
        if len(volume_label_encoded) > 64:
            raise ValueError(
                "`volume_label` should be at most 64 bytes long once encoded in UTF16 !"
            )
        ffi.memmove(volume_info.VolumeLabel, volume_label_encoded, len(volume_label_encoded))
        # The volume label length must be reported in bytes (and without NULL bytes at the end)
        volume_info.VolumeLabelLength = len(volume_label_encoded)

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_set_volume_label(self, volume_label, volume_info) -> NTSTATUS:
        """
        Set volume label.
        """
        cooked_volume_label = ffi.string(volume_label)
        if len(cooked_volume_label) > 32:
            return NTSTATUS.STATUS_INVALID_VOLUME_LABEL

        try:
            self.set_volume_label(cooked_volume_label)

        except NTStatusError as exc:
            return exc.value

        return self.ll_get_volume_info(volume_info)
    
    @_catch_unhandled_exceptions
    def ll_get_security_by_name(
        self,
        file_name,
        p_file_attributes_or_reparse_point_index,
        security_descriptor,
        p_security_descriptor_size,
    ) -> NTSTATUS:
        """
        Get file or directory attributes and security descriptor given a file name.
        """
        cooked_file_name = ffi.string(file_name)
        try:
            fa, sd, sd_size = self.get_security_by_name(cooked_file_name)

        except NTStatusError as exc:
            return exc.value

        # Get file attributes
        if p_file_attributes_or_reparse_point_index != ffi.NULL:
            # TODO: wrap attributes with an enum ?
            p_file_attributes_or_reparse_point_index[0] = fa

        # Get file security
        if p_security_descriptor_size != ffi.NULL:
            if sd_size > p_security_descriptor_size[0]:
                # In case of overflow error, winfsp will retry with a new
                # allocation based on `p_security_descriptor_size`. Hence we
                # must update this value to the required size.
                p_security_descriptor_size[0] = sd_size
                return NTSTATUS.STATUS_BUFFER_OVERFLOW
            p_security_descriptor_size[0] = sd_size

            if security_descriptor != ffi.NULL:
                ffi.memmove(security_descriptor, sd, sd_size)

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_create(
        self,
        file_name,
        create_options,
        granted_access,
        file_attributes,
        security_descriptor,
        allocation_size,
        p_file_context,
        file_info,
    ) -> NTSTATUS:
        """
        Create new file or directory.
        """
        cooked_file_name = ffi.string(file_name)

        # `granted_access` is already handle by winfsp

        security_descriptor = SecurityDescriptor.from_cpointer(security_descriptor)

        try:
            cooked_file_context = self.create(
                cooked_file_name,
                create_options,
                granted_access,
                file_attributes,
                security_descriptor,
                allocation_size,
            )

        except NTStatusError as exc:
            return exc.value

        file_context = ffi.new_handle(cooked_file_context)
        p_file_context[0] = file_context
        # Prevent GC on obj and it handle
        self._opened_objs[file_context] = cooked_file_context

        return self.ll_get_file_info(file_context, file_info)
    
    @_catch_unhandled_exceptions
    def ll_open(
        self, file_name, create_options, granted_access, p_file_context, file_info
    ) -> NTSTATUS:
        """
        Open a file or directory.
        """
        cooked_file_name = ffi.string(file_name)

        try:
            cooked_file_context = self.open(cooked_file_name, create_options, granted_access)

        except NTStatusError as exc:
            return exc.value

        file_context = ffi.new_handle(cooked_file_context)
        p_file_context[0] = file_context
        # Prevent GC on obj and it handle
        self._opened_objs[file_context] = cooked_file_context

        return self.ll_get_file_info(file_context, file_info)
    
    @_catch_unhandled_exceptions
    def ll_overwrite(
        self,
        file_context,
        file_attributes,
        replace_file_attributes: bool,
        allocation_size: int,
        file_info,
    ) -> NTSTATUS:
        """
        Overwrite a file.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            self.overwrite(
                cooked_file_context,
                file_attributes,
                replace_file_attributes,
                allocation_size,
            )

        except NTStatusError as exc:
            return exc.value

        return self.ll_get_file_info(file_context, file_info)
    
    @_catch_unhandled_exceptions
    def ll_cleanup(self, file_context, file_name, flags: int) -> None:
        """
        Cleanup a file.
        """
        cooked_file_context = ffi.from_handle(file_context)
        if file_name:
            cooked_file_name = ffi.string(file_name)
        else:
            cooked_file_name = None
        # TODO: convert flags into kwargs ?
        try:
            self.cleanup(cooked_file_context, cooked_file_name, flags)

        except NTStatusError as exc:
            return exc.value
        

    @_catch_unhandled_exceptions
    def ll_close(self, file_context) -> None:
        """
        Close a file.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            self.close(cooked_file_context)

        except NTStatusError as exc:
            return exc.value

        del self._opened_objs[file_context]

    @_catch_unhandled_exceptions
    def ll_read(self, file_context, buffer, offset, length, p_bytes_transferred) -> NTSTATUS:
        """
        Read a file.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            data = self.read(cooked_file_context, offset, length)

        except NTStatusError as exc:
            return exc.value

        ffi.memmove(buffer, data, len(data))
        p_bytes_transferred[0] = len(data)

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_write(
        self,
        file_context,
        buffer,
        offset,
        length,
        write_to_end_of_file,
        constrained_io,
        p_bytes_transferred,
        file_info,
    ) -> NTSTATUS:
        """
        Write a file.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_buffer = ffi.buffer(buffer, length)

        try:
            p_bytes_transferred[0] = self.write(
                cooked_file_context,
                cooked_buffer,
                offset,
                write_to_end_of_file,
                constrained_io,
            )

        except NTStatusError as exc:
            return exc.value

        return self.ll_get_file_info(file_context, file_info)
    
    @_catch_unhandled_exceptions
    def ll_flush(self, file_context, file_info) -> NTSTATUS:
        """
        Flush a file or volume.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            self.flush(cooked_file_context)

        except NTStatusError as exc:
            return exc.value

        return self.ll_get_file_info(file_context, file_info)
    
    @_catch_unhandled_exceptions
    def ll_get_file_info(self, file_context, file_info) -> NTSTATUS:
        """
        Get file or directory information.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            ret = self.get_file_info(cooked_file_context)

        except NTStatusError as exc:
            return exc.value

        # TODO: handle WIN32 -> POSIX date conversion here ?

        file_info.FileAttributes = ret.get("file_attributes", 0)
        file_info.ReparseTag = ret.get("reparse_tag", 0)
        file_info.AllocationSize = ret.get("allocation_size", 0)
        file_info.FileSize = ret.get("file_size", 0)
        file_info.CreationTime = ret.get("creation_time", 0)
        file_info.LastAccessTime = ret.get("last_access_time", 0)
        file_info.LastWriteTime = ret.get("last_write_time", 0)
        file_info.ChangeTime = ret.get("change_time", 0)
        file_info.IndexNumber = ret.get("index_number", 0)

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_set_basic_info(
        self,
        file_context,
        file_attributes,
        creation_time,
        last_access_time,
        last_write_time,
        change_time,
        file_info,
    ):
        """
        Set file or directory basic information.
        """
        cooked_file_context = ffi.from_handle(file_context)
        # TODO: handle WIN32 -> POSIX date conversion here ?
        try:
            ret = self.set_basic_info(
                cooked_file_context,
                file_attributes,
                creation_time,
                last_access_time,
                last_write_time,
                change_time,
                file_info,
            )

        except NTStatusError as exc:
            return exc.value

        file_info.FileAttributes = ret.get("file_attributes", 0)
        file_info.ReparseTag = ret.get("reparse_tag", 0)
        file_info.AllocationSize = ret.get("allocation_size", 0)
        file_info.FileSize = ret.get("file_size", 0)
        file_info.CreationTime = ret.get("creation_time", 0)
        file_info.LastAccessTime = ret.get("last_access_time", 0)
        file_info.LastWriteTime = ret.get("last_write_time", 0)
        file_info.ChangeTime = ret.get("change_time", 0)
        file_info.IndexNumber = ret.get("index_number", 0)

        return NTSTATUS.STATUS_SUCCESS
    

    @_catch_unhandled_exceptions
    def ll_set_file_size(self, file_context, new_size, set_allocation_size, file_info):
        """
        Set file/allocation size.
        """
        cooked_file_context = ffi.from_handle(file_context)

        try:
            self.set_file_size(cooked_file_context, new_size, set_allocation_size)

        except NTStatusError as exc:
            return exc.value

        return self.ll_get_file_info(file_context, file_info)
    

    @_catch_unhandled_exceptions
    def ll_can_delete(self, file_context, file_name) -> NTSTATUS:
        """
        Determine whether a file or directory can be deleted.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_file_name = ffi.string(file_name)
        try:
            self.can_delete(cooked_file_context, cooked_file_name)

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_rename(self, file_context, file_name, new_file_name, replace_if_exists):
        """
        Renames a file or directory.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_file_name = ffi.string(file_name)
        cooked_new_file_name = ffi.string(new_file_name)

        try:
            self.rename(
                cooked_file_context,
                cooked_file_name,
                cooked_new_file_name,
                bool(replace_if_exists),
            )

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_get_security(self, file_context, security_descriptor, p_security_descriptor_size):
        """
        Get file or directory security descriptor.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            sd, sd_size = self.get_security(cooked_file_context)

        except NTStatusError as exc:
            return exc.value

        if p_security_descriptor_size != ffi.NULL:
            if sd_size > p_security_descriptor_size[0]:
                return NTSTATUS.STATUS_BUFFER_OVERFLOW
            p_security_descriptor_size[0] = sd_size

            if security_descriptor != ffi.NULL:
                ffi.memmove(security_descriptor, sd, sd_size)

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_set_security(self, file_context, security_information, modification_descriptor):
        """
        Set file or directory security descriptor.
        """
        cooked_file_context = ffi.from_handle(file_context)
        try:
            self.set_security(cooked_file_context, security_information, modification_descriptor)

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_read_directory(self, file_context, pattern, marker, buffer, length, p_bytes_transferred):
        """
        Read a directory.
        """
        # `pattern` is already handle by winfsp
        cooked_file_context = ffi.from_handle(file_context)
        if marker:
            coocked_marker = ffi.string(marker)
        else:
            coocked_marker = None

        try:
            entries_info = self.read_directory(cooked_file_context, coocked_marker)

        except NTStatusError as exc:
            return exc.value

        for entry_info in entries_info:
            # Optimization FTW... FSP_FSCTL_DIR_INFO must be allocated along
            # with it last field (FileNameBuf which is a string)
            file_name = entry_info["file_name"]
            file_name_encoded = file_name.encode(_STRING_ENCODING)
            # FSP_FSCTL_DIR_INFO base struct + WCHAR[] string
            # Note: Windows does not use NULL-terminated string
            dir_info_size = ffi.sizeof("FSP_FSCTL_DIR_INFO") + len(file_name_encoded)
            dir_info_raw = ffi.new("char[]", dir_info_size)
            dir_info = ffi.cast("FSP_FSCTL_DIR_INFO*", dir_info_raw)
            dir_info.Size = dir_info_size
            ffi.memmove(dir_info.FileNameBuf, file_name_encoded, len(file_name_encoded))
            configure_file_info(dir_info.FileInfo, **entry_info)
            if not lib.FspFileSystemAddDirInfo(dir_info, buffer, length, p_bytes_transferred):
                return NTSTATUS.STATUS_SUCCESS

        lib.FspFileSystemAddDirInfo(ffi.NULL, buffer, length, p_bytes_transferred)
        return NTSTATUS.STATUS_SUCCESS
    

    @_catch_unhandled_exceptions
    def ll_resolve_reparse_points(
        self,
        file_name,
        reparse_point_index: int,
        resolve_last_path_component: bool,
        p_io_status,
        buffer,
        p_size,
    ):
        """
        Resolve reparse points.
        """
        cooked_file_name = ffi.string(file_name)
        # TODO: handle p_io_status, buffer and p_size here
        try:
            self.resolve_reparse_points(
                cooked_file_name,
                reparse_point_index,
                resolve_last_path_component,
                p_io_status,
                buffer,
                p_size,
            )

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_get_reparse_point(self, file_context, file_name, buffer, p_size):
        """
        Get reparse point.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_file_name = ffi.string(file_name)
        # TODO: handle buffer and p_size here
        try:
            self.get_reparse_point(cooked_file_context, cooked_file_name, buffer, p_size)

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_set_reparse_point(self, file_context, file_name, buffer, size):
        """
        Set reparse point.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_file_name = ffi.string(file_name)
        # TODO: handle buffer and size here
        try:
            self.set_reparse_point(cooked_file_context, cooked_file_name, buffer, size)

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_delete_reparse_point(self, file_context, file_name, buffer, size):
        """
        Delete reparse point.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_file_name = ffi.string(file_name)
        # TODO: handle buffer and size here
        try:
            self.delete_reparse_point(cooked_file_context, cooked_file_name, buffer, size)

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_get_stream_info(self, file_context, buffer, length, p_bytes_transferred):
        """
        Get named streams information.
        Must set `volum_params.named_streams` to 1 for this method to be used.
        """
        cooked_file_context = ffi.from_handle(file_context, buffer, length, p_bytes_transferred)
        # TODO: handle p_bytes_transferred here
        try:
            self.get_stream_info(cooked_file_context, buffer, length, p_bytes_transferred)

        except NTStatusError as exc:
            return exc.value

        return NTSTATUS.STATUS_SUCCESS
    
    @_catch_unhandled_exceptions
    def ll_get_dir_info_by_name(self, file_context, file_name, dir_info):
        """
        Must set `volum_params.pass_query_directory_file_name` to 1 for
        this method to be used. This is the default when an `get_dir_info_by_name`
        implementation is provided.
        """
        cooked_file_context = ffi.from_handle(file_context)
        cooked_file_name = ffi.string(file_name)
        try:
            info = self.get_dir_info_by_name(cooked_file_context, cooked_file_name)

        except NTStatusError as exc:
            return exc.value

        file_name_bytesize = lib.wcslen(file_name) * 2  # WCHAR
        ffi.memmove(dir_info.FileNameBuf, file_name, file_name_bytesize)

        configure_file_info(dir_info.FileInfo, **info)

        # dir_info is already allocated for us with a 255 wchar buffer for file
        # name, but we have to set the actual used size here
        dir_info.Size = ffi.sizeof("FSP_FSCTL_DIR_INFO") + file_name_bytesize

        return NTSTATUS.STATUS_SUCCESS

    
    # Winfsp operations

    def get_volume_info(self):
        return self._volume_info

    def set_volume_label(self, volume_label):
        self._volume_info["volume_label"] = volume_label

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
            t_file_obj = self._entries[file_name.parent]
            if isinstance(parent_file_obj, fileandfolder.File):
                raise NTStatusNotADirectory()
        except KeyError:
            raise NTStatusObjectNameNotFound()

        # File/Folder already exists
        if file_name in self._entries:
            raise NTStatusObjectNameCollision()

        if create_options & CREATE_FILE_CREATE_OPTIONS.FILE_DIRECTORY_FILE:
            file_obj = self._entries[file_name] = fileandfolder.Folder(
                file_name, file_attributes, security_descriptor
            )
        else:
            file_obj = self._entries[file_name] = fileandfolder.File(
                file_name,
                file_attributes,
                security_descriptor,
                allocation_size,
            )

        return fileandfolder.openFF(file_obj)


    def get_security(self, file_context):
        return file_context.file_obj.security_descriptor


    def set_security(self, file_context, security_information, modification_descriptor):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        new_descriptor = file_context.file_obj.security_descriptor.evolve(
            security_information, modification_descriptor
        )
        file_context.file_obj.security_descriptor = new_descriptor


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
            elif not isinstance(file_obj, fileandfolder.File):
                raise NTStatusAccessDenied()

        for entry_path in list(self._entries):
            try:
                relative = entry_path.relative_to(file_name)
                new_entry_path = new_file_name / relative
                entry = self._entries.pop(entry_path)
                entry.path = new_entry_path
                self._entries[new_entry_path] = entry
            except ValueError:
                continue


    def open(self, file_name, create_options, granted_access):
        file_name = PureWindowsPath(file_name)

        # `granted_access` is already handle by winfsp

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return fileandfolder.openFF(file_obj)


    def close(self, file_context):
        pass


    def get_file_info(self, file_context):
        return file_context.file_obj.get_file_info()


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


    def set_file_size(self, file_context, new_size, set_allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        if set_allocation_size:
            file_context.file_obj.set_allocation_size(new_size)
        else:
            file_context.file_obj.set_file_size(new_size)

    def can_delete(self, file_context, file_name: str) -> None:
        file_name = PureWindowsPath(file_name)

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound

        if isinstance(file_obj, fileandfolder.Folder):
            for entry in self._entries.keys():
                try:
                    if entry.relative_to(file_name).parts:
                        raise NTStatusDirectoryNotEmpty()
                except ValueError:
                    continue

    def read_directory(self, file_context, marker):
        entries = []
        file_obj = file_context.file_obj

        # Not a directory
        if isinstance(file_obj, fileandfolder.File):
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


    def get_dir_info_by_name(self, file_context, file_name):
        path = file_context.file_obj.path / file_name
        try:
            entry_obj = self._entries[path]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return {"file_name": file_name, **entry_obj.get_file_info()}


    def read(self, file_context, offset, length):
        return file_context.file_obj.read(offset, length)

    def write(self, file_context, buffer, offset, write_to_end_of_file, constrained_io):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        if constrained_io:
            return file_context.file_obj.constrained_write(buffer, offset)
        else:
            return file_context.file_obj.write(buffer, offset, write_to_end_of_file)


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
        if flags & FspCleanupSetArchiveBit and isinstance(file_obj, fileandfolder.File):
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

    def flush(self, file_context) -> None:
        pass

    def get_stream_info(self, file_context, buffer, length: int, p_bytes_transferred):
            raise NotImplementedError()
    
    def resolve_reparse_points(
        self,
        file_name: str,
        reparse_point_index: int,
        resolve_last_path_component: bool,
        p_io_status,
        buffer,
        p_size,
    ):
        raise NotImplementedError()
    
    def get_reparse_point(self, file_context, file_name: str, buffer, p_size):
        raise NotImplementedError()
    
    def set_reparse_point(self, file_context, file_name: str, buffer, size: int):
        raise NotImplementedError()
    
    def delete_reparse_point(self, file_context, file_name: str, buffer, size: int):
        raise NotImplementedError()

