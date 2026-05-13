module uart_rx #(
    parameter CLK_FREQ = 100_000_000,   //100 MHz clock
    parameter BAUD     = 115200         //BAUD RATE(Try to increase if you want to test/pursue less stalling)
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output reg [7:0]  data,
    output reg        valid
);

    localparam integer OVERSAMPLE = 8;
    localparam integer DIVISOR = CLK_FREQ / (BAUD * OVERSAMPLE);

    reg [31:0] clk_cnt = 0;
    reg [3:0]  sample_cnt = 0;
    reg [3:0]  bit_idx = 0;
    reg [7:0]  sample_buf = 0;
    reg [9:0]  shreg = 0;
    reg busy = 0;

    integer ones;
    
    // UART receiver with oversampling
    // Assert valid when full byte is received
    always @(posedge clk) begin
        if (rst) begin
            valid      <= 0;
            busy       <= 0;
            clk_cnt    <= 0;
            sample_cnt <= 0;
            bit_idx    <= 0;
            sample_buf <= 0;
            shreg      <= 0;
        end else begin
            valid <= 0;

            if (!busy) begin
                if (rx == 1'b0) begin
                    busy       <= 1;
                    clk_cnt    <= 0;
                    sample_cnt <= 0;
                    bit_idx    <= 0;
                    sample_buf <= 0;
                end
            end else begin
                if (clk_cnt == DIVISOR - 1) begin
                    clk_cnt <= 0;

                    sample_buf <= {sample_buf[6:0], rx};
                    sample_cnt <= sample_cnt + 1;

                    if (sample_cnt == OVERSAMPLE - 1) begin
                        sample_cnt <= 0;

                        ones = sample_buf[0] + sample_buf[1] + sample_buf[2] +
                               sample_buf[3] + sample_buf[4] + sample_buf[5] +
                               sample_buf[6] + sample_buf[7];

                        shreg <= { (ones >= 4), shreg[9:1] };
                        bit_idx <= bit_idx + 1;

                        if (bit_idx == 9) begin
                            busy  <= 0;
                            data  <= shreg[8:1];
                            valid <= 1;
                        end
                    end

                end else begin
                    clk_cnt <= clk_cnt + 1;
                end
            end

        end
    end

endmodule
