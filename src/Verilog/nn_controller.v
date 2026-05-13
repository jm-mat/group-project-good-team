`timescale 1ns / 1ps

module nn_controller (
    input  wire        clk,
    input  wire        rst,

    // Frame buffer
    input  wire        frame_ready,

    // NN interface
    output reg         ap_start,
    input  wire        ap_done,

    // Argmax
    input  wire [1:0]  pred_class_in,
    output reg [1:0]   pred_class_latched,

    // UART TX
    output reg         tx_start,
    output reg [7:0]   tx_byte,
    input  wire        tx_busy,

    // Expose busy flag so glue_logic can block new frames
    output wire        nn_busy
);

    // FSM state encoding
    reg [2:0] state;
    reg [2:0] next_state;

    localparam S_IDLE        = 3'd0;
    localparam S_START_NN    = 3'd1;
    localparam S_WAIT_NN     = 3'd2;
    localparam S_WAIT_OUTPUT = 3'd3;
    localparam S_ARGMAX      = 3'd4;
    localparam S_SEND_UART   = 3'd5;
    localparam S_DONE        = 3'd6;


    // NN busy flag (everything except IDLE)
    assign nn_busy = (state != S_IDLE);

    // Latch ap_done to avoid missing the pulse
    reg ap_done_latched;

    always @(posedge clk) begin
        if (rst)
            ap_done_latched <= 0;
        else if (ap_done)
            ap_done_latched <= 1;
        else if (state == S_ARGMAX)
            ap_done_latched <= 0;
    end

    // State register
    always @(posedge clk) begin
        if (rst)
            state <= S_IDLE;
        else
            state <= next_state;
    end

    // Next-state logic + outputs
    always @(*) begin
        // Default outputs
        ap_start = 0;
        tx_start = 0;
        tx_byte  = 8'd0;

        next_state = state;

        case (state)

            S_IDLE: begin
                if (frame_ready)
                    next_state = S_START_NN;
            end

            // Pulse ap_start for exactly 1 cycle
            S_START_NN: begin
                ap_start   = 1;
                next_state = S_WAIT_NN;
            end

            // Wait for NN to finish (latched)
            S_WAIT_NN: begin
                if (ap_done_latched)
                    next_state = S_WAIT_OUTPUT;
            end

            // Allow NN outputs to settle for 1 cycle
            S_WAIT_OUTPUT: begin
                next_state = S_ARGMAX;
            end

            S_ARGMAX: begin
                next_state = S_SEND_UART;
            end

            // Wait here until TX is truly ready
            S_SEND_UART: begin
                if (!tx_busy) begin
                    tx_start = 1;
                    tx_byte  = {6'd0, pred_class_latched};
                    next_state = S_DONE;
                end else begin
                    next_state = S_SEND_UART;
                end
            end

            S_DONE: begin
                next_state = S_IDLE;
            end

            default: next_state = S_IDLE;

        endcase
    end

    // Latch prediction when NN outputs are stable
    always @(posedge clk) begin
        if (rst)
            pred_class_latched <= 2'd0;
        else if (state == S_ARGMAX)
            pred_class_latched <= pred_class_in;
    end

endmodule

