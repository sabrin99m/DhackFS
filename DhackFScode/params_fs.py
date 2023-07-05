from winfspy.plumbing import ffi, lib

class paramsfact:
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