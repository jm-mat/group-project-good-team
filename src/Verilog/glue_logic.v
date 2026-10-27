`timescale 1ns / 1ps
// Will wire all helper modules to the top module
module glue_logic (
    input  wire        clk,
    input  wire        rst,

    // UART pins
    input  wire        uart_rx,
    output wire        uart_tx,

    // Seven segment
    output wire [6:0]  seg,
    output wire [3:0]  an,
    
    // debug leds
    output wire        led0,
    output wire        led1,
    output wire        led2,
    output wire        led3,
    
    // NN interface (to be wired in top.v)
    output wire [10239:0] input_1_V,       // CHANGED
    output wire           input_1_V_ap_vld,
    output wire           ap_start,
    input  wire           ap_done,
    input  wire [23:0]    out0,            // CHANGED
    input  wire [23:0]    out1,            // CHANGED
    input  wire [23:0]    out2             // CHANGED
);

    // UART RX
    wire [7:0] rx_byte;
    wire       rx_valid;

    uart_rx #(
        .CLK_FREQ(100_000_000),
        .BAUD(115200)
    ) u_rx (
        .clk   (clk),
        .rst   (rst),
        .rx    (uart_rx),
        .data  (rx_byte),
        .valid (rx_valid)
    );

    // Frame buffer (raw ready signal)
    wire frame_ready_raw;

    frame_buffer u_fb (
        .clk            (clk),
        .rst            (rst),
        .rx_byte        (rx_byte),
        .rx_valid       (rx_valid),
        .input_vector   (input_1_V),
        .frame_ready_raw(frame_ready_raw)
    );

    // NN busy signal (from controller)
    wire nn_busy;

    // Blocking Protocol: only allow frame_ready when NN is idle
    wire frame_ready = frame_ready_raw & ~nn_busy;

    // input_1_V_ap_vld logic
    reg input_valid_reg;

    always @(posedge clk) begin
        if (rst)
            input_valid_reg <= 0;
        else if (frame_ready)
            input_valid_reg <= 1;
        else if (ap_start)
            input_valid_reg <= 0;  // clear once NN starts
    end

    assign input_1_V_ap_vld = input_valid_reg;

    // Argmax
    wire [1:0] pred_class;

    argmax u_argmax (
        .out0       (out0),
        .out1       (out1),
        .out2       (out2),
        .pred_class (pred_class)
    );

    // UART TX
    wire        tx_start;
    wire [7:0]  tx_byte;
    wire        tx_busy;

    uart_tx #(
        .CLK_FREQ(100_000_000),
        .BAUD(115200)
    ) u_tx (
        .clk   (clk),
        .rst   (rst),
        .start (tx_start),
        .data  (tx_byte),
        .tx    (uart_tx),
        .busy  (tx_busy)
    );

    // NN controller (FSM)
    wire [1:0] pred_class_latched;

    nn_controller u_ctrl (
        .clk                (clk),
        .rst                (rst),
        .frame_ready        (frame_ready),
        .ap_start           (ap_start),
        .ap_done            (ap_done),
        .pred_class_in      (pred_class),
        .pred_class_latched (pred_class_latched),
        .tx_start           (tx_start),
        .tx_byte            (tx_byte),
        .tx_busy            (tx_busy),

        // Busy flag for blocking new frames
        .nn_busy            (nn_busy)
    );

    // Seven segment driver
    seven_seg_driver u_seven (
        .clk        (clk),
        .rst        (rst),
        .pred_class (pred_class_latched),
        .seg        (seg),
        .an         (an)
    );

    // Debug LEDs
    assign led0 = frame_ready;
    assign led1 = ap_start;
    assign led2 = ap_done;
    assign led3 = tx_start;

endmodule

