module top (
    input  wire clk,          // Basys3 100 MHz clock
    input  wire rst_btn,      // Reset button (active high)

    // UART pins (USB-UART on Basys3)
    input  wire uart_rx,
    output wire uart_tx,

    // Seven-segment display
    output wire [6:0] seg,
    output wire [3:0] an
);

    // NN interface wires (32x32 = 10240 bits)
    wire [10239:0] input_1_V;
    wire           input_1_V_ap_vld;
    wire           ap_start;
    wire           ap_done;

    wire [23:0] out0;
    wire [23:0] out1;
    wire [23:0] out2;

    // HLS Neural Network (myproject_0)
    myproject_0 nn_inst (
        .ap_clk(clk),
        .ap_rst(rst_btn),

        .ap_start(ap_start),
        .ap_done(ap_done),
        .ap_ready(),
        .ap_idle(),

        .input_1_V(input_1_V),
        .input_1_V_ap_vld(input_1_V_ap_vld),

        .layer8_out_0_V(out0),
        .layer8_out_0_V_ap_vld(),
        .layer8_out_1_V(out1),
        .layer8_out_1_V_ap_vld(),
        .layer8_out_2_V(out2),
        .layer8_out_2_V_ap_vld()
    );

    // Glue Logic (UART, Neural Network , frame buffer, FSM, argmax, 7-seg)
    glue_logic glue_inst (
        .clk(clk),
        .rst(rst_btn),

        // UART
        .uart_rx(uart_rx),
        .uart_tx(uart_tx),

        // Seven-segment
        .seg(seg),
        .an(an),

        // Neural Network input interface
        .input_1_V(input_1_V),
        .input_1_V_ap_vld(input_1_V_ap_vld),

        // Neural Network control
        .ap_start(ap_start),
        .ap_done(ap_done),

        // Neural Network outputs
        .out0(out0),
        .out1(out1),
        .out2(out2)
    );
endmodule
