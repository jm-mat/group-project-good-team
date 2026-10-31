`timescale 1ns / 1ps

module frame_buffer (
    input  wire        clk,
    input  wire        rst,
    input  wire [7:0]  rx_byte,
    input  wire        rx_valid,

    // Flattened 1024-byte frame → 10240-bit vector
    output reg [10239:0] input_vector,

    // RAW frame_ready (glue_logic will block it using nn_busy)
    output reg         frame_ready_raw
);

    // 32x32 = 1024 bytes
    reg [7:0] mem [0:1023];
    reg [9:0] count = 0;   // 0-1023

    integer i;

    // Sequential logic: collect bytes
    always @(posedge clk) begin
        if (rst) begin
            count           <= 0;
            frame_ready_raw <= 0;
        end else begin
            frame_ready_raw <= 0;  // default low

            if (rx_valid) begin
                mem[count] <= rx_byte;

                if (count == 10'd1023) begin
                    count <= 0;
                    frame_ready_raw <= 1;  // pulse when full frame received
                end else begin
                    count <= count + 1;
                end
            end
        end
    end

    // Combinational flattening (single driver)
    always @(*) begin
    for (i = 0; i < 1024; i = i + 1) begin
        input_vector[i*8 +: 8] = mem[i];
    end
end

endmodule
