from winfspy.plumbing import ffi, lib, cook_ntstatus, nt_success
from winfspy.plumbing import WinFSPyError, FileSystemAlreadyStarted, FileSystemNotStarted

#definizione del file system e dell'intefaccia

def interface(set_delete_available: bool):
    file_system_interface = ffi.new("FSP_FILE_SYSTEM_INTERFACE*")
    file_system_interface.Create = lib._trampolin_fs_Create                   
    file_system_interface.Open = lib._trampolin_fs_Open
    file_system_interface.Close = lib._trampolin_fs_Close
    file_system_interface.Read = lib._trampolin_fs_Read
    file_system_interface.Write = lib._trampolin_fs_Write
    file_system_interface.ReadDirectory = lib._trampolin_fs_ReadDirectory
    file_system_interface.GetFileInfo = lib._trampolin_fs_GetFileInfo
    file_system_interface.CanDelete = lib._trampolin_fs_CanDelete
    file_system_interface.Rename = lib._trampolin_fs_Rename
    file_system_interface.SetBasicInfo = lib._trampolin_fs_SetBasicInfo
    file_system_interface.SetFileSize = lib._trampolin_fs_SetFileSize
    

    return file_system_interface


def _volume_params_factory(
    sector_size=0,
    sectors_per_allocation_unit=0,
    max_component_length=0,
    volume_creation_time=0,
    volume_serial_number=0,
    transact_timeout=0,
    irp_timeout=0,
    irp_capacity=0,
    file_info_timeout=0,
    case_sensitive_search=0,
    case_preserved_names=0,
    unicode_on_disk=0,
    persistent_acls=0,
    reparse_points=0,
    reparse_points_access_check=0,
    named_streams=0,
    hard_links=0,
    extended_attributes=0,
    read_only_volume=0,
    post_cleanup_when_modified_only=0,
    pass_query_directory_pattern=0,
    always_use_double_buffering=0,
    pass_query_directory_file_name=0,
    flush_and_purge_on_cleanup=0,
    device_control=0,
    um_file_context_is_user_context2=0,
    um_file_context_is_full_context=0,
    um_reserved_flags=0,
    allow_open_in_kernel_mode=0,
    case_preserved_extended_attributes=0,
    wsl_features=0,
    directory_marker_as_next_offset=0,
    reject_irp_prior_to_transact0=0,
    km_reserved_flags=0,
    prefix="",
    file_system_name="",
    volume_info_timeout_valid=0,
    dir_info_timeout_valid=0,
    security_timeout_valid=0,
    stream_info_timeout_valid=0,
    km_additional_reserved_flags=0,
    volume_info_timeout=0,
    dir_info_timeout=0,
    security_timeout=0,
    stream_info_timeout=0,
):
    volume_params = ffi.new("FSP_FSCTL_VOLUME_PARAMS*")
    lib.configure_FSP_FSCTL_VOLUME_PARAMS(
        volume_params,
        sector_size,
        sectors_per_allocation_unit,
        max_component_length,
        volume_creation_time,
        volume_serial_number,
        transact_timeout,
        irp_timeout,
        irp_capacity,
        file_info_timeout,
        case_sensitive_search,
        case_preserved_names,
        unicode_on_disk,
        persistent_acls,
        reparse_points,
        reparse_points_access_check,
        named_streams,
        hard_links,
        extended_attributes,
        read_only_volume,
        post_cleanup_when_modified_only,
        pass_query_directory_pattern,
        always_use_double_buffering,
        pass_query_directory_file_name,
        flush_and_purge_on_cleanup,
        device_control,
        um_file_context_is_user_context2,
        um_file_context_is_full_context,
        um_reserved_flags,
        allow_open_in_kernel_mode,
        case_preserved_extended_attributes,
        wsl_features,
        directory_marker_as_next_offset,
        reject_irp_prior_to_transact0,
        km_reserved_flags,
        prefix,
        file_system_name,
        volume_info_timeout_valid,
        dir_info_timeout_valid,
        security_timeout_valid,
        stream_info_timeout_valid,
        km_additional_reserved_flags,
        volume_info_timeout,
        dir_info_timeout,
        security_timeout,
        stream_info_timeout,
    )
    return volume_params

class VFileSys:
    def __init__(self, mountpoint, operations, debug=False, **volume_params):
        self.started = False
        
        self.debug = debug
        self.volume_params = volume_params
        self.mountpoint = mountpoint
        self.operations = operations
        self._apply_volume_params()
        self._create_file_system() 

    
    def _apply_volume_params(self):

        self._volume_params = _volume_params_factory(**self.volume_params)
        self._file_system_interface = interface(
            set_delete_available=True
        )
        self._file_system_ptr = ffi.new("FSP_FILE_SYSTEM**")

    def _create_file_system(self):
        # Network drive if prefix is provided
        if self.volume_params.get("prefix"):
            device_path = lib.WFSPY_FSP_FSCTL_NET_DEVICE_NAME
        else:
            device_path = lib.WFSPY_FSP_FSCTL_DISK_DEVICE_NAME

        result = lib.FspFileSystemCreate(
            device_path, self._volume_params, self._file_system_interface, self._file_system_ptr,
        )
        if not nt_success(result):
            raise WinFSPyError(f"Cannot create file system: {cook_ntstatus(result).name}")

        # Avoid GC on the handle
        self._operations_handle = ffi.new_handle(self.operations)
        self._file_system_ptr[0].UserContext = self._operations_handle

        if self.debug:
            lib.FspFileSystemSetDebugLogF(self._file_system_ptr[0], 0xFFFFFFFF)

    def start(self):
        if self.started:
            raise FileSystemAlreadyStarted()
        self.started = True

        result = lib.FspFileSystemSetMountPoint(self._file_system_ptr[0], self.mountpoint)
        if not nt_success(result):
            raise WinFSPyError(f"Cannot mount file system: {cook_ntstatus(result).name}")
        result = lib.FspFileSystemStartDispatcher(self._file_system_ptr[0], 0)
        if not nt_success(result):
            raise WinFSPyError(f"Cannot start file system dispatcher: {cook_ntstatus(result).name}")

    def restart(self, **volume_params):
        self.stop()
        self.volume_params.update(volume_params)
        self._apply_volume_params()
        self._create_file_system()
        self.start()

    def stop(self):
        if not self.started:
            raise FileSystemNotStarted()
        self.started = False

        lib.FspFileSystemStopDispatcher(self._file_system_ptr[0])
        lib.FspFileSystemDelete(self._file_system_ptr[0])
