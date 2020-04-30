#coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/fbapi.py
# DESCRIPTION:    New Firebird API
# CREATED:        4.3.2020
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""firebird-driver - New Firebird API


"""

import typing as t
import sys
import ctypes as c
from ctypes.util import find_library
from locale import getpreferredencoding
from pathlib import Path
import platform
from .hooks import hooks, HookType

# Constants

#
#isc_dpb_address = 1
#isc_dpb_addr_protocol = 1
#isc_dpb_addr_endpoint = 2
#isc_dpb_addr_flags = 3
#isc_dpb_addr_flag_conn_compressed = 0x1
#isc_dpb_addr_flag_conn_encrypted = 0x2
#isc_dpb_pages = 1
#isc_dpb_records = 2
#isc_dpb_indices = 4
#isc_dpb_transactions = 8
#isc_dpb_no_update = 16
#isc_dpb_repair = 32
#isc_dpb_ignore = 64
#isc_dpb_shut_cache = 0x1
#isc_dpb_shut_attachment = 0x2
#isc_dpb_shut_transaction = 0x4
#isc_dpb_shut_force = 0x8
#isc_dpb_shut_mode_mask = 0x70
#isc_dpb_shut_default = 0x0
#isc_dpb_shut_normal = 0x10
#isc_dpb_shut_multi = 0x20
#isc_dpb_shut_single = 0x30
#isc_dpb_shut_full = 0x40

#RDB_system = 1
#RDB_id_assigned = 2


# BLOB parameter buffer (BPB)
#isc_bpb_version1 = 1
#isc_bpb_source_type = 1
#isc_bpb_target_type = 2
#isc_bpb_type = 3
#isc_bpb_source_interp = 4
#isc_bpb_target_interp = 5
#isc_bpb_filter_parameter = 6
## Added in FB 2.1
#isc_bpb_storage = 7

#isc_bpb_type_segmented = 0x0
#isc_bpb_type_stream = 0x1
## Added in FB 2.1
#isc_bpb_storage_main = 0x0
#isc_bpb_storage_temp = 0x2

# Service parameter block (SPB)
##isc_spb_version1 = 1
##isc_spb_current_version = 2
##isc_spb_version3 = 3 # Firebird 3.0
#isc_spb_user_name = 28 # isc_dpb_user_name
##isc_spb_sys_user_name = isc_dpb_sys_user_name
##isc_spb_sys_user_name_enc = isc_dpb_sys_user_name_enc
#isc_spb_password = 29 # isc_dpb_password
##isc_spb_password_enc = isc_dpb_password_enc
#isc_spb_command_line = 105
#isc_spb_dbname = 106
#isc_spb_verbose = 107
#isc_spb_options = 108
#isc_spb_address_path = 109
## Added in FB 2.1
#isc_spb_process_id = 110
#isc_spb_trusted_auth = 111
#isc_spb_process_name = 112
## Added in FB 2.5
#isc_spb_trusted_role = 113
## Added in FB 3.0
#isc_spb_verbint = 114
#isc_spb_auth_block = 115
#isc_spb_auth_plugin_name = 116
#isc_spb_auth_plugin_list = 117
#isc_spb_utf8_filename = 118
#isc_spb_client_version = 119
#isc_spb_remote_protocol = 120
#isc_spb_host_name = 121
#isc_spb_os_user = 122
#isc_spb_config = 123
#isc_spb_expected_db = 124
# This will not be used in protocol 13, therefore may be reused
#isc_spb_specific_auth_data = isc_spb_trusted_auth

# Service action items
#isc_action_svc_backup = 1           # Starts database backup process on the server
#isc_action_svc_restore = 2          # Starts database restore process on the server
#isc_action_svc_repair = 3           # Starts database repair process on the server
#isc_action_svc_add_user = 4         # Adds a new user to the security database
#isc_action_svc_delete_user = 5      # Deletes a user record from the security database
#isc_action_svc_modify_user = 6      # Modifies a user record in the security database
#isc_action_svc_display_user = 7     # Displays a user record from the security database
#isc_action_svc_properties = 8       # Sets database properties
##isc_action_svc_add_license = 9      # Adds a license to the license file
##isc_action_svc_remove_license = 10  # Removes a license from the license file
#isc_action_svc_db_stats = 11        # Retrieves database statistics
#isc_action_svc_get_fb_log = 12      # Retrieves the Firebird log file from the server
## Added in FB 2.5
#isc_action_svc_nbak = 20
#isc_action_svc_nrest = 21
#isc_action_svc_trace_start = 22
#isc_action_svc_trace_stop = 23
#isc_action_svc_trace_suspend = 24
#isc_action_svc_trace_resume = 25
#isc_action_svc_trace_list = 26
#isc_action_svc_set_mapping = 27
#isc_action_svc_drop_mapping = 28
#isc_action_svc_display_user_adm = 29
#isc_action_svc_validate = 30 # Firebird 3.0
#isc_action_svc_last = 31

# Service information items
#isc_info_svc_svr_db_info = 50    # Retrieves the number of attachments and databases */
#isc_info_svc_get_config = 53     # Retrieves the parameters and values for IB_CONFIG */
#isc_info_svc_version = 54        # Retrieves the version of the services manager */
#isc_info_svc_server_version = 55 # Retrieves the version of the Firebird server */
#isc_info_svc_implementation = 56 # Retrieves the implementation of the Firebird server */
#isc_info_svc_capabilities = 57   # Retrieves a bitmask representing the server's capabilities */
#isc_info_svc_user_dbpath = 58    # Retrieves the path to the security database in use by the server */
#isc_info_svc_get_env = 59        # Retrieves the setting of $FIREBIRD */
#isc_info_svc_get_env_lock = 60   # Retrieves the setting of $FIREBIRD_LCK */
#isc_info_svc_get_env_msg = 61    # Retrieves the setting of $FIREBIRD_MSG */
#isc_info_svc_line = 62           # Retrieves 1 line of service output per call */
#isc_info_svc_to_eof = 63         # Retrieves as much of the server output as will fit in the supplied buffer */
#isc_info_svc_timeout = 64        # Sets / signifies a timeout value for reading service information */
#isc_info_svc_limbo_trans = 66    # Retrieve the limbo transactions */
#isc_info_svc_running = 67        # Checks to see if a service is running on an attachment */
#isc_info_svc_get_users = 68      # Returns the user information from isc_action_svc_display_users */
#isc_info_svc_auth_block = 69     # FB 3.0: Sets authentication block for service query() call */
#isc_info_svc_stdin = 78	         # Returns maximum size of data, needed as stdin for service */

# Parameters for isc_action_{add|del|mod|disp)_user
#isc_spb_sec_userid = 5
#isc_spb_sec_groupid = 6
#isc_spb_sec_username = 7
#isc_spb_sec_password = 8
#isc_spb_sec_groupname = 9
#isc_spb_sec_firstname = 10
#isc_spb_sec_middlename = 11
#isc_spb_sec_lastname = 12
#isc_spb_sec_admin = 13

# Parameters for isc_action_svc_backup
#isc_spb_bkp_file = 5
#isc_spb_bkp_factor = 6
#isc_spb_bkp_length = 7
#isc_spb_bkp_skip_data = 8 # Firebird 3.0
#isc_spb_bkp_stat = 15 # Firebird 2.5
#isc_spb_bkp_ignore_checksums = 0x01
#isc_spb_bkp_ignore_limbo = 0x02
#isc_spb_bkp_metadata_only = 0x04
#isc_spb_bkp_no_garbage_collect = 0x08
#isc_spb_bkp_old_descriptions = 0x10
#isc_spb_bkp_non_transportable = 0x20
#isc_spb_bkp_convert = 0x40
#isc_spb_bkp_expand = 0x80
#isc_spb_bkp_no_triggers = 0x8000

# Parameters for isc_action_svc_properties
#isc_spb_prp_page_buffers = 5
#isc_spb_prp_sweep_interval = 6
#isc_spb_prp_shutdown_db = 7
#isc_spb_prp_deny_new_attachments = 9
#isc_spb_prp_deny_new_transactions = 10
#isc_spb_prp_reserve_space = 11
#isc_spb_prp_write_mode = 12
#isc_spb_prp_access_mode = 13
#isc_spb_prp_set_sql_dialect = 14
#isc_spb_prp_activate = 0x0100
#isc_spb_prp_db_online = 0x0200
#isc_spb_prp_nolinger = 0x0400 # Firebird 3.0
#isc_spb_prp_force_shutdown = 41
#isc_spb_prp_attachments_shutdown = 42
#isc_spb_prp_transactions_shutdown = 43
#isc_spb_prp_shutdown_mode = 44
#isc_spb_prp_online_mode = 45

# Parameters for isc_spb_prp_shutdown_mode and isc_spb_prp_online_mode
#isc_spb_prp_sm_normal = 0
#isc_spb_prp_sm_multi = 1
#isc_spb_prp_sm_single = 2
#isc_spb_prp_sm_full = 3

# Parameters for isc_spb_prp_reserve_space
#isc_spb_prp_res_use_full = 35
#isc_spb_prp_res = 36

# Parameters for isc_spb_prp_write_mode
#isc_spb_prp_wm_async = 37
#isc_spb_prp_wm_sync = 38

# Parameters for isc_spb_prp_access_mode
#isc_spb_prp_am_readonly = 39
#isc_spb_prp_am_readwrite = 40

# Parameters for isc_action_svc_repair
#isc_spb_rpr_commit_trans = 15
#isc_spb_rpr_rollback_trans = 34
#isc_spb_rpr_recover_two_phase = 17
#isc_spb_tra_id = 18
#isc_spb_single_tra_id = 19
#isc_spb_multi_tra_id = 20
#isc_spb_tra_state = 21
#isc_spb_tra_state_limbo = 22
#isc_spb_tra_state_commit = 23
#isc_spb_tra_state_rollback = 24
#isc_spb_tra_state_unknown = 25
#isc_spb_tra_host_site = 26
#isc_spb_tra_remote_site = 27
#isc_spb_tra_db_path = 28
#isc_spb_tra_advise = 29
#isc_spb_tra_advise_commit = 30
#isc_spb_tra_advise_rollback = 31
#isc_spb_tra_advise_unknown = 33
## Added in Firebird 3.0
#isc_spb_tra_id_64 = 46
#isc_spb_single_tra_id_64 = 47
#isc_spb_multi_tra_id_64 = 48
#isc_spb_rpr_commit_trans_64 = 49
#isc_spb_rpr_rollback_trans_64 = 50
#isc_spb_rpr_recover_two_phase_64 = 51

#isc_spb_rpr_validate_db = 0x01
#isc_spb_rpr_sweep_db = 0x02
#isc_spb_rpr_mend_db = 0x04
#isc_spb_rpr_list_limbo_trans = 0x08
#isc_spb_rpr_check_db = 0x10
#isc_spb_rpr_ignore_checksum = 0x20
#isc_spb_rpr_kill_shadows = 0x40
#isc_spb_rpr_full = 0x80
#isc_spb_rpr_icu = 0x0800 # Firebird 3.0

# Parameters for isc_action_svc_restore
#isc_spb_res_skip_data = isc_spb_bkp_skip_data # Firebird 3.0
#isc_spb_res_buffers = 9
#isc_spb_res_page_size = 10
#isc_spb_res_length = 11
#isc_spb_res_access_mode = 12
#isc_spb_res_fix_fss_data = 13
#isc_spb_res_fix_fss_metadata = 14
#isc_spb_res_stat = 15 # Firebird 3.0
#isc_spb_res_metadata_only = 0x04
#isc_spb_res_deactivate_idx = 0x0100
#isc_spb_res_no_shadow = 0x0200
#isc_spb_res_no_validity = 0x0400
#isc_spb_res_one_at_a_time = 0x0800
#isc_spb_res_replace = 0x1000
#isc_spb_res_create = 0x2000
#isc_spb_res_use_all_space = 0x4000

# Parameters for isc_spb_res_access_mode
#isc_spb_res_am_readonly = isc_spb_prp_am_readonly
#isc_spb_res_am_readwrite = isc_spb_prp_am_readwrite

# Parameters for isc_info_svc_svr_db_info
#isc_spb_num_att = 5
#isc_spb_num_db = 6

#isc_spb_val_tab_incl = 1
#isc_spb_val_tab_excl = 2
#isc_spb_val_idx_incl = 3
#isc_spb_val_idx_excl = 4
#isc_spb_val_lock_timeout = 5

# Parameters for isc_info_svc_db_stats
#isc_spb_sts_table = 0x40
#isc_spb_sts_data_pages = 0x01
#isc_spb_sts_db_log = 0x02
#isc_spb_sts_hdr_pages = 0x04
#isc_spb_sts_idx_pages = 0x08
#isc_spb_sts_sys_relations = 0x10
#isc_spb_sts_record_versions = 0x20
#isc_spb_sts_nocreation = 0x80
#isc_spb_sts_encryption = 0x100 # Firebird 3.0

# Parameters for isc_action_svc_nbak
#isc_spb_nbk_level = 5
#isc_spb_nbk_file = 6
#isc_spb_nbk_direct = 7
#isc_spb_nbk_no_triggers = 0x01

# trace
#isc_spb_trc_id = 1
#isc_spb_trc_name = 2
#isc_spb_trc_cfg = 3

#  SDL
#isc_sdl_version1 = 1
#isc_sdl_eoc = 255
#isc_sdl_relation = 2
#isc_sdl_rid = 3
#isc_sdl_field = 4
#isc_sdl_fid = 5
#isc_sdl_struct = 6
#isc_sdl_variable = 7
#isc_sdl_scalar = 8
#isc_sdl_tiny_integer = 9
#isc_sdl_short_integer = 10
#isc_sdl_long_integer = 11
#isc_sdl_add = 13
#isc_sdl_subtract = 14
#isc_sdl_multiply = 15
#isc_sdl_divide = 16
#isc_sdl_negate = 17
#isc_sdl_begin = 31
#isc_sdl_end = 32
#isc_sdl_do3 = 33
#isc_sdl_do2 = 34
#isc_sdl_do1 = 35
#isc_sdl_element = 36

# Blob Subtypes
isc_blob_untyped = 0
# internal subtypes
isc_blob_text = 1
isc_blob_blr = 2
isc_blob_acl = 3
isc_blob_ranges = 4
isc_blob_summary = 5
isc_blob_format = 6
isc_blob_tra = 7
isc_blob_extfile = 8
isc_blob_debug_info = 9
isc_blob_max_predefined_subtype = 10

# Masks for fb_shutdown_callback
#fb_shut_confirmation = 1
#fb_shut_preproviders = 2
#fb_shut_postproviders = 4
#fb_shut_finish = 8
#fb_shut_exit = 16 # Firebird 3.0

# Cancel types for fb_cancel_operation
#fb_cancel_disable = 1
#fb_cancel_enable = 2
#fb_cancel_raise = 3
#fb_cancel_abort = 4

# Debug information items
#fb_dbg_version = 1
#fb_dbg_end = 255
#fb_dbg_map_src2blr = 2
#fb_dbg_map_varname = 3
#fb_dbg_map_argument = 4
## Firebird 3.0
#fb_dbg_subproc = 5
#fb_dbg_subfunc = 6
#fb_dbg_map_curname = 7

# sub code for fb_dbg_map_argument
#fb_dbg_arg_input = 0
#fb_dbg_arg_output = 1

#isc_facility		= 20;
#isc_err_base		= 335544320;
#isc_err_factor		= 1;
#isc_arg_end		= 0;	(* end of argument list *)
#isc_arg_gds		= 1;	(* generic DSRI status value *)
#isc_arg_string		= 2;	(* string argument *)
#isc_arg_cstring		= 3;	(* count & string argument *)
#isc_arg_number		= 4;	(* numeric argument (long) *)
#isc_arg_interpreted	= 5;	(* interpreted status code (string) *)
#isc_arg_vms		= 6;	(* VAX/VMS status code (long) *)
#isc_arg_unix		= 7;	(* UNIX error code *)
#isc_arg_domain		= 8;	(* Apollo/Domain error code *)
#isc_arg_dos		= 9;	(* MSDOS/OS2 error code *)

# Implementation codes
isc_info_db_impl_rdb_vms = 1
isc_info_db_impl_rdb_eln = 2
isc_info_db_impl_rdb_eln_dev = 3
isc_info_db_impl_rdb_vms_y = 4
isc_info_db_impl_rdb_eln_y = 5
isc_info_db_impl_jri = 6
isc_info_db_impl_jsv = 7
isc_info_db_impl_isc_apl_68K = 25
isc_info_db_impl_isc_vax_ultr = 26
isc_info_db_impl_isc_vms = 27
isc_info_db_impl_isc_sun_68k = 28
isc_info_db_impl_isc_os2 = 29
isc_info_db_impl_isc_sun4 = 30
isc_info_db_impl_isc_hp_ux = 31
isc_info_db_impl_isc_sun_386i = 32
isc_info_db_impl_isc_vms_orcl = 33
isc_info_db_impl_isc_mac_aux = 34
isc_info_db_impl_isc_rt_aix = 35
isc_info_db_impl_isc_mips_ult = 36
isc_info_db_impl_isc_xenix = 37
isc_info_db_impl_isc_dg = 38
isc_info_db_impl_isc_hp_mpexl = 39
isc_info_db_impl_isc_hp_ux68K = 40
isc_info_db_impl_isc_sgi = 41
isc_info_db_impl_isc_sco_unix = 42
isc_info_db_impl_isc_cray = 43
isc_info_db_impl_isc_imp = 44
isc_info_db_impl_isc_delta = 45
isc_info_db_impl_isc_next = 46
isc_info_db_impl_isc_dos = 47
isc_info_db_impl_m88K = 48
isc_info_db_impl_unixware = 49
isc_info_db_impl_isc_winnt_x86 = 50
isc_info_db_impl_isc_epson = 51
isc_info_db_impl_alpha_osf = 52
isc_info_db_impl_alpha_vms = 53
isc_info_db_impl_netware_386 = 54
isc_info_db_impl_win_only = 55
isc_info_db_impl_ncr_3000 = 56
isc_info_db_impl_winnt_ppc = 57
isc_info_db_impl_dg_x86 = 58
isc_info_db_impl_sco_ev = 59
isc_info_db_impl_i386 = 60
isc_info_db_impl_freebsd = 61
isc_info_db_impl_netbsd = 62
isc_info_db_impl_darwin_ppc = 63
isc_info_db_impl_sinixz = 64
isc_info_db_impl_linux_sparc = 65
isc_info_db_impl_linux_amd64 = 66
isc_info_db_impl_freebsd_amd64 = 67
isc_info_db_impl_winnt_amd64 = 68
isc_info_db_impl_linux_ppc = 69
isc_info_db_impl_darwin_x86 = 70
isc_info_db_impl_linux_mipsel = 71 # changed in 2.1, it was isc_info_db_impl_sun_amd64 in 2.0
# Added in FB 2.1
isc_info_db_impl_linux_mips = 72
isc_info_db_impl_darwin_x64 = 73
isc_info_db_impl_sun_amd64 = 74
isc_info_db_impl_linux_arm = 75
isc_info_db_impl_linux_ia64 = 76
isc_info_db_impl_darwin_ppc64 = 77
isc_info_db_impl_linux_s390x = 78
isc_info_db_impl_linux_s390 = 79
isc_info_db_impl_linux_sh = 80
isc_info_db_impl_linux_sheb = 81
# Added in FB 2.5
isc_info_db_impl_linux_hppa = 82
isc_info_db_impl_linux_alpha = 83
isc_info_db_impl_linux_arm64 = 84
isc_info_db_impl_linux_ppc64el = 85
isc_info_db_impl_linux_ppc64 = 86 # Firebird 3.0
isc_info_db_impl_last_value = (isc_info_db_impl_linux_ppc64 + 1)

# Info DB provider
isc_info_db_code_rdb_eln = 1
isc_info_db_code_rdb_vms = 2
isc_info_db_code_interbase = 3
isc_info_db_code_firebird = 4
isc_info_db_code_last_value = (isc_info_db_code_firebird+1)

# Info db class
isc_info_db_class_access = 1
isc_info_db_class_y_valve = 2
isc_info_db_class_rem_int = 3
isc_info_db_class_rem_srvr = 4
isc_info_db_class_pipe_int = 7
isc_info_db_class_pipe_srvr = 8
isc_info_db_class_sam_int = 9
isc_info_db_class_sam_srvr = 10
isc_info_db_class_gateway = 11
isc_info_db_class_cache = 12
isc_info_db_class_classic_access = 13
isc_info_db_class_server_access = 14
isc_info_db_class_last_value = (isc_info_db_class_server_access+1)

# Type codes

SQL_TEXT = 452
SQL_VARYING = 448
SQL_SHORT = 500
SQL_LONG = 496
SQL_FLOAT = 482
SQL_DOUBLE = 480
SQL_D_FLOAT = 530
SQL_TIMESTAMP = 510
SQL_BLOB = 520
SQL_ARRAY = 540
SQL_QUAD = 550
SQL_TYPE_TIME = 560
SQL_TYPE_DATE = 570
SQL_INT64 = 580
SQL_BOOLEAN = 32764 # Firebird 3
SQL_NULL = 32766

SUBTYPE_NUMERIC = 1
SUBTYPE_DECIMAL = 2

# Internal type codes (for example used by ARRAY descriptor)

blr_text = 14
blr_text2 = 15
blr_short = 7
blr_long = 8
blr_quad = 9
blr_float = 10
blr_double = 27
blr_d_float = 11
blr_timestamp = 35
blr_varying = 37
blr_varying2 = 38
blr_blob = 261
blr_cstring = 40
blr_cstring2 = 41
blr_blob_id = 45
blr_sql_date = 12
blr_sql_time = 13
blr_int64 = 16
blr_blob2 = 17
# Added in FB 2.1
blr_domain_name = 18
blr_domain_name2 = 19
blr_not_nullable = 20
# Added in FB 2.5
blr_column_name = 21
blr_column_name2 = 22
# Added in FB 3.0
blr_bool = 23
# Rest of BLR is defined in fdb.blr

# GDS code structure

ISC_MASK   = 0x14000000
FAC_MASK   = 0x00FF0000
CODE_MASK  = 0x0000FFFF
CLASS_MASK = 0xF0000000

def get_gds_facility(msg: int) -> int:
    return (msg & FAC_MASK) >> 16

def get_gds_class(msg: int) -> int:
    return (msg & CLASS_MASK) >> 30

def get_gds_code(msg: int) -> int:
    return (msg & CODE_MASK)

def is_gds_msg(msg: int) -> bool:
    return (msg & ISC_MASK) == ISC_MASK

if platform.architecture() == ('64bit', 'WindowsPE'):
    intptr_t = c.c_longlong
    uintptr_t = c.c_ulonglong
else:
    intptr_t = c.c_long
    uintptr_t = c.c_ulong

# Types

Int64 = c.c_long
Int64Ptr = c.POINTER(Int64)
QWord = c.c_ulong
STRING = c.c_char_p
ISC_DATE = c.c_int
ISC_TIME = c.c_uint
ISC_UCHAR = c.c_ubyte
ISC_SHORT = c.c_short
ISC_USHORT = c.c_ushort
ISC_LONG = c.c_int
ISC_LONG_PTR = c.POINTER(ISC_LONG)
ISC_ULONG = c.c_uint
ISC_INT64 = c.c_longlong
ISC_UINT64 = c.c_ulonglong

ISC_STATUS = intptr_t
ISC_STATUS_PTR = c.POINTER(ISC_STATUS)
ISC_STATUS_ARRAY = ISC_STATUS * 20
ISC_STATUS_ARRAY_PTR = c.POINTER(ISC_STATUS_ARRAY)
#StatusArray = ISC_STATUS * 40
#StatusArrayPtr = c.POINTER(StatusArray)
FB_API_HANDLE = c.c_uint
FB_API_HANDLE_PTR = c.POINTER(FB_API_HANDLE)

RESULT_VECTOR = ISC_ULONG * 15
ISC_EVENT_CALLBACK = c.CFUNCTYPE(None, c.POINTER(ISC_UCHAR), c.c_ushort, c.POINTER(ISC_UCHAR))

class ISC_QUAD(c.Structure):
    "Firebird QUAD structure"
ISC_QUAD._fields_ = [
    ('high', c.c_int),
    ('low', c.c_uint),
]
ISC_QUAD_PTR = c.POINTER(ISC_QUAD)

class ISC_ARRAY_BOUND(c.Structure):
    pass
ISC_ARRAY_BOUND._fields_ = [
    ('array_bound_lower', c.c_short),
    ('array_bound_upper', c.c_short),
]

class ISC_ARRAY_DESC(c.Structure):
    pass
ISC_ARRAY_DESC._fields_ = [
    ('array_desc_dtype', c.c_ubyte),
    ('array_desc_scale', c.c_ubyte), ## was ISC_SCHAR),
    ('array_desc_length', c.c_ushort),
    ('array_desc_field_name', c.c_char * 32),
    ('array_desc_relation_name', c.c_char * 32),
    ('array_desc_dimensions', c.c_short),
    ('array_desc_flags', c.c_short),
    ('array_desc_bounds', ISC_ARRAY_BOUND * 16),
]
ISC_ARRAY_DESC_PTR = c.POINTER(ISC_ARRAY_DESC)

class TraceCounts(c.Structure):
    "Trace counters for table"
TraceCounts._fields_ = [
    ('relation_id', c.c_int),
    ('relation_name', c.c_char_p),
    ('counters', Int64Ptr)
]
TraceCountsPtr = c.POINTER(TraceCounts)

class PerformanceInfo(c.Structure):
    "Performance info"
PerformanceInfo._fields_ = [
    ('time', c.c_long),
    ('counters', Int64Ptr),
    ('count', c.c_uint),
    ('tables', TraceCountsPtr),
    ('records_fetched', c.c_long)
]

class Dsc(c.Structure):
    "Field descriptor"
Dsc._fields_ = [
    ('dtype', c.c_byte),
    ('scale', c.c_byte),
    ('length', c.c_short),
    ('sub_type', c.c_short),
    ('flags', c.c_short),
    ('address', c.POINTER(c.c_byte))
]

BooleanPtr = c.POINTER(c.c_byte)
BytePtr = c.POINTER(c.c_char)
Cardinal = c.c_uint
CardinalPtr = c.POINTER(Cardinal)
ISC_QUADPtr = c.POINTER(ISC_QUAD)
NativeInt = intptr_t
NativeIntPtr = c.POINTER(NativeInt)
PerformanceInfoPtr = c.POINTER(PerformanceInfo)
dscPtr = c.POINTER(Dsc)
func_ptr = c.c_ulong

# ------------------------------------------------------------------------------
# Interface - Forward definitions
# ------------------------------------------------------------------------------
# IVersioned(1)
class IVersioned_VTable(c.Structure):
    "Interface virtual method table"
IVersioned_VTablePtr = c.POINTER(IVersioned_VTable)
class IVersioned_struct(c.Structure):
    "Fiebird Interface data structure"
IVersioned = c.POINTER(IVersioned_struct)
# IReferenceCounted(2)
class IReferenceCounted_VTable(c.Structure):
    "IReferenceCounted virtual method table"
IReferenceCounted_VTablePtr = c.POINTER(IReferenceCounted_VTable)
class IReferenceCounted_struct(c.Structure):
    "IReferenceCounted data structure"
IReferenceCounted = c.POINTER(IReferenceCounted_struct)
# IDisposable(2)
class IDisposable_VTable(c.Structure):
    "IDisposable virtual method table"
IDisposable_VTablePtr = c.POINTER(IDisposable_VTable)
class IDisposable_struct(c.Structure):
    "IDisposable data structure"
IDisposable = c.POINTER(IDisposable_struct)
# IStatus(3) : Disposable
class IStatus_VTable(c.Structure):
    "IStatus VTable"
IStatus_VTablePtr = c.POINTER(IStatus_VTable)
class IStatus_struct(c.Structure):
    "IStatus interface"
IStatus = c.POINTER(IStatus_struct)
# IMaster(2) : Versioned
class IMaster_VTable(c.Structure):
    "IMaster virtual method table"
IMaster_VTablePtr = c.POINTER(IMaster_VTable)
class IMaster_struct(c.Structure):
    "IMaster interface"
IMaster = c.POINTER(IMaster_struct)
# IPluginBase(3) : ReferenceCounted
class IPluginBase_VTable(c.Structure):
    "IPluginBase virtual method table"
IPluginBase_VTablePtr = c.POINTER(IPluginBase_VTable)
class IPluginBase_struct(c.Structure):
    "IPluginBase interface"
IPluginBase = c.POINTER(IPluginBase_struct)
# IPluginSet(3) : ReferenceCounted
class IPluginSet_VTable(c.Structure):
    "IPluginSet virtual method table"
IPluginSet_VTablePtr = c.POINTER(IPluginSet_VTable)
class IPluginSet_struct(c.Structure):
    "IPluginSet interface"
IPluginSet = c.POINTER(IPluginSet_struct)
# IConfigEntry(3) : ReferenceCounted
class IConfigEntry_VTable(c.Structure):
    "IConfigEntry virtual method table"
IConfigEntry_VTablePtr = c.POINTER(IConfigEntry_VTable)
class IConfigEntry_struct(c.Structure):
    "IConfigEntry interface"
IConfigEntry = c.POINTER(IConfigEntry_struct)
# IConfig(3) : ReferenceCounted
class IConfig_VTable(c.Structure):
    "IConfig virtual method table"
IConfig_VTablePtr = c.POINTER(IConfig_VTable)
class IConfig_struct(c.Structure):
    "IConfig interface"
IConfig = c.POINTER(IConfig_struct)
# IFirebirdConf(3) : ReferenceCounted
class IFirebirdConf_VTable(c.Structure):
    "IFirebirdConf virtual method table"
IFirebirdConf_VTablePtr = c.POINTER(IFirebirdConf_VTable)
class IFirebirdConf_struct(c.Structure):
    "IFirebirdConf interface"
IFirebirdConf = c.POINTER(IFirebirdConf_struct)
# IPluginConfig(3) : ReferenceCounted
class IPluginConfig_VTable(c.Structure):
    "IPluginConfig virtual method table"
IPluginConfig_VTablePtr = c.POINTER(IPluginConfig_VTable)
class IPluginConfig_struct(c.Structure):
    "IPluginConfig interface"
IPluginConfig = c.POINTER(IPluginConfig_struct)
# IPluginFactory(2) : Versioned
class IPluginFactory_VTable(c.Structure):
    "IPluginFactory virtual method table"
IPluginFactory_VTablePtr = c.POINTER(IPluginFactory_VTable)
class IPluginFactory_struct(c.Structure):
    "IPluginFactory interface"
IPluginFactory = c.POINTER(IPluginFactory_struct)
# IPluginModule(3) : Versioned
class IPluginModule_VTable(c.Structure):
    "IPluginModule virtual method table"
IPluginModule_VTablePtr = c.POINTER(IPluginModule_VTable)
class IPluginModule_struct(c.Structure):
    "IPluginModule interface"
IPluginModule = c.POINTER(IPluginModule_struct)
# IPluginManager(2) : Versioned
class IPluginManager_VTable(c.Structure):
    "IPluginManager virtual method table"
IPluginManager_VTablePtr = c.POINTER(IPluginManager_VTable)
class IPluginManager_struct(c.Structure):
    "IPluginManager interface"
IPluginManager = c.POINTER(IPluginManager_struct)
# ICryptKey(2) : Versioned
class ICryptKey_VTable(c.Structure):
    "ICryptKey virtual method table"
ICryptKey_VTablePtr = c.POINTER(ICryptKey_VTable)
class ICryptKey_struct(c.Structure):
    "ICryptKey interface"
ICryptKey = c.POINTER(ICryptKey_struct)
# IConfigManager(2) : Versioned
class IConfigManager_VTable(c.Structure):
    "IConfigManager virtual method table"
IConfigManager_VTablePtr = c.POINTER(IConfigManager_VTable)
class IConfigManager_struct(c.Structure):
    "IConfigManager interface"
IConfigManager = c.POINTER(IConfigManager_struct)
# IEventCallback(3) : ReferenceCounted
class IEventCallback_VTable(c.Structure):
    "IEventCallback virtual method table"
IEventCallback_VTablePtr = c.POINTER(IEventCallback_VTable)
class IEventCallback_struct(c.Structure):
    "IEventCallback interface"
IEventCallback = c.POINTER(IEventCallback_struct)
# IBlob(3) : ReferenceCounted
class IBlob_VTable(c.Structure):
    "IBlob virtual method table"
IBlob_VTablePtr = c.POINTER(IBlob_VTable)
class IBlob_struct(c.Structure):
    "IBlob interface"
IBlob = c.POINTER(IBlob_struct)
# ITransaction(3) : ReferenceCounted
class ITransaction_VTable(c.Structure):
    "ITransaction virtual method table"
ITransaction_VTablePtr = c.POINTER(ITransaction_VTable)
class ITransaction_struct(c.Structure):
    "ITransaction interface"
ITransaction = c.POINTER(ITransaction_struct)
# IMessageMetadata(3) : ReferenceCounted
class IMessageMetadata_VTable(c.Structure):
    "IMessageMetadata virtual method table"
IMessageMetadata_VTablePtr = c.POINTER(IMessageMetadata_VTable)
class IMessageMetadata_struct(c.Structure):
    "IMessageMetadata interface"
IMessageMetadata = c.POINTER(IMessageMetadata_struct)
# IMetadataBuilder(3) : ReferenceCounted
class IMetadataBuilder_VTable(c.Structure):
    "IMetadataBuilder virtual method table"
IMetadataBuilder_VTablePtr = c.POINTER(IMetadataBuilder_VTable)
class IMetadataBuilder_struct(c.Structure):
    "IMetadataBuilder interface"
IMetadataBuilder = c.POINTER(IMetadataBuilder_struct)
# IResultSet(3) : ReferenceCounted
class IResultSet_VTable(c.Structure):
    "IResultSet virtual method table"
IResultSet_VTablePtr = c.POINTER(IResultSet_VTable)
class IResultSet_struct(c.Structure):
    "IResultSet interface"
IResultSet = c.POINTER(IResultSet_struct)
# IStatement(3) : ReferenceCounted
class IStatement_VTable(c.Structure):
    "IStatement virtual method table"
IStatement_VTablePtr = c.POINTER(IStatement_VTable)
class IStatement_struct(c.Structure):
    "IStatement interface"
IStatement = c.POINTER(IStatement_struct)
# IRequest(3) : ReferenceCounted
class IRequest_VTable(c.Structure):
    "IRequest virtual method table"
IRequest_VTablePtr = c.POINTER(IRequest_VTable)
class IRequest_struct(c.Structure):
    "IRequest interface"
IRequest = c.POINTER(IRequest_struct)
# IEvents(3) : ReferenceCounted
class IEvents_VTable(c.Structure):
    "IEvents virtual method table"
IEvents_VTablePtr = c.POINTER(IEvents_VTable)
class IEvents_struct(c.Structure):
    "IEvents interface"
IEvents = c.POINTER(IEvents_struct)
# IAttachment(3) : ReferenceCounted
class IAttachment_VTable(c.Structure):
    "IAttachment virtual method table"
IAttachment_VTablePtr = c.POINTER(IAttachment_VTable)
class IAttachment_struct(c.Structure):
    "IAttachment interface"
IAttachment = c.POINTER(IAttachment_struct)
# IService(3) : ReferenceCounted
class IService_VTable(c.Structure):
    "IService virtual method table"
IService_VTablePtr = c.POINTER(IService_VTable)
class IService_struct(c.Structure):
    "IService interface"
IService = c.POINTER(IService_struct)
# IProvider(4) : PluginBase
class IProvider_VTable(c.Structure):
    "IProvider virtual method table"
IProvider_VTablePtr = c.POINTER(IProvider_VTable)
class IProvider_struct(c.Structure):
    "IProvider interface"
IProvider = c.POINTER(IProvider_struct)
# IDtcStart(3) : Disposable
class IDtcStart_VTable(c.Structure):
    "IDtcStart virtual method table"
IDtcStart_VTablePtr = c.POINTER(IDtcStart_VTable)
class IDtcStart_struct(c.Structure):
    "IDtcStart interface"
IDtcStart = c.POINTER(IDtcStart_struct)
# IDtc(2) : Versioned
class IDtc_VTable(c.Structure):
    "IDtc virtual method table"
IDtc_VTablePtr = c.POINTER(IDtc_VTable)
class IDtc_struct(c.Structure):
    "IDtc interface"
IDtc = c.POINTER(IDtc_struct)
# IAuth(4) : PluginBase
class IAuth_VTable(c.Structure):
    "IAuth virtual method table"
IAuth_VTablePtr = c.POINTER(IAuth_VTable)
class IAuth_struct(c.Structure):
    "IAuth interface"
IAuth = c.POINTER(IAuth_struct)
# IWriter(2) : Versioned
class IWriter_VTable(c.Structure):
    "IWriter virtual method table"
IWriter_VTablePtr = c.POINTER(IWriter_VTable)
class IWriter_struct(c.Structure):
    "IWriter interface"
IWriter = c.POINTER(IWriter_struct)
# IServerBlock(2) : Versioned
class IServerBlock_VTable(c.Structure):
    "IServerBlock virtual method table"
IServerBlock_VTablePtr = c.POINTER(IServerBlock_VTable)
class IServerBlock_struct(c.Structure):
    "IServerBlock interface"
IServerBlock = c.POINTER(IServerBlock_struct)
# IClientBlock(4) : ReferenceCounted
class IClientBlock_VTable(c.Structure):
    "IClientBlock virtual method table"
IClientBlock_VTablePtr = c.POINTER(IClientBlock_VTable)
class IClientBlock_struct(c.Structure):
    "IClientBlock interface"
IClientBlock = c.POINTER(IClientBlock_struct)
# IServer(6) : Auth
class IServer_VTable(c.Structure):
    "IServer virtual method table"
IServer_VTablePtr = c.POINTER(IServer_VTable)
class IServer_struct(c.Structure):
    "IServer interface"
IServer = c.POINTER(IServer_struct)
# IClient(5) : Auth
class IClient_VTable(c.Structure):
    "IClient virtual method table"
IClient_VTablePtr = c.POINTER(IClient_VTable)
class IClient_struct(c.Structure):
    "IClient interface"
IClient = c.POINTER(IClient_struct)
# IUserField(2) : Versioned
class IUserField_VTable(c.Structure):
    "IUserField virtual method table"
IUserField_VTablePtr = c.POINTER(IUserField_VTable)
class IUserField_struct(c.Structure):
    "IUserField interface"
IUserField = c.POINTER(IUserField_struct)
# ICharUserField(3) : IUserField
class ICharUserField_VTable(c.Structure):
    "ICharUserField virtual method table"
ICharUserField_VTablePtr = c.POINTER(ICharUserField_VTable)
class ICharUserField_struct(c.Structure):
    "ICharUserField interface"
ICharUserField = c.POINTER(ICharUserField_struct)
# IIntUserField(3) : IUserField
class IIntUserField_VTable(c.Structure):
    "IIntUserField virtual method table"
IIntUserField_VTablePtr = c.POINTER(IIntUserField_VTable)
class IIntUserField_struct(c.Structure):
    "IIntUserField interface"
IIntUserField = c.POINTER(IIntUserField_struct)
# IUser(2) : Versioned
class IUser_VTable(c.Structure):
    "IUser virtual method table"
IUser_VTablePtr = c.POINTER(IUser_VTable)
class IUser_struct(c.Structure):
    "IUser interface"
IUser = c.POINTER(IUser_struct)
# IListUsers(2) : Versioned
class IListUsers_VTable(c.Structure):
    "IListUsers virtual method table"
IListUsers_VTablePtr = c.POINTER(IListUsers_VTable)
class IListUsers_struct(c.Structure):
    "IListUsers interface"
IListUsers = c.POINTER(IListUsers_struct)
# ILogonInfo(2) : Versioned
class ILogonInfo_VTable(c.Structure):
    "ILogonInfo virtual method table"
ILogonInfo_VTablePtr = c.POINTER(ILogonInfo_VTable)
class ILogonInfo_struct(c.Structure):
    "ILogonInfo interface"
ILogonInfo = c.POINTER(ILogonInfo_struct)
# IManagement(4) : PluginBase
class IManagement_VTable(c.Structure):
    "IManagement virtual method table"
IManagement_VTablePtr = c.POINTER(IManagement_VTable)
class IManagement_struct(c.Structure):
    "IManagement interface"
IManagement = c.POINTER(IManagement_struct)
# IAuthBlock(2) : Versioned
class IAuthBlock_VTable(c.Structure):
    "IAuthBlock virtual method table"
IAuthBlock_VTablePtr = c.POINTER(IAuthBlock_VTable)
class IAuthBlock_struct(c.Structure):
    "IAuthBlock interface"
IAuthBlock = c.POINTER(IAuthBlock_struct)
# IWireCryptPlugin(4) : PluginBase
class IWireCryptPlugin_VTable(c.Structure):
    "IWireCryptPlugin virtual method table"
IWireCryptPlugin_VTablePtr = c.POINTER(IWireCryptPlugin_VTable)
class IWireCryptPlugin_struct(c.Structure):
    "IWireCryptPlugin interface"
IWireCryptPlugin = c.POINTER(IWireCryptPlugin_struct)
# ICryptKeyCallback(2) : Versioned
class ICryptKeyCallback_VTable(c.Structure):
    "ICryptKeyCallback virtual method table"
ICryptKeyCallback_VTablePtr = c.POINTER(ICryptKeyCallback_VTable)
class ICryptKeyCallback_struct(c.Structure):
    "ICryptKeyCallback interface"
ICryptKeyCallback = c.POINTER(ICryptKeyCallback_struct)
# IKeyHolderPlugin(5) : PluginBase
class IKeyHolderPlugin_VTable(c.Structure):
    "IKeyHolderPlugin virtual method table"
IKeyHolderPlugin_VTablePtr = c.POINTER(IKeyHolderPlugin_VTable)
class IKeyHolderPlugin_struct(c.Structure):
    "IKeyHolderPlugin interface"
IKeyHolderPlugin = c.POINTER(IKeyHolderPlugin_struct)
# IDbCryptInfo(3) : ReferenceCounted
class IDbCryptInfo_VTable(c.Structure):
    "IDbCryptInfo virtual method table"
IDbCryptInfo_VTablePtr = c.POINTER(IDbCryptInfo_VTable)
class IDbCryptInfo_struct(c.Structure):
    "IDbCryptInfo interface"
IDbCryptInfo = c.POINTER(IDbCryptInfo_struct)
# IDbCryptPlugin(5) : PluginBase
class IDbCryptPlugin_VTable(c.Structure):
    "IDbCryptPlugin virtual method table"
IDbCryptPlugin_VTablePtr = c.POINTER(IDbCryptPlugin_VTable)
class IDbCryptPlugin_struct(c.Structure):
    "IDbCryptPlugin interface"
IDbCryptPlugin = c.POINTER(IDbCryptPlugin_struct)
# IExternalContext(2) : Versioned
class IExternalContext_VTable(c.Structure):
    "IExternalContext virtual method table"
IExternalContext_VTablePtr = c.POINTER(IExternalContext_VTable)
class IExternalContext_struct(c.Structure):
    "IExternalContext interface"
IExternalContext = c.POINTER(IExternalContext_struct)
# IExternalResultSet(3) : Disposable
class IExternalResultSet_VTable(c.Structure):
    "IExternalResultSet virtual method table"
IExternalResultSet_VTablePtr = c.POINTER(IExternalResultSet_VTable)
class IExternalResultSet_struct(c.Structure):
    "IExternalResultSet interface"
IExternalResultSet = c.POINTER(IExternalResultSet_struct)
# IExternalFunction(3) : Disposable
class IExternalFunction_VTable(c.Structure):
    "IExternalFunction virtual method table"
IExternalFunction_VTablePtr = c.POINTER(IExternalFunction_VTable)
class IExternalFunction_struct(c.Structure):
    "IExternalFunction interface"
IExternalFunction = c.POINTER(IExternalFunction_struct)
# IExternalProcedure(3) : Disposable
class IExternalProcedure_VTable(c.Structure):
    "IExternalProcedure virtual method table"
IExternalProcedure_VTablePtr = c.POINTER(IExternalProcedure_VTable)
class IExternalProcedure_struct(c.Structure):
    "IExternalProcedure interface"
IExternalProcedure = c.POINTER(IExternalProcedure_struct)
# IExternalTrigger(3) : Disposable
class IExternalTrigger_VTable(c.Structure):
    "IExternalTrigger virtual method table"
IExternalTrigger_VTablePtr = c.POINTER(IExternalTrigger_VTable)
class IExternalTrigger_struct(c.Structure):
    "IExternalTrigger interface"
IExternalTrigger = c.POINTER(IExternalTrigger_struct)
# IRoutineMetadata(2) : Versioned
class IRoutineMetadata_VTable(c.Structure):
    "IRoutineMetadata virtual method table"
IRoutineMetadata_VTablePtr = c.POINTER(IRoutineMetadata_VTable)
class IRoutineMetadata_struct(c.Structure):
    "IRoutineMetadata interface"
IRoutineMetadata = c.POINTER(IRoutineMetadata_struct)
# IExternalEngine(4) : PluginBase
class IExternalEngine_VTable(c.Structure):
    "IExternalEngine virtual method table"
IExternalEngine_VTablePtr = c.POINTER(IExternalEngine_VTable)
class IExternalEngine_struct(c.Structure):
    "IExternalEngine interface"
IExternalEngine = c.POINTER(IExternalEngine_struct)
# ITimer(3) : ReferenceCounted
class ITimer_VTable(c.Structure):
    "ITimer virtual method table"
ITimer_VTablePtr = c.POINTER(ITimer_VTable)
class ITimer_struct(c.Structure):
    "ITimer interface"
ITimer = c.POINTER(ITimer_struct)
# ITimerControl(2) : Versioned
class ITimerControl_VTable(c.Structure):
    "ITimerControl virtual method table"
ITimerControl_VTablePtr = c.POINTER(ITimerControl_VTable)
class ITimerControl_struct(c.Structure):
    "ITimerControl interface"
ITimerControl = c.POINTER(ITimerControl_struct)
# IVersionCallback(2) : Versioned
class IVersionCallback_VTable(c.Structure):
    "IVersionCallback virtual method table"
IVersionCallback_VTablePtr = c.POINTER(IVersionCallback_VTable)
class IVersionCallback_struct(c.Structure):
    "IVersionCallback interface"
IVersionCallback = c.POINTER(IVersionCallback_struct)
# IUtil(2) : Versioned
class IUtil_VTable(c.Structure):
    "IUtil virtual method table"
IUtil_VTablePtr = c.POINTER(IUtil_VTable)
class IUtil_struct(c.Structure):
    "IUtil interface"
IUtil = c.POINTER(IUtil_struct)
# IOffsetsCallback(2) : Versioned
class IOffsetsCallback_VTable(c.Structure):
    "IOffsetsCallback virtual method table"
IOffsetsCallback_VTablePtr = c.POINTER(IOffsetsCallback_VTable)
class IOffsetsCallback_struct(c.Structure):
    "IOffsetsCallback interface"
IOffsetsCallback = c.POINTER(IOffsetsCallback_struct)
# IXpbBuilder(3) : Disposable
class IXpbBuilder_VTable(c.Structure):
    "IXpbBuilder virtual method table"
IXpbBuilder_VTablePtr = c.POINTER(IXpbBuilder_VTable)
class IXpbBuilder_struct(c.Structure):
    "IXpbBuilder interface"
IXpbBuilder = c.POINTER(IXpbBuilder_struct)
# ITraceConnection(2) : Versioned
class ITraceConnection_VTable(c.Structure):
    "ITraceConnection virtual method table"
ITraceConnection_VTablePtr = c.POINTER(ITraceConnection_VTable)
class ITraceConnection_struct(c.Structure):
    "ITraceConnection interface"
ITraceConnection = c.POINTER(ITraceConnection_struct)
# ITraceDatabaseConnection(3) : TraceConnection
class ITraceDatabaseConnection_VTable(c.Structure):
    "ITraceDatabaseConnection virtual method table"
ITraceDatabaseConnection_VTablePtr = c.POINTER(ITraceDatabaseConnection_VTable)
class ITraceDatabaseConnection_struct(c.Structure):
    "ITraceDatabaseConnection interface"
ITraceDatabaseConnection = c.POINTER(ITraceDatabaseConnection_struct)
# ITraceTransaction(3) : Versioned
class ITraceTransaction_VTable(c.Structure):
    "ITraceTransaction virtual method table"
ITraceTransaction_VTablePtr = c.POINTER(ITraceTransaction_VTable)
class ITraceTransaction_struct(c.Structure):
    "ITraceTransaction interface"
ITraceTransaction = c.POINTER(ITraceTransaction_struct)
# ITraceParams(3) : Versioned
class ITraceParams_VTable(c.Structure):
    "ITraceParams virtual method table"
ITraceParams_VTablePtr = c.POINTER(ITraceParams_VTable)
class ITraceParams_struct(c.Structure):
    "ITraceParams interface"
ITraceParams = c.POINTER(ITraceParams_struct)
# ITraceStatement(2) : Versioned
class ITraceStatement_VTable(c.Structure):
    "ITraceStatement virtual method table"
ITraceStatement_VTablePtr = c.POINTER(ITraceStatement_VTable)
class ITraceStatement_struct(c.Structure):
    "ITraceStatement interface"
ITraceStatement = c.POINTER(ITraceStatement_struct)
# ITraceSQLStatement(3) : TraceStatement
class ITraceSQLStatement_VTable(c.Structure):
    "ITraceSQLStatement virtual method table"
ITraceSQLStatement_VTablePtr = c.POINTER(ITraceSQLStatement_VTable)
class ITraceSQLStatement_struct(c.Structure):
    "ITraceSQLStatement interface"
ITraceSQLStatement = c.POINTER(ITraceSQLStatement_struct)
# ITraceBLRStatement(3) : TraceStatement
class ITraceBLRStatement_VTable(c.Structure):
    "ITraceBLRStatement virtual method table"
ITraceBLRStatement_VTablePtr = c.POINTER(ITraceBLRStatement_VTable)
class ITraceBLRStatement_struct(c.Structure):
    "ITraceBLRStatement interface"
ITraceBLRStatement = c.POINTER(ITraceBLRStatement_struct)
# ITraceDYNRequest(2) : Versioned
class ITraceDYNRequest_VTable(c.Structure):
    "ITraceDYNRequest virtual method table"
ITraceDYNRequest_VTablePtr = c.POINTER(ITraceDYNRequest_VTable)
class ITraceDYNRequest_struct(c.Structure):
    "ITraceDYNRequest interface"
ITraceDYNRequest = c.POINTER(ITraceDYNRequest_struct)
# ITraceContextVariable(2) : Versioned
class ITraceContextVariable_VTable(c.Structure):
    "ITraceContextVariable virtual method table"
ITraceContextVariable_VTablePtr = c.POINTER(ITraceContextVariable_VTable)
class ITraceContextVariable_struct(c.Structure):
    "ITraceContextVariable interface"
ITraceContextVariable = c.POINTER(ITraceContextVariable_struct)
# ITraceProcedure(2) : Versioned
class ITraceProcedure_VTable(c.Structure):
    "ITraceProcedure virtual method table"
ITraceProcedure_VTablePtr = c.POINTER(ITraceProcedure_VTable)
class ITraceProcedure_struct(c.Structure):
    "ITraceProcedure interface"
ITraceProcedure = c.POINTER(ITraceProcedure_struct)
# ITraceFunction(2) : Versioned
class ITraceFunction_VTable(c.Structure):
    "ITraceFunction virtual method table"
ITraceFunction_VTablePtr = c.POINTER(ITraceFunction_VTable)
class ITraceFunction_struct(c.Structure):
    "ITraceFunction interface"
ITraceFunction = c.POINTER(ITraceFunction_struct)
# ITraceTrigger(2) : Versioned
class ITraceTrigger_VTable(c.Structure):
    "ITraceTrigger virtual method table"
ITraceTrigger_VTablePtr = c.POINTER(ITraceTrigger_VTable)
class ITraceTrigger_struct(c.Structure):
    "ITraceTrigger interface"
ITraceTrigger = c.POINTER(ITraceTrigger_struct)
# ITraceServiceConnection(3) : TraceConnection
class ITraceServiceConnection_VTable(c.Structure):
    "ITraceServiceConnection virtual method table"
ITraceServiceConnection_VTablePtr = c.POINTER(ITraceServiceConnection_VTable)
class ITraceServiceConnection_struct(c.Structure):
    "ITraceServiceConnection interface"
ITraceServiceConnection = c.POINTER(ITraceServiceConnection_struct)
# ITraceStatusVector(2) : Versioned
class ITraceStatusVector_VTable(c.Structure):
    "ITraceStatusVector virtual method table"
ITraceStatusVector_VTablePtr = c.POINTER(ITraceStatusVector_VTable)
class ITraceStatusVector_struct(c.Structure):
    "ITraceStatusVector interface"
ITraceStatusVector = c.POINTER(ITraceStatusVector_struct)
# ITraceSweepInfo(2) : Versioned
class ITraceSweepInfo_VTable(c.Structure):
    "ITraceSweepInfo virtual method table"
ITraceSweepInfo_VTablePtr = c.POINTER(ITraceSweepInfo_VTable)
class ITraceSweepInfo_struct(c.Structure):
    "ITraceSweepInfo interface"
ITraceSweepInfo = c.POINTER(ITraceSweepInfo_struct)
# ITraceLogWriter(4) : ReferenceCounted
class ITraceLogWriter_VTable(c.Structure):
    "ITraceLogWriter virtual method table"
ITraceLogWriter_VTablePtr = c.POINTER(ITraceLogWriter_VTable)
class ITraceLogWriter_struct(c.Structure):
    "ITraceLogWriter interface"
ITraceLogWriter = c.POINTER(ITraceLogWriter_struct)
# ITraceInitInfo(2) : Versioned
class ITraceInitInfo_VTable(c.Structure):
    "ITraceInitInfo virtual method table"
ITraceInitInfo_VTablePtr = c.POINTER(ITraceInitInfo_VTable)
class ITraceInitInfo_struct(c.Structure):
    "ITraceInitInfo interface"
ITraceInitInfo = c.POINTER(ITraceInitInfo_struct)
# ITracePlugin(3) : ReferenceCounted
class ITracePlugin_VTable(c.Structure):
    "ITracePlugin virtual method table"
ITracePlugin_VTablePtr = c.POINTER(ITracePlugin_VTable)
class ITracePlugin_struct(c.Structure):
    "ITracePlugin interface"
ITracePlugin = c.POINTER(ITracePlugin_struct)
# ITraceFactory(4) : PluginBase
class ITraceFactory_VTable(c.Structure):
    "ITraceFactory virtual method table"
ITraceFactory_VTablePtr = c.POINTER(ITraceFactory_VTable)
class ITraceFactory_struct(c.Structure):
    "ITraceFactory interface"
ITraceFactory = c.POINTER(ITraceFactory_struct)
# IUdrFunctionFactory(3) : Disposable
class IUdrFunctionFactory_VTable(c.Structure):
    "IUdrFunctionFactory virtual method table"
IUdrFunctionFactory_VTablePtr = c.POINTER(IUdrFunctionFactory_VTable)
class IUdrFunctionFactory_struct(c.Structure):
    "IUdrFunctionFactory interface"
IUdrFunctionFactory = c.POINTER(IUdrFunctionFactory_struct)
# IUdrProcedureFactory(3) : Disposable
class IUdrProcedureFactory_VTable(c.Structure):
    "IUdrProcedureFactory virtual method table"
IUdrProcedureFactory_VTablePtr = c.POINTER(IUdrProcedureFactory_VTable)
class IUdrProcedureFactory_struct(c.Structure):
    "IUdrProcedureFactory interface"
IUdrProcedureFactory = c.POINTER(IUdrProcedureFactory_struct)
# IUdrTriggerFactory(3) : Disposable
class IUdrTriggerFactory_VTable(c.Structure):
    "IUdrTriggerFactory virtual method table"
IUdrTriggerFactory_VTablePtr = c.POINTER(IUdrTriggerFactory_VTable)
class IUdrTriggerFactory_struct(c.Structure):
    "IUdrTriggerFactory interface"
IUdrTriggerFactory = c.POINTER(IUdrTriggerFactory_struct)
# IUdrPlugin(2) : Versioned
class IUdrPlugin_VTable(c.Structure):
    "IUdrPlugin virtual method table"
IUdrPlugin_VTablePtr = c.POINTER(IUdrPlugin_VTable)
class IUdrPlugin_struct(c.Structure):
    "IUdrPlugin interface"
IUdrPlugin = c.POINTER(IUdrPlugin_struct)
# ====================
# Interfaces - Methods
# ====================
#
# IReferenceCounted(2)
# --------------------
# procedure addRef(this: IReferenceCounted)
IReferenceCounted_addRef = c.CFUNCTYPE(None, IReferenceCounted)
# function release(this: IReferenceCounted): Integer
IReferenceCounted_release = c.CFUNCTYPE(c.c_int, IReferenceCounted)
#
# IDisposable(2)
# --------------
# procedure dispose(this: IDisposable)
IDisposable_dispose = c.CFUNCTYPE(None, IDisposable)
#
# IStatus(3) : Disposable
# -----------------------
# procedure init(this: IStatus)
IStatus_init = c.CFUNCTYPE(None, IStatus)
# function getState(this: IStatus): Cardinal
IStatus_getState = c.CFUNCTYPE(Cardinal, IStatus)
# procedure setErrors2(this: IStatus; length: Cardinal; value: NativeIntPtr)
IStatus_setErrors2 = c.CFUNCTYPE(None, IStatus, Cardinal, NativeIntPtr)
# procedure setWarnings2(this: IStatus; length: Cardinal; value: NativeIntPtr)
IStatus_setWarnings2 = c.CFUNCTYPE(None, IStatus, Cardinal, NativeIntPtr)
# procedure setErrors(this: IStatus; value: NativeIntPtr)
IStatus_setErrors = c.CFUNCTYPE(None, IStatus, NativeIntPtr)
# procedure setWarnings(this: IStatus; value: NativeIntPtr)
IStatus_setWarnings = c.CFUNCTYPE(None, IStatus, NativeIntPtr)
# function getErrors(this: IStatus): NativeIntPtr
IStatus_getErrors = c.CFUNCTYPE(NativeIntPtr, IStatus)
# function getWarnings(this: IStatus): NativeIntPtr
IStatus_getWarnings = c.CFUNCTYPE(NativeIntPtr, IStatus)
# function clone(this: IStatus): IStatus
IStatus_clone = c.CFUNCTYPE(IStatus, IStatus)
#
# IMaster(2) : Versioned
# ----------------------
# function getStatus(this: IMaster): IStatus
IMaster_getStatus = c.CFUNCTYPE(IStatus, IMaster)
# function getDispatcher(this: IMaster): IProvider
IMaster_getDispatcher = c.CFUNCTYPE(IProvider, IMaster)
# function getPluginManager(this: IMaster): IPluginManager
IMaster_getPluginManager = c.CFUNCTYPE(IPluginManager, IMaster)
# function getTimerControl(this: IMaster): ITimerControl
IMaster_getTimerControl = c.CFUNCTYPE(ITimerControl, IMaster)
# function getDtc(this: IMaster): IDtc
IMaster_getDtc = c.CFUNCTYPE(IDtc, IMaster)
# function registerAttachment(this: IMaster; provider: IProvider; attachment: IAttachment): IAttachment
IMaster_registerAttachment = c.CFUNCTYPE(IAttachment, IMaster, IProvider, IAttachment)
# function registerTransaction(this: IMaster; attachment: IAttachment; transaction: ITransaction): ITransaction
IMaster_registerTransaction = c.CFUNCTYPE(ITransaction, IMaster, IAttachment, ITransaction)
# function getMetadataBuilder(this: IMaster; status: IStatus; fieldCount: Cardinal): IMetadataBuilder
IMaster_getMetadataBuilder = c.CFUNCTYPE(IMetadataBuilder, IMaster, IStatus, c.c_uint)
# function serverMode(this: IMaster; mode: Integer): Integer
IMaster_serverMode = c.CFUNCTYPE(c.c_int, IMaster, c.c_int)
# function getUtilInterface(this: IMaster): IUtil
IMaster_getUtilInterface = c.CFUNCTYPE(IUtil, IMaster)
# function getConfigManager(this: IMaster): IConfigManager
IMaster_getConfigManager = c.CFUNCTYPE(IConfigManager, IMaster)
# function getProcessExiting(this: IMaster): Boolean
IMaster_getProcessExiting = c.CFUNCTYPE(c.c_bool, IMaster)
#
# IPluginBase(3) : ReferenceCounted
# ---------------------------------
# procedure setOwner(this: IPluginBase; r: IReferenceCounted)
IPluginBase_setOwner = c.CFUNCTYPE(None, IPluginBase, IReferenceCounted)
# function getOwner(this: IPluginBase): IReferenceCounted
IPluginBase_getOwner = c.CFUNCTYPE(IReferenceCounted, IPluginBase)
#
# IConfigEntry(3) : ReferenceCounted
# ----------------------------------
# function getName(this: IConfigEntry): PAnsiChar
IConfigEntry_getName = c.CFUNCTYPE(c.c_char_p, IConfigEntry)
# function getValue(this: IConfigEntry): PAnsiChar
IConfigEntry_getValue = c.CFUNCTYPE(c.c_char_p, IConfigEntry)
# function getIntValue(this: IConfigEntry): Int64
IConfigEntry_getIntValue = c.CFUNCTYPE(Int64, IConfigEntry)
# function getBoolValue(this: IConfigEntry): Boolean
IConfigEntry_getBoolValue = c.CFUNCTYPE(c.c_bool, IConfigEntry)
# function getSubConfig(this: IConfigEntry; status: IStatus): IConfig
IConfigEntry_getSubConfig = c.CFUNCTYPE(IConfig, IConfigEntry, IStatus)
#
# IConfig(3) : ReferenceCounted
# -----------------------------
# function find(this: IConfig; status: IStatus; name: PAnsiChar): IConfigEntry
IConfig_find = c.CFUNCTYPE(IConfigEntry, IConfig, IStatus, c.c_char_p)
# function findValue(this: IConfig; status: IStatus; name: PAnsiChar; value: PAnsiChar): IConfigEntry
IConfig_findValue = c.CFUNCTYPE(IConfigEntry, IConfig, IStatus, c.c_char_p, c.c_char_p)
# function findPos(this: IConfig; status: IStatus; name: PAnsiChar; pos: Cardinal): IConfigEntry
IConfig_findPos = c.CFUNCTYPE(IConfigEntry, IConfig, IStatus, c.c_char_p, Cardinal)
#
# IFirebirdConf(3) : ReferenceCounted
# -----------------------------------
# function getKey(this: IFirebirdConf; name: PAnsiChar): Cardinal
IFirebirdConf_getKey = c.CFUNCTYPE(Cardinal, IFirebirdConf, c.c_char_p)
# function asInteger(this: IFirebirdConf; key: Cardinal): Int64
IFirebirdConf_asInteger = c.CFUNCTYPE(Int64, IFirebirdConf, Cardinal)
# function asString(this: IFirebirdConf; key: Cardinal): PAnsiChar
IFirebirdConf_asString = c.CFUNCTYPE(c.c_char_p, IFirebirdConf, Cardinal)
# function asBoolean(this: IFirebirdConf; key: Cardinal): Boolean
IFirebirdConf_asBoolean = c.CFUNCTYPE(c.c_bool, IFirebirdConf, Cardinal)
#
# IConfigManager(2) : Versioned
# -----------------------------
# function getDirectory(this: IConfigManager; code: Cardinal): PAnsiChar
IConfigManager_getDirectory = c.CFUNCTYPE(c.c_char_p, IConfigManager, Cardinal)
# function getFirebirdConf(this: IConfigManager): IFirebirdConf
IConfigManager_getFirebirdConf = c.CFUNCTYPE(IFirebirdConf, IConfigManager)
# function getDatabaseConf(this: IConfigManager; dbName: PAnsiChar): IFirebirdConf
IConfigManager_getDatabaseConf = c.CFUNCTYPE(IFirebirdConf, IConfigManager, c.c_char_p)
# function getPluginConfig(this: IConfigManager; configuredPlugin: PAnsiChar): IConfig
IConfigManager_getPluginConfig = c.CFUNCTYPE(IConfig, IConfigManager, c.c_char_p)
# function getInstallDirectory(this: IConfigManager): PAnsiChar
IConfigManager_getInstallDirectory = c.CFUNCTYPE(c.c_char_p, IConfigManager)
# function getRootDirectory(this: IConfigManager): PAnsiChar
IConfigManager_getRootDirectory = c.CFUNCTYPE(c.c_char_p, IConfigManager)
#
# IEventCallback(3) : ReferenceCounted
# ------------------------------------
# procedure eventCallbackFunction(this: IEventCallback; length: Cardinal; events: BytePtr)
IEventCallback_eventCallbackFunction = c.CFUNCTYPE(None, IEventCallback, Cardinal, BytePtr)
#
# IBlob(3) : ReferenceCounted
# ---------------------------
# procedure getInfo(this: IBlob; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IBlob_getInfo = c.CFUNCTYPE(None, IBlob, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# function getSegment(this: IBlob; status: IStatus; bufferLength: Cardinal; buffer: Pointer; segmentLength: CardinalPtr): Integer
IBlob_getSegment = c.CFUNCTYPE(c.c_int, IBlob, IStatus, Cardinal, c.c_void_p, CardinalPtr)
# procedure putSegment(this: IBlob; status: IStatus; length: Cardinal; buffer: Pointer)
IBlob_putSegment = c.CFUNCTYPE(None, IBlob, IStatus, Cardinal, c.c_void_p)
# procedure cancel(this: IBlob; status: IStatus)
IBlob_cancel = c.CFUNCTYPE(None, IBlob, IStatus)
# procedure close(this: IBlob; status: IStatus)
IBlob_close = c.CFUNCTYPE(None, IBlob, IStatus)
# function seek(this: IBlob; status: IStatus; mode: Integer; offset: Integer): Integer
IBlob_seek = c.CFUNCTYPE(c.c_int, IBlob, IStatus, c.c_int, c.c_int)
#
# ITransaction(3) : ReferenceCounted
# ----------------------------------
# procedure getInfo(this: ITransaction; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
ITransaction_getInfo = c.CFUNCTYPE(None, ITransaction, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# procedure prepare(this: ITransaction; status: IStatus; msgLength: Cardinal; message: BytePtr)
ITransaction_prepare = c.CFUNCTYPE(None, ITransaction, IStatus, Cardinal, BytePtr)
# procedure commit(this: ITransaction; status: IStatus)
ITransaction_commit = c.CFUNCTYPE(None, ITransaction, IStatus)
# procedure commitRetaining(this: ITransaction; status: IStatus)
ITransaction_commitRetaining = c.CFUNCTYPE(None, ITransaction, IStatus)
# procedure rollback(this: ITransaction; status: IStatus)
ITransaction_rollback = c.CFUNCTYPE(None, ITransaction, IStatus)
# procedure rollbackRetaining(this: ITransaction; status: IStatus)
ITransaction_rollbackRetaining = c.CFUNCTYPE(None, ITransaction, IStatus)
# procedure disconnect(this: ITransaction; status: IStatus)
ITransaction_disconnect = c.CFUNCTYPE(None, ITransaction, IStatus)
# function join(this: ITransaction; status: IStatus; transaction: ITransaction): ITransaction
ITransaction_join = c.CFUNCTYPE(ITransaction, ITransaction, IStatus, ITransaction)
# function validate(this: ITransaction; status: IStatus; attachment: IAttachment): ITransaction
ITransaction_validate = c.CFUNCTYPE(ITransaction, ITransaction, IStatus, IAttachment)
# function enterDtc(this: ITransaction; status: IStatus): ITransaction
ITransaction_enterDtc = c.CFUNCTYPE(ITransaction, ITransaction, IStatus)
#
# IMessageMetadata(3) : ReferenceCounted
# --------------------------------------
# function getCount(this: IMessageMetadata; status: IStatus): Cardinal
IMessageMetadata_getCount = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus)
# function getField(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getField = c.CFUNCTYPE(c.c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getRelation(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getRelation = c.CFUNCTYPE(c.c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getOwner(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getOwner = c.CFUNCTYPE(c.c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getAlias(this: IMessageMetadata; status: IStatus; index: Cardinal): PAnsiChar
IMessageMetadata_getAlias = c.CFUNCTYPE(c.c_char_p, IMessageMetadata, IStatus, Cardinal)
# function getType(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getType = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function isNullable(this: IMessageMetadata; status: IStatus; index: Cardinal): Boolean
IMessageMetadata_isNullable = c.CFUNCTYPE(c.c_bool, IMessageMetadata, IStatus, Cardinal)
# function getSubType(this: IMessageMetadata; status: IStatus; index: Cardinal): Integer
IMessageMetadata_getSubType = c.CFUNCTYPE(c.c_int, IMessageMetadata, IStatus, Cardinal)
# function getLength(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getLength = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getScale(this: IMessageMetadata; status: IStatus; index: Cardinal): Integer
IMessageMetadata_getScale = c.CFUNCTYPE(c.c_int, IMessageMetadata, IStatus, Cardinal)
# function getCharSet(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getCharSet = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getOffset(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getOffset = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getNullOffset(this: IMessageMetadata; status: IStatus; index: Cardinal): Cardinal
IMessageMetadata_getNullOffset = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus, Cardinal)
# function getBuilder(this: IMessageMetadata; status: IStatus): IMetadataBuilder
IMessageMetadata_getBuilder = c.CFUNCTYPE(IMetadataBuilder, IMessageMetadata, IStatus)
# function getMessageLength(this: IMessageMetadata; status: IStatus): Cardinal
IMessageMetadata_getMessageLength = c.CFUNCTYPE(Cardinal, IMessageMetadata, IStatus)
#
# IMetadataBuilder(3) : ReferenceCounted
# --------------------------------------
# procedure setType(this: IMetadataBuilder; status: IStatus; index: Cardinal; type_: Cardinal)
IMetadataBuilder_setType = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, Cardinal)
# procedure setSubType(this: IMetadataBuilder; status: IStatus; index: Cardinal; subType: Integer)
IMetadataBuilder_setSubType = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c.c_int)
# procedure setLength(this: IMetadataBuilder; status: IStatus; index: Cardinal; length: Cardinal)
IMetadataBuilder_setLength = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, Cardinal)
# procedure setCharSet(this: IMetadataBuilder; status: IStatus; index: Cardinal; charSet: Cardinal)
IMetadataBuilder_setCharSet = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, Cardinal)
# procedure setScale(this: IMetadataBuilder; status: IStatus; index: Cardinal; scale: Integer)
IMetadataBuilder_setScale = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal, c.c_int)
# procedure truncate(this: IMetadataBuilder; status: IStatus; count: Cardinal)
IMetadataBuilder_truncate = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal)
# procedure moveNameToIndex(this: IMetadataBuilder; status: IStatus; name: PAnsiChar; index: Cardinal)
IMetadataBuilder_moveNameToIndex = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, c.c_char_p, Cardinal)
# procedure remove(this: IMetadataBuilder; status: IStatus; index: Cardinal)
IMetadataBuilder_remove = c.CFUNCTYPE(None, IMetadataBuilder, IStatus, Cardinal)
# function addField(this: IMetadataBuilder; status: IStatus): Cardinal
IMetadataBuilder_addField = c.CFUNCTYPE(Cardinal, IMetadataBuilder, IStatus)
# function getMetadata(this: IMetadataBuilder; status: IStatus): IMessageMetadata
IMetadataBuilder_getMetadata = c.CFUNCTYPE(IMessageMetadata, IMetadataBuilder, IStatus)
#
# IResultSet(3) : ReferenceCounted
# --------------------------------
# function fetchNext(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchNext = c.CFUNCTYPE(c.c_int, IResultSet, IStatus, c.c_void_p)
# function fetchPrior(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchPrior = c.CFUNCTYPE(c.c_int, IResultSet, IStatus, c.c_void_p)
# function fetchFirst(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchFirst = c.CFUNCTYPE(c.c_int, IResultSet, IStatus, c.c_void_p)
# function fetchLast(this: IResultSet; status: IStatus; message: Pointer): Integer
IResultSet_fetchLast = c.CFUNCTYPE(c.c_int, IResultSet, IStatus, c.c_void_p)
# function fetchAbsolute(this: IResultSet; status: IStatus; position: Integer; message: Pointer): Integer
IResultSet_fetchAbsolute = c.CFUNCTYPE(c.c_int, IResultSet, IStatus, c.c_int, c.c_void_p)
# function fetchRelative(this: IResultSet; status: IStatus; offset: Integer; message: Pointer): Integer
IResultSet_fetchRelative = c.CFUNCTYPE(c.c_int, IResultSet, IStatus, c.c_int, c.c_void_p)
# function isEof(this: IResultSet; status: IStatus): Boolean
IResultSet_isEof = c.CFUNCTYPE(c.c_bool, IResultSet, IStatus)
# function isBof(this: IResultSet; status: IStatus): Boolean
IResultSet_isBof = c.CFUNCTYPE(c.c_bool, IResultSet, IStatus)
# function getMetadata(this: IResultSet; status: IStatus): IMessageMetadata
IResultSet_getMetadata = c.CFUNCTYPE(IMessageMetadata, IResultSet, IStatus)
# procedure close(this: IResultSet; status: IStatus)
IResultSet_close = c.CFUNCTYPE(None, IResultSet, IStatus)
# procedure setDelayedOutputFormat(this: IResultSet; status: IStatus; format: IMessageMetadata)
IResultSet_setDelayedOutputFormat = c.CFUNCTYPE(None, IResultSet, IStatus, IMessageMetadata)
#
# IStatement(3) : ReferenceCounted
# --------------------------------
# procedure getInfo(this: IStatement; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IStatement_getInfo = c.CFUNCTYPE(None, IStatement, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# function getType(this: IStatement; status: IStatus): Cardinal
IStatement_getType = c.CFUNCTYPE(Cardinal, IStatement, IStatus)
# function getPlan(this: IStatement; status: IStatus; detailed: Boolean): PAnsiChar
IStatement_getPlan = c.CFUNCTYPE(c.c_char_p, IStatement, IStatus, c.c_bool)
# function getAffectedRecords(this: IStatement; status: IStatus): QWord
IStatement_getAffectedRecords = c.CFUNCTYPE(QWord, IStatement, IStatus)
# function getInputMetadata(this: IStatement; status: IStatus): IMessageMetadata
IStatement_getInputMetadata = c.CFUNCTYPE(IMessageMetadata, IStatement, IStatus)
# function getOutputMetadata(this: IStatement; status: IStatus): IMessageMetadata
IStatement_getOutputMetadata = c.CFUNCTYPE(IMessageMetadata, IStatement, IStatus)
# function execute(this: IStatement; status: IStatus; transaction: ITransaction; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; outBuffer: Pointer): ITransaction
IStatement_execute = c.CFUNCTYPE(ITransaction, IStatement, IStatus, ITransaction, IMessageMetadata, c.c_void_p, IMessageMetadata, c.c_void_p)
# function openCursor(this: IStatement; status: IStatus; transaction: ITransaction; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; flags: Cardinal): IResultSet
IStatement_openCursor = c.CFUNCTYPE(IResultSet, IStatement, IStatus, ITransaction, IMessageMetadata, c.c_void_p, IMessageMetadata, Cardinal)
# procedure setCursorName(this: IStatement; status: IStatus; name: PAnsiChar)
IStatement_setCursorName = c.CFUNCTYPE(None, IStatement, IStatus, c.c_char_p)
# procedure free(this: IStatement; status: IStatus)
IStatement_free = c.CFUNCTYPE(None, IStatement, IStatus)
# function getFlags(this: IStatement; status: IStatus): Cardinal
IStatement_getFlags = c.CFUNCTYPE(Cardinal, IStatement, IStatus)
#
# IRequest(3) : ReferenceCounted
# ------------------------------
# procedure receive(this: IRequest; status: IStatus; level: Integer; msgType: Cardinal; length: Cardinal; message: BytePtr)
IRequest_receive = c.CFUNCTYPE(None, IRequest, IStatus, c.c_int, Cardinal, Cardinal, BytePtr)
# procedure send(this: IRequest; status: IStatus; level: Integer; msgType: Cardinal; length: Cardinal; message: BytePtr)
IRequest_send = c.CFUNCTYPE(None, IRequest, IStatus, c.c_int, Cardinal, Cardinal, BytePtr)
# procedure getInfo(this: IRequest; status: IStatus; level: Integer; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IRequest_getInfo = c.CFUNCTYPE(None, IRequest, IStatus, c.c_int, Cardinal, BytePtr, Cardinal, BytePtr)
# procedure start(this: IRequest; status: IStatus; tra: ITransaction; level: Integer)
IRequest_start = c.CFUNCTYPE(None, IRequest, IStatus, ITransaction, c.c_int)
# procedure startAndSend(this: IRequest; status: IStatus; tra: ITransaction; level: Integer; msgType: Cardinal; length: Cardinal; message: BytePtr)
IRequest_startAndSend = c.CFUNCTYPE(None, IRequest, IStatus, ITransaction, c.c_int, Cardinal, Cardinal, BytePtr)
# procedure unwind(this: IRequest; status: IStatus; level: Integer)
IRequest_unwind = c.CFUNCTYPE(None, IRequest, IStatus, c.c_int)
# procedure free(this: IRequest; status: IStatus)
IRequest_free = c.CFUNCTYPE(None, IRequest, IStatus)
#
# IEvents(3) : ReferenceCounted
# -----------------------------
# procedure cancel(this: IEvents; status: IStatus)
IEvents_cancel = c.CFUNCTYPE(None, IEvents, IStatus)
#
# IAttachment(3) : ReferenceCounted
# ---------------------------------
# procedure getInfo(this: IAttachment; status: IStatus; itemsLength: Cardinal; items: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IAttachment_getInfo = c.CFUNCTYPE(None, IAttachment, IStatus, Cardinal, BytePtr, Cardinal, BytePtr)
# function startTransaction(this: IAttachment; status: IStatus; tpbLength: Cardinal; tpb: BytePtr): ITransaction
IAttachment_startTransaction = c.CFUNCTYPE(ITransaction, IAttachment, IStatus, Cardinal, BytePtr)
# function reconnectTransaction(this: IAttachment; status: IStatus; length: Cardinal; id: BytePtr): ITransaction
IAttachment_reconnectTransaction = c.CFUNCTYPE(ITransaction, IAttachment, IStatus, Cardinal, BytePtr)
# function compileRequest(this: IAttachment; status: IStatus; blrLength: Cardinal; blr: BytePtr): IRequest
IAttachment_compileRequest = c.CFUNCTYPE(IRequest, IAttachment, IStatus, Cardinal, BytePtr)
# procedure transactRequest(this: IAttachment; status: IStatus; transaction: ITransaction; blrLength: Cardinal; blr: BytePtr; inMsgLength: Cardinal; inMsg: BytePtr; outMsgLength: Cardinal; outMsg: BytePtr)
IAttachment_transactRequest = c.CFUNCTYPE(None, IAttachment, IStatus, ITransaction, Cardinal, BytePtr, Cardinal, BytePtr, Cardinal, BytePtr)
# function createBlob(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; bpbLength: Cardinal; bpb: BytePtr): IBlob
IAttachment_createBlob = c.CFUNCTYPE(IBlob, IAttachment, IStatus, ITransaction, ISC_QUADPtr, Cardinal, BytePtr)
# function openBlob(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; bpbLength: Cardinal; bpb: BytePtr): IBlob
IAttachment_openBlob = c.CFUNCTYPE(IBlob, IAttachment, IStatus, ITransaction, ISC_QUADPtr, Cardinal, BytePtr)
# function getSlice(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; sdlLength: Cardinal; sdl: BytePtr; paramLength: Cardinal; param: BytePtr; sliceLength: Integer; slice: BytePtr): Integer
IAttachment_getSlice = c.CFUNCTYPE(c.c_int, IAttachment, IStatus, ITransaction, ISC_QUADPtr, Cardinal, BytePtr, Cardinal, BytePtr, c.c_int, BytePtr)
# procedure putSlice(this: IAttachment; status: IStatus; transaction: ITransaction; id: ISC_QUADPtr; sdlLength: Cardinal; sdl: BytePtr; paramLength: Cardinal; param: BytePtr; sliceLength: Integer; slice: BytePtr)
IAttachment_putSlice = c.CFUNCTYPE(None, IAttachment, IStatus, ITransaction, ISC_QUADPtr, Cardinal, BytePtr, Cardinal, BytePtr, c.c_int, BytePtr)
# procedure executeDyn(this: IAttachment; status: IStatus; transaction: ITransaction; length: Cardinal; dyn: BytePtr)
IAttachment_executeDyn = c.CFUNCTYPE(None, IAttachment, IStatus, ITransaction, Cardinal, BytePtr)
# function prepare(this: IAttachment; status: IStatus; tra: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; flags: Cardinal): IStatement
IAttachment_prepare = c.CFUNCTYPE(IStatement, IAttachment, IStatus, ITransaction, Cardinal, c.c_char_p, Cardinal, Cardinal)
# function execute(this: IAttachment; status: IStatus; transaction: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; outBuffer: Pointer): ITransaction
IAttachment_execute = c.CFUNCTYPE(ITransaction, IAttachment, IStatus, ITransaction, Cardinal, c.c_char_p, Cardinal, IMessageMetadata, c.c_void_p, IMessageMetadata, c.c_void_p)
# function openCursor(this: IAttachment; status: IStatus; transaction: ITransaction; stmtLength: Cardinal; sqlStmt: PAnsiChar; dialect: Cardinal; inMetadata: IMessageMetadata; inBuffer: Pointer; outMetadata: IMessageMetadata; cursorName: PAnsiChar; cursorFlags: Cardinal): IResultSet
IAttachment_openCursor = c.CFUNCTYPE(IResultSet, IAttachment, IStatus, ITransaction, Cardinal, c.c_char_p, Cardinal, IMessageMetadata, c.c_void_p, IMessageMetadata, c.c_char_p, Cardinal)
# function queEvents(this: IAttachment; status: IStatus; callback: IEventCallback; length: Cardinal; events: BytePtr): IEvents
IAttachment_queEvents = c.CFUNCTYPE(IEvents, IAttachment, IStatus, IEventCallback, Cardinal, BytePtr)
# procedure cancelOperation(this: IAttachment; status: IStatus; option: Integer)
IAttachment_cancelOperation = c.CFUNCTYPE(None, IAttachment, IStatus, c.c_int)
# procedure ping(this: IAttachment; status: IStatus)
IAttachment_ping = c.CFUNCTYPE(None, IAttachment, IStatus)
# procedure detach(this: IAttachment; status: IStatus)
IAttachment_detach = c.CFUNCTYPE(None, IAttachment, IStatus)
# procedure dropDatabase(this: IAttachment; status: IStatus)
IAttachment_dropDatabase = c.CFUNCTYPE(None, IAttachment, IStatus)
#
# IService(3) : ReferenceCounted
# ------------------------------
# procedure detach(this: IService; status: IStatus)
IService_detach = c.CFUNCTYPE(None, IService, IStatus)
# procedure query(this: IService; status: IStatus; sendLength: Cardinal; sendItems: BytePtr; receiveLength: Cardinal; receiveItems: BytePtr; bufferLength: Cardinal; buffer: BytePtr)
IService_query = c.CFUNCTYPE(None, IService, IStatus, Cardinal, BytePtr, Cardinal, BytePtr, Cardinal, BytePtr)
# procedure start(this: IService; status: IStatus; spbLength: Cardinal; spb: BytePtr)
IService_start = c.CFUNCTYPE(None, IService, IStatus, Cardinal, BytePtr)
#
# IProvider(4) : PluginBase
# -------------------------
# function attachDatabase(this: IProvider; status: IStatus; fileName: PAnsiChar; dpbLength: Cardinal; dpb: BytePtr): IAttachment
IProvider_attachDatabase = c.CFUNCTYPE(IAttachment, IProvider, IStatus, c.c_char_p, Cardinal, BytePtr)
# function createDatabase(this: IProvider; status: IStatus; fileName: PAnsiChar; dpbLength: Cardinal; dpb: BytePtr): IAttachment
IProvider_createDatabase = c.CFUNCTYPE(IAttachment, IProvider, IStatus, c.c_char_p, Cardinal, BytePtr)
# function attachServiceManager(this: IProvider; status: IStatus; service: PAnsiChar; spbLength: Cardinal; spb: BytePtr): IService
IProvider_attachServiceManager = c.CFUNCTYPE(IService, IProvider, IStatus, c.c_char_p, Cardinal, BytePtr)
# procedure shutdown(this: IProvider; status: IStatus; timeout: Cardinal; reason: Integer)
IProvider_shutdown = c.CFUNCTYPE(None, IProvider, IStatus, Cardinal, c.c_int)
# procedure setDbCryptCallback(this: IProvider; status: IStatus; cryptCallback: ICryptKeyCallback)
IProvider_setDbCryptCallback = c.CFUNCTYPE(None, IProvider, IStatus, ICryptKeyCallback)
#
# IDtcStart(3) : Disposable
# -------------------------
# procedure addAttachment(this: IDtcStart; status: IStatus; att: IAttachment)
IDtcStart_addAttachment = c.CFUNCTYPE(None, IDtcStart, IStatus, IAttachment)
# procedure addWithTpb(this: IDtcStart; status: IStatus; att: IAttachment; length: Cardinal; tpb: BytePtr)
IDtcStart_addWithTpb = c.CFUNCTYPE(None, IDtcStart, IStatus, IAttachment, Cardinal, BytePtr)
# function start(this: IDtcStart; status: IStatus): ITransaction
IDtcStart_start = c.CFUNCTYPE(ITransaction, IDtcStart, IStatus)
#
# IDtc(2) : Versioned
# -------------------
# function join(this: IDtc; status: IStatus; one: ITransaction; two: ITransaction): ITransaction
IDtc_join = c.CFUNCTYPE(ITransaction, IDtc, IStatus, ITransaction, ITransaction)
# function startBuilder(this: IDtc; status: IStatus): IDtcStart
IDtc_startBuilder = c.CFUNCTYPE(IDtcStart, IDtc, IStatus)
#
# ICryptKeyCallback(2) : Versioned
# --------------------------------
# function callback(this: ICryptKeyCallback; dataLength: Cardinal; data: Pointer; bufferLength: Cardinal; buffer: Pointer): Cardinal
ICryptKeyCallback_callback = c.CFUNCTYPE(Cardinal, ICryptKeyCallback, Cardinal, c.c_void_p, Cardinal, c.c_void_p)
#
# ITimer(3) : ReferenceCounted
# ----------------------------
# procedure handler(this: ITimer)
ITimer_handler = c.CFUNCTYPE(None, ITimer)
#
# ITimerControl(2) : Versioned
# ----------------------------
# procedure start(this: ITimerControl; status: IStatus; timer: ITimer; microSeconds: QWord)
ITimerControl_start = c.CFUNCTYPE(None, ITimerControl, IStatus, ITimer, QWord)
# procedure stop(this: ITimerControl; status: IStatus; timer: ITimer)
ITimerControl_stop = c.CFUNCTYPE(None, ITimerControl, IStatus, ITimer)
#
# IVersionCallback(2) : Versioned
# -------------------------------
# procedure callback(this: IVersionCallback; status: IStatus; text: PAnsiChar)
IVersionCallback_callback = c.CFUNCTYPE(None, IVersionCallback, IStatus, c.c_char_p)
#
# IUtil(2) : Versioned
# --------------------
# procedure getFbVersion(this: IUtil; status: IStatus; att: IAttachment; callback: IVersionCallback)
IUtil_getFbVersion = c.CFUNCTYPE(None, IUtil, IStatus, IAttachment, IVersionCallback)
# procedure loadBlob(this: IUtil; status: IStatus; blobId: ISC_QUADPtr; att: IAttachment; tra: ITransaction; file_: PAnsiChar; txt: Boolean)
IUtil_loadBlob = c.CFUNCTYPE(None, IUtil, IStatus, ISC_QUADPtr, IAttachment, ITransaction, c.c_char_p, c.c_bool)
# procedure dumpBlob(this: IUtil; status: IStatus; blobId: ISC_QUADPtr; att: IAttachment; tra: ITransaction; file_: PAnsiChar; txt: Boolean)
IUtil_dumpBlob = c.CFUNCTYPE(None, IUtil, IStatus, ISC_QUADPtr, IAttachment, ITransaction, c.c_char_p, c.c_bool)
# procedure getPerfCounters(this: IUtil; status: IStatus; att: IAttachment; countersSet: PAnsiChar; counters: Int64Ptr)
IUtil_getPerfCounters = c.CFUNCTYPE(None, IUtil, IStatus, IAttachment, c.c_char_p, Int64Ptr)
# function executeCreateDatabase(this: IUtil; status: IStatus; stmtLength: Cardinal; creatDBstatement: PAnsiChar; dialect: Cardinal; stmtIsCreateDb: BooleanPtr): IAttachment
IUtil_executeCreateDatabase = c.CFUNCTYPE(IAttachment, IUtil, IStatus, Cardinal, c.c_char_p, Cardinal, BooleanPtr)
# procedure decodeDate(this: IUtil; date: ISC_DATE; year: CardinalPtr; month: CardinalPtr; day: CardinalPtr)
IUtil_decodeDate = c.CFUNCTYPE(None, IUtil, ISC_DATE, CardinalPtr, CardinalPtr, CardinalPtr)
# procedure decodeTime(this: IUtil; time: ISC_TIME; hours: CardinalPtr; minutes: CardinalPtr; seconds: CardinalPtr; fractions: CardinalPtr)
IUtil_decodeTime = c.CFUNCTYPE(None, IUtil, ISC_TIME, CardinalPtr, CardinalPtr, CardinalPtr, CardinalPtr)
# function encodeDate(this: IUtil; year: Cardinal; month: Cardinal; day: Cardinal): ISC_DATE
IUtil_encodeDate = c.CFUNCTYPE(ISC_DATE, IUtil, Cardinal, Cardinal, Cardinal)
# function encodeTime(this: IUtil; hours: Cardinal; minutes: Cardinal; seconds: Cardinal; fractions: Cardinal): ISC_TIME
IUtil_encodeTime = c.CFUNCTYPE(ISC_TIME, IUtil, Cardinal, Cardinal, Cardinal, Cardinal)
# function formatStatus(this: IUtil; buffer: PAnsiChar; bufferSize: Cardinal; status: IStatus): Cardinal
IUtil_formatStatus = c.CFUNCTYPE(Cardinal, IUtil, c.c_char_p, Cardinal, IStatus)
# function getClientVersion(this: IUtil): Cardinal
IUtil_getClientVersion = c.CFUNCTYPE(Cardinal, IUtil)
# function getXpbBuilder(this: IUtil; status: IStatus; kind: Cardinal; buf: BytePtr; len: Cardinal): IXpbBuilder
IUtil_getXpbBuilder = c.CFUNCTYPE(IXpbBuilder, IUtil, IStatus, Cardinal, BytePtr, Cardinal)
# function setOffsets(this: IUtil; status: IStatus; metadata: IMessageMetadata; callback: IOffsetsCallback): Cardinal
IUtil_setOffsets = c.CFUNCTYPE(Cardinal, IUtil, IStatus, IMessageMetadata, IOffsetsCallback)
#
# IOffsetsCallback(2) : Versioned
# -------------------------------
# procedure setOffset(this: IOffsetsCallback; status: IStatus; index: Cardinal; offset: Cardinal; nullOffset: Cardinal)
IOffsetsCallback_setOffset = c.CFUNCTYPE(None, IOffsetsCallback, IStatus, Cardinal, Cardinal, Cardinal)
#
# IXpbBuilder(3) : Disposable
# ---------------------------
# procedure clear(this: IXpbBuilder; status: IStatus)
IXpbBuilder_clear = c.CFUNCTYPE(None, IXpbBuilder, IStatus)
# procedure removeCurrent(this: IXpbBuilder; status: IStatus)
IXpbBuilder_removeCurrent = c.CFUNCTYPE(None, IXpbBuilder, IStatus)
# procedure insertInt(this: IXpbBuilder; status: IStatus; tag: Byte; value: Integer)
IXpbBuilder_insertInt = c.CFUNCTYPE(None, IXpbBuilder, IStatus, c.c_byte, c.c_int)
# procedure insertBigInt(this: IXpbBuilder; status: IStatus; tag: Byte; value: Int64)
IXpbBuilder_insertBigInt = c.CFUNCTYPE(None, IXpbBuilder, IStatus, c.c_byte, Int64)
# procedure insertBytes(this: IXpbBuilder; status: IStatus; tag: Byte; bytes: Pointer; length: Cardinal)
IXpbBuilder_insertBytes = c.CFUNCTYPE(None, IXpbBuilder, IStatus, c.c_byte, c.c_void_p, Cardinal)
# procedure insertString(this: IXpbBuilder; status: IStatus; tag: Byte; str: PAnsiChar)
IXpbBuilder_insertString = c.CFUNCTYPE(None, IXpbBuilder, IStatus, c.c_byte, c.c_char_p)
# procedure insertTag(this: IXpbBuilder; status: IStatus; tag: Byte)
IXpbBuilder_insertTag = c.CFUNCTYPE(None, IXpbBuilder, IStatus, c.c_byte)
# function isEof(this: IXpbBuilder; status: IStatus): Boolean
IXpbBuilder_isEof = c.CFUNCTYPE(c.c_bool, IXpbBuilder, IStatus)
# procedure moveNext(this: IXpbBuilder; status: IStatus)
IXpbBuilder_moveNext = c.CFUNCTYPE(None, IXpbBuilder, IStatus)
# procedure rewind(this: IXpbBuilder; status: IStatus)
IXpbBuilder_rewind = c.CFUNCTYPE(None, IXpbBuilder, IStatus)
# function findFirst(this: IXpbBuilder; status: IStatus; tag: Byte): Boolean
IXpbBuilder_findFirst = c.CFUNCTYPE(c.c_bool, IXpbBuilder, IStatus, c.c_byte)
# function findNext(this: IXpbBuilder; status: IStatus): Boolean
IXpbBuilder_findNext = c.CFUNCTYPE(c.c_bool, IXpbBuilder, IStatus)
# function getTag(this: IXpbBuilder; status: IStatus): Byte
IXpbBuilder_getTag = c.CFUNCTYPE(c.c_byte, IXpbBuilder, IStatus)
# function getLength(this: IXpbBuilder; status: IStatus): Cardinal
IXpbBuilder_getLength = c.CFUNCTYPE(Cardinal, IXpbBuilder, IStatus)
# function getInt(this: IXpbBuilder; status: IStatus): Integer
IXpbBuilder_getInt = c.CFUNCTYPE(c.c_int, IXpbBuilder, IStatus)
# function getBigInt(this: IXpbBuilder; status: IStatus): Int64
IXpbBuilder_getBigInt = c.CFUNCTYPE(Int64, IXpbBuilder, IStatus)
# function getString(this: IXpbBuilder; status: IStatus): PAnsiChar
IXpbBuilder_getString = c.CFUNCTYPE(c.c_char_p, IXpbBuilder, IStatus)
# function getBytes(this: IXpbBuilder; status: IStatus): BytePtr
IXpbBuilder_getBytes = c.CFUNCTYPE(BytePtr, IXpbBuilder, IStatus)
# function getBufferLength(this: IXpbBuilder; status: IStatus): Cardinal
IXpbBuilder_getBufferLength = c.CFUNCTYPE(Cardinal, IXpbBuilder, IStatus)
# function getBuffer(this: IXpbBuilder; status: IStatus): BytePtr
IXpbBuilder_getBuffer = c.CFUNCTYPE(BytePtr, IXpbBuilder, IStatus)
# ------------------------------------------------------------------------------
# Interfaces - Data structures
# ------------------------------------------------------------------------------
# IVersioned(1)
IVersioned_VTable._fields_ = [('dummy', c.c_void_p),
                              ('version', c.c_ulong)
                              ]
IVersioned_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IVersioned_VTablePtr)]
# IReferenceCounted(2)
IReferenceCounted_VTable._fields_ = [('dummy', c.c_void_p),
                                     ('version', c.c_ulong),
                                     ('addRef', IReferenceCounted_addRef),
                                     ('release', IReferenceCounted_release),
                                     ]
IReferenceCounted_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IReferenceCounted_VTablePtr)]
# IDisposable(2)
IDisposable_VTable._fields_ = [('dummy', c.c_void_p),
                               ('version', c.c_ulong),
                               ('dispose', IDisposable_dispose),
                               ]
IDisposable_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IDisposable_VTablePtr)]
# IStatus(3) : Disposable
IStatus_VTable._fields_ = [('dummy', c.c_void_p),
                           ('version', c.c_ulong),
                           ('dispose', IDisposable_dispose),
                           ('init', IStatus_init),
                           ('getState', IStatus_getState),
                           ('setErrors2', IStatus_setErrors2),
                           ('setWarnings2', IStatus_setWarnings2),
                           ('setErrors', IStatus_setErrors),
                           ('setWarnings', IStatus_setWarnings),
                           ('getErrors', IStatus_getErrors),
                           ('getWarnings', IStatus_getWarnings),
                           ('clone', IStatus_clone)
                           ]
IStatus_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IStatus_VTablePtr)]
# IMaster(2) : Versioned
IMaster_VTable._fields_ = [('dummy', c.c_void_p),
                           ('version', c.c_ulong),
                           ('getStatus', IMaster_getStatus),
                           ('getDispatcher', IMaster_getDispatcher),
                           ('getPluginManager', IMaster_getPluginManager),
                           ('getTimerControl', IMaster_getTimerControl),
                           ('getDtc', IMaster_getDtc),
                           ('registerAttachment', IMaster_registerAttachment),
                           ('registerTransaction', IMaster_registerTransaction),
                           ('getMetadataBuilder', IMaster_getMetadataBuilder),
                           ('serverMode', IMaster_serverMode),
                           ('getUtilInterface', IMaster_getUtilInterface),
                           ('getConfigManager', IMaster_getConfigManager),
                           ('getProcessExiting', IMaster_getProcessExiting),
                           ]
IMaster_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IMaster_VTablePtr)]
# IPluginBase(3) : ReferenceCounted
IPluginBase_VTable._fields_ = [('dummy', c.c_void_p),
                               ('version', c.c_ulong),
                               ('addRef', IReferenceCounted_addRef),
                               ('release', IReferenceCounted_release),
                               ('setOwner', IPluginBase_setOwner),
                               ('getOwner', IPluginBase_getOwner),
                               ]
IPluginBase_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IPluginBase_VTablePtr)]
# IPluginSet(3) : ReferenceCounted
# IConfigEntry(3) : ReferenceCounted
IConfigEntry_VTable._fields_ = [('dummy', c.c_void_p),
                                ('version',c.c_ulong),
                                ('addRef', IReferenceCounted_addRef),
                                ('release', IReferenceCounted_release),
                                ('getName', IConfigEntry_getName),
                                ('getValue', IConfigEntry_getValue),
                                ('getIntValue', IConfigEntry_getIntValue),
                                ('getBoolValue', IConfigEntry_getBoolValue),
                                ('getSubConfig', IConfigEntry_getSubConfig),
                                ]
IConfigEntry_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IConfigEntry_VTablePtr)]
# IConfig(3) : ReferenceCounted
IConfig_VTable._fields_ = [('dummy', c.c_void_p),
                           ('version',c.c_ulong),
                           ('addRef', IReferenceCounted_addRef),
                           ('release', IReferenceCounted_release),
                           ('find', IConfig_find),
                           ('findValue', IConfig_findValue),
                           ('findPos', IConfig_findPos),
                           ]
IConfig_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IConfig_VTablePtr)]
# IFirebirdConf(3) : ReferenceCounted
IFirebirdConf_VTable._fields_ = [('dummy', c.c_void_p),
                                 ('version',c.c_ulong),
                                 ('addRef', IReferenceCounted_addRef),
                                 ('release', IReferenceCounted_release),
                                 ('getKey', IFirebirdConf_getKey),
                                 ('asInteger', IFirebirdConf_asInteger),
                                 ('asString', IFirebirdConf_asString),
                                 ('asBoolean', IFirebirdConf_asBoolean),
                                 ]
IFirebirdConf_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IFirebirdConf_VTablePtr)]
# IPluginConfig(3) : ReferenceCounted
# IPluginFactory(2) : Versioned
# IPluginModule(3) : Versioned
# IPluginManager(2) : Versioned
# ICryptKey(2) : Versioned
# IConfigManager(2) : Versioned
IConfigManager_VTable._fields_ = [('dummy', c.c_void_p),
                                  ('version',c.c_ulong),
                                  ('getDirectory', IConfigManager_getDirectory),
                                  ('getFirebirdConf', IConfigManager_getFirebirdConf),
                                  ('getDatabaseConf', IConfigManager_getDatabaseConf),
                                  ('getPluginConfig', IConfigManager_getPluginConfig),
                                  ('getInstallDirectory', IConfigManager_getInstallDirectory),
                                  ('getRootDirectory', IConfigManager_getRootDirectory),
                                  ]
IConfigManager_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IConfigManager_VTablePtr)]
# IEventCallback(3) : ReferenceCounted
IEventCallback_VTable._fields_ = [('dummy', c.c_void_p),
                                  ('version', c.c_ulong),
                                  ('addRef', IReferenceCounted_addRef),
                                  ('release', IReferenceCounted_release),
                                  ('eventCallbackFunction', IEventCallback_eventCallbackFunction),
                                  ]
IEventCallback_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IEventCallback_VTablePtr)]
# IBlob(3) : ReferenceCounted
IBlob_VTable._fields_ = [('dummy', c.c_void_p),
                         ('version', c.c_ulong),
                         ('addRef', IReferenceCounted_addRef),
                         ('release', IReferenceCounted_release),
                         ('getInfo', IBlob_getInfo),
                         ('getSegment', IBlob_getSegment),
                         ('putSegment', IBlob_putSegment),
                         ('cancel', IBlob_cancel),
                         ('close', IBlob_close),
                         ('seek', IBlob_seek),
                         ]
IBlob_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IBlob_VTablePtr)]
# ITransaction(3) : ReferenceCounted
ITransaction_VTable._fields_ = [('dummy', c.c_void_p),
                                ('version', c.c_ulong),
                                ('addRef', IReferenceCounted_addRef),
                                ('release', IReferenceCounted_release),
                                ('getInfo', ITransaction_getInfo),
                                ('prepare', ITransaction_prepare),
                                ('commit', ITransaction_commit),
                                ('commitRetaining', ITransaction_commitRetaining),
                                ('rollback', ITransaction_rollback),
                                ('rollbackRetaining', ITransaction_rollbackRetaining),
                                ('disconnect', ITransaction_disconnect),
                                ('join', ITransaction_join),
                                ('validate', ITransaction_validate),
                                ('enterDtc', ITransaction_enterDtc),
                                ]
ITransaction_struct._fields_ = [('dummy', c.c_void_p), ('vtable', ITransaction_VTablePtr)]
# IMessageMetadata(3) : ReferenceCounted
IMessageMetadata_VTable._fields_ = [('dummy', c.c_void_p),
                                    ('version', c.c_ulong),
                                    ('addRef', IReferenceCounted_addRef),
                                    ('release', IReferenceCounted_release),
                                    ('getCount', IMessageMetadata_getCount),
                                    ('getField', IMessageMetadata_getField),
                                    ('getRelation', IMessageMetadata_getRelation),
                                    ('getOwner', IMessageMetadata_getOwner),
                                    ('getAlias', IMessageMetadata_getAlias),
                                    ('getType', IMessageMetadata_getType),
                                    ('isNullable', IMessageMetadata_isNullable),
                                    ('getSubType', IMessageMetadata_getSubType),
                                    ('getLength', IMessageMetadata_getLength),
                                    ('getScale', IMessageMetadata_getScale),
                                    ('getCharSet', IMessageMetadata_getCharSet),
                                    ('getOffset', IMessageMetadata_getOffset),
                                    ('getNullOffset', IMessageMetadata_getNullOffset),
                                    ('getBuilder', IMessageMetadata_getBuilder),
                                    ('getMessageLength', IMessageMetadata_getMessageLength),
                                    ]
IMessageMetadata_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IMessageMetadata_VTablePtr)]
# IMetadataBuilder(3) : ReferenceCounted
IMetadataBuilder_VTable._fields_ = [('dummy', c.c_void_p),
                                    ('version', c.c_ulong),
                                    ('addRef', IReferenceCounted_addRef),
                                    ('release', IReferenceCounted_release),
                                    ('setType', IMetadataBuilder_setType),
                                    ('setSubType', IMetadataBuilder_setSubType),
                                    ('setLength', IMetadataBuilder_setLength),
                                    ('setCharSet', IMetadataBuilder_setCharSet),
                                    ('setScale', IMetadataBuilder_setScale),
                                    ('truncate', IMetadataBuilder_truncate),
                                    ('moveNameToIndex', IMetadataBuilder_moveNameToIndex),
                                    ('remove', IMetadataBuilder_remove),
                                    ('addField', IMetadataBuilder_addField),
                                    ('getMetadata', IMetadataBuilder_getMetadata),
                                    ]
IMetadataBuilder_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IMetadataBuilder_VTablePtr)]
# IResultSet(3) : ReferenceCounted
IResultSet_VTable._fields_ = [('dummy', c.c_void_p),
                              ('version', c.c_ulong),
                              ('addRef', IReferenceCounted_addRef),
                              ('release', IReferenceCounted_release),
                              ('fetchNext', IResultSet_fetchNext),
                              ('fetchPrior', IResultSet_fetchPrior),
                              ('fetchFirst', IResultSet_fetchFirst),
                              ('fetchLast', IResultSet_fetchLast),
                              ('fetchAbsolute', IResultSet_fetchAbsolute),
                              ('fetchRelative', IResultSet_fetchRelative),
                              ('isEof', IResultSet_isEof),
                              ('isBof', IResultSet_isBof),
                              ('getMetadata', IResultSet_getMetadata),
                              ('close', IResultSet_close),
                              ('setDelayedOutputFormat', IResultSet_setDelayedOutputFormat),
                              ]
IResultSet_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IResultSet_VTablePtr)]
# IStatement(3) : ReferenceCounted
IStatement_VTable._fields_ = [('dummy', c.c_void_p),
                              ('version', c.c_ulong),
                              ('addRef', IReferenceCounted_addRef),
                              ('release', IReferenceCounted_release),
                              ('getInfo', IStatement_getInfo),
                              ('getType', IStatement_getType),
                              ('getPlan', IStatement_getPlan),
                              ('getAffectedRecords', IStatement_getAffectedRecords),
                              ('getInputMetadata', IStatement_getInputMetadata),
                              ('getOutputMetadata', IStatement_getOutputMetadata),
                              ('execute', IStatement_execute),
                              ('openCursor', IStatement_openCursor),
                              ('setCursorName', IStatement_setCursorName),
                              ('free', IStatement_free),
                              ('getFlags', IStatement_getFlags),
                              ]
IStatement_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IStatement_VTablePtr)]
# IRequest(3) : ReferenceCounted
IRequest_VTable._fields_ = [('dummy', c.c_void_p),
                            ('version', c.c_ulong),
                            ('addRef', IReferenceCounted_addRef),
                            ('release', IReferenceCounted_release),
                            ('receive', IRequest_receive),
                            ('send', IRequest_send),
                            ('getInfo', IRequest_getInfo),
                            ('start', IRequest_start),
                            ('startAndSend', IRequest_startAndSend),
                            ('unwind', IRequest_unwind),
                            ('free', IRequest_free),
                            ]
IRequest_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IRequest_VTablePtr)]
# IEvents(3) : ReferenceCounted
IEvents_VTable._fields_ = [('dummy', c.c_void_p),
                           ('version', c.c_ulong),
                           ('addRef', IReferenceCounted_addRef),
                           ('release', IReferenceCounted_release),
                           ('cancel', IEvents_cancel),
                           ]
IEvents_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IEvents_VTablePtr)]
# IAttachment(3) : ReferenceCounted
IAttachment_VTable._fields_ = [('dummy', c.c_void_p),
                               ('version', c.c_ulong),
                               ('addRef', IReferenceCounted_addRef),
                               ('release', IReferenceCounted_release),
                               ('getInfo', IAttachment_getInfo),
                               ('startTransaction', IAttachment_startTransaction),
                               ('reconnectTransaction', IAttachment_reconnectTransaction),
                               ('compileRequest', IAttachment_compileRequest),
                               ('transactRequest', IAttachment_transactRequest),
                               ('createBlob', IAttachment_createBlob),
                               ('openBlob', IAttachment_openBlob),
                               ('getSlice', IAttachment_getSlice),
                               ('putSlice', IAttachment_putSlice),
                               ('executeDyn', IAttachment_executeDyn),
                               ('prepare', IAttachment_prepare),
                               ('execute', IAttachment_execute),
                               ('openCursor', IAttachment_openCursor),
                               ('queEvents', IAttachment_queEvents),
                               ('cancelOperation', IAttachment_cancelOperation),
                               ('ping', IAttachment_ping),
                               ('detach', IAttachment_detach),
                               ('dropDatabase', IAttachment_dropDatabase),
                               ]
IAttachment_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IAttachment_VTablePtr)]
# IService(3) : ReferenceCounted
IService_VTable._fields_ = [('dummy', c.c_void_p),
                            ('version', c.c_ulong),
                            ('addRef', IReferenceCounted_addRef),
                            ('release', IReferenceCounted_release),
                            ('detach', IService_detach),
                            ('query', IService_query),
                            ('start', IService_start),
                            ]
IService_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IService_VTablePtr)]
# IProvider(4) : PluginBase
IProvider_VTable._fields_ = [('dummy', c.c_void_p),
                             ('version', c.c_ulong),
                             ('addRef', IReferenceCounted_addRef),
                             ('release', IReferenceCounted_release),
                             ('setOwner', IPluginBase_setOwner),
                             ('getOwner', IPluginBase_getOwner),
                             ('attachDatabase', IProvider_attachDatabase),
                             ('createDatabase', IProvider_createDatabase),
                             ('attachServiceManager', IProvider_attachServiceManager),
                             ('shutdown', IProvider_shutdown),
                             ('setDbCryptCallback', IProvider_setDbCryptCallback),
                             ]
IProvider_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IProvider_VTablePtr)]
# IDtcStart(3) : Disposable
IDtcStart_VTable._fields_ = [('dummy', c.c_void_p),
                             ('version', c.c_ulong),
                             ('dispose', IDisposable_dispose),
                             ('addAttachment', IDtcStart_addAttachment),
                             ('addWithTpb', IDtcStart_addWithTpb),
                             ('start', IDtcStart_start),
                             ]
IDtcStart_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IDtcStart_VTablePtr)]
# IDtc(2) : Versioned
IDtc_VTable._fields_ = [('dummy', c.c_void_p),
                        ('version', c.c_ulong),
                        ('join', IDtc_join),
                        ('startBuilder', IDtc_startBuilder),
                        ]
IDtc_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IDtc_VTablePtr)]
#? IAuth(4) : PluginBase
#? IWriter(2) : Versioned
#? IServerBlock(2) : Versioned
#? IClientBlock(4) : ReferenceCounted
#? IServer(6) : Auth
#? IClient(5) : Auth
#? IUserField(2) : Versioned
#? ICharUserField(3) : IUserField
#? IIntUserField(3) : IUserField
#? IUser(2) : Versioned
#? IListUsers(2) : Versioned
#? ILogonInfo(2) : Versioned
#? IManagement(4) : PluginBase
#? IAuthBlock(2) : Versioned
#? IWireCryptPlugin(4) : PluginBase
# ICryptKeyCallback(2) : Versioned
ICryptKeyCallback_VTable._fields_ = [('dummy', c.c_void_p),
                                     ('version', c.c_ulong),
                                     ('callback', ICryptKeyCallback_callback),
                                     ]
ICryptKeyCallback_struct._fields_ = [('dummy', c.c_void_p), ('vtable', ICryptKeyCallback_VTablePtr)]
#? IKeyHolderPlugin(5) : PluginBase
#? IDbCryptInfo(3) : ReferenceCounted
#? IDbCryptPlugin(5) : PluginBase
#? IExternalContext(2) : Versioned
#? IExternalResultSet(3) : Disposable
#? IExternalFunction(3) : Disposable
#? IExternalProcedure(3) : Disposable
#? IExternalTrigger(3) : Disposable
#? IRoutineMetadata(2) : Versioned
#? IExternalEngine(4) : PluginBase
# ITimer(3) : ReferenceCounted
ITimer_VTable._fields_ = [('dummy', c.c_void_p),
                          ('version', c.c_ulong),
                          ('addRef', IReferenceCounted_addRef),
                          ('release', IReferenceCounted_release),
                          ('handler', ITimer_handler),
                          ]
ITimer_struct._fields_ = [('dummy', c.c_void_p), ('vtable', ITimer_VTablePtr)]
# ITimerControl(2) : Versioned
ITimerControl_VTable._fields_ = [('dummy', c.c_void_p),
                                 ('version', c.c_ulong),
                                 ('start', ITimerControl_start),
                                 ('stop', ITimerControl_stop),
                                 ]
ITimerControl_struct._fields_ = [('dummy', c.c_void_p), ('vtable', ITimerControl_VTablePtr)]
# IVersionCallback(2) : Versioned
IVersionCallback_VTable._fields_ = [('dummy', c.c_void_p),
                                    ('version', c.c_ulong),
                                    ('callback', IVersionCallback_callback),
                                    ]
IVersionCallback_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IVersionCallback_VTablePtr)]
# IUtil(2) : Versioned
IUtil_VTable._fields_ = [('dummy', c.c_void_p),
                         ('version', c.c_ulong),
                         ('getFbVersion', IUtil_getFbVersion),
                         ('loadBlob', IUtil_loadBlob),
                         ('dumpBlob', IUtil_dumpBlob),
                         ('getPerfCounters', IUtil_getPerfCounters),
                         ('executeCreateDatabase', IUtil_executeCreateDatabase),
                         ('decodeDate', IUtil_decodeDate),
                         ('decodeTime', IUtil_decodeTime),
                         ('encodeDate', IUtil_encodeDate),
                         ('encodeTime', IUtil_encodeTime),
                         ('formatStatus', IUtil_formatStatus),
                         ('getClientVersion', IUtil_getClientVersion),
                         ('getXpbBuilder', IUtil_getXpbBuilder),
                         ('setOffsets', IUtil_setOffsets),
                         ]
IUtil_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IUtil_VTablePtr)]
# IOffsetsCallback(2) : Versioned
IOffsetsCallback_VTable._fields_ = [('dummy', c.c_void_p),
                                    ('version', c.c_ulong),
                                    ('setOffset', IOffsetsCallback_setOffset),
                                    ]
IOffsetsCallback_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IOffsetsCallback_VTablePtr)]
# IXpbBuilder(3) : Disposable
IXpbBuilder_VTable._fields_ = [('dummy', c.c_void_p),
                               ('version', c.c_ulong),
                               ('dispose', IDisposable_dispose),
                               ('clear', IXpbBuilder_clear),
                               ('removeCurrent', IXpbBuilder_removeCurrent),
                               ('insertInt', IXpbBuilder_insertInt),
                               ('insertBigInt', IXpbBuilder_insertBigInt),
                               ('insertBytes', IXpbBuilder_insertBytes),
                               ('insertString', IXpbBuilder_insertString),
                               ('insertTag', IXpbBuilder_insertTag),
                               ('isEof', IXpbBuilder_isEof),
                               ('moveNext', IXpbBuilder_moveNext),
                               ('rewind', IXpbBuilder_rewind),
                               ('findFirst', IXpbBuilder_findFirst),
                               ('findNext', IXpbBuilder_findNext),
                               ('getTag', IXpbBuilder_getTag),
                               ('getLength', IXpbBuilder_getLength),
                               ('getInt', IXpbBuilder_getInt),
                               ('getBigInt', IXpbBuilder_getBigInt),
                               ('getString', IXpbBuilder_getString),
                               ('getBytes', IXpbBuilder_getBytes),
                               ('getBufferLength', IXpbBuilder_getBufferLength),
                               ('getBuffer', IXpbBuilder_getBuffer),
                               ]
IXpbBuilder_struct._fields_ = [('dummy', c.c_void_p), ('vtable', IXpbBuilder_VTablePtr)]
#? ITraceConnection(2) : Versioned
#? ITraceDatabaseConnection(3) : TraceConnection
#? ITraceTransaction(3) : Versioned
#? ITraceParams(3) : Versioned
#? ITraceStatement(2) : Versioned
#? ITraceSQLStatement(3) : TraceStatement
#? ITraceBLRStatement(3) : TraceStatement
#? ITraceDYNRequest(2) : Versioned
#? ITraceContextVariable(2) : Versioned
#? ITraceProcedure(2) : Versioned
#? ITraceFunction(2) : Versioned
#? ITraceTrigger(2) : Versioned
#? ITraceServiceConnection(3) : TraceConnection
#? ITraceStatusVector(2) : Versioned
#? ITraceSweepInfo(2) : Versioned
#? ITraceLogWriter(4) : ReferenceCounted
#? ITraceInitInfo(2) : Versioned
#? ITracePlugin(3) : ReferenceCounted
#? ITraceFactory(4) : PluginBase
#? IUdrFunctionFactory(3) : Disposable
#? IUdrProcedureFactory(3) : Disposable
#? IUdrTriggerFactory(3) : Disposable
#? IUdrPlugin(2) : Versioned

sys_encoding = getpreferredencoding()

def db_api_error(status_vector: ISC_STATUS_ARRAY) -> bool:
    return status_vector[0] == 1 and status_vector[1] > 0

def exception_from_status(error, status: ISC_STATUS_ARRAY, preamble: str=None) -> Exception:
    msglist = []
    msg = c.create_string_buffer(512)
    if preamble:
        msglist.append(preamble)
    sqlcode = api.isc_sqlcode(status)
    error_code = status[1]
    msglist.append('- SQLCODE: %i' % sqlcode)

    pvector = c.cast(c.addressof(status), ISC_STATUS_PTR)
    sqlstate = c.create_string_buffer(6)
    api.fb_sqlstate(sqlstate, pvector)

    while True:
        result = api.fb_interpret(msg, 512, pvector)
        if result != 0:
            msglist.append('- ' + (msg.value).decode(sys_encoding))
        else:
            break
    return error('\n'.join(msglist), sqlcode=sqlcode, sqlstate=sqlstate, gds_codes=[error_code])

# Client library

class FirebirdAPI:
    """Firebird Client API interface object. Loads Firebird Client Library and
exposes `fb_get_master_interface()`. Uses :ref:`ctypes <python:module-ctypes>`
for bindings.
"""
    def __init__(self, filename: Path = None):
        if filename is None:
            if sys.platform == 'darwin':
                filename = find_library('Firebird')
            elif sys.platform == 'win32':
                filename = find_library('fbclient.dll')
            else:
                filename = find_library('fbclient')
                if not filename:
                    try:
                        c.CDLL('libfbclient.so')
                        filename = 'libfbclient.so'
                    except:
                        pass

            if not filename:
                raise Exception("The location of Firebird Client Library could not be determined.")
        elif not filename.exists():
            file_name = find_library(filename.name)
            if not file_name:
                raise Exception("Firebird Client Library '%s' not found" % filename)
            else:
                filename = file_name
        #
        if sys.platform in ['win32', 'cygwin', 'os2', 'os2emx']:
            self.client_library: c.CDLL = c.WinDLL(filename)
        else:
            self.client_library: c.CDLL = c.CDLL(filename)
        #
        self.client_library_name: Path = Path(filename)
        self.fb_get_master_interface = self.client_library.fb_get_master_interface
        self.fb_get_master_interface.restype = IMaster
        self.fb_get_master_interface.argtypes = []
        #
        # ISC_STATUS ISC_EXPORT fb_get_database_handle(ISC_STATUS*, isc_db_handle*, void*);
        self.fb_get_database_handle = self.client_library.fb_get_database_handle
        self.fb_get_database_handle.restype = ISC_STATUS
        self.fb_get_database_handle.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR, IAttachment]
        # ISC_STATUS ISC_EXPORT fb_get_transaction_handle(ISC_STATUS*, isc_tr_handle*, void*);
        self.fb_get_transaction_handle = self.client_library.fb_get_transaction_handle
        self.fb_get_transaction_handle.restype = ISC_STATUS
        self.fb_get_transaction_handle.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR, ITransaction]
        # void ISC_EXPORT fb_sqlstate(char*, const ISC_STATUS*);
        self.fb_sqlstate = self.client_library.fb_sqlstate
        self.fb_sqlstate.restype = None
        self.fb_sqlstate.argtypes = [STRING, ISC_STATUS_PTR]
        # isc_array_lookup_bounds(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(isc_tr_handle), STRING, STRING, POINTER(ISC_ARRAY_DESC))
        self.isc_array_lookup_bounds = self.client_library.isc_array_lookup_bounds
        self.isc_array_lookup_bounds.restype = ISC_STATUS
        self.isc_array_lookup_bounds.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                                 FB_API_HANDLE_PTR, STRING,
                                                 STRING, ISC_ARRAY_DESC_PTR]
        ## isc_get_slice(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(isc_tr_handle), POINTER(ISC_QUAD), c_short, STRING, c_short, POINTER(ISC_LONG), ISC_LONG, c_void_p, POINTER(ISC_LONG))
        #self.isc_get_slice = self.client_library.isc_get_slice
        #self.isc_get_slice.restype = ISC_STATUS
        #self.isc_get_slice.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                       #FB_API_HANDLE_PTR, ISC_QUAD_PTR,
                                       #c.c_short, STRING, c.c_short,
                                       #ISC_LONG_PTR, ISC_LONG, c.c_void_p, ISC_LONG_PTR]
        ## isc_put_slice(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(isc_tr_handle), POINTER(ISC_QUAD), c_short, STRING, c_short, POINTER(ISC_LONG), ISC_LONG, c_void_p)
        #self.isc_put_slice = self.client_library.isc_put_slice
        #self.isc_put_slice.restype = ISC_STATUS
        #self.isc_put_slice.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                       #FB_API_HANDLE_PTR, ISC_QUAD_PTR,
                                       #c.c_short, STRING, c.c_short,
                                       #ISC_LONG_PTR, ISC_LONG, c.c_void_p]
        # isc_array_put_slice(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(isc_tr_handle), POINTER(ISC_QUAD), POINTER(ISC_ARRAY_DESC), c_void_p, POINTER(ISC_LONG))
        self.isc_array_put_slice = self.client_library.isc_array_put_slice
        self.isc_array_put_slice.restype = ISC_STATUS
        self.isc_array_put_slice.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                             FB_API_HANDLE_PTR, ISC_QUAD_PTR,
                                             ISC_ARRAY_DESC_PTR, c.c_void_p,
                                             ISC_LONG_PTR]
        # isc_array_get_slice(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(isc_tr_handle), POINTER(ISC_QUAD), POINTER(ISC_ARRAY_DESC), c_void_p, POINTER(ISC_LONG))
        self.isc_array_get_slice = self.client_library.isc_array_get_slice
        self.isc_array_get_slice.restype = ISC_STATUS
        self.isc_array_get_slice.argtypes = [ISC_STATUS_PTR, FB_API_HANDLE_PTR,
                                             FB_API_HANDLE_PTR, ISC_QUAD_PTR,
                                             ISC_ARRAY_DESC_PTR, c.c_void_p,
                                             ISC_LONG_PTR]
        # isc_sqlcode(POINTER(ISC_STATUS))
        self.isc_sqlcode = self.client_library.isc_sqlcode
        self.isc_sqlcode.restype = ISC_LONG
        self.isc_sqlcode.argtypes = [ISC_STATUS_PTR]
        #: isc_sql_interprete(c_short, STRING, c_short)
        self.isc_sql_interprete = self.client_library.isc_sql_interprete
        self.isc_sql_interprete.restype = None
        self.isc_sql_interprete.argtypes = [c.c_short, STRING, c.c_short]
        #: fb_interpret(STRING, c_uint, POINTER(POINTER(ISC_STATUS)))
        self.fb_interpret = self.client_library.fb_interpret
        self.fb_interpret.restype = ISC_LONG
        self.fb_interpret.argtypes = [STRING, c.c_uint, c.POINTER(c.POINTER(ISC_STATUS))]
        #
        self.P_isc_event_block = c.CFUNCTYPE(ISC_LONG, c.POINTER(c.POINTER(ISC_UCHAR)),
                                             c.POINTER(c.POINTER(ISC_UCHAR)), ISC_USHORT)
        #: C_isc_event_block(ISC_LONG, POINTER(POINTER(ISC_UCHAR)), POINTER(POINTER(ISC_UCHAR)), ISC_USHORT)
        self.C_isc_event_block = self.P_isc_event_block(('isc_event_block', self.client_library))
        self.P_isc_event_block_args = self.C_isc_event_block.argtypes
        #: isc_que_events(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(ISC_LONG), c_short, POINTER(ISC_UCHAR), ISC_EVENT_CALLBACK, POINTER(ISC_UCHAR))
        self.isc_que_events = self.client_library.isc_que_events
        self.isc_que_events.restype = ISC_STATUS
        self.isc_que_events.argtypes = [c.POINTER(ISC_STATUS), c.POINTER(FB_API_HANDLE),
                                        c.POINTER(ISC_LONG), c.c_short, c.POINTER(ISC_UCHAR),
                                        ISC_EVENT_CALLBACK, c.POINTER(ISC_UCHAR)]
        #: isc_event_counts(POINTER(RESULT_VECTOR), c_short, POINTER(ISC_UCHAR), POINTER(ISC_UCHAR))
        self.isc_event_counts = self.client_library.isc_event_counts
        self.isc_event_counts.restype = None
        self.isc_event_counts.argtypes = [c.POINTER(RESULT_VECTOR), c.c_short, c.POINTER(ISC_UCHAR),
                                          c.POINTER(ISC_UCHAR)]
        #: isc_cancel_events(POINTER(ISC_STATUS), POINTER(isc_db_handle), POINTER(ISC_LONG))
        self.isc_cancel_events = self.client_library.isc_cancel_events
        self.isc_cancel_events.restype = ISC_STATUS
        self.isc_cancel_events.argtypes = [c.POINTER(ISC_STATUS), c.POINTER(FB_API_HANDLE),
                                           c.POINTER(ISC_LONG)]
        #: isc_prepare_transaction(POINTER(ISC_STATUS), POINTER(isc_tr_handle))
        self.isc_prepare_transaction = self.client_library.isc_prepare_transaction
        self.isc_prepare_transaction.restype = ISC_STATUS
        self.isc_prepare_transaction.argtypes = [c.POINTER(ISC_STATUS), c.POINTER(FB_API_HANDLE)]
        # Next netributes are set in types by API_LOADED hook
        self.master = None
        self.util = None
    def isc_event_block(self, event_buffer, result_buffer, *args) -> int:
        "Injects variable number of parameters into C_isc_event_block call"
        if len(args) > 15:
            raise ValueError("isc_event_block takes no more than 15 event names")
        newargs = list(self.P_isc_event_block_args)
        newargs.extend(STRING for x in args)
        self.C_isc_event_block.argtypes = newargs
        return self.C_isc_event_block(event_buffer, result_buffer, len(args), *args)

def has_api() -> bool:
    "Reaturns True if Firebird API is already loaded"
    return api is not None

def load_api(filename: t.Union[None, str, Path] = None) -> None:
    """Initializes bindings to Firebird Client Library unless they are already initialized.
Called automatically by :func:`firebird.driver.connect` and :func:`firebird.driver.create_database`.

Args:
    filename (Path): (optional) Path to Firebird Client Library.
    When it's not specified, driver does its best to locate appropriate client library.

Returns:
    :class:`FirebirdAPI` instance.

Hooks:
    Event :class:`HookType.HOOK_API_LOADED`: Executed after api is initialized.
    Hook routine must have signature: `hook_func(api)`. Any value returned by
    hook is ignored.
"""
    if not has_api():
        if filename and not isinstance(filename, Path):
            filename = Path(filename)
        api = FirebirdAPI(filename)
        setattr(sys.modules[__name__], 'api', api)
        for hook in hooks.get_hooks(HookType.API_LOADED):
            hook(api)

def get_api() -> FirebirdAPI:
    "Returns Firebird API. Loads the API if needed."
    if not has_api():
        load_api()
    return api

api: FirebirdAPI = None
