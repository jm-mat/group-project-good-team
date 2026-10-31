set sim_dir [file dirname [file normalize [info script]]]
set hardware_root [file normalize [file join $sim_dir ..]]
set repo_root [file normalize [file join $hardware_root ../..]]

create_project -force grader_sim \
    [file join $repo_root build vivado_sim] \
    -part xc7a35tcpg236-1

set rtl_files [list \
    [file join $hardware_root rtl top.v] \
    [file join $hardware_root rtl glue_logic.v] \
    [file join $hardware_root rtl frame_buffer.v] \
    [file join $hardware_root rtl argmax.v] \
    [file join $hardware_root rtl nn_controller.v] \
    [file join $hardware_root rtl seven_seg_driver.v] \
    [file join $hardware_root rtl uart_rx.v] \
    [file join $hardware_root rtl uart_tx.v] \
]

add_files -norecurse $rtl_files

add_files -fileset sim_1 -norecurse \
    [file join $sim_dir tb_top_with_hls_stub.v]

set_property top tb_top_with_hls_stub [get_filesets sim_1]

launch_simulation -mode batch -simset sim_1

close_project