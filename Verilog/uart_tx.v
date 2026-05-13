module uart_tx #(
    parameter CLK_FREQ = 100_000_000,   //100 MHz Clock
    parameter BAUD     = 115200         //BAUD RATE(should be same value as in uart_rx
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] data,
    output reg        tx,
    output reg        busy
);

    // Divisor math
    localparam integer DIVISOR = CLK_FREQ / BAUD;

    reg [31:0] clk_cnt = 0;
    reg [3:0]  bit_idx = 0;
    reg [9:0]  shreg   = 10'b1111111111;
    
    // UART transmitter: loads start/data/stop bits into shreg and shifts them out
    always @(posedge clk) begin
        if (rst) begin
            tx      <= 1'b1;
            busy    <= 1'b0;
            clk_cnt <= 0;
            bit_idx <= 0;
            shreg   <= 10'b1111111111;
        end else begin

            if (!busy) begin
                if (start) begin
                    shreg   <= {1'b1, data, 1'b0};  // stop, data, start
                    busy    <= 1'b1;
                    bit_idx <= 0;
                    clk_cnt <= 0;
                end
            end else begin
                if (clk_cnt == DIVISOR - 1) begin
                    clk_cnt <= 0;

                    tx <= shreg[0];
                    shreg <= {1'b1, shreg[9:1]};
                    bit_idx <= bit_idx + 1;

                    if (bit_idx == 9) begin
                        busy <= 1'b0;
                        tx   <= 1'b1;
                    end
                end else begin
                    clk_cnt <= clk_cnt + 1;
                end
            end

        end
    end

endmodule
